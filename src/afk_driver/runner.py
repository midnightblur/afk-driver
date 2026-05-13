"""AFK driver orchestrator.

Single drain pass: fetch label-tagged SubTasks, group by parent ticket
(Enhancement or Bug — workflows overlap but differ at the Dev-Pending step:
Enhancement goes Dev-Pending → Dev-Designing → Dev-Developing, Bug goes
Dev-Pending → Dev-Developing directly), process them in priority order with
per-SubTask retries, idempotent transitions, and post-last-SubTask rebase
against the resolved Target Branch.

All I/O is injected so the runner can be exercised end-to-end with fakes.
"""

from __future__ import annotations

import os
import shutil
import time
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional

from afk_driver.config import DriverConfig
from afk_driver.gitlab_client import SubtaskItem
from afk_driver.scm_protocol import Scm
from afk_driver.tracker_protocol import IssueTracker
from afk_driver.worktree_manager import WorktreeError, WorktreeSpec


ClaudeStatus = Literal[
    "success",
    "test_fail",
    "build_fail",
    "timeout",
    "design_conflict",
    "contract_mismatch",
    "produces_drift",
    "other",
]


@dataclass(frozen=True)
class ClaudeOutcome:
    status: ClaudeStatus
    detail: str = ""
    # Populated only for ``contract_mismatch``: the producer SubTask key whose
    # ``## Produces`` artifact failed the consumer's preflight grep. The runner
    # routes a comment there so the human knows where the binding-contract
    # break lives, separate from the consumer's own abort comment.
    producer_key: Optional[str] = None


ClaudeRunner = Callable[[str, Path, int], ClaudeOutcome]


@dataclass
class SubTaskRun:
    key: str
    summary: str
    status: Literal["success", "aborted", "skipped"] = "skipped"
    attempts: int = 0
    detail: str = ""
    duration_s: float = 0.0
    # S1 — true when this SubTask succeeded on attempt N>1 AND at least
    # one prior attempt failed with ``test_fail``. The retry loop hides
    # flake otherwise: a successful retry looks identical to a clean
    # first-attempt success in the digest, but the underlying cause may
    # be a race / timing-dependent test rather than a real fix. Surfacing
    # the suspicion gives the human a flag to investigate without
    # forcing a hard failure on the SubTask. Excludes ``build_fail``
    # because build infrastructure transients are a different
    # category — they look like flake at the run level but are
    # typically dep-cache / network issues that don't recur in CI.
    flaky_suspect: bool = False


@dataclass
class ParentRun:
    key: str
    summary: str = ""
    issuetype: str = ""
    target_branch: str = ""
    mr_url: str = ""
    subtasks: list[SubTaskRun] = field(default_factory=list)
    rebase: Literal["clean", "conflict", ""] = ""
    skip_reason: str = ""
    duration_s: float = 0.0


@dataclass(frozen=True)
class RepoFailed:
    """Per-repo failure record for the GitHub multi-repo outer loop.

    Emitted by ``Runner._drain_repo`` when ``repo_clone_manager.ensure_clone``
    raises, when the queue-discovery groups a repo whose default branch can't
    be resolved, or when any other repo-scoped pre-condition fails before the
    per-parent loop opens. ST09's digest writer renders one row per entry so
    the morning summary surfaces which repos were skipped and why (ADR-0003
    flowchart ``skip_repo`` rung — SDD §7 failure-recovery matrix row
    "``gh repo clone`` fails").

    ``backend`` is the discriminator (``"github"`` | ``"jira"``); the
    ``owner`` / ``repo`` pair are the per-repo coordinates (empty strings on
    backends that have no notion of multi-repo, but the type is still
    populated so consumers can rely on the field's presence).
    """

    backend: str
    owner: str = ""
    repo: str = ""
    reason: str = ""


@dataclass
class RunRecord:
    """One drain-pass result.

    Backwards-compatible with the pre-ST07 shape: ``parents`` remains the
    canonical list the digest writer iterates. ST07 adds ``backend`` (digest
    discriminator column per SDD §7 use-case 4) and ``repo_failures`` (per-
    repo skip records — see ``RepoFailed``); both default to empty / "jira"
    so the existing Jira+GitLab path constructs identically.
    """

    started_iso: str
    ended_iso: str = ""
    backend: str = "jira"
    parents: list[ParentRun] = field(default_factory=list)
    repo_failures: list[RepoFailed] = field(default_factory=list)


class PreflightError(RuntimeError):
    """Raised when pre-flight checks fail."""


def preflight(
    config: DriverConfig,
    *,
    repo_root: Path,
    env: Mapping[str, str],
    which: Callable[[str], Optional[str]] = shutil.which,
) -> None:
    """Hard-fail any of the documented pre-flight conditions.

    PRDs live in each parent ticket's Jira description (``## PRD`` section,
    owned by the ``/to-prd`` skill). One drain pass spans many parents, so
    there is no single local-file PRD for the driver to validate.
    """
    missing_tools = [t for t in ("glab", "mvn", "node", "claude", "git") if which(t) is None]
    if missing_tools:
        raise PreflightError(f"required tools missing on PATH: {missing_tools}")
    if not env.get("GITLAB_TOKEN"):
        raise PreflightError("GITLAB_TOKEN env not set")
    if not repo_root.is_dir():
        raise PreflightError(f"repo root not a directory: {repo_root}")


@dataclass
class Runner:
    """Orchestrator.

    Post-ST07 the runner is **Protocol-driven**: it accepts an
    ``IssueTracker`` and an ``Scm`` (not concrete ``JiraClient`` /
    ``GitLabClient``) so the same orchestration layer drives both the
    Jira+GitLab and the GitHub Issues+PR backends (SDD §8 row
    "runner (modified)", PRD §"Backend abstraction").

    Migration boundary — NOT all Jira-side calls have been lifted onto the
    Protocol surface yet. The runner still invokes the following methods
    directly on the concrete Jira adapter when the active backend is Jira;
    these are Nakisa-workflow-specific fixtures the PRD §"Backend
    abstraction" explicitly leaves "off by default on GitHub" and ST02's
    docstring on each stub method names ST07 as where they would be lifted:

      * ``get_my_account_id`` / ``assign`` — Nakisa workflow validator on
        Start Development demands an assignee; GitHub backend has no
        equivalent gate, so this code path stays Jira-only.
      * ``transition`` for ``Start Designing`` / ``Start Development`` /
        ``Request CR & Merge`` / ``Request Development`` — phase transitions
        are NOW routed through Protocol aliases (``start_designing``,
        ``start_developing``, ``request_cr_merge``, ``revert_to_pending``)
        which both adapters implement; the legacy ``transition(key, name)``
        signature is no longer called from the runner.
      * ``update_implementation_notes`` — JiraClient renders bullet-at-a-time
        ADF; the Protocol's ``splice_notes_block(parent_id, body)`` takes a
        whole rendered block. ST02 left ``splice_notes_block`` as a stub on
        ``JiraClient`` with the note "ST07 will route the runner through
        this; until then the legacy bullet-at-a-time path stays the
        canonical writer." Per spec rule 4 (option b) we keep the legacy
        path and document this boundary; lifting it requires a separate
        slice that ports the bullet-rendering logic onto ADF generation in
        the adapter and adds GitHub-side parity.
      * ``set_fields`` / ``set_field_if_unset`` — Nakisa Dev-CR/Merge gate
        custom fields (merge-request-link, SRED eligibility, time
        estimation, SRED rationale, A+ Clarity). GitHub backend has no
        analogue (PRD §"Tracker-only fields" — "Nakisa-specific gates are
        dropped on the GitHub path").
      * ``flip_acceptance_checkboxes`` — Jira ADF parses ``[ ]``/``[x]``
        markers inside the Acceptance section; GitHub renders task lists
        differently. The Acceptance flip is Jira-only by design.
      * ``get_status`` — used only by the ``contract_mismatch`` routing
        which fetches the producer SubTask's workflow status. GitHub's
        equivalent is the ``afk:*`` phase label; lifting this requires a
        Protocol method that returns the phase rather than the raw status
        string. Out of scope for ST07.

    The runner branches on ``record.backend`` (set from
    ``repo_coords.backend`` when supplied; otherwise ``"jira"`` for the
    legacy single-repo flow) so Jira-only calls execute only under the
    Jira backend. When ``record.backend == "github"`` the Jira-only steps
    are skipped — the GitHub adapter's phase labels carry the same
    semantics without the gate-field ceremony.

    Scm migration boundary — the runner still calls a small set of
    GitLab-shape methods directly on ``self.scm`` (``find_open_mr_by_parent_key``,
    ``open_draft_mr(source_branch=..., target_branch=..., title=...,
    description=..., assignee=...)``, ``update_subtasks_checklist``). Each
    of these has a Protocol counterpart (``find_open_pr_by_parent``,
    ``open_draft_pr(OpenDraftPrSpec)``, ``splice_pr_block``); lifting the
    runner onto the Protocol surface fully is out of scope for ST07 (the
    Protocol-typed parameters and the per-(repo, parent) outer loop are
    the load-bearing changes here). For now both ``GitLabClient`` and
    ``GitHubPrClient`` are expected to expose the GitLab-shape surface
    when wired into the runner; the GitHub adapter's Protocol surface is
    additive (``find_open_pr_by_parent`` / ``open_draft_pr`` /
    ``splice_pr_block`` plus the GitLab-shape compatibility shims).
    """

    tracker: IssueTracker
    scm: Scm
    worktrees: Any
    claude_runner: ClaudeRunner
    config: DriverConfig
    repo_root: Path
    label: str = "afk-agents"
    project_key: str = "P2P"
    # Composition-root binding from ``backend_select.Backend``. When supplied
    # and ``repo_coords.backend == "github"`` AND ``config.github.mode ==
    # "all-repos"`` the runner switches on the per-repo outer loop (ADR-0003
    # flowchart). The legacy single-repo flow is preserved when this is
    # ``None`` — existing Jira+GitLab callers construct without it.
    repo_coords: Optional[Any] = None
    # Optional injectable for ``repo_clone_manager.ensure_clone``. Accepts
    # ``(owner, repo, root) -> Path``. Only used when the multi-repo outer
    # loop fires; otherwise ignored.
    repo_clone_manager: Optional[Callable[[str, str, Path], Path]] = None
    now_iso: Callable[[], str] = field(
        default_factory=lambda: lambda: datetime.now(timezone.utc).isoformat()
    )
    monotonic: Callable[[], float] = time.monotonic
    # Live progress sink. Defaults to stdout so a real `afk` invocation shows
    # the user what the driver is up to without having to tail a log file. Tests
    # pass a no-op callable to keep pytest output clean.
    progress: Callable[[str], None] = field(default=lambda msg: print(msg, flush=True))

    # ------------------------------------------------------------------
    # Legacy attribute aliases (read-only) so the migration boundary is
    # explicit: code paths that call ``jira.X`` are routing through the
    # Jira-specific surface listed in the class docstring. Removing these
    # aliases requires lifting the corresponding Jira-only calls onto the
    # ``IssueTracker`` / ``Scm`` Protocols.
    # ------------------------------------------------------------------

    @property
    def jira(self):
        """Jira-only surface alias for ``self.tracker``. Used by code paths
        documented in the class docstring's "Migration boundary" list —
        ``get_my_account_id``, ``assign``, ``set_fields``,
        ``set_field_if_unset``, ``update_implementation_notes``,
        ``flip_acceptance_checkboxes``, ``get_status``, ``comment``,
        ``transition`` (legacy — phase transitions now go through Protocol
        aliases). Branched on ``record.backend`` so these execute only on
        the Jira backend.
        """
        return self.tracker

    @property
    def gitlab(self):
        """GitLab-only surface alias for ``self.scm``. Used by code paths
        that still call ``open_draft_mr`` (kwargs flavour),
        ``find_open_mr_by_parent_key``, ``update_subtasks_checklist`` — all
        GitLab-shaped APIs that ST02 kept alongside the Scm Protocol
        methods. The GitHub adapter exposes the Protocol surface; lifting
        the remaining call sites onto Protocol methods is out of scope for
        ST07.
        """
        return self.scm

    def one_pass(self) -> RunRecord:
        """Run a single drain pass.

        Dispatches between two execution shapes based on the active backend:

        1. **Single-repo (Jira+GitLab, or GitHub with ``mode = "cwd"``)** —
           the historical flow. One JQL/search call lists pickable
           sub-issues, parents are grouped, and ``_process_parent`` /
           ``_process_standalone`` drive each to completion against
           ``self.repo_root``.
        2. **Multi-repo (GitHub with ``mode = "all-repos"``)** — per
           ADR-0003. Queue discovery still returns a flat list of
           sub-issue refs, but each ref carries its ``owner/repo`` in its
           id. The runner groups by repo and delegates to ``_drain_repo``
           per group, with each group wrapped in a per-repo isolation
           ``try/except`` so a clone failure on repo A does not abort
           repos B…Z. Auth-level failures (raised by ``tracker`` /
           ``scm`` pre-flight) propagate up and halt the whole run.
        """
        backend = self._backend_name()
        record = RunRecord(started_iso=self.now_iso(), backend=backend)
        self.progress(
            f"[afk] one_pass start (backend={backend} project={self.project_key} "
            f"label={self.label})"
        )

        if self._is_github_multi_repo():
            self._drain_github_multi_repo(record)
        else:
            self._drain_single_repo(record)

        record.ended_iso = self.now_iso()
        self.progress(
            f"[afk] one_pass done ({len(record.parents)} parent(s) processed, "
            f"{len(record.repo_failures)} repo failure(s))"
        )
        return record

    # ------------------------------------------------------------------
    # Backend dispatch helpers (ST07)
    # ------------------------------------------------------------------

    def _backend_name(self) -> str:
        """Return the active backend discriminator.

        Reads ``repo_coords.backend`` when the runner was constructed with
        a ``Backend`` binding (post-ST08 cli wiring path); falls back to
        ``"jira"`` for legacy callers (existing single-repo Jira+GitLab
        flow keeps working without modification).
        """
        coords = self.repo_coords
        if coords is None:
            return "jira"
        return getattr(coords, "backend", "jira") or "jira"

    def _is_github_multi_repo(self) -> bool:
        """True iff this runner should fan-out the per-repo outer loop.

        Three conjuncts: (1) active backend is github, (2)
        ``config.github.mode == "all-repos"`` (ADR-0003 trigger), and
        (3) a ``repo_clone_manager`` is wired (test fakes can short-circuit
        the loop by leaving it as the default ``None`` on the legacy
        single-repo branch).
        """
        if self._backend_name() != "github":
            return False
        mode = (self.config.github.mode or "").strip().lower()
        if mode != "all-repos":
            return False
        return self.repo_clone_manager is not None

    def _drain_single_repo(self, record: RunRecord) -> None:
        """Legacy single-repo drain — wraps the historical body of
        ``one_pass`` so the multi-repo branch can dispatch to the same
        per-parent / per-standalone loop without code duplication."""
        backend = record.backend
        # Cache the authenticated account once; needed before every transition
        # that runs through the "Assignee must be specified" workflow validator.
        # Jira-only — GitHub backend has no equivalent gate.
        if backend == "jira":
            self._account_id = self.jira.get_my_account_id()
        else:
            self._account_id = ""

        issues = self._list_pickable_for_single_repo()
        if not issues:
            self.progress("[afk] no pickable tickets found; exiting")
            return
        self.progress(f"[afk] found {len(issues)} pickable ticket(s)")

        self._drain_issue_list(issues, record)

    def _drain_github_multi_repo(self, record: RunRecord) -> None:
        """Per-(repo, parent) outer loop for ADR-0003.

        Single ``tracker.list_pickable()`` call discovers the queue across
        all owned repos; grouping happens here. Each repo is wrapped in a
        try/except so a clone failure isolates without aborting siblings.
        Auth-level errors raised by ``list_pickable()`` itself propagate
        (no try/except around the call) — the PRD §"Pre-flight checks"
        rule says auth halts.
        """
        self._account_id = ""
        issues = self.tracker.list_pickable()
        if not issues:
            self.progress("[afk] no pickable tickets found; exiting")
            return
        self.progress(f"[afk] found {len(issues)} pickable ticket(s)")

        groups = _group_issues_by_repo(issues)
        self.progress(f"[afk] grouped into {len(groups)} repo(s)")

        clone_root = self._auto_clone_root()
        for (owner, repo), repo_issues in groups.items():
            try:
                self._drain_repo(owner, repo, repo_issues, clone_root, record)
            except _RepoIsolatedError as e:
                record.repo_failures.append(
                    RepoFailed(
                        backend="github", owner=owner, repo=repo, reason=str(e),
                    )
                )
                self.progress(
                    f"[afk] repo {owner}/{repo}: SKIPPED — {e}"
                )

    def _drain_repo(
        self,
        owner: str,
        repo: str,
        repo_issues: list,
        clone_root: Path,
        record: RunRecord,
    ) -> None:
        """Drain a single repo's parents within the multi-repo outer loop.

        Idempotent clone via ``self.repo_clone_manager.ensure_clone`` is the
        first step; any failure here raises ``_RepoIsolatedError`` which
        the caller converts to a ``RepoFailed`` record. Once the working
        tree exists, the runner swaps ``self.repo_root`` to that path for
        the duration of this group's parents, then restores it — the
        per-parent worktree manager reads ``self.repo_root`` to position
        its per-parent worktrees, and each repo's worktrees must live
        inside the corresponding clone.
        """
        self.progress(f"[afk] repo {owner}/{repo}: {len(repo_issues)} issue(s)")
        if self.repo_clone_manager is None:
            raise _RepoIsolatedError("no repo_clone_manager wired")
        try:
            repo_path = self.repo_clone_manager(owner, repo, clone_root)
        except Exception as e:  # noqa: BLE001 — clone errors isolate per repo
            raise _RepoIsolatedError(f"clone failed: {e}") from e

        saved_root = self.repo_root
        self.repo_root = Path(repo_path)
        try:
            self._drain_issue_list(repo_issues, record)
        finally:
            self.repo_root = saved_root

    def _drain_issue_list(self, issues: list, record: RunRecord) -> None:
        """Shared per-parent / per-standalone fan-out used by both the
        single-repo path and the per-repo branch of the multi-repo path.

        Classifies into ``by_parent`` (sub-issues with a parent ref) and
        ``standalones`` (parent-less labelled tickets driven directly).
        Order is preserved from the input list except that parents already
        past the pending phase sort first — keeps in-flight work draining
        before fresh work spawns new worktrees.
        """
        by_parent: dict[str, list] = defaultdict(list)
        standalone_candidates: list = []
        for issue in issues:
            parent_key = self._issue_parent_key(issue)
            if parent_key:
                by_parent[parent_key].append(issue)
            else:
                standalone_candidates.append(issue)
        covered_as_parent = set(by_parent.keys())
        standalones = [
            i for i in standalone_candidates
            if self._issue_key(i) not in covered_as_parent
        ]

        # Order parent-flow entries: those already past pending first.
        ordered: list[tuple[str, dict, list]] = []
        for parent_key, subs in by_parent.items():
            parent = self._get_parent_fields(parent_key)
            ordered.append((parent_key, parent, subs))
        ordered.sort(key=lambda t: 0 if t[1].get("status") != "Dev-Pending" else 1)

        for parent_key, parent, subs in ordered:
            run = self._process_parent(parent_key, parent, subs)
            record.parents.append(run)

        for standalone in standalones:
            run = self._process_standalone(standalone)
            record.parents.append(run)

    def _list_pickable_for_single_repo(self) -> list:
        """Single-repo queue discovery.

        Jira backend: uses the existing JQL ``search`` directly (Nakisa-
        specific JQL stays on the runner per the ST02 stub docstring; the
        Protocol's ``list_pickable`` raises ``NotImplementedError`` on the
        Jira adapter for the same reason). GitHub backend: delegates to
        the Protocol method (the GitHub adapter's implementation).
        """
        if self._backend_name() == "jira":
            return self.jira.search(
                f'project = {self.project_key} AND labels = "{self.label}" '
                f'AND status = "Dev-Pending" ORDER BY rank'
            )
        return self.tracker.list_pickable()

    @staticmethod
    def _issue_parent_key(issue) -> str:
        """Return the parent id of an issue ref in a backend-agnostic way.

        Jira ``IssueSummary`` exposes ``parent_key``; GitHub
        ``SubIssueRef`` exposes ``parent_id``. The runner accepts either
        shape so ``_drain_issue_list`` can stay backend-agnostic.
        """
        if hasattr(issue, "parent_key"):
            return getattr(issue, "parent_key", "") or ""
        return getattr(issue, "parent_id", "") or ""

    @staticmethod
    def _issue_key(issue) -> str:
        """Return the sub-issue's own id (``IssueSummary.key`` or
        ``SubIssueRef.id``)."""
        if hasattr(issue, "key"):
            return issue.key
        return getattr(issue, "id", "")

    def _get_parent_fields(self, parent_key: str) -> dict:
        """Backend-agnostic parent-field fetch.

        Jira backend uses the rich ``get_parent_fields`` (issuetype,
        fix_versions, target_branch custom field, …). GitHub uses the
        Protocol's ``get_parent`` for title + ``get_target_branch`` for
        the branch label, projected into the same dict shape the runner's
        single-repo code path expects.
        """
        if self._backend_name() == "jira":
            return self.jira.get_parent_fields(parent_key)
        # GitHub branch: build the parent-fields dict from the Protocol
        # surface. ``issuetype`` is not part of GitHub's data model —
        # leave blank so the Bug-vs-Enhancement Start-Designing fork
        # collapses to the always-skip branch (GitHub uses afk:designing
        # uniformly regardless of issue category).
        try:
            parent_ref = self.tracker.get_parent(parent_key)
            title = parent_ref.title
        except Exception:  # noqa: BLE001 - best-effort title fetch
            title = ""
        try:
            target = self.tracker.get_target_branch(parent_key)
        except Exception:  # noqa: BLE001 - target branch fetch is best-effort
            target = ""
        return {
            "summary": title,
            "status": "Dev-Pending",  # phase fork is GitHub-uniform
            "issuetype": "",
            "fix_versions": ["github"],  # bypass the "no fixVersions" skip
            "components": [],
            "target_branch": target,
        }

    def _auto_clone_root(self) -> Path:
        """Resolve the on-disk root where per-repo clones live.

        Defaults to ``{config.worktree_root}/github`` per SDD §4 state
        table row "Cloned repos (GitHub)". An explicit
        ``config.github.auto_clone_root`` override wins when non-empty.
        """
        if self.config.github.auto_clone_root:
            return Path(self.config.github.auto_clone_root).expanduser()
        return Path(self.config.worktree_root)

    def _process_parent(self, parent_key, parent, subtasks):
        issuetype = parent.get("issuetype", "")
        run = ParentRun(
            key=parent_key,
            summary=parent.get("summary", ""),
            issuetype=issuetype,
        )
        t0 = self.monotonic()
        self.progress(
            f"[afk] parent {parent_key} ({issuetype or '?'}): {len(subtasks)} SubTask(s)"
        )

        parent_status = parent.get("status", "")
        bootstrap = self._bootstrap_for_work(
            parent_key, parent, run,
            label_prefix="parent",
            t0=t0,
            extra_precheck=lambda: (
                f"parent status {parent_status!r}, refusing to process SubTasks"
                if parent_status not in ("Dev-Pending", "Dev-Developing")
                else None
            ),
        )
        if bootstrap is None:
            return run
        spec, worktree_path, mr, target_branch = bootstrap

        # Jira side-effects are a side quest. The driver's main job is to
        # spawn claude and ship code; ticket lifecycle updates must never
        # crash the run. _try_jira logs failures via self.progress and folds
        # them into run.skip_reason so a stale workflow state on parent N
        # doesn't block the rest of the pass.
        def _try_jira(label: str, fn: Callable[[], Any]) -> None:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                msg = f"{label}: {e}"
                run.skip_reason = (
                    f"{run.skip_reason}; {msg}" if run.skip_reason else msg
                )
                self.progress(
                    f"[afk] parent {parent_key}: jira side-effect failed — {msg}"
                )

        on_jira = self._backend_name() == "jira"
        if parent_status == "Dev-Pending":
            if on_jira:
                # Assignee-required Nakisa workflow validator; GitHub backend
                # has no equivalent gate (PRD §"Backend abstraction").
                _try_jira("assign parent",
                          lambda: self.jira.assign(parent_key, self._account_id))
            # Bug workflow goes Dev-Pending → Dev-Developing directly; only the
            # Enhancement workflow has the intermediate "Start Designing"
            # transition. Verified empirically against P2P-1228 (Bug):
            # available transitions did not include "Start Designing". On the
            # GitHub backend the Bug-vs-Enhancement distinction collapses
            # (one ``afk:designing`` label regardless of issue category),
            # so issuetype defaults to "" and this branch is skipped.
            if parent.get("issuetype") == "Enhancement":
                _try_jira("transition Start Designing",
                          lambda: self.tracker.start_designing(parent_key))
            _try_jira("transition Start Development",
                      lambda: self.tracker.start_developing(parent_key))

        any_aborted = False
        for sub in subtasks:
            sub_run = self._process_subtask(sub, worktree_path, parent_key, mr.web_url, spec)
            run.subtasks.append(sub_run)
            if sub_run.status == "aborted":
                any_aborted = True
                break

        # Update Draft MR checklist
        items = [
            SubtaskItem(s.key, s.summary, done=(s.status == "success"))
            for s in run.subtasks
        ]
        try:
            self.gitlab.update_subtasks_checklist(spec.branch, items)
        except Exception as e:  # noqa: BLE001 - want to record but not abort
            run.skip_reason = f"checklist update failed: {e}"

        if not any_aborted and run.subtasks:
            self.progress(f"[afk] parent {parent_key}: rebase onto origin/{target_branch}")
            outcome = self.worktrees.rebase_onto_target(spec)
            run.rebase = outcome
            self.progress(f"[afk] parent {parent_key}: rebase {outcome}")
            if outcome == "clean":
                if on_jira:
                    # Dev-CR/Merge gate-field writes + acceptance flips are
                    # Nakisa-workflow-specific; GitHub backend has no analogue.
                    _try_jira("populate Dev-CR/Merge gate fields",
                              lambda: self._populate_dev_cr_merge_gate(parent_key, mr.web_url))
                _try_jira("transition Request CR & Merge",
                          lambda: self.tracker.request_cr_merge(parent_key))
                if on_jira:
                    _try_jira("flip acceptance checkboxes",
                              lambda: self.jira.flip_acceptance_checkboxes(parent_key))
                self.progress(f"[afk] parent {parent_key}: transitioned to cr-merge")
            else:
                _try_jira("rebase-conflict comment",
                          lambda: self.tracker.comment(
                              parent_key,
                              f"AFK rebase against `{target_branch}` reported conflicts. "
                              "Resolve manually before merging."))

        run.duration_s = self.monotonic() - t0
        self.progress(
            f"[afk] parent {parent_key}: done in {run.duration_s:.1f}s "
            f"({sum(1 for s in run.subtasks if s.status == 'success')}/{len(run.subtasks)} SubTasks ok)"
        )
        return run

    def _process_subtask(self, subtask, worktree_path, parent_key, mr_url, spec):
        sub_run = SubTaskRun(key=subtask.key, summary=subtask.summary)
        t0 = self.monotonic()
        self.progress(f"[afk]   subtask {subtask.key}: {subtask.summary}")
        # Per-subtask safety net: discard any uncommitted leftover from a
        # prior interruption (claude server died, OS killed the process,
        # user Ctrl+C'd) before this SubTask spawns claude. The contract is
        # "completed SubTasks must be committed before the next starts" —
        # which the runner already upholds via commit_dirty_changes after
        # claude success — so anything dirty here is by definition NOT part
        # of a completed SubTask. Resuming partial edits is unsafe (claude
        # has no notion of "pick up where the dead session left off"), so
        # the deterministic recovery is to start from HEAD.
        if self.worktrees.reset_to_clean(spec):
            self.progress(
                f"[afk]   subtask {subtask.key}: discarded uncommitted "
                f"leftovers from prior interruption"
            )
        # Jira side-effects on the SubTask are best-effort. claude_runner
        # writing + committing code is the main job; ticket transitions /
        # implementation-notes / acceptance-checkbox flips are bookkeeping
        # that must never crash the parent loop. A failure here is logged
        # via self.progress and accumulated into sub_run.detail so the human
        # can fix the ticket state manually after the run. CRITICAL: a Jira
        # hiccup on subtask N must NOT block subtask N+1 (regression we hit
        # when transition('Request CR & Merge') failed mid-loop and the
        # parent's for-each-subtask aborted early — P2P-1237 → P2P-1238).
        jira_errors: list[str] = []

        def _try_sub(label: str, fn: Callable[[], Any]) -> None:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                msg = f"{label}: {e}"
                jira_errors.append(msg)
                self.progress(
                    f"[afk]   subtask {subtask.key}: jira side-effect failed — {msg}"
                )

        # Lifecycle: pending → designing → developing
        on_jira = self._backend_name() == "jira"
        if on_jira:
            _try_sub("assign", lambda: self.jira.assign(subtask.key, self._account_id))
        _try_sub("transition Start Designing",
                 lambda: self.tracker.start_designing(subtask.key))
        _try_sub("transition Start Development",
                 lambda: self.tracker.start_developing(subtask.key))

        outcome: Optional[ClaudeOutcome] = None
        pre_tip = self.worktrees.head_sha(spec)
        prior_statuses: list[str] = []
        for attempt in range(1, self.config.retry_count + 1):
            sub_run.attempts = attempt
            self.progress(
                f"[afk]   subtask {subtask.key}: attempt {attempt}/{self.config.retry_count} "
                f"— spawning claude (cap={self.config.wall_clock_cap_seconds}s)"
            )
            outcome = self.claude_runner(
                subtask.key, worktree_path, self.config.wall_clock_cap_seconds
            )
            self.progress(
                f"[afk]   subtask {subtask.key}: claude returned {outcome.status}"
                + (f" — {outcome.detail}" if outcome.detail else "")
            )
            if outcome.status == "success":
                # S1 — flag flaky-suspect when a prior attempt was
                # ``test_fail`` but a later attempt succeeded. The runner
                # has no way to tell "real fix" from "race that resolved"
                # without re-running deterministically; the flag tells
                # the human to look. Build_fail recovery is excluded —
                # see SubTaskRun.flaky_suspect docstring for rationale.
                if "test_fail" in prior_statuses:
                    sub_run.flaky_suspect = True
                # Safety net: claude was supposed to commit + push during its
                # session, but the spawned --print Code session has been
                # observed to edit files and exit without committing
                # (P2P-1233/1234/1235 smoke run, recovered by manual rescue
                # commit). Auto-stage + commit any leftover dirty state, then
                # require that *something* (claude's own commit OR our auto-
                # commit) has actually advanced the branch tip. A pure no-op
                # SubTask (no edits, no commits) is treated as a failure — we
                # refuse to transition a SubTask that didn't change any code.
                auto_msg = (
                    f"[{subtask.key}] AFK auto-commit\n\n"
                    "Claude session reported success but did not run git commit "
                    "before exiting. Runner is committing the leftover dirty "
                    "tree to ensure the work lands on the branch."
                )
                committed = self.worktrees.commit_dirty_changes(spec, auto_msg)
                post_tip = self.worktrees.head_sha(spec)
                if post_tip == pre_tip and not committed:
                    detail = "claude reported success but no code changes detected on branch"
                    self.progress(f"[afk]   subtask {subtask.key}: {detail} — failing SubTask")
                    outcome = ClaudeOutcome(status="other", detail=detail)
                    break
                if committed:
                    self.progress(
                        f"[afk]   subtask {subtask.key}: auto-commit captured "
                        f"claude's uncommitted edits ({pre_tip[:7]} -> {post_tip[:7]})"
                    )
                else:
                    self.progress(
                        f"[afk]   subtask {subtask.key}: claude committed "
                        f"({pre_tip[:7]} -> {post_tip[:7]})"
                    )
                self.worktrees.push_branch(spec)
                # Code already committed + pushed by this point. sub_run is
                # "success" no matter what these Jira calls do — we don't
                # punish the run because Jira refused a workflow transition.
                if on_jira:
                    _try_sub("populate Dev-CR/Merge gate fields",
                             lambda: self._populate_dev_cr_merge_gate(subtask.key, mr_url))
                _try_sub("transition Request CR & Merge",
                         lambda: self.tracker.request_cr_merge(subtask.key))
                if on_jira:
                    # Bullet-at-a-time ADF writer is the canonical Jira path
                    # (ST02 left the Protocol's whole-block ``splice_notes_block``
                    # as ``NotImplementedError``); GitHub uses the Protocol
                    # method via the runner's ADR-0004 ``splice_pr_block``
                    # neighbour rather than per-bullet ADF.
                    _try_sub("update implementation notes",
                             lambda: self.jira.update_implementation_notes(
                                 parent_key, subtask.key, subtask.summary))
                    _try_sub("flip acceptance checkboxes",
                             lambda: self.jira.flip_acceptance_checkboxes(subtask.key))
                sub_run.status = "success"
                if jira_errors:
                    sub_run.detail = "; ".join(jira_errors)
                sub_run.duration_s = self.monotonic() - t0
                if sub_run.flaky_suspect:
                    self.progress(
                        f"[afk]   subtask {subtask.key}: flaky-suspect — "
                        f"passed on attempt {attempt} after test_fail on a prior attempt"
                    )
                    flake_body = _flaky_suspect_comment(attempt, prior_statuses)
                    _try_sub("flaky-suspect note",
                             lambda: self.tracker.comment(subtask.key, flake_body))
                self.progress(
                    f"[afk]   subtask {subtask.key}: success in {sub_run.duration_s:.1f}s"
                )
                return sub_run
            prior_statuses.append(outcome.status)
            if outcome.status not in ("test_fail", "build_fail"):
                break  # timeout/other → no retry

        # exhausted retries or non-retryable failure
        detail = outcome.detail if outcome else "no outcome"
        self.progress(f"[afk]   subtask {subtask.key}: aborting — {detail}")
        # Fetch producer status for ``contract_mismatch`` so the comment
        # framing can branch on lock-point — re-open vs. emit-corrective.
        # On fetch failure (network, 404 if producer key was wrong, etc.)
        # producer_status stays empty and the comment falls back to the
        # historic re-open framing rather than guessing.
        producer_status = ""
        if (
            outcome is not None
            and outcome.status == "contract_mismatch"
            and outcome.producer_key
        ):
            try:
                producer_status = self.jira.get_status(outcome.producer_key)
            except Exception as e:
                jira_errors.append(f"producer status fetch failed: {e}")
        comment_body = _abort_comment(
            outcome, sub_run.attempts, detail, producer_status=producer_status,
        )
        _try_sub("abort comment",
                 lambda: self.tracker.comment(subtask.key, comment_body))
        if (
            outcome is not None
            and outcome.status == "contract_mismatch"
            and outcome.producer_key
        ):
            producer_body = _producer_mismatch_comment(
                subtask.key, outcome, producer_status,
            )
            _try_sub(
                "producer mismatch comment",
                lambda: self.tracker.comment(outcome.producer_key, producer_body),
            )
        _try_sub("transition Request Development (back to Dev-Pending)",
                 lambda: self.tracker.revert_to_pending(subtask.key))
        sub_run.detail = "; ".join([detail, *jira_errors])
        sub_run.status = "aborted"
        sub_run.duration_s = self.monotonic() - t0
        return sub_run

    def _process_standalone(self, issue):
        """Drive a labelled ticket that has no labelled SubTasks.

        Collapses the parent loop and the per-subtask loop onto a single
        ticket: one Draft MR, one claude spawn, one lifecycle through
        Designing/Developing/Request CR & Merge. The ticket description
        must follow the SubTask Markdown contract — full set: ``## Goal /
        ## Design refs (cited) / ## Scope / ## Acceptance / ## Produces
        (cited) / ## Test command / ## Parent PRD / ## Parent SDD (cited) /
        ## Blocked by / ## Consumes (cited+blocked) / ## Conflict procedure
        (cited) / ## Implementation Notes`` — that is what /afk:execute reads.

        Cited-mode contract enforcement applies equally to the standalone
        path: /afk:execute runs the consumer preflight (Step 2) and producer
        self-preflight (Step 10) regardless of whether this is a SubTask
        or a standalone. A ``contract_mismatch`` raised here names a
        producer that may live outside this drain pass — the runner still
        posts the producer-side comment via ``ClaudeOutcome.producer_key``.
        """
        key = issue.key
        info = self.jira.get_parent_fields(key)
        issuetype = info.get("issuetype") or issue.issuetype
        run = ParentRun(
            key=key,
            summary=info.get("summary", "") or issue.summary,
            issuetype=issuetype,
        )
        sub_run = SubTaskRun(key=key, summary=run.summary)
        run.subtasks.append(sub_run)
        t0 = self.monotonic()
        self.progress(
            f"[afk] standalone {key} ({issuetype or '?'}): no SubTasks — driving directly"
        )

        bootstrap = self._bootstrap_for_work(
            key, info, run, label_prefix="standalone", t0=t0,
        )
        if bootstrap is None:
            # _bootstrap_for_work set run.skip_reason / run.duration_s for us.
            # The standalone digest contract is "subtasks list is non-empty",
            # so propagate the skip onto the self-keyed SubTaskRun too.
            sub_run.status = "skipped"
            sub_run.detail = run.skip_reason
            return run
        spec, worktree_path, mr, target_branch = bootstrap

        def _try_jira(label: str, fn: Callable[[], Any]) -> None:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                msg = f"{label}: {e}"
                run.skip_reason = (
                    f"{run.skip_reason}; {msg}" if run.skip_reason else msg
                )
                self.progress(
                    f"[afk] standalone {key}: jira side-effect failed — {msg}"
                )

        on_jira = self._backend_name() == "jira"
        if on_jira:
            _try_jira("assign", lambda: self.jira.assign(key, self._account_id))
        if issuetype == "Enhancement":
            _try_jira("transition Start Designing",
                      lambda: self.tracker.start_designing(key))
        _try_jira("transition Start Development",
                  lambda: self.tracker.start_developing(key))

        if self.worktrees.reset_to_clean(spec):
            self.progress(
                f"[afk] standalone {key}: discarded uncommitted leftovers"
            )

        outcome: Optional[ClaudeOutcome] = None
        pre_tip = self.worktrees.head_sha(spec)
        prior_statuses: list[str] = []
        for attempt in range(1, self.config.retry_count + 1):
            sub_run.attempts = attempt
            self.progress(
                f"[afk] standalone {key}: attempt {attempt}/{self.config.retry_count} "
                f"— spawning claude (cap={self.config.wall_clock_cap_seconds}s)"
            )
            outcome = self.claude_runner(
                key, worktree_path, self.config.wall_clock_cap_seconds
            )
            self.progress(
                f"[afk] standalone {key}: claude returned {outcome.status}"
                + (f" — {outcome.detail}" if outcome.detail else "")
            )
            if outcome.status == "success":
                if "test_fail" in prior_statuses:
                    sub_run.flaky_suspect = True
                auto_msg = (
                    f"[{key}] AFK auto-commit\n\n"
                    "Claude session reported success but did not run git commit "
                    "before exiting. Runner is committing the leftover dirty "
                    "tree to ensure the work lands on the branch."
                )
                committed = self.worktrees.commit_dirty_changes(spec, auto_msg)
                post_tip = self.worktrees.head_sha(spec)
                if post_tip == pre_tip and not committed:
                    detail = "claude reported success but no code changes detected on branch"
                    self.progress(f"[afk] standalone {key}: {detail} — failing")
                    outcome = ClaudeOutcome(status="other", detail=detail)
                    break
                self.worktrees.push_branch(spec)
                sub_run.status = "success"
                break
            prior_statuses.append(outcome.status)
            if outcome.status not in ("test_fail", "build_fail"):
                break

        if sub_run.status == "success" and sub_run.flaky_suspect:
            self.progress(
                f"[afk] standalone {key}: flaky-suspect — "
                f"passed on attempt {sub_run.attempts} after test_fail on a prior attempt"
            )
            flake_body = _flaky_suspect_comment(sub_run.attempts, prior_statuses)
            _try_jira(
                "flaky-suspect note",
                lambda: self.tracker.comment(key, flake_body),
            )

        if sub_run.status != "success":
            detail = outcome.detail if outcome else "no outcome"
            self.progress(f"[afk] standalone {key}: aborting — {detail}")
            # Fetch producer status for ``contract_mismatch`` so the comment
            # framing branches on lock-point. Standalones can name producers
            # in entirely different drain pools, so the producer may already
            # be merged — if it is, "re-open" is wrong advice.
            producer_status = ""
            if (
                outcome is not None
                and outcome.status == "contract_mismatch"
                and outcome.producer_key
            ):
                try:
                    producer_status = self.jira.get_status(outcome.producer_key)
                except Exception as e:  # noqa: BLE001
                    self.progress(
                        f"[afk] standalone {key}: producer status fetch "
                        f"failed ({e}) — falling back to mutable framing"
                    )
            comment_body = _abort_comment(
                outcome, sub_run.attempts, detail, producer_status=producer_status,
            )
            _try_jira("abort comment",
                      lambda: self.tracker.comment(key, comment_body))
            if (
                outcome is not None
                and outcome.status == "contract_mismatch"
                and outcome.producer_key
            ):
                producer_body = _producer_mismatch_comment(
                    key, outcome, producer_status,
                )
                _try_jira(
                    "producer mismatch comment",
                    lambda: self.tracker.comment(outcome.producer_key, producer_body),
                )
            _try_jira("transition Request Development (back to Dev-Pending)",
                      lambda: self.tracker.revert_to_pending(key))
            sub_run.status = "aborted"
            sub_run.detail = detail
            sub_run.duration_s = self.monotonic() - t0
            run.duration_s = self.monotonic() - t0
            return run

        self.progress(f"[afk] standalone {key}: rebase onto origin/{target_branch}")
        rebase_outcome = self.worktrees.rebase_onto_target(spec)
        run.rebase = rebase_outcome
        self.progress(f"[afk] standalone {key}: rebase {rebase_outcome}")
        if rebase_outcome == "clean":
            if on_jira:
                _try_jira("populate Dev-CR/Merge gate fields",
                          lambda: self._populate_dev_cr_merge_gate(key, mr.web_url))
            _try_jira("transition Request CR & Merge",
                      lambda: self.tracker.request_cr_merge(key))
            if on_jira:
                _try_jira("flip acceptance checkboxes",
                          lambda: self.jira.flip_acceptance_checkboxes(key))
            self.progress(f"[afk] standalone {key}: transitioned to cr-merge")
        else:
            _try_jira("rebase-conflict comment",
                      lambda: self.tracker.comment(
                          key,
                          f"AFK rebase against `{target_branch}` reported conflicts. "
                          "Resolve manually before merging."))

        sub_run.duration_s = self.monotonic() - t0
        run.duration_s = self.monotonic() - t0
        self.progress(f"[afk] standalone {key}: done in {run.duration_s:.1f}s")
        return run

    def _bootstrap_for_work(
        self,
        key: str,
        info: Mapping[str, Any],
        run: ParentRun,
        *,
        label_prefix: str,
        t0: float,
        extra_precheck: Optional[Callable[[], Optional[str]]] = None,
    ):
        """Validate fields, set up worktree+branch, open Draft MR.

        Shared preamble for both ``_process_parent`` (parent + labelled
        SubTasks) and ``_process_standalone`` (one labelled non-subtask).
        Returns ``(spec, worktree_path, mr, target_branch)`` on success,
        or ``None`` if a skip was recorded — in which case ``run.skip_reason``
        and ``run.duration_s`` are already populated and the caller should
        return ``run`` immediately. ``extra_precheck`` runs after target
        branch resolution but before MR lookup; returning a non-empty
        string aborts the bootstrap with that message as ``skip_reason``
        (used by ``_process_parent`` to enforce its mid-state status
        guard).
        """
        if not info.get("fix_versions"):
            run.skip_reason = "ticket has no fixVersions"
            run.duration_s = self.monotonic() - t0
            self.progress(f"[afk] {label_prefix} {key}: skipped — {run.skip_reason}")
            return None
        target_value = _extract_value(info.get("target_branch"))
        if not target_value:
            run.skip_reason = "ticket has no Target Branch"
            run.duration_s = self.monotonic() - t0
            self.progress(f"[afk] {label_prefix} {key}: skipped — {run.skip_reason}")
            return None
        target_branch = self.config.target_branch_value_map.get(
            target_value, target_value
        )
        run.target_branch = target_branch

        if extra_precheck is not None:
            precheck_msg = extra_precheck()
            if precheck_msg:
                run.skip_reason = precheck_msg
                run.duration_s = self.monotonic() - t0
                self.progress(
                    f"[afk] {label_prefix} {key}: skipped — {run.skip_reason}"
                )
                return None

        spec = WorktreeSpec(
            repo_root=self.repo_root,
            worktree_root=self.config.worktree_root,
            parent_id=key,
            base_branch=target_branch,
        )
        # Branch / worktree discovery: a user may have already opened an MR
        # against a hand-crafted branch (Nakisa convention:
        # ``kapteyn/development/mvu/{slug}``). When that's the case the AFK
        # driver must continue work on THAT branch — opening a fresh
        # ``mvu/afk/{key}`` would orphan the human's existing MR. Lookup
        # is by key in MR title; ambiguity (>1 open MR) is a GitLabError
        # raised by find_open_mr_by_parent_key — we trap it as a skip
        # rather than crashing the pass.
        try:
            existing_mr = self.gitlab.find_open_mr_by_parent_key(key)
        except Exception as e:  # noqa: BLE001
            run.skip_reason = f"MR lookup failed: {e}"
            run.duration_s = self.monotonic() - t0
            self.progress(f"[afk] {label_prefix} {key}: skipped — {run.skip_reason}")
            return None
        if existing_mr is not None and existing_mr.source_branch:
            spec = replace(spec, branch_override=existing_mr.source_branch)
            self.progress(
                f"[afk] {label_prefix} {key}: reusing existing MR !{existing_mr.iid} "
                f"on branch {existing_mr.source_branch}"
            )
            try:
                foreign_path = self.worktrees.find_worktree_for_branch(
                    self.repo_root, spec.branch
                )
            except Exception:  # noqa: BLE001 - discovery is best-effort
                foreign_path = None
            if foreign_path is not None and foreign_path != spec.path:
                spec = replace(spec, path_override=foreign_path)
                self.progress(
                    f"[afk] {label_prefix} {key}: reusing existing worktree at "
                    f"{foreign_path}"
                )

        try:
            worktree_path = self.worktrees.ensure(spec)
            self.worktrees.publish_branch(spec)
        except WorktreeError as e:
            run.skip_reason = f"worktree setup failed: {e}"
            run.duration_s = self.monotonic() - t0
            self.progress(f"[afk] {label_prefix} {key}: skipped — {run.skip_reason}")
            return None
        self.progress(
            f"[afk] {label_prefix} {key}: worktree ready at {worktree_path} "
            f"(branch {spec.branch}, base {target_branch})"
        )

        mr = self.gitlab.open_draft_mr(
            source_branch=spec.branch,
            target_branch=target_branch,
            title=f"[{key}] {run.summary}",
            description=(
                f"AFK auto-managed Draft MR for {key}.\n\n"
                "<!-- afk:subtasks:start -->\n<!-- afk:subtasks:end -->"
            ),
            assignee=self.config.mr_assignee or None,
        )
        run.mr_url = mr.web_url
        self.progress(f"[afk] {label_prefix} {key}: MR {mr.web_url}")

        # Attach MR link immediately so reviewers can find the in-flight
        # branch even before any work reaches Dev-CR/Merge. Jira-only — the
        # Nakisa MR-link custom field has no GitHub equivalent (PRD §"Tracker
        # -only fields"); the PR's own description carries the linkage on
        # GitHub.
        on_jira = self._backend_name() == "jira"
        if on_jira:
            mr_link_field = self.config.dev_cr_merge_gate_fields.get("merge_request_link")
            if mr_link_field:
                try:
                    self.jira.set_fields(key, {mr_link_field: mr.web_url})
                except Exception as e:  # noqa: BLE001
                    run.skip_reason = f"MR-link write failed: {e}"
            # Default A+ Clarity to green when unset; never overrides a
            # deliberate human choice (set_field_if_unset is no-op when set).
            if self.config.aplus_clarity_field and self.config.aplus_clarity_green_option_id:
                try:
                    self.jira.set_field_if_unset(
                        key,
                        self.config.aplus_clarity_field,
                        {"id": self.config.aplus_clarity_green_option_id},
                    )
                except Exception as e:  # noqa: BLE001
                    run.skip_reason = f"A+ clarity write failed: {e}"

        return spec, worktree_path, mr, target_branch

    def _populate_dev_cr_merge_gate(self, key: str, mr_url: str) -> None:
        """Fill the custom fields the Nakisa workflow validator demands on the
        Request CR & Merge transition. Without these, the transition POST
        returns 400 with errors like "Merge Request Link field needs to be
        filled in" / "Eligibility for SRED must be specified" /
        "Time estimation must be provided" / "Rationale for eligible/ineligible
        must be provided".

        The merge-request-link value comes from the live MR; everything else
        uses the configured default so the AFK lane can run without per-ticket
        ceremony — the user is on the hook for adjusting these fields manually
        if a SubTask actually merits SRED treatment.

        sred_rationale is a rich-text customfield: Jira rejects plain strings
        with "Operation value must be an Atlassian Document". The runner wraps
        any string value for that logical field into a one-paragraph ADF doc
        so config.toml stays user-friendly.
        """
        fields_map = self.config.dev_cr_merge_gate_fields
        defaults = self.config.dev_cr_merge_gate_defaults
        payload: dict[str, Any] = {}
        link_field = fields_map.get("merge_request_link")
        if link_field and mr_url:
            payload[link_field] = mr_url
        for logical, default_value in defaults.items():
            cf_id = fields_map.get(logical)
            if cf_id is None:
                continue
            if logical in _RICH_TEXT_LOGICAL_FIELDS and isinstance(default_value, str):
                payload[cf_id] = _wrap_string_as_adf(default_value)
            else:
                payload[cf_id] = default_value
        if payload:
            self.jira.set_fields(key, payload)


class _RepoIsolatedError(RuntimeError):
    """Internal-only signal that one repo's work failed in a way that should
    isolate (record as ``RepoFailed`` + continue to next repo) rather than
    halt the run.

    Raised inside ``Runner._drain_repo`` when ``ensure_clone`` fails or any
    other per-repo pre-condition can't be satisfied. The enclosing
    ``Runner._drain_github_multi_repo`` catches it, emits the run-record
    entry, and proceeds to the next repo (ADR-0003 flowchart ``skip_repo``
    rung).

    Auth-level failures (raised by ``tracker`` / ``scm`` pre-flight) are
    NOT wrapped in this type — they propagate up and halt the entire run
    per PRD §"Pre-flight checks".
    """


def _group_issues_by_repo(issues: list) -> dict[tuple[str, str], list]:
    """Group GitHub ``SubIssueRef`` rows by ``(owner, repo)``.

    Each ref's ``id`` follows the ``owner/repo#N`` convention (see
    ``tracker_protocol.SubIssueRef``). Issues whose id cannot be parsed
    (e.g. a non-GitHub backend leaking into the wrong code path) are
    silently dropped here — the runner's caller is expected to fan-out
    only GitHub queues into this helper. Order within each group is
    preserved from the input list.
    """
    groups: dict[tuple[str, str], list] = {}
    for issue in issues:
        issue_id = getattr(issue, "id", "") or getattr(issue, "key", "")
        if not issue_id or "#" not in issue_id:
            continue
        left, _, _ = issue_id.rpartition("#")
        if "/" not in left:
            continue
        owner, _, repo = left.partition("/")
        if not owner or not repo:
            continue
        groups.setdefault((owner, repo), []).append(issue)
    return groups


# Producer SubTask statuses for which "re-open and correct" is a viable
# recovery path. Anything else (Dev-CR/Merge, Done, Closed, Resolved, the
# Merged terminus, etc.) means the producer ticket has passed the lock
# point — re-opening it would require reverting a merge — so the runner
# tells the human to emit a *corrective* SubTask under the same parent
# instead. Without this branching the consumer would bounce back to
# Dev-Pending forever, waiting for a producer ticket that nobody can
# touch. (S3 closure 2026-05-08.)
_PRODUCER_MUTABLE_STATUSES = frozenset({
    "Dev-Pending",
    "Dev-Designing",
    "Dev-Developing",
})


def _producer_is_locked(producer_status: str) -> bool:
    """A producer is locked when its workflow position is past the
    Dev-Developing terminus — re-opening would mean reverting a merge.
    Empty / unknown status is treated as mutable (status-fetch failure
    falls back to the historic re-open framing rather than emitting the
    locked framing on guesswork)."""
    return bool(producer_status) and producer_status not in _PRODUCER_MUTABLE_STATUSES


def _abort_comment(
    outcome: Optional[ClaudeOutcome], attempts: int, detail: str,
    *, producer_status: str = "",
) -> str:
    """Build the Jira comment body for an aborted SubTask.

    Three binding-contract outcomes get explicit framing:

    - ``design_conflict`` — the SDD/ADR mandate is wrong/infeasible. Routes
      the human to ``/architect-grill`` for a superseding ADR.
    - ``contract_mismatch`` — an upstream SubTask's ``## Produces`` artifact
      failed this consumer's preflight grep (signature drift, missing symbol,
      wrong file). Routes the human to the producer SubTask. Without the
      explicit framing, the human reads "aborted: <detail>" and assumes a
      flaky test, retries, and the chain wedges again.
    - ``produces_drift`` — this SubTask's OWN producer self-preflight failed:
      it declared artifacts in ``## Produces`` but its own grep found them
      missing or signature-divergent. Symmetric to ``contract_mismatch`` but
      with no separate producer ticket — the producer IS this SubTask. Routes
      the human to either fix the impl OR re-emit the slice with a corrected
      ``## Produces`` declaration. Without the explicit framing the failure
      surfaces only at the next consumer's preflight — wasting a drain pass
      on the wrong ticket.
    """
    if outcome is not None and outcome.status == "design_conflict":
        return (
            f"AFK aborted: **design conflict** flagged by the implementing agent "
            f"after {attempts} attempt(s).\n\n"
            f"{detail}\n\n"
            "The agent found a binding decision in the SDD/ADR wrong, infeasible, "
            "or contradicting reality. Resolve via `/architect-grill` and emit a "
            "superseding ADR (Status: Accepted, Supersedes: NNNN) before "
            "re-queueing this SubTask. Do not retry as-is."
        )
    if outcome is not None and outcome.status == "contract_mismatch":
        if outcome.producer_key and _producer_is_locked(producer_status):
            producer_line = (
                f"Producer SubTask: **{outcome.producer_key}** "
                f"(currently `{producer_status}` — past the lock point).\n\n"
            )
            recovery = (
                "The producer ticket is **locked** — its workflow has passed "
                "Dev-Developing, so re-opening it would mean reverting a "
                "merge. Emit a **corrective SubTask** under the same parent "
                "that delivers the missing/divergent `## Produces` artifact, "
                "then re-rank this consumer behind it before re-queueing. Do "
                "NOT retry this consumer as-is — it will bounce on the same "
                "preflight every drain pass until the corrective slice lands."
            )
        else:
            producer_status_note = (
                f" (currently `{producer_status}`)"
                if outcome.producer_key and producer_status
                else ""
            )
            producer_line = (
                f"Producer SubTask: **{outcome.producer_key}**{producer_status_note}\n\n"
                if outcome.producer_key
                else ""
            )
            recovery = (
                "An upstream `## Produces` artifact does not match what this "
                "SubTask's `## Consumes` declared. Fix the producer (re-open "
                "it or emit a corrective SubTask) before re-queueing this "
                "one. Retrying as-is will fail the same way."
            )
        return (
            f"AFK aborted: **contract mismatch** detected by the implementing "
            f"agent's preflight on attempt {attempts}.\n\n"
            f"{producer_line}{detail}\n\n"
            f"{recovery}"
        )
    if outcome is not None and outcome.status == "produces_drift":
        return (
            f"AFK aborted: **producer self-check failed** on attempt "
            f"{attempts}.\n\n"
            f"{detail}\n\n"
            "This SubTask declared artifacts in `## Produces` that its own "
            "pre-success grep could not find on the branch — either the "
            "implementation diverged from the declared signature, or the "
            "declared signature itself was wrong. Fix the implementation OR "
            "re-emit the slice with a corrected `## Produces` declaration "
            "before re-queueing. Retrying as-is will fail the same way. "
            "(If the declared signature is wrong because a binding SDD/ADR "
            "decision is wrong, exit `design_conflict` next time, not "
            "`produces_drift`.)"
        )
    return f"AFK aborted after {attempts} attempt(s): {detail}"


def _flaky_suspect_comment(
    success_attempt: int, prior_statuses: list[str],
) -> str:
    """Comment posted when a SubTask succeeded on a retry after a prior
    ``test_fail``. The retry mechanism is supposed to absorb genuine
    transients (network blip, lock contention), but a test that passes
    on attempt N and fails on attempt N-1 with the same code is by
    definition not deterministic — the human needs a heads-up so the
    flake can be diagnosed before it's normalized into the test suite's
    background noise. (S1 closure 2026-05-08.)
    """
    history = " → ".join(prior_statuses + ["success"])
    return (
        f"AFK note: **flaky-suspect** — this SubTask passed on retry "
        f"attempt **{success_attempt}** after at least one earlier "
        f"`test_fail`. Attempt history: `{history}`.\n\n"
        "The retry loop absorbed the failure, but the same code passed "
        "the same test command twice with different outcomes — that's a "
        "race / timing dependency / shared-state leak by definition, not "
        "a genuine transient. Investigate before this normalises into "
        "background noise: rerun the test in isolation, check for "
        "shared mutable fixtures, look for time-of-day or ordering "
        "dependencies. If confirmed flaky, file a separate ticket — "
        "do not just close this comment."
    )


def _producer_mismatch_comment(
    consumer_key: str, outcome: ClaudeOutcome, producer_status: str = "",
) -> str:
    """Comment posted on the **producer** SubTask when its consumer flagged a
    contract mismatch. Surfaces the break at the producing SubTask's history
    so the human triaging that ticket knows the downstream impact without
    cross-referencing the consumer's comment thread.

    Branches on producer status: when the producer is past the Dev-Developing
    lock point (Dev-CR/Merge, Done, Closed, ...), telling the human to "re-
    open" is wrong — re-opening would mean reverting a merge. The locked
    framing tells them to emit a corrective SubTask instead. (S3 closure
    2026-05-08.)
    """
    if _producer_is_locked(producer_status):
        return (
            f"AFK contract break flagged by downstream SubTask **{consumer_key}**:\n\n"
            f"{outcome.detail}\n\n"
            f"This SubTask is currently in `{producer_status}` — past the "
            "Dev-Developing lock point. Do **not** re-open it (that would "
            "require reverting a merge). Instead, emit a **corrective "
            "SubTask** under the same parent that delivers the missing or "
            "divergent `## Produces` artifact the consumer expected. Re-rank "
            "the consumer behind that corrective slice before re-queueing. "
            "If the binding contract itself is wrong, route via "
            "`/architect-grill` for a superseding ADR before slicing the "
            "correction."
        )
    return (
        f"AFK contract break flagged by downstream SubTask **{consumer_key}**:\n\n"
        f"{outcome.detail}\n\n"
        "This SubTask's `## Produces` artifact does not match the signature / "
        "symbol the consumer expected. Re-open and correct the produced "
        "interface, or supersede via `/architect-grill` if the binding "
        "contract itself was wrong. The consumer SubTask is blocked until "
        "this is resolved."
    )


# Logical field names whose values must be sent as ADF documents, even though
# the config exposes them as plain strings for ergonomic toml editing.
_RICH_TEXT_LOGICAL_FIELDS = frozenset({"sred_rationale"})


def _wrap_string_as_adf(text: str) -> dict:
    """Wrap a plain string as a one-paragraph ADF document."""
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ],
    }


def _extract_value(field_value: Any) -> str:
    """Pull a string out of a Jira field that may be a string, dict {value:..},
    or cascade {value:.., child:{value:..}}."""
    if field_value is None:
        return ""
    if isinstance(field_value, str):
        return field_value
    if isinstance(field_value, dict):
        return str(field_value.get("value", ""))
    return str(field_value)

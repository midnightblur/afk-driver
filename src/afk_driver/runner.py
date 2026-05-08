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
from afk_driver.worktree_manager import WorktreeError, WorktreeSpec


ClaudeStatus = Literal["success", "test_fail", "build_fail", "timeout", "other"]


@dataclass(frozen=True)
class ClaudeOutcome:
    status: ClaudeStatus
    detail: str = ""


ClaudeRunner = Callable[[str, Path, int], ClaudeOutcome]


@dataclass
class SubTaskRun:
    key: str
    summary: str
    status: Literal["success", "aborted", "skipped"] = "skipped"
    attempts: int = 0
    detail: str = ""
    duration_s: float = 0.0


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


@dataclass
class RunRecord:
    started_iso: str
    ended_iso: str = ""
    parents: list[ParentRun] = field(default_factory=list)


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
    jira: Any
    gitlab: Any
    worktrees: Any
    claude_runner: ClaudeRunner
    config: DriverConfig
    repo_root: Path
    label: str = "afk-agents"
    project_key: str = "P2P"
    now_iso: Callable[[], str] = field(
        default_factory=lambda: lambda: datetime.now(timezone.utc).isoformat()
    )
    monotonic: Callable[[], float] = time.monotonic
    # Live progress sink. Defaults to stdout so a real `afk` invocation shows
    # the user what the driver is up to without having to tail a log file. Tests
    # pass a no-op callable to keep pytest output clean.
    progress: Callable[[str], None] = field(default=lambda msg: print(msg, flush=True))

    def one_pass(self) -> RunRecord:
        record = RunRecord(started_iso=self.now_iso())
        self.progress(f"[afk] one_pass start (project={self.project_key} label={self.label})")
        # Cache the authenticated account once; needed before every transition
        # that runs through the "Assignee must be specified" workflow validator.
        self._account_id = self.jira.get_my_account_id()
        issues = self.jira.search(
            f'project = {self.project_key} AND labels = "{self.label}" '
            f'AND status = "Dev-Pending" ORDER BY rank'
        )
        if not issues:
            self.progress("[afk] no Dev-Pending labelled tickets found; exiting")
            record.ended_iso = self.now_iso()
            return record
        self.progress(f"[afk] found {len(issues)} Dev-Pending labelled ticket(s)")

        # Classify: anything with a parent_key is a SubTask under the existing
        # group-by-parent flow. Anything without is a candidate "standalone"
        # (Enhancement/Bug labelled directly with no labelled SubTasks driving
        # it). If a non-subtask ALSO has labelled SubTasks in this same
        # result, prefer the SubTask flow — a labelled parent in that case is
        # treated as residual.
        by_parent: dict[str, list] = defaultdict(list)
        standalone_candidates: list = []
        for issue in issues:
            if issue.parent_key:
                by_parent[issue.parent_key].append(issue)
            else:
                standalone_candidates.append(issue)
        covered_as_parent = set(by_parent.keys())
        standalones = [
            i for i in standalone_candidates if i.key not in covered_as_parent
        ]

        # Order parent-flow entries: those already past Dev-Pending first.
        ordered: list[tuple[str, dict, list]] = []
        for parent_key, subs in by_parent.items():
            parent = self.jira.get_parent_fields(parent_key)
            ordered.append((parent_key, parent, subs))
        ordered.sort(key=lambda t: 0 if t[1].get("status") != "Dev-Pending" else 1)

        for parent_key, parent, subs in ordered:
            run = self._process_parent(parent_key, parent, subs)
            record.parents.append(run)

        for standalone in standalones:
            run = self._process_standalone(standalone)
            record.parents.append(run)

        record.ended_iso = self.now_iso()
        self.progress(f"[afk] one_pass done ({len(record.parents)} parent(s) processed)")
        return record

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

        if parent_status == "Dev-Pending":
            _try_jira("assign parent",
                      lambda: self.jira.assign(parent_key, self._account_id))
            # Bug workflow goes Dev-Pending → Dev-Developing directly; only the
            # Enhancement workflow has the intermediate "Start Designing"
            # transition. Verified empirically against P2P-1228 (Bug):
            # available transitions did not include "Start Designing".
            if parent.get("issuetype") == "Enhancement":
                _try_jira("transition Start Designing",
                          lambda: self.jira.transition(parent_key, "Start Designing"))
            _try_jira("transition Start Development",
                      lambda: self.jira.transition(parent_key, "Start Development"))

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
                _try_jira("populate Dev-CR/Merge gate fields",
                          lambda: self._populate_dev_cr_merge_gate(parent_key, mr.web_url))
                _try_jira("transition Request CR & Merge",
                          lambda: self.jira.transition(parent_key, "Request CR & Merge"))
                _try_jira("flip acceptance checkboxes",
                          lambda: self.jira.flip_acceptance_checkboxes(parent_key))
                self.progress(f"[afk] parent {parent_key}: transitioned to Dev-CR/Merge")
            else:
                _try_jira("rebase-conflict comment",
                          lambda: self.jira.comment(
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

        # Lifecycle: Dev-Pending → Dev-Designing → Dev-Developing
        _try_sub("assign", lambda: self.jira.assign(subtask.key, self._account_id))
        _try_sub("transition Start Designing",
                 lambda: self.jira.transition(subtask.key, "Start Designing"))
        _try_sub("transition Start Development",
                 lambda: self.jira.transition(subtask.key, "Start Development"))

        outcome: Optional[ClaudeOutcome] = None
        pre_tip = self.worktrees.head_sha(spec)
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
                _try_sub("populate Dev-CR/Merge gate fields",
                         lambda: self._populate_dev_cr_merge_gate(subtask.key, mr_url))
                _try_sub("transition Request CR & Merge",
                         lambda: self.jira.transition(subtask.key, "Request CR & Merge"))
                _try_sub("update implementation notes",
                         lambda: self.jira.update_implementation_notes(
                             parent_key, subtask.key, subtask.summary))
                _try_sub("flip acceptance checkboxes",
                         lambda: self.jira.flip_acceptance_checkboxes(subtask.key))
                sub_run.status = "success"
                if jira_errors:
                    sub_run.detail = "; ".join(jira_errors)
                sub_run.duration_s = self.monotonic() - t0
                self.progress(
                    f"[afk]   subtask {subtask.key}: success in {sub_run.duration_s:.1f}s"
                )
                return sub_run
            if outcome.status not in ("test_fail", "build_fail"):
                break  # timeout/other → no retry

        # exhausted retries or non-retryable failure
        detail = outcome.detail if outcome else "no outcome"
        self.progress(f"[afk]   subtask {subtask.key}: aborting — {detail}")
        _try_sub("abort comment",
                 lambda: self.jira.comment(
                     subtask.key,
                     f"AFK aborted after {sub_run.attempts} attempt(s): {detail}"))
        _try_sub("transition Request Development (back to Dev-Pending)",
                 lambda: self.jira.transition(subtask.key, "Request Development"))
        sub_run.detail = "; ".join([detail, *jira_errors])
        sub_run.status = "aborted"
        sub_run.duration_s = self.monotonic() - t0
        return sub_run

    def _process_standalone(self, issue):
        """Drive a labelled ticket that has no labelled SubTasks.

        Collapses the parent loop and the per-subtask loop onto a single
        ticket: one Draft MR, one claude spawn, one lifecycle through
        Designing/Developing/Request CR & Merge. The ticket description
        must follow the SubTask Markdown contract (## Goal / ## Scope /
        ## Acceptance / ## Test command / ## Parent PRD / ## Blocked by /
        ## Implementation Notes) — that is what /afk-go reads.
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

        _try_jira("assign", lambda: self.jira.assign(key, self._account_id))
        if issuetype == "Enhancement":
            _try_jira("transition Start Designing",
                      lambda: self.jira.transition(key, "Start Designing"))
        _try_jira("transition Start Development",
                  lambda: self.jira.transition(key, "Start Development"))

        if self.worktrees.reset_to_clean(spec):
            self.progress(
                f"[afk] standalone {key}: discarded uncommitted leftovers"
            )

        outcome: Optional[ClaudeOutcome] = None
        pre_tip = self.worktrees.head_sha(spec)
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
            if outcome.status not in ("test_fail", "build_fail"):
                break

        if sub_run.status != "success":
            detail = outcome.detail if outcome else "no outcome"
            self.progress(f"[afk] standalone {key}: aborting — {detail}")
            _try_jira("abort comment",
                      lambda: self.jira.comment(
                          key,
                          f"AFK aborted after {sub_run.attempts} attempt(s): {detail}"))
            _try_jira("transition Request Development (back to Dev-Pending)",
                      lambda: self.jira.transition(key, "Request Development"))
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
            _try_jira("populate Dev-CR/Merge gate fields",
                      lambda: self._populate_dev_cr_merge_gate(key, mr.web_url))
            _try_jira("transition Request CR & Merge",
                      lambda: self.jira.transition(key, "Request CR & Merge"))
            _try_jira("flip acceptance checkboxes",
                      lambda: self.jira.flip_acceptance_checkboxes(key))
            self.progress(f"[afk] standalone {key}: transitioned to Dev-CR/Merge")
        else:
            _try_jira("rebase-conflict comment",
                      lambda: self.jira.comment(
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
        # branch even before any work reaches Dev-CR/Merge.
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

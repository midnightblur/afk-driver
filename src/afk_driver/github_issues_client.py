"""GitHub-backed ``IssueTracker`` implementation (ST04).

Wraps the ``gh`` CLI (and ``gh api`` for endpoints the CLI does not natively
expose — namely the sub-issue REST surface) to drive the same phase-semantic
operations the Jira adapter exposes. Phase is encoded as a mutually-exclusive
``afk:*`` label set (ADR-0002); every transition is implemented as a single
``gh issue edit --remove-label … --add-label …`` followed by a
``gh issue view --json labels`` verification read, retried up to three times
with backoff before aborting with a comment on the issue (ADR-0004).

All subprocess I/O flows through an injected ``GhRunner`` callable so tests
can stub command outputs deterministically — mirrors the ``GlabRunner`` /
``repo_clone_manager.GhRunner`` pattern. No HTTP libraries are imported here
(ADR-0001 — driver-side path is ``gh`` CLI only).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from afk_driver.section_splice import SectionMarkerMissing, marker_id_text
from afk_driver.tracker_protocol import IssueTracker, ParentRef, SubIssueRef


# ---------------------------------------------------------------------------
# Public constants — phase-label vocabulary (ADR-0002)
# ---------------------------------------------------------------------------

PHASE_PENDING = "afk:pending"
PHASE_DESIGNING = "afk:designing"
PHASE_DEVELOPING = "afk:developing"
PHASE_CR_MERGE = "afk:cr-merge"

ALL_PHASE_LABELS: tuple[str, ...] = (
    PHASE_PENDING,
    PHASE_DESIGNING,
    PHASE_DEVELOPING,
    PHASE_CR_MERGE,
)

AFK_AGENTS_LABEL = "afk-agents"

# Marker id for the parent's auto-maintained Implementation Notes block.
_NOTES_MARKER_ID = "notes"

# Verify-after-write retry policy (ADR-0004 + SDD §5 retry table). Three
# attempts total; backoffs applied *before* attempts 2 and 3. Sleep is
# parametrised by injection (see ``GitHubIssuesClient.__init__``) so tests
# can pass a no-op stub instead of waiting wall-clock milliseconds.
_VERIFY_BACKOFF_MS: tuple[int, int, int] = (0, 200, 600)


GhRunner = Callable[[list[str]], subprocess.CompletedProcess]
SleepFn = Callable[[float], None]


def default_runner(args: list[str]) -> subprocess.CompletedProcess:
    """Default runner — shells out to the host's ``gh`` CLI.

    Unlike ``repo_clone_manager.default_runner`` this client only ever calls
    ``gh`` (never raw ``git``); the runner therefore prepends ``gh`` itself
    so call sites pass only the subcommand arguments.
    """
    return subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


# ---------------------------------------------------------------------------
# Typed errors
# ---------------------------------------------------------------------------


class GitHubApiError(RuntimeError):
    """Raised when a ``gh`` invocation exits non-zero or returns
    unparseable JSON. Carries the stderr / stdout context so the digest
    writer can surface it without re-shelling.
    """


class GitHubLabelMismatch(RuntimeError):
    """Raised by the internal verify step when a label-read disagrees with
    the target phase. Pure signalling type — never reaches the caller
    directly; converted into ``PhaseTransitionError`` once retries are
    exhausted.
    """


class PhaseTransitionError(RuntimeError):
    """Raised when ``transition_phase`` exhausts its retry budget (ADR-0004).

    The caller has already posted an abort comment on the issue at the
    point this is raised — the runner uses the typed exception purely to
    decide whether to advance to the next parent or halt.
    """


# ---------------------------------------------------------------------------
# Internal value records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _IssueCoords:
    """Parsed ``owner/repo#N`` issue identifier."""

    owner: str
    repo: str
    number: int

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    @property
    def ref(self) -> str:
        return f"{self.owner}/{self.repo}#{self.number}"


def _parse_issue_id(issue_id: str) -> _IssueCoords:
    """Parse ``owner/repo#N`` into its three components.

    Accepts only the canonical AFK GitHub coordinate (matches the shape
    documented in ``tracker_protocol.SubIssueRef``). Anything else raises
    ``GitHubApiError`` — refusing to guess is safer than silently
    constructing an ill-formed ``gh`` invocation.
    """
    if "#" not in issue_id:
        raise GitHubApiError(
            f"github issue id must be 'owner/repo#N', got {issue_id!r}"
        )
    left, _, num_s = issue_id.rpartition("#")
    if "/" not in left:
        raise GitHubApiError(
            f"github issue id must be 'owner/repo#N', got {issue_id!r}"
        )
    owner, _, repo = left.partition("/")
    try:
        number = int(num_s)
    except ValueError as e:
        raise GitHubApiError(
            f"github issue id number not an int: {issue_id!r}"
        ) from e
    if not owner or not repo:
        raise GitHubApiError(
            f"github issue id must be 'owner/repo#N', got {issue_id!r}"
        )
    return _IssueCoords(owner=owner, repo=repo, number=number)


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class GitHubIssuesClient(IssueTracker):
    """GitHub-side ``IssueTracker`` implementation.

    See module docstring + SDD §8 row ``github_issues_client`` for the
    architectural slot. ``runner`` is injected (``GhRunner``); ``sleep`` is
    injected (``SleepFn``) so the verify-after-write backoff is testable
    without real wall-clock waits.
    """

    def __init__(
        self,
        runner: GhRunner = default_runner,
        *,
        sleep: SleepFn = time.sleep,
        backoff_ms: Sequence[int] = _VERIFY_BACKOFF_MS,
    ) -> None:
        self._run = runner
        self._sleep = sleep
        # Copy to a tuple so callers can't mutate the policy post-construction.
        self._backoff_ms: tuple[int, ...] = tuple(backoff_ms)
        if len(self._backoff_ms) < 1:
            raise ValueError("backoff_ms must declare at least one attempt")

    # ------------------------------------------------------------------
    # Queue discovery
    # ------------------------------------------------------------------

    def list_pickable(self) -> list[SubIssueRef]:
        """Single ``gh search issues`` call for AFK-eligible pending issues
        assigned to the authenticated user (SDD §3 queue-discovery
        sequenceDiagram, ADR §AuthZ row "AFK-eligible sub-issue").
        """
        return self._search_issues(
            f"assignee:@me state:open label:{AFK_AGENTS_LABEL} label:{PHASE_PENDING}"
        )

    def list_stuck_subissues(self) -> list[SubIssueRef]:
        """Sweeper's view: any non-pending afk:* label still attached to an
        assignee=@me issue indicates a prior crashed run (ADR-0005). The
        GitHub search grammar does not support OR between label terms in a
        single call; we issue one search per non-pending phase and
        union-by-id.
        """
        seen: dict[str, SubIssueRef] = {}
        for phase in (PHASE_DESIGNING, PHASE_DEVELOPING, PHASE_CR_MERGE):
            for ref in self._search_issues(
                f"assignee:@me state:open label:{AFK_AGENTS_LABEL} label:{phase}"
            ):
                seen.setdefault(ref.id, ref)
        return list(seen.values())

    def _search_issues(self, query: str) -> list[SubIssueRef]:
        """Shared search worker — runs ``gh search issues`` with the canonical
        JSON fields and parses each row into a ``SubIssueRef``.
        """
        proc = self._run([
            "search", "issues",
            "--json", "repository,number,title,body",
            "--",  # belt-and-braces: ensure the query is positional
            query,
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh search issues failed: {proc.stderr.strip()}"
            )
        try:
            rows = json.loads(proc.stdout) if proc.stdout.strip() else []
        except json.JSONDecodeError as e:
            raise GitHubApiError(
                f"gh search issues returned non-JSON: {proc.stdout[:200]}"
            ) from e
        if not isinstance(rows, list):
            raise GitHubApiError(
                f"gh search issues expected JSON array, got {type(rows).__name__}"
            )
        out: list[SubIssueRef] = []
        for row in rows:
            try:
                repo = row.get("repository") or {}
                # gh returns repository as either {"nameWithOwner": "o/r"} or
                # {"name": "r", "owner": {"login": "o"}} depending on the
                # field set — we accept both.
                slug = repo.get("nameWithOwner") or _slug_from_legacy(repo)
                number = int(row["number"])
            except (KeyError, TypeError, ValueError) as e:
                raise GitHubApiError(
                    f"gh search issues row malformed: {row!r}"
                ) from e
            issue_id = f"{slug}#{number}"
            # Resolving the parent requires a separate ``sub-issue`` REST
            # round-trip; queue-discovery callers fill it in lazily via
            # ``get_parent``. Leave blank here to keep the search call O(1).
            out.append(SubIssueRef(id=issue_id, parent_id=""))
        return out

    # ------------------------------------------------------------------
    # Parent resolution
    # ------------------------------------------------------------------

    def get_parent(self, child_id: str) -> ParentRef:
        """Resolve the parent of ``child_id`` via the sub-issue REST surface.

        GitHub's native sub-issue API exposes the parent on the child
        issue's payload (``GET /repos/{owner}/{repo}/issues/{N}`` includes
        a ``sub_issues_summary`` and ``parent`` field when the issue is
        attached as a sub-issue). The CLI ``gh issue view`` does not
        surface this field by default, so we shell ``gh api`` and parse.
        """
        coords = _parse_issue_id(child_id)
        payload = self._gh_api_get(
            f"/repos/{coords.owner}/{coords.repo}/issues/{coords.number}"
        )
        parent = payload.get("parent") or payload.get("sub_issue_parent")
        if not parent:
            raise GitHubApiError(
                f"get_parent: {child_id} has no parent sub-issue link"
            )
        try:
            parent_number = int(parent["number"])
            parent_title = str(parent.get("title", ""))
            # The parent may live in a different repository — fall back to
            # the child's repo coordinates only if the parent payload
            # omits its own repository reference.
            parent_repo = parent.get("repository") or {}
            slug = parent_repo.get("nameWithOwner") or coords.slug
        except (KeyError, TypeError, ValueError) as e:
            raise GitHubApiError(
                f"get_parent: malformed parent payload for {child_id}: {parent!r}"
            ) from e
        return ParentRef(
            id=f"{slug}#{parent_number}",
            backend="github",
            title=parent_title,
        )

    # ------------------------------------------------------------------
    # Phase transitions (ADR-0002 / ADR-0004)
    # ------------------------------------------------------------------

    def start_designing(self, child_id: str) -> None:
        self.transition_phase(child_id, PHASE_DESIGNING)

    def start_developing(self, child_id: str) -> None:
        self.transition_phase(child_id, PHASE_DEVELOPING)

    def request_cr_merge(self, child_id: str) -> None:
        self.transition_phase(child_id, PHASE_CR_MERGE)

    def revert_to_pending(self, child_id: str) -> None:
        self.transition_phase(child_id, PHASE_PENDING)

    def transition_phase(self, issue_id: str, target_label: str) -> None:
        """Single entrypoint for phase changes.

        Wire shape per ADR-0004: one ``gh issue edit`` (remove every
        ``afk:*`` label, add ``target_label``), then ``gh issue view --json
        labels`` to verify. Up to ``len(self._backoff_ms)`` attempts; on
        exhaustion, post an abort comment and raise
        ``PhaseTransitionError``.
        """
        if target_label not in ALL_PHASE_LABELS:
            raise ValueError(
                f"transition_phase: unknown target label {target_label!r}; "
                f"expected one of {ALL_PHASE_LABELS}"
            )
        coords = _parse_issue_id(issue_id)
        remove_csv = ",".join(ALL_PHASE_LABELS)
        last_err: Optional[BaseException] = None
        for attempt, delay_ms in enumerate(self._backoff_ms, start=1):
            if delay_ms > 0:
                self._sleep(delay_ms / 1000.0)
            try:
                self._gh_issue_edit_swap(coords, remove_csv, target_label)
                self._verify_label(coords, target_label)
                return
            except (GitHubLabelMismatch, GitHubApiError) as e:
                last_err = e
                continue
        # Retries exhausted — post abort comment, raise typed error.
        try:
            self._post_abort_comment(coords)
        except GitHubApiError:
            # Abort comment is best-effort; the typed error below is the
            # canonical failure signal to the runner.
            pass
        raise PhaseTransitionError(
            f"phase transition to {target_label!r} on {issue_id} failed after "
            f"{len(self._backoff_ms)} attempts: {last_err}"
        )

    def _gh_issue_edit_swap(
        self, coords: _IssueCoords, remove_csv: str, add_label: str
    ) -> None:
        """Single ``gh issue edit`` invocation — both ``--remove-label`` and
        ``--add-label`` in the same call (ADR-0002 atomicity guarantee).
        """
        proc = self._run([
            "issue", "edit", str(coords.number),
            "--repo", coords.slug,
            "--remove-label", remove_csv,
            "--add-label", add_label,
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue edit {coords.ref} failed: {proc.stderr.strip()}"
            )

    def _verify_label(
        self, coords: _IssueCoords, target_label: str
    ) -> None:
        """Read back the labels and assert exactly one ``afk:*`` label is
        attached, equal to ``target_label``. Mismatch raises
        ``GitHubLabelMismatch`` so the caller can retry.
        """
        proc = self._run([
            "issue", "view", str(coords.number),
            "--repo", coords.slug,
            "--json", "labels",
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue view {coords.ref} failed: {proc.stderr.strip()}"
            )
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise GitHubApiError(
                f"gh issue view {coords.ref} non-JSON: {proc.stdout[:200]}"
            ) from e
        labels = payload.get("labels") or []
        names = {l.get("name") for l in labels if isinstance(l, dict)}
        afk_labels = {n for n in names if n and n.startswith("afk:")}
        if afk_labels != {target_label}:
            raise GitHubLabelMismatch(
                f"{coords.ref}: expected afk labels {{{target_label!r}}}, "
                f"got {sorted(afk_labels)!r}"
            )

    def _post_abort_comment(self, coords: _IssueCoords) -> None:
        """Post the canonical abort message (ADR-0004 §sequenceDiagram).

        Bypasses the comment-dedup path on purpose — the abort message is
        an audit-trail signal; replaying after a retried mismatch should
        still leave evidence on the issue.
        """
        proc = self._run([
            "issue", "comment", str(coords.number),
            "--repo", coords.slug,
            "--body", "AFK: phase transition failed; aborting",
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue comment {coords.ref} failed: {proc.stderr.strip()}"
            )

    # ------------------------------------------------------------------
    # Terminal close
    # ------------------------------------------------------------------

    def close(self, child_id: str, reason: str) -> None:
        """Close the sub-issue via ``gh issue close`` with the matching
        ``--reason`` flag. GitHub accepts ``completed`` and ``not planned``
        (note the space) — we normalise both AFK-side spellings.
        """
        coords = _parse_issue_id(child_id)
        gh_reason = "not planned" if reason in ("not_planned", "not planned") else "completed"
        proc = self._run([
            "issue", "close", str(coords.number),
            "--repo", coords.slug,
            "--reason", gh_reason,
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue close {coords.ref} failed: {proc.stderr.strip()}"
            )

    # ------------------------------------------------------------------
    # Comment posting (with content-hash dedup — SDD §5 idempotency)
    # ------------------------------------------------------------------

    def comment(self, child_id: str, body: str) -> None:
        """Post a comment on ``child_id`` unless an identical body already
        exists on the issue (content-hash dedup window per SDD §5).
        """
        coords = _parse_issue_id(child_id)
        if self._issue_already_has_comment(coords, body):
            return
        proc = self._run([
            "issue", "comment", str(coords.number),
            "--repo", coords.slug,
            "--body", body,
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue comment {coords.ref} failed: {proc.stderr.strip()}"
            )

    def _issue_already_has_comment(self, coords: _IssueCoords, body: str) -> bool:
        """Return True iff one of the issue's existing comment bodies hashes
        equal to ``body``'s hash. Uses ``gh api`` (the CLI ``gh issue view
        --comments`` flag exists but its JSON projection varies across
        ``gh`` versions; the raw REST surface is stable).
        """
        target_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        try:
            comments = self._gh_api_get(
                f"/repos/{coords.owner}/{coords.repo}/issues/{coords.number}/comments"
            )
        except GitHubApiError:
            # If we can't list comments we'd rather double-post than drop
            # the message — comments are observability, not correctness.
            return False
        if not isinstance(comments, list):
            return False
        for c in comments:
            existing = c.get("body", "") if isinstance(c, dict) else ""
            if hashlib.sha256(existing.encode("utf-8")).hexdigest() == target_hash:
                return True
        return False

    # ------------------------------------------------------------------
    # Parent-side splices (Implementation Notes block — section_splice)
    # ------------------------------------------------------------------

    def splice_notes_block(self, parent_id: str, body: str) -> None:
        """Idempotently replace the parent's ``<!-- afk:notes:* -->`` block
        with ``body``. Reads the current body, splices, writes back only if
        the body actually changed.
        """
        coords = _parse_issue_id(parent_id)
        payload = self._gh_api_get(
            f"/repos/{coords.owner}/{coords.repo}/issues/{coords.number}"
        )
        existing_body = str(payload.get("body") or "")
        new_body = splice_marker_block(
            existing_body,
            body,
            marker_id=_NOTES_MARKER_ID,
            create_if_missing=True,
        )
        if new_body == existing_body:
            return
        proc = self._run([
            "issue", "edit", str(coords.number),
            "--repo", coords.slug,
            "--body", new_body,
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue edit {coords.ref} (notes splice) failed: "
                f"{proc.stderr.strip()}"
            )

    # ------------------------------------------------------------------
    # Target-branch resolution
    # ------------------------------------------------------------------

    def get_target_branch(self, parent_id: str) -> str:
        """Read the ``target:{branch}`` label on the parent issue; fall back
        to the repo's default branch when none is present (PRD §"GitHub
        data model").
        """
        coords = _parse_issue_id(parent_id)
        proc = self._run([
            "issue", "view", str(coords.number),
            "--repo", coords.slug,
            "--json", "labels",
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh issue view {coords.ref} failed: {proc.stderr.strip()}"
            )
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise GitHubApiError(
                f"gh issue view {coords.ref} non-JSON: {proc.stdout[:200]}"
            ) from e
        for raw in payload.get("labels") or []:
            name = raw.get("name", "") if isinstance(raw, dict) else ""
            if name.startswith("target:"):
                return name[len("target:") :]
        # Fallback — repo default branch
        return self._get_default_branch(coords)

    def _get_default_branch(self, coords: _IssueCoords) -> str:
        """``gh repo view --json defaultBranchRef`` → ``"main"`` (typical)."""
        proc = self._run([
            "repo", "view", coords.slug,
            "--json", "defaultBranchRef",
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh repo view {coords.slug} failed: {proc.stderr.strip()}"
            )
        try:
            payload = json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise GitHubApiError(
                f"gh repo view {coords.slug} non-JSON: {proc.stdout[:200]}"
            ) from e
        ref = payload.get("defaultBranchRef") or {}
        return str(ref.get("name") or "")

    # ------------------------------------------------------------------
    # Native sub-issue endpoints (REST via ``gh api``)
    # ------------------------------------------------------------------

    def list_sub_issues(self, parent_id: str) -> list[SubIssueRef]:
        """``GET /repos/{o}/{r}/issues/{N}/sub_issues`` — used by
        ``prd-to-subtasks`` to search-before-create (SDD §5 idempotency
        row "Sub-issue create").
        """
        coords = _parse_issue_id(parent_id)
        rows = self._gh_api_get(
            f"/repos/{coords.owner}/{coords.repo}/issues/{coords.number}/sub_issues"
        )
        if not isinstance(rows, list):
            raise GitHubApiError(
                f"list_sub_issues: expected JSON array, got {type(rows).__name__}"
            )
        out: list[SubIssueRef] = []
        for row in rows:
            if not isinstance(row, dict):
                raise GitHubApiError(
                    f"list_sub_issues: row not an object: {row!r}"
                )
            try:
                number = int(row["number"])
            except (KeyError, TypeError, ValueError) as e:
                raise GitHubApiError(
                    f"list_sub_issues: malformed row: {row!r}"
                ) from e
            repo = row.get("repository") or {}
            slug = repo.get("nameWithOwner") or _slug_from_legacy(repo) or coords.slug
            out.append(SubIssueRef(id=f"{slug}#{number}", parent_id=parent_id))
        return out

    def attach_sub_issue(self, parent_id: str, child_id: str) -> None:
        """``POST /repos/{o}/{r}/issues/{N}/sub_issues`` body
        ``{"sub_issue_id": M}``. 201 verified before return.
        """
        parent = _parse_issue_id(parent_id)
        child = _parse_issue_id(child_id)
        # The sub-issue REST endpoint expects the *internal* issue id
        # (the numeric ``id`` field, not the human ``number``). Caller
        # passes the human coordinate; we resolve the id with a single
        # extra GET.
        child_payload = self._gh_api_get(
            f"/repos/{child.owner}/{child.repo}/issues/{child.number}"
        )
        try:
            sub_issue_id = int(child_payload["id"])
        except (KeyError, TypeError, ValueError) as e:
            raise GitHubApiError(
                f"attach_sub_issue: cannot resolve numeric id for {child_id}"
            ) from e
        proc = self._run([
            "api",
            "-X", "POST",
            f"/repos/{parent.owner}/{parent.repo}/issues/{parent.number}/sub_issues",
            "-f", f"sub_issue_id={sub_issue_id}",
        ])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh api POST .../sub_issues {parent.ref} <- {child.ref} "
                f"failed: {proc.stderr.strip()}"
            )

    def ensure_phase_labels(self, owner: str, repo: str) -> None:
        """Create the four ``afk:*`` phase labels and the ``afk-agents``
        gate label in ``owner/repo`` via ``gh label create --force``
        (idempotent; ``--force`` updates colour/description if the label
        already exists). Called by ``prd-to-subtasks`` once per target
        repo; cheap enough to re-run every time.
        """
        slug = f"{owner}/{repo}"
        specs: tuple[tuple[str, str, str], ...] = (
            (PHASE_PENDING,     "ededed", "AFK phase: pending pickup"),
            (PHASE_DESIGNING,   "fbca04", "AFK phase: designing"),
            (PHASE_DEVELOPING,  "0e8a16", "AFK phase: developing"),
            (PHASE_CR_MERGE,    "5319e7", "AFK phase: awaiting CR & merge"),
            (AFK_AGENTS_LABEL,  "1d76db", "AFK eligibility gate"),
        )
        for name, colour, desc in specs:
            proc = self._run([
                "label", "create", name,
                "--repo", slug,
                "--color", colour,
                "--description", desc,
                "--force",
            ])
            if proc.returncode != 0:
                raise GitHubApiError(
                    f"gh label create {name!r} on {slug} failed: "
                    f"{proc.stderr.strip()}"
                )

    # ------------------------------------------------------------------
    # gh api JSON helper
    # ------------------------------------------------------------------

    def _gh_api_get(self, path: str) -> object:
        """``gh api {path}`` → parsed JSON. Wraps non-zero exit and parse
        failures as ``GitHubApiError`` so callers don't deal with raw
        subprocess types.
        """
        proc = self._run(["api", path])
        if proc.returncode != 0:
            raise GitHubApiError(
                f"gh api GET {path} failed: {proc.stderr.strip()}"
            )
        try:
            return json.loads(proc.stdout) if proc.stdout.strip() else {}
        except json.JSONDecodeError as e:
            raise GitHubApiError(
                f"gh api GET {path} non-JSON: {proc.stdout[:200]}"
            ) from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug_from_legacy(repo: dict) -> Optional[str]:
    """Reconstruct ``owner/repo`` from the verbose repository shape that
    some ``gh`` projections emit (``{"owner": {"login": ...}, "name": ...}``).
    Returns ``None`` if either field is missing.
    """
    owner = repo.get("owner") or {}
    login = owner.get("login") if isinstance(owner, dict) else None
    name = repo.get("name")
    if login and name:
        return f"{login}/{name}"
    return None


def splice_marker_block(
    description: str,
    block_body: str,
    *,
    marker_id: str,
    create_if_missing: bool = False,
) -> str:
    """HTML-comment marker-pair splicer — same semantics as the GitLab
    splicer in ``gitlab_client``. Duplicated here to avoid a cross-adapter
    import; the body is identical and ``section_splice`` exposes the
    marker-id helper but not the splicer (each format owns its own —
    Jira's lives in ``jira_section`` for ADF; GitLab's in ``gitlab_client``
    for MR markdown; this one mirrors the latter for issue bodies).
    """
    start_id, end_id = marker_id_text(marker_id)
    start_marker = f"<!-- {start_id} -->"
    end_marker = f"<!-- {end_id} -->"
    new_block = (
        f"{start_marker}\n{block_body}\n{end_marker}"
        if block_body
        else f"{start_marker}\n{end_marker}"
    )
    start = description.find(start_marker)
    end = description.find(end_marker)
    if start == -1 and end == -1:
        if not create_if_missing:
            raise SectionMarkerMissing(
                f"marker pair {marker_id!r} absent (create_if_missing=False)"
            )
        sep = "\n\n" if description and not description.endswith("\n\n") else ""
        return description + sep + new_block + "\n"
    if start == -1 or end == -1 or end < start:
        raise SectionMarkerMissing(
            f"marker pair {marker_id!r} malformed "
            f"(start={start} end={end})"
        )
    end_full = end + len(end_marker)
    return description[:start] + new_block + description[end_full:]

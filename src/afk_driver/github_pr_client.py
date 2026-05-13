"""GitHub Draft PR client via the ``gh`` CLI (ST05).

Implements the cross-backend ``Scm`` Protocol (``src/afk_driver/scm_protocol.py``)
for the GitHub adapter ring. All operations shell out to ``gh`` through an
injected ``GhRunner`` callable so tests can stub command outputs
deterministically — mirrors the ``GlabRunner`` (``gitlab_client``) and
``GhRunner`` (``github_issues_client``, ``repo_clone_manager``) pattern.

No HTTP libraries are imported here (ADR-0001 — driver-side path is ``gh``
CLI only). Subprocess discipline matches ``github_issues_client``:

* exit non-zero / non-JSON output → ``GitHubPrError`` with stderr context;
* ``find_open_pr_by_branch`` returns ``None`` for the empty-result case
  rather than raising — the call shape is "look first, decide later";
* ``find_open_pr_by_parent`` re-applies the title-substring filter
  client-side (``gh pr list --search`` matches description too, so a
  body-only mention of ``[#N]`` would otherwise be a false positive — see
  SDD §5 idempotency row "Find PR by parent issue"); >1 match raises
  rather than guessing.

Idempotency (SDD §5 idempotency row "PR create"): ``open_draft_pr`` calls
``find_open_pr_by_branch`` first; if a PR exists for the source branch it
is returned unchanged, preventing a duplicate ``gh pr create --draft``.
The body is rendered to contain ``Closes #{parent_issue_number}`` on
first open so the parent issue auto-closes when the human merges the PR
(PRD §"How are GitHub issues closed when work completes").

The body splice path mirrors ``gitlab_client.splice_pr_block``: read the
existing PR body, ``splice_marker_block(...)`` between the
``<!-- afk:subtasks:* -->`` marker pair, and re-issue
``gh pr edit --body`` only if the body actually changed.

``splice_marker_block`` is duplicated locally rather than imported from
``gitlab_client`` (or ``github_issues_client``) — both upstream modules
duplicate it for the same reason: each adapter owns its own marker-pair
splicer (Jira's lives in ``jira_section`` for ADF; GitLab's in
``gitlab_client``; GitHub-issues' in ``github_issues_client``; this one
mirrors them for GitHub PR markdown). Cross-adapter imports would couple
SCM/issue layers needlessly. See SDD §8 row "section_splice (existing,
unchanged)".
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from afk_driver.scm_protocol import PrRef, Scm
from afk_driver.section_splice import SectionMarkerMissing, marker_id_text


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

# Marker id for the auto-maintained subtasks/Closes block in the PR body.
_SUBTASKS_MARKER_ID = "subtasks"

# ``gh pr edit --body`` retry budget per SDD §5 retry table — 2 attempts,
# 0/500 ms backoff. ``gh pr create --draft`` is a single attempt; on failure
# we re-query for an existing PR and surface the error if still absent
# (SDD §5 retry table row "gh pr create --draft").
_EDIT_BACKOFF_MS: tuple[int, ...] = (0, 500)


GhRunner = Callable[[list[str]], subprocess.CompletedProcess]
SleepFn = Callable[[float], None]


def default_runner(args: list[str]) -> subprocess.CompletedProcess:
    """Default runner — shells out to the host's ``gh`` CLI.

    Matches the convention from ``github_issues_client.default_runner``:
    the runner prepends ``gh`` itself so call sites pass only subcommand
    arguments.
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


class GitHubPrError(RuntimeError):
    """Raised when a ``gh pr ...`` invocation exits non-zero or returns
    unparseable JSON. Carries the stderr / stdout context so the digest
    writer can surface it without re-shelling.
    """


# ---------------------------------------------------------------------------
# Internal value records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PRInfo:
    """Parsed ``gh pr view`` / ``gh pr list`` row. Kept module-internal —
    public consumers see the cross-backend ``PrRef`` (SDD §6 erDiagram
    ``DraftPullRequest``).
    """

    number: int
    url: str
    state: str
    title: str
    body: str
    head_ref_name: str
    base_ref_name: str
    is_draft: bool


@dataclass(frozen=True)
class OpenDraftPrSpec:
    """Adapter-specific request record consumed by ``Scm.open_draft_pr``
    (SDD §9 Strategy classDiagram). Keeps the cross-backend Protocol module
    free of GitHub-specific fields while pinning the inputs
    ``GitHubPrClient`` needs to call ``gh pr create``.

    ``parent_issue_number`` is the GitHub-side parent (the AFK Parent
    issue's number on the same repo); inserted into the body as
    ``Closes #{parent_issue_number}`` so the human's merge auto-closes the
    issue tree (PRD §"How are GitHub issues closed when work completes").

    ``repo`` is the canonical ``owner/repo`` slug. ``gh pr ...`` requires
    a ``--repo`` flag when invoked outside a repo working tree, and the
    AFK driver shells from the driver's CWD (the worktree) — passing it
    explicitly keeps the call portable.
    """

    repo: str
    source_branch: str
    target_branch: str
    title: str
    body: str
    parent_issue_number: int


# ---------------------------------------------------------------------------
# JSON projection fields requested from ``gh``
# ---------------------------------------------------------------------------

# Single source of truth for the ``--json`` projection so view/list calls
# agree on field shape. ``isDraft`` distinguishes Draft from Ready PRs;
# ``state`` is OPEN/CLOSED/MERGED.
_PR_JSON_FIELDS = "number,url,state,title,body,headRefName,baseRefName,isDraft"


# ---------------------------------------------------------------------------
# Implementation
# ---------------------------------------------------------------------------


class GitHubPrClient(Scm):
    """GitHub-side ``Scm`` Protocol implementation.

    See module docstring + SDD §8 row ``github_pr_client``. ``runner`` is
    injected (``GhRunner``); ``sleep`` is injected (``SleepFn``) so the
    ``gh pr edit`` retry backoff is testable without real wall-clock
    waits.

    Explicit Protocol nominal subtype (``Scm``) — matches the ST02
    pattern on ``GitLabClient``.
    """

    def __init__(
        self,
        runner: GhRunner = default_runner,
        *,
        sleep: SleepFn = __import__("time").sleep,
        edit_backoff_ms: Sequence[int] = _EDIT_BACKOFF_MS,
    ) -> None:
        self._run = runner
        self._sleep = sleep
        self._edit_backoff_ms: tuple[int, ...] = tuple(edit_backoff_ms)
        if len(self._edit_backoff_ms) < 1:
            raise ValueError("edit_backoff_ms must declare at least one attempt")

    # ------------------------------------------------------------------
    # Find paths
    # ------------------------------------------------------------------

    def find_open_pr_by_branch(self, repo: str, branch: str) -> Optional[PRInfo]:
        """Return the single open PR whose head ref is ``branch``, or
        ``None`` if no open PR exists. Idempotency anchor for
        ``open_draft_pr`` (SDD §5 idempotency row "PR create").

        ``gh pr list --head {branch} --state open`` returns ≥0 PRs; we
        accept 0 (None) or 1 (the PR). >1 is theoretically impossible on
        GitHub (one open PR per head branch per repo) but we surface it
        as ``GitHubPrError`` rather than silently picking — matching
        ``find_open_pr_by_parent``'s ambiguity stance.
        """
        proc = self._run([
            "pr", "list",
            "--repo", repo,
            "--head", branch,
            "--state", "open",
            "--json", _PR_JSON_FIELDS,
            "--limit", "10",
        ])
        if proc.returncode != 0:
            raise GitHubPrError(
                f"gh pr list --head {branch} on {repo} failed: "
                f"{proc.stderr.strip()}"
            )
        rows = _parse_json_array(proc.stdout, "gh pr list --head")
        if not rows:
            return None
        if len(rows) > 1:
            numbers = sorted(int(r.get("number", 0)) for r in rows)
            raise GitHubPrError(
                f"unexpected: {len(rows)} open PRs on {repo} for head {branch} "
                f"(numbers={numbers}); refusing to pick one"
            )
        return _parse_pr(rows[0])

    def find_open_pr_by_parent_number(
        self, repo: str, parent_issue_number: int
    ) -> Optional[PRInfo]:
        """Look up the open PR whose title references the parent issue by
        the ``[#{N}]`` prefix convention. Used by the runner for PR
        discovery when the human opened the PR by hand against a
        non-template source branch.

        ``--search`` matches both title and description, so we re-apply
        the title-contains filter client-side to avoid false positives
        from descriptions that merely mention the parent issue.

        Returns ``None`` for zero matches. Raises ``GitHubPrError`` for
        >1 to force the runner to skip the parent rather than guess
        (SDD §5 idempotency row "Find PR by parent issue").
        """
        token = f"[#{parent_issue_number}]"
        proc = self._run([
            "pr", "list",
            "--repo", repo,
            "--search", token,
            "--state", "open",
            "--json", _PR_JSON_FIELDS,
            "--limit", "100",
        ])
        if proc.returncode != 0:
            raise GitHubPrError(
                f"gh pr list --search {token!r} on {repo} failed: "
                f"{proc.stderr.strip()}"
            )
        rows = _parse_json_array(proc.stdout, "gh pr list --search")
        matches = [r for r in rows if token in str(r.get("title", ""))]
        if not matches:
            return None
        if len(matches) > 1:
            numbers = sorted(int(r.get("number", 0)) for r in matches)
            raise GitHubPrError(
                f"ambiguous: {len(matches)} open PRs match parent {token} on "
                f"{repo} (numbers={numbers}); refusing to pick one"
            )
        return _parse_pr(matches[0])

    # ------------------------------------------------------------------
    # Open
    # ------------------------------------------------------------------

    def open_draft_pr_from_spec(self, spec: OpenDraftPrSpec) -> PRInfo:
        """Open a Draft PR matching ``spec``. Idempotent: re-query by
        head branch first; if an open PR exists, return it instead of
        creating a duplicate.

        Body is rendered to embed ``Closes #{spec.parent_issue_number}``
        before the auto-maintained subtasks block so the human's merge
        of the PR auto-closes the parent issue (PRD §"How are GitHub
        issues closed when work completes"). The Closes line stays inside
        the marker block so subsequent ``splice_pr_block`` calls can
        re-render the full block (Closes lines + sub-issue checklist) as
        one canonical write.

        Returns the ``PRInfo`` of the live PR (existing or newly created).
        """
        existing = self.find_open_pr_by_branch(spec.repo, spec.source_branch)
        if existing is not None:
            return existing
        rendered_body = _render_initial_body(spec)
        proc = self._run([
            "pr", "create",
            "--repo", spec.repo,
            "--draft",
            "--base", spec.target_branch,
            "--head", spec.source_branch,
            "--title", spec.title,
            "--body", rendered_body,
        ])
        if proc.returncode != 0:
            # Per SDD §5 retry table row "gh pr create --draft": single
            # attempt; on failure, re-query for existing PR. If still
            # absent, surface the failure.
            existing = self.find_open_pr_by_branch(spec.repo, spec.source_branch)
            if existing is not None:
                return existing
            raise GitHubPrError(
                f"gh pr create on {spec.repo} for head {spec.source_branch} "
                f"failed: {proc.stderr.strip()}"
            )
        # gh pr create stdout shape varies across versions; canonical view
        # is via re-query against the head branch.
        pr = self.find_open_pr_by_branch(spec.repo, spec.source_branch)
        if pr is None:
            raise GitHubPrError(
                f"gh pr create on {spec.repo} succeeded but re-query for "
                f"head {spec.source_branch} returned None"
            )
        return pr

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_pr_description_for(
        self, repo: str, source_branch: str, body: str
    ) -> None:
        """Replace the PR body on ``source_branch`` with ``body`` in full.

        Used by the runner to write the rendered subtasks-checklist block
        on first PR open. Retries up to ``len(self._edit_backoff_ms)``
        times (SDD §5 retry table row "gh pr edit --body"); on
        exhaustion, raises ``GitHubPrError``.
        """
        last_err: Optional[BaseException] = None
        for delay_ms in self._edit_backoff_ms:
            if delay_ms > 0:
                self._sleep(delay_ms / 1000.0)
            proc = self._run([
                "pr", "edit", source_branch,
                "--repo", repo,
                "--body", body,
            ])
            if proc.returncode == 0:
                return
            last_err = GitHubPrError(
                f"gh pr edit {source_branch} on {repo} failed: "
                f"{proc.stderr.strip()}"
            )
        assert last_err is not None
        raise last_err

    # ------------------------------------------------------------------
    # Splice
    # ------------------------------------------------------------------

    def splice_pr_block_for(
        self, repo: str, source_branch: str, body: str
    ) -> None:
        """Idempotently replace the ``<!-- afk:subtasks:* -->`` block in
        the PR body with ``body`` (pre-rendered). Read–splice–write
        only if the body actually changed — matches
        ``gitlab_client.splice_pr_block``'s no-op-on-no-change discipline.
        """
        existing = self.find_open_pr_by_branch(repo, source_branch)
        if existing is None:
            raise GitHubPrError(
                f"no open PR for head {source_branch} on {repo}"
            )
        new_body = splice_marker_block(
            existing.body,
            body,
            marker_id=_SUBTASKS_MARKER_ID,
            create_if_missing=True,
        )
        if new_body == existing.body:
            return
        self.update_pr_description_for(repo, source_branch, new_body)

    # ------------------------------------------------------------------
    # Scm Protocol conformance (Protocol uses (branch, body) sigs only —
    # the GitHub adapter needs ``repo`` too; the runner passes it via the
    # spec on the open path, and via the legacy ``find_*_for`` wrappers on
    # the splice/update paths. To satisfy the Protocol's two-arg shape
    # without coupling the Protocol module to GitHub coordinates, the
    # adapter stashes ``last_open_repo`` on first ``open_draft_pr`` call
    # — same pattern the ST07 runner will adopt for cross-backend
    # dispatch.)
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        # Defensive — dataclasses-only hook; this class isn't a dataclass
        # but the no-op keeps subclasses safe if added later.
        pass

    def find_open_pr_by_parent(self, parent_id: str) -> PrRef | None:
        """Protocol method. ``parent_id`` is the AFK GitHub coordinate
        ``owner/repo#N`` (matching ``tracker_protocol.SubIssueRef``).
        Reduces to the cross-backend ``PrRef`` shape.
        """
        repo, number = _split_github_parent_id(parent_id)
        info = self.find_open_pr_by_parent_number(repo, number)
        return _pr_ref_from_info(info) if info is not None else None

    def open_draft_pr(self, spec: object) -> PrRef:
        """Protocol method. ``spec`` must be an ``OpenDraftPrSpec``
        declared in this module. Reduces the returned ``PRInfo`` to
        ``PrRef``; stashes ``(repo, source_branch)`` so subsequent
        Protocol-shape ``update_pr_description`` / ``splice_pr_block``
        calls (which only get the branch) can address the same PR.
        """
        if not isinstance(spec, OpenDraftPrSpec):
            raise TypeError(
                "GitHubPrClient.open_draft_pr requires an OpenDraftPrSpec; "
                f"got {type(spec).__name__}"
            )
        info = self.open_draft_pr_from_spec(spec)
        # Stash so the Protocol-shape update/splice methods can address
        # the same repo without re-plumbing the signature.
        self._last_open: tuple[str, str] = (spec.repo, spec.source_branch)
        return _pr_ref_from_info(info)

    def update_pr_description(self, branch: str, body: str) -> None:
        """Protocol method. Replaces the PR body for ``branch`` with
        ``body`` in full. Requires a prior ``open_draft_pr`` so the
        adapter knows which repo the branch belongs to (the Protocol's
        two-arg shape doesn't carry repo coordinates).
        """
        repo = self._repo_for_branch(branch)
        self.update_pr_description_for(repo, branch, body)

    def splice_pr_block(self, branch: str, body: str) -> None:
        """Protocol method. Idempotently splices ``body`` between the
        ``afk:subtasks`` markers in the PR body for ``branch``.
        """
        repo = self._repo_for_branch(branch)
        self.splice_pr_block_for(repo, branch, body)

    def _repo_for_branch(self, branch: str) -> str:
        last = getattr(self, "_last_open", None)
        if last is None or last[1] != branch:
            raise GitHubPrError(
                f"no recorded repo for branch {branch!r}; call "
                f"open_draft_pr(OpenDraftPrSpec) first or use the "
                f"*_for(repo, branch, ...) variants"
            )
        return last[0]


# ---------------------------------------------------------------------------
# Body rendering
# ---------------------------------------------------------------------------


def _render_initial_body(spec: OpenDraftPrSpec) -> str:
    """Render the initial PR body. The author-supplied ``spec.body``
    becomes the human-prose preamble; below it sits the auto-maintained
    marker block holding the ``Closes #{N}`` line for the parent issue.

    Subsequent ``splice_pr_block`` calls overwrite the block contents
    (adding ``Closes #{sub}`` lines for each landed sub-issue + the
    checklist) while leaving the preamble byte-identical.
    """
    start_id, end_id = marker_id_text(_SUBTASKS_MARKER_ID)
    closes_line = f"Closes #{spec.parent_issue_number}"
    marker_block = (
        f"<!-- {start_id} -->\n{closes_line}\n<!-- {end_id} -->"
    )
    preamble = spec.body.rstrip("\n")
    if preamble:
        return f"{preamble}\n\n{marker_block}\n"
    return f"{marker_block}\n"


# ---------------------------------------------------------------------------
# JSON / payload helpers
# ---------------------------------------------------------------------------


def _parse_json_array(stdout: str, ctx: str) -> list[dict]:
    """Parse ``gh``'s JSON-array stdout; raise typed error on shape drift."""
    try:
        data = json.loads(stdout) if stdout.strip() else []
    except json.JSONDecodeError as e:
        raise GitHubPrError(
            f"{ctx} returned non-JSON: {stdout[:200]}"
        ) from e
    if not isinstance(data, list):
        raise GitHubPrError(
            f"{ctx} expected JSON array, got {type(data).__name__}"
        )
    return data


def _parse_pr(row: dict) -> PRInfo:
    """Reduce a single ``gh pr list`` / ``gh pr view`` JSON row to
    ``PRInfo``. Permissive on missing fields — older ``gh`` versions
    omit ``isDraft`` from list projections."""
    return PRInfo(
        number=int(row.get("number", 0)),
        url=str(row.get("url", "")),
        state=str(row.get("state", "")),
        title=str(row.get("title", "")),
        body=str(row.get("body") or ""),
        head_ref_name=str(row.get("headRefName", "")),
        base_ref_name=str(row.get("baseRefName", "")),
        is_draft=bool(row.get("isDraft", False)),
    )


def _pr_ref_from_info(info: PRInfo) -> PrRef:
    """Reduce a ``PRInfo`` to the cross-backend ``PrRef`` shape
    (SDD §6 erDiagram ``DraftPullRequest``)."""
    return PrRef(
        source_branch=info.head_ref_name,
        target_branch=info.base_ref_name,
        url=info.url,
    )


def _split_github_parent_id(parent_id: str) -> tuple[str, int]:
    """Parse ``owner/repo#N`` into ``("owner/repo", N)``.

    Refuses to guess on malformed input; matches
    ``github_issues_client._parse_issue_id`` strictness.
    """
    if "#" not in parent_id:
        raise GitHubPrError(
            f"github parent id must be 'owner/repo#N', got {parent_id!r}"
        )
    left, _, num_s = parent_id.rpartition("#")
    if "/" not in left:
        raise GitHubPrError(
            f"github parent id must be 'owner/repo#N', got {parent_id!r}"
        )
    try:
        number = int(num_s)
    except ValueError as e:
        raise GitHubPrError(
            f"github parent id number not an int: {parent_id!r}"
        ) from e
    return left, number


# ---------------------------------------------------------------------------
# Marker-block splicer (duplicated from gitlab_client / github_issues_client
# per the per-adapter convention — see module docstring).
# ---------------------------------------------------------------------------


def splice_marker_block(
    description: str,
    block_body: str,
    *,
    marker_id: str,
    create_if_missing: bool = False,
) -> str:
    """HTML-comment marker-pair splicer — same semantics as the GitLab
    splicer in ``gitlab_client`` and the GitHub-issues splicer in
    ``github_issues_client``. Duplicated here to avoid cross-adapter
    imports; the body is identical.

    Behaviour:
    - Both markers present, in order: returns ``before + new_block + after``
      with ``before`` and ``after`` (everything outside the markers)
      preserved byte-identical.
    - Both markers absent: if ``create_if_missing=True``, appends a fresh
      marker block at the end of the description (separated by a blank
      line if the existing description doesn't already end with
      ``\\n\\n``). Otherwise raises ``SectionMarkerMissing``.
    - One marker present without its mate, or end before start: raises
      ``SectionMarkerMissing`` even when ``create_if_missing=True``.
      Corrupt state — auto-repair would risk losing whatever the
      survivor anchors.
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

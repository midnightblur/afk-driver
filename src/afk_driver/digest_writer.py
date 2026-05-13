"""L4 morning digest formatter.

Pure function: ``format_digest(record) -> str`` produces the markdown the user
reads first thing in the morning.

ST09 (github-backend) extensions:

* Per-parent rollup gains ``Backend`` + ``Repo`` columns whenever the record
  contains at least one GitHub-shaped parent (parent key matching
  ``owner/repo#N``). Pure-Jira records render byte-identical to the pre-ST09
  template per PRD §"Backend abstraction" — "byte-for-byte unchanged".
* Per-sub-issue rows render the issue id verbatim (``P2P-1234`` on Jira,
  ``owner/repo#42`` on GitHub) — both shapes already live in
  ``SubTaskRun.key`` (PRD §"Observability" — User Story 41).
* MR/PR URLs render as clickable Markdown (``[#42](https://...)``) when the
  URL maps to a parseable PR/MR coordinate; otherwise the raw URL is kept.
* The sweeper-warnings block (ST08's ``SweepWarning``) is prepended above the
  per-parent rollup when ``warnings`` is non-empty (SDD §5 observability
  table row "Sweeper warning bullets in digest"). Empty list → block omitted.
"""

from __future__ import annotations

import re
from typing import Sequence

from afk_driver.runner import ParentRun, RepoFailed, RunRecord, SubTaskRun


# ``owner/repo#N`` shape used as the GitHub parent / sub-issue key — see
# ``tracker_protocol.SubIssueRef`` docstring. Same regex also validates
# GitHub PR URLs of the form ``https://github.com/owner/repo/pull/N``.
_GH_KEY_RE = re.compile(r"^(?P<repo>[^/\s]+/[^/\s#]+)#(?P<num>\d+)$")
_GH_PR_URL_RE = re.compile(
    r"^https?://github\.com/(?P<repo>[^/\s]+/[^/\s]+)/pull/(?P<num>\d+)/?$"
)
# GitLab MR shape: ``https://example.com/group/proj/-/merge_requests/N``.
_GL_MR_URL_RE = re.compile(
    r"^https?://[^/\s]+/.+?/-/merge_requests/(?P<num>\d+)/?$"
)


def format_digest(
    record: RunRecord,
    warnings: Sequence["SweepWarningLike"] = (),
) -> str:
    """Render the morning digest markdown.

    ``warnings`` is the sequence of ST08 ``SweepWarning`` records (kept as a
    structural type — anything with ``issue_id`` / ``action`` / ``error``
    attributes is accepted, so the digest writer does not have to import
    from ``cli.py`` and create a cycle).
    """
    out: list[str] = []
    out.extend(_render_sweeper_warnings(warnings))
    out.append("# AFK morning digest")
    out.append("")
    out.append(f"_Run: {record.started_iso} → {record.ended_iso}_")
    out.append("")
    if not record.parents and not record.repo_failures:
        out.append("No labelled SubTasks found.")
        return "\n".join(out) + "\n"
    success = sum(
        1 for p in record.parents for s in p.subtasks if s.status == "success"
    )
    aborted = sum(
        1 for p in record.parents for s in p.subtasks if s.status == "aborted"
    )
    skipped_parents = sum(1 for p in record.parents if p.skip_reason)
    flaky = sum(
        1 for p in record.parents for s in p.subtasks
        if s.status == "success" and s.flaky_suspect
    )
    flaky_note = f", {flaky} flaky-suspect" if flaky else ""
    out.append(
        f"**Summary:** {len(record.parents)} parent(s), "
        f"{success} SubTask(s) succeeded{flaky_note}, {aborted} aborted, "
        f"{skipped_parents} parent(s) skipped."
    )
    out.append("")
    # ST09 — record-level backend toggle. Any GitHub-shaped parent in the
    # record promotes every row to the extended Backend/Repo columns so a
    # mixed run renders consistently. Pure-Jira stays byte-identical with
    # the pre-ST09 template.
    show_backend_cols = any(_is_github_key(p.key) for p in record.parents)
    for parent in record.parents:
        out.extend(_render_parent(parent, show_backend_cols=show_backend_cols))
        out.append("")
    if record.repo_failures:
        out.extend(_render_repo_failures(record.repo_failures))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Sweeper warnings (ST09 takes ownership from cli.py's shim)
# ---------------------------------------------------------------------------


class SweepWarningLike:  # pragma: no cover - typing protocol stand-in
    """Structural type for sweeper warnings — see ``cli.SweepWarning``."""

    issue_id: str
    action: str
    error: str


def _render_sweeper_warnings(
    warnings: Sequence["SweepWarningLike"],
) -> list[str]:
    """Build the ``## Sweeper warnings`` prefix block.

    Returns an empty list when ``warnings`` is empty — the caller must NOT
    emit an empty section per the acceptance criterion in ST09's spec
    ("omit ... entirely rather than rendering an empty section").
    """
    if not warnings:
        return []
    lines = ["## Sweeper warnings", ""]
    for w in warnings:
        err = getattr(w, "error", "") or ""
        if err:
            lines.append(f"- `{w.issue_id}` — {w.action} ({err})")
        else:
            lines.append(f"- `{w.issue_id}` — {w.action}")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# Per-parent rendering
# ---------------------------------------------------------------------------


def _render_parent(parent: ParentRun, *, show_backend_cols: bool) -> list[str]:
    label = f"{parent.issuetype} " if parent.issuetype else ""
    lines = [f"## {label}{parent.key} — {parent.summary}"]
    if parent.skip_reason:
        lines.append(f"_skipped: {parent.skip_reason}_")
        return lines
    if show_backend_cols:
        lines.append(f"- Backend: `{_backend_of(parent)}`")
        lines.append(f"- Repo: `{_repo_of(parent)}`")
    lines.append(f"- Target branch: `{parent.target_branch}`")
    lines.append(f"- MR: {_format_mr_link(parent.mr_url) or '(none)'}")
    lines.append(f"- Duration: {parent.duration_s:.1f}s")
    if parent.rebase:
        lines.append(f"- Post-last-SubTask rebase: **{parent.rebase}**")
    lines.append("")
    lines.append("| SubTask | Status | Attempts | Detail |")
    lines.append("|---------|--------|----------|--------|")
    for s in parent.subtasks:
        lines.append(_subtask_row(s))
    return lines


def _subtask_row(s: SubTaskRun) -> str:
    detail = (s.detail or "").replace("|", r"\|")
    # S1 — append flaky-suspect tag to the status column so morning-digest
    # readers see it inline. The Jira comment carries the full framing;
    # here we just need a visual cue.
    status = f"{s.status} ⚠️ flaky-suspect" if s.flaky_suspect else s.status
    return f"| {s.key} | {status} | {s.attempts} | {detail} |"


# ---------------------------------------------------------------------------
# Per-repo failure rendering (ST07's RepoFailed surfaces here, ST09)
# ---------------------------------------------------------------------------


def _render_repo_failures(failures: Sequence[RepoFailed]) -> list[str]:
    """Render the per-repo skip block produced by the GitHub multi-repo
    outer loop (ADR-0003 flowchart ``skip_repo`` rung)."""
    lines = ["## Skipped repos", ""]
    for f in failures:
        coord = f"{f.owner}/{f.repo}" if f.owner and f.repo else f.backend
        reason = f.reason or "(no reason recorded)"
        lines.append(f"- `{coord}` — {reason}")
    return lines


# ---------------------------------------------------------------------------
# Key / URL helpers
# ---------------------------------------------------------------------------


def _is_github_key(key: str) -> bool:
    """True iff ``key`` matches the GitHub ``owner/repo#N`` shape."""
    return bool(_GH_KEY_RE.match(key or ""))


def _backend_of(parent: ParentRun) -> str:
    """Per-parent backend discriminator.

    Derives from the parent key shape: ``owner/repo#N`` → ``github``,
    anything else (typically ``PROJ-NNN``) → ``jira``. Keeps the digest
    writer decoupled from ``RunRecord.backend`` so a mixed-backend record
    (forward-compat) renders correctly row-by-row.
    """
    return "github" if _is_github_key(parent.key) else "jira"


def _repo_of(parent: ParentRun) -> str:
    """Per-parent repo coordinate.

    GitHub: ``owner/repo`` extracted from ``parent.key``. Jira: the project
    key extracted from ``PROJ-NNN`` (everything before the last ``-``).
    Empty string if neither shape matches (defensive — should not happen
    for any well-formed run record).
    """
    m = _GH_KEY_RE.match(parent.key or "")
    if m:
        return m.group("repo")
    if "-" in (parent.key or ""):
        return parent.key.rsplit("-", 1)[0]
    return ""


def _format_mr_link(url: str) -> str:
    """Render an MR/PR URL as a clickable Markdown link with ``#N`` / ``!N``
    label when the URL is a recognisable GitHub PR or GitLab MR. Falls back
    to the raw URL on no-match so unfamiliar SCMs (or future backends)
    still produce a useful digest line. Empty input → empty string.
    """
    if not url:
        return ""
    m = _GH_PR_URL_RE.match(url)
    if m:
        return f"[#{m.group('num')}]({url})"
    m = _GL_MR_URL_RE.match(url)
    if m:
        return f"[!{m.group('num')}]({url})"
    return url

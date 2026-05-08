"""L4 morning digest formatter.

Pure function: ``format_digest(record) -> str`` produces the markdown the user
reads first thing in the morning.
"""

from __future__ import annotations

from afk_driver.runner import ParentRun, RunRecord, SubTaskRun


def format_digest(record: RunRecord) -> str:
    out: list[str] = ["# AFK morning digest", ""]
    out.append(f"_Run: {record.started_iso} → {record.ended_iso}_")
    out.append("")
    if not record.parents:
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
    for parent in record.parents:
        out.extend(_render_parent(parent))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def _render_parent(parent: ParentRun) -> list[str]:
    label = f"{parent.issuetype} " if parent.issuetype else ""
    lines = [f"## {label}{parent.key} — {parent.summary}"]
    if parent.skip_reason:
        lines.append(f"_skipped: {parent.skip_reason}_")
        return lines
    lines.append(f"- Target branch: `{parent.target_branch}`")
    lines.append(f"- MR: {parent.mr_url or '(none)'}")
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

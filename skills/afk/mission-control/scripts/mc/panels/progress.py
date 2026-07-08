"""MC-1 Progress board — derived from `plan/PLAN.md`'s progress tracker
(PRD "Mission-control panels" row MC-1).
"""
from __future__ import annotations

import html
from pathlib import Path

from .. import mdtable
from ..vm import Absent, PanelVM

PANEL_ID = "progress"
PANEL_TITLE = "Progress board"


def parse(spec_dir: Path):
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return Absent(PANEL_ID, "plan/PLAN.md not found")

    text = plan_path.read_text(encoding="utf-8")
    section = mdtable.extract_section(text, "Progress tracker")
    if section is None:
        return Absent(PANEL_ID, "no '## Progress tracker' section in plan/PLAN.md")

    rows = mdtable.parse_table(section)
    if not rows:
        return Absent(PANEL_ID, "'## Progress tracker' section has no table rows")

    body = ['<table class="mc-table">', "<tr><th>Subtask</th><th>Title</th><th>Status</th></tr>"]
    for row in rows:
        subtask = html.escape(row.get("Subtask", "?"))
        title = html.escape(row.get("Title", ""))
        status = row.get("Status", "?")
        status_slug = html.escape(_status_slug(status))
        body.append(
            "<tr><td>{subtask}</td><td>{title}</td>"
            '<td class="mc-status mc-status-{slug}">{status}</td></tr>'.format(
                subtask=subtask, title=title, slug=status_slug, status=html.escape(status)
            )
        )
    body.append("</table>")
    return PanelVM(PANEL_ID, PANEL_TITLE, "\n".join(body))


def _status_slug(status: str) -> str:
    slug = "".join(ch if ch.isalnum() else "-" for ch in status.lower()).strip("-")
    return slug or "unknown"

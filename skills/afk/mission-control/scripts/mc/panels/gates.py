"""MC-5 Gates — derived from `plan/review/INDEX.md`, the smoke-gate table,
and the preflight step table, all inside `plan/PLAN.md` or its `review/`
subfolder (PRD "Mission-control panels" row MC-5).

The `## Preflight` table read here does not exist in any shipped plan yet —
0005-preflight-skill is the writer. Per ADR-0004's follow-up note, this
parser now *is* the lockstep source of truth for that table's shape until
0005 lands: one row per PF step, columns `# | Step | Status | Cycle |
Evidence`. 0005 must emit a `## Preflight` section in `plan/PLAN.md` matching
this shape (or this parser needs a matching lockstep update in the same
change).
"""
from __future__ import annotations

import html
from pathlib import Path

from .. import mdtable
from ..vm import Absent, PanelVM

PANEL_ID = "gates"
PANEL_TITLE = "Gates"

_SMOKE_COLUMNS = ["#", "Scenario (integrated)", "Modality", "Status"]
_PREFLIGHT_COLUMNS = ["#", "Step", "Status", "Cycle", "Evidence"]
_REVIEW_COLUMNS = ["Subtask", "Latest report", "Verdict", "crit/high/med/low", "Open advisories"]


def parse(spec_dir: Path):
    plan_path = spec_dir / "plan" / "PLAN.md"
    review_index_path = spec_dir / "plan" / "review" / "INDEX.md"

    smoke_rows: list = []
    preflight_rows: list = []
    if plan_path.is_file():
        text = plan_path.read_text(encoding="utf-8")
        smoke_section = mdtable.extract_section(text, "Feature smoke gate")
        if smoke_section is not None:
            smoke_rows = mdtable.parse_table(smoke_section)
        preflight_section = mdtable.extract_section(text, "Preflight")
        if preflight_section is not None:
            preflight_rows = mdtable.parse_table(preflight_section)

    review_rows: list = []
    if review_index_path.is_file():
        review_rows = mdtable.parse_table(review_index_path.read_text(encoding="utf-8"))

    if not smoke_rows and not preflight_rows and not review_rows:
        return Absent(
            PANEL_ID,
            "no gate sources found (plan/PLAN.md smoke gate table, "
            "'## Preflight' table, and plan/review/INDEX.md are all absent)",
        )

    body = [
        _render_group("Smoke gate", smoke_rows, _SMOKE_COLUMNS, "no '## Feature smoke gate' table in plan/PLAN.md"),
        _render_group(
            "Preflight",
            preflight_rows,
            _PREFLIGHT_COLUMNS,
            "no '## Preflight' table yet (built by 0005-preflight-skill)",
        ),
        _render_group("Review rollup", review_rows, _REVIEW_COLUMNS, "no plan/review/INDEX.md yet"),
    ]
    return PanelVM(PANEL_ID, PANEL_TITLE, "\n".join(body))


def _render_group(title: str, rows: list, columns: list, empty_reason: str) -> str:
    out = [f'<div class="mc-gate-group"><h3>{html.escape(title)}</h3>']
    if not rows:
        out.append(f'<div class="mc-empty-sub">{html.escape(empty_reason)}</div>')
    else:
        out.append('<table class="mc-table"><tr>' + "".join(f"<th>{html.escape(c)}</th>" for c in columns) + "</tr>")
        for row in rows:
            out.append("<tr>" + "".join(f"<td>{html.escape(row.get(c, ''))}</td>" for c in columns) + "</tr>")
        out.append("</table>")
    out.append("</div>")
    return "\n".join(out)

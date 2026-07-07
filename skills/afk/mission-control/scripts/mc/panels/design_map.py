"""MC-3 Design map — derived from the SDD's Mermaid diagrams, the plan's seam
register, and each subtask contract's `## Produces` / `## Consumes` anchors
(PRD "Mission-control panels" row MC-3).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from .. import mdtable
from ..vm import Absent, PanelVM

PANEL_ID = "design_map"
PANEL_TITLE = "Design map"

_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
_PRODUCES_RE = re.compile(r"^-\s+(?P<file>.+?)#`(?P<anchor>[^`]+)`\s*[—-]\s*(?P<desc>.*)$")
_CONSUMES_RE = re.compile(r"^-\s+(?P<producer>\S+)\s+(?P<file>.+?)#`(?P<anchor>[^`]+)`\s*[—-]\s*(?P<desc>.*)$")


def parse(spec_dir: Path):
    sdd_path = spec_dir / "SDD.md"
    if not sdd_path.is_file():
        return Absent(PANEL_ID, "SDD.md not found")

    sdd_text = sdd_path.read_text(encoding="utf-8")
    diagrams = _MERMAID_RE.findall(sdd_text)
    if not diagrams:
        return Absent(PANEL_ID, "no mermaid diagrams found in SDD.md")

    seam_rows = _seam_rows(spec_dir)
    anchors = _produces_consumes_anchors(spec_dir)

    body = [f'<div class="mc-mermaid-count">{len(diagrams)} design diagram(s) in SDD.md</div>']
    body.append(_render_seam_table(seam_rows))
    body.append(_render_anchor_table(anchors))
    return PanelVM(PANEL_ID, PANEL_TITLE, "\n".join(body))


def _seam_rows(spec_dir: Path) -> list:
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return []
    section = mdtable.extract_section(plan_path.read_text(encoding="utf-8"), "Seam register")
    if section is None:
        return []
    return mdtable.parse_table(section)


def _produces_consumes_anchors(spec_dir: Path) -> list:
    plan_dir = spec_dir / "plan"
    if not plan_dir.is_dir():
        return []
    anchors = []
    for md_path in sorted(plan_dir.glob("*.md")):
        if md_path.name in ("PLAN.md", "JOURNAL.md"):
            continue
        text = md_path.read_text(encoding="utf-8")
        for section_name, pattern in (("Produces", _PRODUCES_RE), ("Consumes", _CONSUMES_RE)):
            section = mdtable.extract_section(text, section_name)
            if not section:
                continue
            for line in section.splitlines():
                match = pattern.match(line.strip())
                if match:
                    anchors.append((md_path.stem, section_name, match.group("file"), match.group("anchor"), match.group("desc")))
    return anchors


def _render_seam_table(rows: list) -> str:
    if not rows:
        return '<div class="mc-empty-sub">no seam register table in plan/PLAN.md</div>'
    out = ['<table class="mc-table"><tr><th>Seam</th><th>Implemented by</th><th>Used by</th></tr>']
    for row in rows:
        seam = row.get("Seam (SDD §9b row)") or row.get("Seam") or ""
        out.append(
            "<tr><td>{seam}</td><td>{impl}</td><td>{used}</td></tr>".format(
                seam=html.escape(seam),
                impl=html.escape(row.get("Implemented by", "")),
                used=html.escape(row.get("Used by", "")),
            )
        )
    out.append("</table>")
    return "\n".join(out)


def _render_anchor_table(anchors: list) -> str:
    if not anchors:
        return '<div class="mc-empty-sub">no Produces/Consumes anchors found in plan/*.md</div>'
    out = ['<table class="mc-table"><tr><th>Subtask</th><th>Kind</th><th>Anchor</th></tr>']
    for subtask, kind, filepath, anchor, desc in anchors:
        out.append(
            "<tr><td>{s}</td><td>{k}</td><td><code>{f}#{a}</code> &mdash; {d}</td></tr>".format(
                s=html.escape(subtask),
                k=html.escape(kind),
                f=html.escape(filepath),
                a=html.escape(anchor),
                d=html.escape(desc),
            )
        )
    out.append("</table>")
    return "\n".join(out)

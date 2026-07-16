"""Architecture — the digest's module map merged with an always-fresh live
overlay: the plan's seam register, each contract's Produces/Consumes anchors,
and the PLAN.md solution-map mermaid source.

Section state mirrors the digest (ok/stale/missing/invalid) — the live
overlay renders regardless, so a never-built digest still shows the seams
and anchors the plan itself declares.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import digests, mdtable
from ..vm import SectionVM

SECTION_ID = "architecture"
SECTION_TITLE = "Architecture"

_MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
# Anchor grammar (owned by skills/afk/to-subtasks/SUBTASK-CONTRACT.md):
# `- {file}#{grep-anchor} — {desc}` (Consumes prepends `{producer-id} `).
# Anchors are free text up to the em-dash separator — real plans emit both
# backtick-wrapped (`anchor`) and bare anchors that may contain spaces and
# parens (e.g. `#export const entityRefOf`, `#useTabGridUrlSync(`).
_SEP = r"\s+[—–-]\s+"
_PRODUCES_RE = re.compile(r"^-\s+(?P<file>\S+?)#(?P<anchor>.+?)" + _SEP + r"(?P<desc>.*)$")
_CONSUMES_RE = re.compile(r"^-\s+(?P<producer>\d{4}[a-z0-9-]*)\s+(?P<file>\S+?)#(?P<anchor>.+?)" + _SEP + r"(?P<desc>.*)$")


def parse(spec_dir: Path):
    digest_vm = digests.load(spec_dir, "architecture", SECTION_ID, SECTION_TITLE)
    live = {
        "seams": _seam_rows(spec_dir),
        "anchors": _anchors(spec_dir),
        "solution_map": _solution_map(spec_dir),
        "sdd_diagram_count": _sdd_diagram_count(spec_dir),
    }
    data = {"digest": digest_vm.data, "live": live}
    return SectionVM(
        SECTION_ID,
        SECTION_TITLE,
        digest_vm.kind,
        data,
        digest_vm.state,
        digest_vm.reason,
        digest_vm.freshness,
    )


def _seam_rows(spec_dir: Path) -> list:
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return []
    section = mdtable.extract_section(plan_path.read_text(encoding="utf-8"), "Seam register", prefix=True)
    if section is None:
        return []
    rows = []
    for row in mdtable.parse_table(section):
        rows.append(
            {
                "seam": row.get("Seam (SDD §9b row)") or row.get("Seam") or "",
                "implemented_by": row.get("Implemented by", ""),
                "used_by": row.get("Used by", ""),
            }
        )
    return rows


def _anchors(spec_dir: Path) -> list:
    plan_dir = spec_dir / "plan"
    if not plan_dir.is_dir():
        return []
    anchors = []
    for md_path in sorted(plan_dir.glob("*.md")):
        if md_path.name in ("PLAN.md", "JOURNAL.md", "TRACE.md"):
            continue
        text = md_path.read_text(encoding="utf-8")
        for section_name, pattern in (("Produces", _PRODUCES_RE), ("Consumes", _CONSUMES_RE)):
            section = mdtable.extract_section(text, section_name)
            if not section:
                continue
            for line in section.splitlines():
                match = pattern.match(line.strip())
                if match:
                    anchors.append(
                        {
                            "subtask": md_path.stem,
                            "kind": section_name.lower(),
                            "producer": match.groupdict().get("producer", ""),
                            "file": match.group("file"),
                            "anchor": match.group("anchor").strip().strip("`"),
                            "desc": match.group("desc"),
                        }
                    )
    return anchors


def _solution_map(spec_dir: Path):
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return None
    section = mdtable.extract_section(plan_path.read_text(encoding="utf-8"), "Solution map", prefix=True)
    if not section:
        return None
    match = _MERMAID_RE.search(section)
    return match.group(1).strip() if match else None


def _sdd_diagram_count(spec_dir: Path) -> int:
    sdd_path = spec_dir / "SDD.md"
    if not sdd_path.is_file():
        return 0
    return len(_MERMAID_RE.findall(sdd_path.read_text(encoding="utf-8")))

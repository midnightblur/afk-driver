"""Gates — smoke gate, preflight ladder, review rollup, adversary verdicts.

Sources: plan/PLAN.md `## Feature smoke gate` (both variants; shape owned by
skills/afk/to-subtasks/PLAN-TEMPLATE.md + SMOKE-GATE.md), `## Preflight`
(lockstep copy: column shape `# | Step | Status | Cycle | Evidence` owned
jointly with /afk-toolkit:preflight — the PLAN-TEMPLATE notes this parser by path),
plan/review/INDEX.md (skills/afk/review/SKILL.md), and
plan/review/*-adversary.md verdict lines.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import mdtable
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "gates"
SECTION_TITLE = "Gates"

_ADVERSARY_VERDICT_RE = re.compile(
    r"verdict\s*[:*`]*\s*(clean|findings|tainted|env_unreachable)", re.IGNORECASE
)
# Real reports also write the verdict as prose: `- **Verdict:** <sentence>`.
_ADVERSARY_PROSE_RE = re.compile(r"\*\*Verdict:?\*\*:?\s*(?P<text>.+)", re.IGNORECASE)


def parse(spec_dir: Path):
    plan_path = spec_dir / "plan" / "PLAN.md"
    review_dir = spec_dir / "plan" / "review"

    smoke = None
    preflight = None
    if plan_path.is_file():
        text = plan_path.read_text(encoding="utf-8")
        smoke = _smoke(text)
        preflight = _table_block(text, "Preflight")

    review = None
    index_path = review_dir / "INDEX.md"
    if index_path.is_file():
        columns, rows = mdtable.parse_table_ordered(index_path.read_text(encoding="utf-8"))
        if rows:
            review = {"columns": columns, "rows": rows}

    adversary = _adversary(review_dir)

    if smoke is None and preflight is None and review is None and not adversary:
        return Absent(
            SECTION_ID,
            "no gate sources found (smoke gate / preflight tables in plan/PLAN.md, "
            "plan/review/INDEX.md, adversary reports all absent)",
        )

    data = {
        "smoke": smoke,
        "preflight": preflight,
        "review_rollup": review,
        "adversary": adversary,
    }
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, data)


def _smoke(text: str):
    variant = "full"
    section = mdtable.extract_section(text, "Feature smoke gate", prefix=True)
    if section is None:
        return None
    # extract_section(prefix=True) also matches the minimal variant heading.
    if mdtable.extract_section(text, "Feature smoke gate (minimal)") is not None:
        variant = "minimal"

    meta, last_run, history = [], "", []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("> -"):
            history.append(stripped[3:].strip())
        elif stripped.startswith(">"):
            content = stripped.lstrip("> ").strip()
            if content.lower().startswith("last run:"):
                last_run = content[len("last run:"):].strip()
            elif content:
                meta.append(content)

    columns, rows = mdtable.parse_table_ordered(section)
    return {
        "variant": variant,
        "meta": meta,
        "last_run": last_run,
        "run_history": history,
        "columns": columns,
        "rows": rows,
    }


def _table_block(text: str, heading: str):
    section = mdtable.extract_section(text, heading, prefix=True)
    if section is None:
        return None
    columns, rows = mdtable.parse_table_ordered(section)
    if not rows:
        return None
    return {"columns": columns, "rows": rows}


def _adversary(review_dir: Path) -> list:
    reports = []
    if not review_dir.is_dir():
        return reports
    for path in sorted(review_dir.glob("*-adversary.md")):
        verdict = ""
        verdict_text = ""
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
            match = _ADVERSARY_VERDICT_RE.search(head)
            if match:
                verdict = match.group(1).lower()
            prose = _ADVERSARY_PROSE_RE.search(head)
            if prose:
                verdict_text = prose.group("text").strip()[:300]
        except OSError:
            pass
        reports.append(
            {
                "subtask": path.name[: -len("-adversary.md")],
                "file": path.name,
                "verdict": verdict,
                "verdict_text": verdict_text,
            }
        )
    return reports

"""Composes all section view-models into the one `MC_DATA` dict the shell
renders. Pure function of (spec_dir, parsers) — no wall-clock, no environment
lookups — so re-rendering unchanged artifacts is byte-identical (requirement
ADR-0005; SDD §5 idempotency).
"""
from __future__ import annotations

from pathlib import Path

from .sections import overview
from .vm import Absent, KIND_DIGEST, KIND_LIVE, absent_json

# Nav order = section order in the shell sidebar. Overview is always first
# (composed from the rest, never parsed).
NAV_ORDER = [
    "architecture",
    "flows",
    "entities",
    "decisions",
    "critical-logic",
    "progress",
    "timeline",
    "gates",
    "insights",
    "diffs",
    "legend",
]

# title + kind for sections that come back Absent (an Absent carries neither).
SECTION_META = {
    "architecture": ("Architecture", KIND_DIGEST),
    "flows": ("Flows", KIND_DIGEST),
    "entities": ("Entities", KIND_DIGEST),
    "decisions": ("Decisions", KIND_DIGEST),
    "critical-logic": ("Critical logic", KIND_DIGEST),
    "progress": ("Progress", KIND_LIVE),
    "timeline": ("Timeline", KIND_LIVE),
    "gates": ("Gates", KIND_LIVE),
    "insights": ("Insights", KIND_LIVE),
    "diffs": ("Diffs", KIND_LIVE),
    "legend": ("Legend", KIND_DIGEST),
}


def build(spec_dir: Path, parsers: list) -> dict:
    vms = {}
    for parser in parsers:
        result = parser(spec_dir)
        vms[result.section_id] = result

    sections = [overview.compose(spec_dir, vms).to_json()]
    for section_id in NAV_ORDER:
        if section_id not in vms:
            continue
        vm = vms[section_id]
        if isinstance(vm, Absent):
            title, kind = SECTION_META.get(section_id, (section_id.title(), KIND_LIVE))
            sections.append(absent_json(section_id, title, kind, vm.reason))
        else:
            sections.append(vm.to_json())

    return {
        "meta": {
            "spec_name": spec_dir.name,
            "digests_dir": "plan/digests",
        },
        "sections": sections,
    }

"""Overview — the landing hero, COMPOSED from the other sections' parsed
view-models plus the PLAN.md header block and the spec folder's artifact
inventory. A derived section: it re-reads no table another section already
parsed (single parse per artifact per render).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import understanding
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "overview"
SECTION_TITLE = "Overview"

# design → planned → executing → smoke → preflight → shipped
PHASES = ["design", "planned", "executing", "smoke", "preflight", "shipped"]

_HEADER_FIELD_RE = re.compile(r"^>\s*(?P<key>[A-Za-z][A-Za-z /()':.-]*?):\s*(?P<value>.+)$")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def compose(spec_dir: Path, sections: dict) -> SectionVM:
    """`sections` = {section_id: SectionVM|Absent} for everything else."""
    header = _plan_header(spec_dir)
    artifacts = _artifact_inventory(spec_dir)
    understanding_card, understanding_reason = understanding.parse(spec_dir)

    progress = _data(sections, "progress")
    gates = _data(sections, "gates")
    insights = _data(sections, "insights")

    digest_states = {}
    for section_id in ("architecture", "flows", "entities", "decisions", "critical-logic", "legend"):
        vm = sections.get(section_id)
        if isinstance(vm, SectionVM):
            digest_states[section_id] = vm.state
        elif isinstance(vm, Absent):
            digest_states[section_id] = "absent"

    data = {
        "header": header,
        "artifacts": artifacts,
        "phase": _phase(header, artifacts, progress, gates),
        "phases": PHASES,
        "progress_counts": (progress or {}).get("counts", {}),
        "subtask_total": len((progress or {}).get("subtasks", [])),
        "gate_summary": _gate_summary(header, gates),
        "top_insights": ((insights or {}).get("items") or [])[:3],
        "digest_states": digest_states,
        "understanding": understanding_card,
        "understanding_reason": understanding_reason,
    }
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, data)


def _data(sections: dict, section_id: str):
    vm = sections.get(section_id)
    return vm.data if isinstance(vm, SectionVM) else None


def _plan_header(spec_dir: Path) -> dict:
    """`> Key: value` lines between the PLAN.md title and the first `##`.
    Real keys seen: Parent ticket (+ trailing `Mode:`), Branch, Last updated,
    Feature. Values keep only their first 400 chars — real 'Last updated'
    lines run to whole paragraphs."""
    plan_path = spec_dir / "plan" / "PLAN.md"
    header = {"title": ""}
    if not plan_path.is_file():
        return header
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            break
        if line.startswith("# ") and not header["title"]:
            header["title"] = line[2:].strip()
            continue
        match = _HEADER_FIELD_RE.match(line.strip())
        if not match:
            continue
        value = _COMMENT_RE.sub("", match.group("value")).strip()
        key = match.group("key").strip().lower()
        if key.startswith("parent ticket"):
            ticket, _, mode_part = value.partition("Mode:")
            header["parent_ticket"] = ticket.strip()
            if mode_part.strip():
                header["mode"] = mode_part.strip()
        elif key.startswith("branch"):
            header["branch"] = value
        elif key == "feature":
            header["feature"] = value[:400]
        elif key.startswith("last updated"):
            header["last_updated"] = value[:400]
        elif key == "mode":
            header["mode"] = value
    return header


def _artifact_inventory(spec_dir: Path) -> dict:
    def count_dir(rel: str) -> int:
        directory = spec_dir / rel
        return len(list(directory.glob("*.md"))) if directory.is_dir() else 0

    return {
        "prd": (spec_dir / "PRD.md").is_file(),
        "sdd": (spec_dir / "SDD.md").is_file(),
        "verification_plan": (spec_dir / "VERIFICATION-PLAN.md").is_file(),
        "grill_log": (spec_dir / "GRILL-LOG.md").is_file(),
        "prototype": (spec_dir / "PROTOTYPE.md").is_file(),
        "index": (spec_dir / "INDEX.md").is_file(),
        "trace": (spec_dir / "plan" / "TRACE.md").is_file(),
        "plan": (spec_dir / "plan" / "PLAN.md").is_file(),
        "adr_requirements": count_dir("adr/requirements"),
        "adr_design": count_dir("adr/design"),
    }


def _phase(header: dict, artifacts: dict, progress, gates) -> str:
    if not artifacts["plan"]:
        return "design"
    preflight = (gates or {}).get("preflight")
    if preflight:
        statuses = [row.get("Status", "").strip().lower() for row in preflight.get("rows", [])]
        if statuses and all(status == "green" for status in statuses):
            return "shipped"
        return "preflight"
    feature = (header.get("feature") or "").lower()
    if feature.startswith("complete"):
        return "smoke"  # smoke green, awaiting/never-ran preflight
    counts = (progress or {}).get("counts", {})
    total = sum(counts.values())
    if total and counts.get("done", 0) == total:
        return "smoke"
    if total and counts.get("pending", 0) < total:
        return "executing"
    return "planned"


def _gate_summary(header: dict, gates) -> dict:
    smoke = (gates or {}).get("smoke") or {}
    preflight = (gates or {}).get("preflight") or {}
    review = (gates or {}).get("review_rollup") or {}
    adversary = (gates or {}).get("adversary") or []

    feature = header.get("feature", "")
    pf_rows = preflight.get("rows", [])
    verdicts = {}
    for row in review.get("rows", []):
        token = row.get("Verdict", "").split("(")[0].strip().lower()
        if token:
            verdicts[token] = verdicts.get(token, 0) + 1

    return {
        "feature_line": feature,
        "smoke_variant": smoke.get("variant", ""),
        "smoke_last_run": smoke.get("last_run", ""),
        "smoke_rows": len(smoke.get("rows", [])),
        "preflight_green": sum(1 for r in pf_rows if r.get("Status", "").strip().lower() == "green"),
        "preflight_total": len(pf_rows),
        "review_verdicts": verdicts,
        "adversary_count": len(adversary),
    }

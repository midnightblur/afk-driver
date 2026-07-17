"""Progress — the live per-subtask board with sub-phase detail.

Joins, per subtask: the PLAN.md progress-tracker row (single source of the
Status ladder), the subtask contract's Complexity + Verification tiers, the
review rollup row (plan/review/INDEX.md), settle-round evidence (per-round
outcomes files and/or cycle notes in the verdict cell), per-subtask commits
(subject convention `[NNNN-slug] ...`), and the subtask's latest journal
line. Formats owned by: skills/afk/to-subtasks/PLAN-TEMPLATE.md,
SUBTASK-CONTRACT.md, skills/afk/review/SKILL.md, JOURNAL-FORMAT.md.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import commitjoin
from .. import journal, mdtable
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "progress"
SECTION_TITLE = "Progress"

_STATUS_LADDER = ["pending", "designing", "developing", "verifying", "reviewing", "done"]

_SUBTASK_ID_RE = re.compile(r"\d{4}[a-z0-9-]*")
_ROUND_FILE_RE = re.compile(r"-r(\d+)\.outcomes\.json$")
_CYCLE_NOTE_RE = re.compile(r"(?:cycle|round)\s+(\d+)", re.IGNORECASE)
_STATUS_RE = re.compile(r"^(?P<token>[a-z_-]+)\s*(?:\((?P<note>.*)\))?$", re.DOTALL)
_TICKET_RE = re.compile(r"^>\s*Parent ticket:\s*(\S+)", re.MULTILINE)


def parse(spec_dir: Path):
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return Absent(SECTION_ID, "plan/PLAN.md not found")

    text = plan_path.read_text(encoding="utf-8")
    section = mdtable.extract_section(text, "Progress tracker", prefix=True)
    if section is None:
        return Absent(SECTION_ID, "no '## Progress tracker' section in plan/PLAN.md")
    rows = mdtable.parse_table(section)
    if not rows:
        return Absent(SECTION_ID, "'## Progress tracker' section has no table rows")

    review_rows = _review_rollup(spec_dir)
    review_dir = spec_dir / "plan" / "review"
    events = journal.parse_journal(spec_dir) or []

    ids = [row.get("Subtask", "").strip() for row in rows]
    ticket_match = _TICKET_RE.search(text)
    commit_join = commitjoin.join(spec_dir, ids, ticket_match.group(1) if ticket_match else "")
    commits = commit_join["by_subtask"]

    subtasks = []
    for row in rows:
        subtask_id = row.get("Subtask", "").strip()
        status_token, status_note = _split_status(row.get("Status", ""))
        review = review_rows.get(subtask_id)
        rounds = _rounds(review_dir, subtask_id, review)
        contract = _contract(spec_dir, subtask_id)
        subtasks.append(
            {
                "num": row.get("#", ""),
                "id": subtask_id,
                "title": row.get("Title", ""),
                "status": status_token,
                "status_note": status_note,
                "blocked_by": _resolve_ids(row.get("Blocked by", ""), ids),
                "tiers": _csv(row.get("Tiers", "")),
                "seams": row.get("Seams", ""),
                "complexity": contract["complexity"],
                "verification": contract["verification"],
                "review": review,
                "rounds": rounds,
                "adversary": (review_dir / f"{subtask_id}-adversary.md").is_file(),
                "commits": commits.get(subtask_id, []),
                "latest_event": _latest_event(events, subtask_id),
                "sub_phase": _sub_phase(status_token, status_note, rounds, review),
            }
        )

    counts = {}
    for sub in subtasks:
        counts[sub["status"]] = counts.get(sub["status"], 0) + 1
    data = {"subtasks": subtasks, "counts": counts, "ladder": _STATUS_LADDER}
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, data)


def _split_status(cell: str) -> tuple:
    """'done (api/e2e→gate)' -> ('done', 'api/e2e→gate'); 'blocked(x)' ->
    ('blocked', 'x'). Unknown shapes pass through as the raw token."""
    cell = cell.strip()
    match = _STATUS_RE.match(cell)
    if match:
        return match.group("token"), (match.group("note") or "").strip()
    return cell, ""


def _csv(cell: str) -> list:
    cell = cell.strip()
    if not cell or cell in ("—", "-"):
        return []
    return [part.strip() for part in cell.split(",") if part.strip()]


def _resolve_ids(cell: str, ids: list) -> list:
    """Blocked-by cells hold full ids or bare `NNNN` prefixes; resolve both."""
    resolved = []
    for token in _SUBTASK_ID_RE.findall(cell):
        full = next((i for i in ids if i == token or i.startswith(token + "-")), token)
        if full not in resolved:
            resolved.append(full)
    return resolved


def _review_rollup(spec_dir: Path) -> dict:
    index_path = spec_dir / "plan" / "review" / "INDEX.md"
    if not index_path.is_file():
        return {}
    rows = mdtable.parse_table(index_path.read_text(encoding="utf-8"))
    rollup = {}
    for row in rows:
        subtask_id = row.get("Subtask", "").strip()
        verdict_cell = row.get("Verdict", "").strip()
        token = verdict_cell.split("(")[0].strip() if verdict_cell else ""
        rollup[subtask_id] = {
            "verdict": token,
            "verdict_note": verdict_cell[len(token):].strip(" ()"),
            "counts": row.get("crit/high/med/low", ""),
            "report": row.get("Latest report", ""),
            "advisories": row.get("Open advisories", ""),
        }
    return rollup


def _rounds(review_dir: Path, subtask_id: str, review):
    """Highest settle-loop round seen: per-round outcomes files win, the
    verdict cell's 'cycle N' note is the fallback (real rollups carry it)."""
    best = 0
    if review_dir.is_dir():
        for path in review_dir.glob(f"{subtask_id}-*.outcomes.json"):
            match = _ROUND_FILE_RE.search(path.name)
            if match:
                best = max(best, int(match.group(1)))
    if review:
        for note in (review.get("verdict_note", ""), review.get("advisories", "")):
            for match in _CYCLE_NOTE_RE.finditer(note or ""):
                best = max(best, int(match.group(1)))
    return best or None


def _contract(spec_dir: Path, subtask_id: str) -> dict:
    contract_path = spec_dir / "plan" / f"{subtask_id}.md"
    out = {"complexity": "", "verification": []}
    if not contract_path.is_file():
        return out
    text = contract_path.read_text(encoding="utf-8")
    complexity = mdtable.extract_section(text, "Complexity")
    if complexity:
        first = complexity.strip().split()
        out["complexity"] = first[0].strip("`*").lower() if first else ""
    verification = mdtable.extract_section(text, "Verification")
    if verification:
        out["verification"] = [
            {
                "tier": row.get("Tier", ""),
                "check": row.get("Check (command or method)", ""),
                "proves": row.get("Proves", ""),
            }
            for row in mdtable.parse_table(verification)
        ]
    return out


def _latest_event(events: list, subtask_id: str):
    for event in reversed(events):
        if event["subject"] == subtask_id:
            return event
    return None


def _sub_phase(status: str, status_note: str, rounds, review) -> str:
    """One short human phrase under the status chip — the 'where exactly is
    it' answer (e.g. 'settle round 3 — 2 findings open')."""
    if status == "blocked":
        return status_note or "blocked"
    if status == "reviewing":
        if rounds:
            return f"settle round {rounds}"
        return "independent review running"
    if status == "done":
        parts = []
        if review and review.get("verdict"):
            parts.append(f"review {review['verdict']}")
            if rounds:
                parts.append(f"after {rounds} round(s)")
        if status_note:
            parts.append(status_note)
        return " · ".join(parts)
    return status_note

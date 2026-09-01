"""Insights — what the agents would surface first at the next human
interaction, mined deterministically from the run artifacts (no LLM):
parks + exit statuses in the journal, blocking review verdicts, open
advisories, pattern-debt rows, non-clean adversary verdicts, smoke reds.
"""
from __future__ import annotations

import re
from pathlib import Path

from .. import journal, mdtable
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "insights"
SECTION_TITLE = "Insights"

# severity buckets drive ordering in the shell: act > know > note
_ACT, _KNOW, _NOTE = "act", "know", "note"

_JOURNAL_FLAGS = [
    # status tokens only (`park(reason)` / `PF-n parked(reason)`), not prose
    # mentioning parking — journal grammar: JOURNAL-FORMAT.md
    (re.compile(r"(?:^|\s)park(?:ed)?\(", re.IGNORECASE), _ACT, "park"),
    (re.compile(r"design_conflict|contract_mismatch|produces_drift|adversary_fail|adversary_unrun|review_fail|needs_decision"), _ACT, "exit"),
    (re.compile(r"smoke[- ]failing", re.IGNORECASE), _ACT, "smoke-red"),
    (re.compile(r"refused", re.IGNORECASE), _KNOW, "refused"),
    (re.compile(r"review blocking", re.IGNORECASE), _KNOW, "review-blocking"),
]

_ADVERSARY_VERDICT_RE = re.compile(
    r"verdict\s*[:*`]*\s*(findings|tainted|env_unreachable)", re.IGNORECASE
)
# Prose verdicts (`- **Verdict:** <sentence>`) flag as an insight when they
# mention a finding — deterministic heuristic, severity 'know'.
_ADVERSARY_PROSE_RE = re.compile(r"\*\*Verdict:?\*\*:?\s*(?P<text>.+)", re.IGNORECASE)


def parse(spec_dir: Path):
    resolved = _current_state(spec_dir)
    items = []
    items.extend(item for item in _from_journal(spec_dir) if not _superseded(item, resolved))
    items.extend(_from_review(spec_dir))
    items.extend(_from_pattern_debt(spec_dir))
    items.extend(_from_adversary(spec_dir))

    if not items:
        # A run with nothing to flag is a finding in itself, not an error —
        # but with no sources at all, stay honest about why it's empty.
        if not (spec_dir / "plan").is_dir():
            return Absent(SECTION_ID, "no plan/ directory to mine")
        return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, {"items": []})

    # severity buckets first, newest first inside each bucket
    order = {_ACT: 0, _KNOW: 1, _NOTE: 2}
    items.sort(key=lambda item: (order.get(item["severity"], 9), _neg_ts(item)))
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, {"items": items})


def _current_state(spec_dir: Path) -> dict:
    """What the plan says is resolved NOW — used to drop journal events a
    later state supersedes (a park whose preflight step is green again, a
    subtask park whose tracker row is done, a review-blocking that settled).
    """
    state = {"done_subtasks": set(), "green_pf": set(), "feature_complete": False, "blocking_now": set()}
    plan_path = spec_dir / "plan" / "PLAN.md"
    if plan_path.is_file():
        text = plan_path.read_text(encoding="utf-8")
        tracker = mdtable.extract_section(text, "Progress tracker", prefix=True)
        if tracker:
            for row in mdtable.parse_table(tracker):
                if row.get("Status", "").strip().lower().startswith("done"):
                    state["done_subtasks"].add(row.get("Subtask", "").strip())
        preflight = mdtable.extract_section(text, "Preflight", prefix=True)
        if preflight:
            for row in mdtable.parse_table(preflight):
                if row.get("Status", "").strip().lower() == "green":
                    step = row.get("Step", "")
                    match = re.match(r"(PF-\d+[a-z]?)", step)
                    if match:
                        state["green_pf"].add(match.group(1))
        feature_match = re.search(r"^>\s*Feature:\s*complete", text, re.MULTILINE)
        state["feature_complete"] = bool(feature_match)
    index_path = spec_dir / "plan" / "review" / "INDEX.md"
    if index_path.is_file():
        for row in mdtable.parse_table(index_path.read_text(encoding="utf-8")):
            if row.get("Verdict", "").strip().lower().startswith("blocking"):
                state["blocking_now"].add(row.get("Subtask", "").strip())
    return state


def _superseded(item: dict, state: dict) -> bool:
    subject = item.get("subject", "")
    kind = item.get("kind", "")
    if kind in ("park", "exit", "refused"):
        if subject in state["done_subtasks"]:
            return True
        # journal subjects for preflight parks are the step id, or a range
        # like `PF-2..5`; a park is superseded when its FIRST step went green
        match = re.match(r"(PF-\d+[a-z]?)", subject)
        if match and match.group(1) in state["green_pf"]:
            return True
    if kind == "smoke-red" and state["feature_complete"]:
        return True
    if kind == "review-blocking" and subject not in state["blocking_now"]:
        return True
    return False


def _neg_ts(item) -> str:
    """Sort helper: newest first inside a severity bucket (ISO timestamps
    invert cleanly by codepoint complement of the string comparison)."""
    ts = item.get("ts") or ""
    return "".join(chr(0x10FFFF - ord(ch)) for ch in ts)


def _from_journal(spec_dir: Path) -> list:
    events = journal.parse_journal(spec_dir) or []
    items = []
    for event in events:
        blob = event["event"]
        for pattern, severity, kind in _JOURNAL_FLAGS:
            if pattern.search(blob):
                items.append(
                    {
                        "kind": kind,
                        "severity": severity,
                        "subject": event["subject"],
                        "writer": event["writer"],
                        "ts": event["ts"],
                        "text": event["event"],
                        "detail": event["plain"],
                        "source": "plan/JOURNAL.md",
                    }
                )
                break
    return items


def _from_review(spec_dir: Path) -> list:
    index_path = spec_dir / "plan" / "review" / "INDEX.md"
    if not index_path.is_file():
        return []
    items = []
    for row in mdtable.parse_table(index_path.read_text(encoding="utf-8")):
        verdict = row.get("Verdict", "").strip().lower()
        advisories = row.get("Open advisories", "").strip()
        subtask = row.get("Subtask", "").strip()
        if verdict.startswith("blocking"):
            items.append(
                {
                    "kind": "review-blocking",
                    "severity": _ACT,
                    "subject": subtask,
                    "writer": "review",
                    "ts": "",
                    "text": f"review blocking ({row.get('crit/high/med/low', '')})",
                    "detail": advisories,
                    "source": "plan/review/INDEX.md",
                }
            )
        elif advisories and advisories.lower() not in ("none", "—", "-"):
            items.append(
                {
                    "kind": "advisory",
                    "severity": _NOTE,
                    "subject": subtask,
                    "writer": "review",
                    "ts": "",
                    "text": f"open advisories ({row.get('crit/high/med/low', '')})",
                    "detail": advisories,
                    "source": "plan/review/INDEX.md",
                }
            )
    return items


def _from_pattern_debt(spec_dir: Path) -> list:
    debt_path = spec_dir / "plan" / "review" / "PATTERN-DEBT.md"
    if not debt_path.is_file():
        return []
    items = []
    for row in mdtable.parse_table(debt_path.read_text(encoding="utf-8")):
        cells = list(row.values())
        items.append(
            {
                "kind": "pattern-debt",
                "severity": _NOTE,
                "subject": cells[1] if len(cells) > 1 else "",
                "writer": "review",
                "ts": cells[0] if cells else "",
                "text": "pattern-debt recorded",
                "detail": " · ".join(cell for cell in cells[2:] if cell),
                "source": "plan/review/PATTERN-DEBT.md",
            }
        )
    return items


def _from_adversary(spec_dir: Path) -> list:
    review_dir = spec_dir / "plan" / "review"
    if not review_dir.is_dir():
        return []
    items = []
    for path in sorted(review_dir.glob("*-adversary.md")):
        try:
            head = path.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        match = _ADVERSARY_VERDICT_RE.search(head)
        if match:
            items.append(
                {
                    "kind": "adversary",
                    "severity": _ACT if match.group(1).lower() != "env_unreachable" else _KNOW,
                    "subject": path.name[: -len("-adversary.md")],
                    "writer": "adversary",
                    "ts": "",
                    "text": f"adversary verdict: {match.group(1).lower()}",
                    "detail": "",
                    "source": f"plan/review/{path.name}",
                }
            )
            continue
        prose = _ADVERSARY_PROSE_RE.search(head)
        if prose and re.search(r"finding", prose.group("text"), re.IGNORECASE):
            items.append(
                {
                    "kind": "adversary",
                    "severity": _KNOW,
                    "subject": path.name[: -len("-adversary.md")],
                    "writer": "adversary",
                    "ts": "",
                    "text": "adversary report notes a finding",
                    "detail": prose.group("text").strip()[:300],
                    "source": f"plan/review/{path.name}",
                }
            )
    return items

"""Diffs — the feature's commits grouped by owning subtask, with per-file
numstat. The spec folder shares git history with the whole monorepo, so
commits are FILTERED to the feature via mc.sections.commitjoin (subject tag /
journal-recorded hash / parent-ticket tag); unrelated history is excluded and
reported only as a count. One numstat call (SDD §9b git seam, read-only).
"""
from __future__ import annotations

import re
from pathlib import Path

from . import commitjoin
from .. import gitio, mdtable
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "diffs"
SECTION_TITLE = "Diffs"

_MAX_NUMSTAT = 600
_TICKET_RE = re.compile(r"^>\s*Parent ticket:\s*(\S+)", re.MULTILINE)


def parse(spec_dir: Path):
    if not gitio.inside_work_tree(spec_dir):
        return Absent(SECTION_ID, "spec folder is not inside a git working tree")

    ids, ticket = _plan_context(spec_dir)
    join = commitjoin.join(spec_dir, ids, ticket)
    if join["scanned"] == 0:
        return Absent(SECTION_ID, "git log returned no commits")

    owner = {}
    for subtask_id, commits in join["by_subtask"].items():
        for commit in commits:
            owner[commit["short"]] = subtask_id
    for commit in join["feature"]:
        owner.setdefault(commit["short"], "")

    if not owner:
        return Absent(
            SECTION_ID,
            "no commits attributable to this feature in recent history "
            "(no subtask tag, journal-recorded hash, or parent-ticket tag matched)",
        )

    stats = {c["hash"]: c for c in (gitio.log_with_numstat(spec_dir, _MAX_NUMSTAT) or [])}

    groups = {}
    order = []
    for short, subtask_id in owner.items():
        stat = stats.get(short)
        entry = {
            "hash": short,
            "subject": (stat or {}).get("subject", ""),
            "files": (stat or {}).get("files", []),
            "adds": sum(_int(f["add"]) for f in (stat or {}).get("files", [])),
            "dels": sum(_int(f["del"]) for f in (stat or {}).get("files", [])),
        }
        if not entry["subject"]:  # older than the numstat window — subject from the join
            entry["subject"] = _subject_from_join(join, short)
        if subtask_id not in groups:
            groups[subtask_id] = []
            order.append(subtask_id)
        groups[subtask_id].append(entry)

    data = {
        "groups": [
            {"id": key, "label": key or "(feature-level commits)", "commits": groups[key]}
            for key in sorted(order, key=lambda k: (k == "", k))
        ],
        "scanned": join["scanned"],
    }
    return SectionVM(SECTION_ID, SECTION_TITLE, KIND_LIVE, data)


def _plan_context(spec_dir: Path) -> tuple:
    plan_path = spec_dir / "plan" / "PLAN.md"
    if not plan_path.is_file():
        return [], ""
    text = plan_path.read_text(encoding="utf-8")
    section = mdtable.extract_section(text, "Progress tracker", prefix=True)
    ids = []
    if section:
        ids = [row.get("Subtask", "").strip() for row in mdtable.parse_table(section)]
    match = _TICKET_RE.search(text)
    return ids, match.group(1) if match else ""


def _subject_from_join(join: dict, short: str) -> str:
    for commits in join["by_subtask"].values():
        for commit in commits:
            if commit["short"] == short:
                return commit["subject"]
    for commit in join["feature"]:
        if commit["short"] == short:
            return commit["subject"]
    return ""


def _int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0  # numstat prints '-' for binary files

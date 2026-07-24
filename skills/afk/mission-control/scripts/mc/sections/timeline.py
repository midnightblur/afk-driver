"""Timeline — the journal as filterable event data (newest first).
Grammar: skills/afk/to-subtasks/JOURNAL-FORMAT.md via mc.journal.
"""
from __future__ import annotations

from pathlib import Path

from .. import journal
from ..vm import KIND_LIVE, Absent, SectionVM

SECTION_ID = "timeline"
SECTION_TITLE = "Timeline"


def parse(spec_dir: Path):
    events = journal.parse_journal(spec_dir)
    if events is None:
        return Absent(SECTION_ID, "plan/JOURNAL.md not found")
    if not events:
        return Absent(SECTION_ID, "plan/JOURNAL.md has no parseable event lines")

    newest_first = list(reversed(events))
    writers = sorted({event["writer"] for event in newest_first})
    return SectionVM(
        SECTION_ID,
        SECTION_TITLE,
        KIND_LIVE,
        {"events": newest_first, "writers": writers},
    )

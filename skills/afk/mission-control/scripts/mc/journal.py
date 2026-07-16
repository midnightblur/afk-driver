"""Shared JOURNAL.md line parsing. Grammar owned by
`skills/afk/to-subtasks/JOURNAL-FORMAT.md` (lockstep copy at this parse
site): `{YYYY-MM-DD HH:mm} | {writer} | {subject} | {event} — {plain terms}`.
"""
from __future__ import annotations

import re
from pathlib import Path

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (?P<writer>[^|]+) \| "
    r"(?P<subject>[^|]+) \| (?P<rest>.+)$"
)
# The event/plain-terms divider is an em-dash per the format; tolerate an
# ASCII hyphen fallback seen in older journals.
_REST_SPLIT_RE = re.compile(r"\s+[—-]\s+")


def parse_journal(spec_dir: Path):
    """[{ts, writer, subject, event, plain}] in file order, or None when the
    journal is missing. Unparseable lines are skipped (append-only file may
    carry a header + blank lines)."""
    journal_path = spec_dir / "plan" / "JOURNAL.md"
    if not journal_path.is_file():
        return None
    events = []
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line.strip())
        if not match:
            continue
        rest = match.group("rest").strip()
        parts = _REST_SPLIT_RE.split(rest, maxsplit=1)
        events.append(
            {
                "ts": match.group("ts"),
                "writer": match.group("writer").strip(),
                "subject": match.group("subject").strip(),
                "event": parts[0].strip(),
                "plain": parts[1].strip() if len(parts) > 1 else "",
            }
        )
    return events

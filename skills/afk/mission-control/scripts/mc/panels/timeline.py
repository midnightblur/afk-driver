"""MC-2 Timeline — derived from `plan/JOURNAL.md` (PRD "Mission-control
panels" row MC-2). Line grammar per
`skills/afk/to-subtasks/JOURNAL-FORMAT.md`:
`{YYYY-MM-DD HH:mm} | {writer} | {subject} | {event} - {plain terms}`.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from ..vm import Absent, PanelVM

PANEL_ID = "timeline"
PANEL_TITLE = "Timeline"

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \| (?P<writer>[^|]+) \| "
    r"(?P<subject>[^|]+) \| (?P<rest>.+)$"
)


def parse(spec_dir: Path):
    journal_path = spec_dir / "plan" / "JOURNAL.md"
    if not journal_path.is_file():
        return Absent(PANEL_ID, "plan/JOURNAL.md not found")

    events = []
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line.strip())
        if match:
            events.append(match.groupdict())
    if not events:
        return Absent(PANEL_ID, "plan/JOURNAL.md has no parseable event lines")

    body = ['<ol class="mc-timeline">']
    for event in reversed(events):  # newest first, matching the panel's purpose
        body.append(
            '<li><span class="mc-ts">{ts}</span> '
            '<span class="mc-writer">{writer}</span> '
            '<span class="mc-subject">{subject}</span> '
            "&mdash; {rest}</li>".format(
                ts=html.escape(event["ts"]),
                writer=html.escape(event["writer"].strip()),
                subject=html.escape(event["subject"].strip()),
                rest=html.escape(event["rest"].strip()),
            )
        )
    body.append("</ol>")
    return PanelVM(PANEL_ID, PANEL_TITLE, "\n".join(body))

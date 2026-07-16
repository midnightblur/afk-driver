"""Shared markdown section/table parsing helpers for the panel parsers.

Every panel reads one or more of the plugin's lockstep markdown formats
(the plan progress tracker, the smoke-gate table, the journal, the review
rollup, ...). These helpers are intentionally forgiving: a heading or table
that can't be found returns `None` / `[]` rather than raising, so a caller
can turn that into an `Absent(reason)` value (ADR-0007).
"""
from __future__ import annotations

import re

_HEADING_RE = re.compile(r"^(#+)\s+(.*)$")


def extract_section(text: str, heading: str, prefix: bool = False) -> "str | None":
    """Return the body between a heading line matching `heading` (exact text
    after stripping the leading `#`s and surrounding whitespace) and the next
    heading of the same or shallower level. `None` if no such heading exists.

    `prefix=True` matches a heading that *starts with* `heading` — real plans
    decorate headings with trailing HTML comments or variant suffixes (e.g.
    `## Preflight   <!-- created on first run -->`, `## Feature smoke gate
    (minimal)`).
    """
    lines = text.splitlines()
    start = None
    start_level = None
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        title = match.group(2).strip()
        if title == heading or (prefix and title.startswith(heading)):
            start = index + 1
            start_level = len(match.group(1))
            break
    if start is None:
        return None

    end = len(lines)
    for index in range(start, len(lines)):
        match = _HEADING_RE.match(lines[index])
        if match and len(match.group(1)) <= start_level:
            end = index
            break
    return "\n".join(lines[start:end])


def parse_table(block: str) -> list:
    """Parse the first GitHub-flavored markdown table found in `block` into a
    list of `dict`s keyed by header cell text. `[]` if no table is found.
    """
    _, rows = parse_table_ordered(block)
    return rows


def parse_table_ordered(block: str) -> tuple:
    """Like `parse_table` but also returns the header cells in column order:
    `(headers, rows)` — the shell renders unknown table shapes generically and
    needs the order the artifact declared. `([], [])` if no table is found.
    """
    lines = [line for line in block.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return [], []
    header = [cell.strip() for cell in lines[0].strip().strip("|").split("|")]
    rows = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return header, rows

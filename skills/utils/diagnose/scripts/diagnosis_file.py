"""Read DIAGNOSIS.md parts and the tables of DIAGNOSIS-FORMAT.md.

Shared by check_diagnosis.py and outside_writes.py, so both read the format
file's tables the same way and neither holds a copy of them.
"""
from __future__ import annotations

import re
from pathlib import Path

FORMAT_PATH = Path(__file__).resolve().parent.parent / "DIAGNOSIS-FORMAT.md"
HEADING = re.compile(r"^##\s+(.+?)\s*$")


def sections(text: str) -> dict[str, list[str]]:
    """`## Heading` -> its content lines, keyed lower-case; fenced lines stay inside."""
    found: dict[str, list[str]] = {}
    current = None
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        match = None if fenced else HEADING.match(line)
        if match:
            current = match.group(1).lower()
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: _trim(lines) for name, lines in found.items()}


def _trim(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return lines


def table(text: str, heading: str) -> list[list[str]]:
    """Body rows of the first Markdown table under `## heading`, cells stripped."""
    rows = []
    for line in sections(text).get(heading.lower(), []):
        if not line.startswith("|"):
            if rows:
                break
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        raise ValueError(f"no table under `## {heading}` in the diagnosis format file")
    return rows[2:]


def load_format(path: Path | None = None) -> str:
    return Path(path or FORMAT_PATH).read_text(encoding="utf-8")


def outside_write_kinds(format_text: str) -> set[str]:
    return {row[0].strip("`") for row in table(format_text, "Outside writes entries")}

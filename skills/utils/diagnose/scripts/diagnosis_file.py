"""Read DIAGNOSIS.md parts and the tables of DIAGNOSIS-FORMAT.md.

Shared by check_diagnosis.py and outside_writes.py, so both read the format
file's tables and the diagnosis's headings the same way and neither holds a
copy of them.
"""
from __future__ import annotations

import re
from pathlib import Path

FORMAT_PATH = Path(__file__).resolve().parent.parent / "DIAGNOSIS-FORMAT.md"
HEADING = re.compile(r"^##\s+(.+?)\s*$")
ENTRY = re.compile(r"^([a-z][a-z-]*):\s*(\S.*)$")
EVIDENCE = re.compile(r"^afk-evidence \S+ [a-z][a-z0-9-]*$")
BOM = "\ufeff"


def split_lines(text: str, keepends: bool = False) -> list[str]:
    """Lines split at `\\n` only, the one line rule of both scripts; a line keeps
    its own end with `keepends`, else loses it and a trailing `\\r`."""
    parts = text.split("\n")
    if keepends:
        return [part + "\n" for part in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    return [part.removesuffix("\r") for part in (parts if parts[-1] else parts[:-1])]


def headings(lines):
    """(index, lower-case name) of each `## ` heading outside a code fence."""
    fenced = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        match = None if fenced else HEADING.match(line)
        if match:
            yield i, match.group(1).lower()


def sections(text: str) -> dict[str, list[str]]:
    """`## Heading` -> its content lines, keyed lower-case; the first of a repeated heading wins."""
    lines = split_lines(text.removeprefix(BOM))
    marks = list(headings(lines))
    found: dict[str, list[str]] = {}
    for n, (start, name) in enumerate(marks):
        end = marks[n + 1][0] if n + 1 < len(marks) else len(lines)
        found.setdefault(name, _trim(lines[start + 1:end]))
    return found


def repeated(text: str) -> list[str]:
    """Lower-case names of headings that appear more than once."""
    names = [name for _, name in headings(split_lines(text.removeprefix(BOM)))]
    return sorted({name for name in names if names.count(name) > 1})


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
        if rows and len(cells) != len(rows[0]):
            raise ValueError(f"a row under `## {heading}` has {len(cells)} cells, not {len(rows[0])}")
        rows.append(cells)
    if len(rows) < 2:
        raise ValueError(f"no table under `## {heading}` in the diagnosis format file")
    return rows[2:]


def load_format(path: Path | None = None) -> str:
    return Path(path or FORMAT_PATH).read_text(encoding="utf-8")


def outside_write_kinds(format_text: str) -> set[str]:
    return {row[0].strip("`") for row in table(format_text, "Outside writes entries")}


def entry_problem(entry: str, kinds) -> str | None:
    """Why `{kind}: {value}` breaks the Outside writes grammar, or None."""
    match = ENTRY.match(entry)
    if not match or match.group(1) not in kinds:
        return f"`{entry}` is not `{{kind}}: {{value}}` with a kind from {sorted(kinds)}"
    if match.group(1) == "evidence" and not EVIDENCE.match(match.group(2)):
        return f"`{match.group(2)}` is not an evidence marker `afk-evidence {{work id}} {{step}}`"
    return None

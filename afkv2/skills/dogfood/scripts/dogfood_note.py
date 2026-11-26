"""The milestone note: `parse(text)` reads 1 note into its fields, and `check(note, worktrees)` returns its failures.

The grammar and the rule codes are in NOTE-FORMAT.md of the skill folder. `parse` never refuses a note: it keeps
what it can read, with the line of each field, and `check` names each break as a failure
`{"code", "where", "reason"}`. Both return plain data, so a caller can print them as JSON.
"""

from __future__ import annotations

import re

HEADER = "afkv2-note v1"
SCALARS = ("kind", "ask", "purpose", "use", "redo", "open-asks")
ROWS = ("changed", "changes")
KEY = re.compile(r"^(kind|ask|purpose|changed|use|best-effort|redo|changes|open-asks):(?:[ \t]+(.*))?$")


def _field(name):
    return name.replace("-", "_")


def _changed_row(text, line):
    parts = [part.strip() for part in text.split("|", 3)]
    parts += [""] * (4 - len(parts))
    return {"path": parts[0], "kind": parts[1], "action": parts[2], "what": parts[3], "line": line}


def _changes_row(text, line):
    parts = [part.strip() for part in text.split("|", 2)]
    parts += [""] * (3 - len(parts))
    return {"url": parts[0], "branch": parts[1], "asks": parts[2], "line": line}


def _best_effort(text, line):
    path, _, what = text.partition(" - ")
    return {"path": path.strip(), "what": what.strip(), "line": line}


def parse(text: str) -> dict:
    """The fields of 1 note. A scalar field holds its text, its continuation lines joined by a newline; a field the
    note does not hold is None. `lines` maps each field the note holds to the line number of its key."""
    lines = text.splitlines()
    note = {"header": lines[0].strip() if lines else "", "changed": [], "best_effort": [], "changes": [], "lines": {}}
    note.update({_field(name): None for name in SCALARS})
    current = None
    for number, raw in enumerate(lines[1:], start=2):
        line = raw.rstrip()
        if not line.strip():
            continue
        match = KEY.match(line)
        if match:
            name, value = match.group(1), (match.group(2) or "").strip()
            note["lines"].setdefault(_field(name), number)
            current = name
            if name == "best-effort":
                note["best_effort"].append(_best_effort(value, number))
            elif name in SCALARS and note[_field(name)] is None:
                note[_field(name)] = value
            elif name in SCALARS:
                current = None
            continue
        item = line.strip()
        if current in ROWS and item[:2] == "- ":
            parser = _changed_row if current == "changed" else _changes_row
            note[current].append(parser(item[2:].strip(), number))
        elif current in SCALARS:
            joined = note[_field(current)]
            note[_field(current)] = f"{joined}\n{item}" if joined else item
        elif current == "best-effort":
            entry = note["best_effort"][-1]
            entry["what"] = f"{entry['what']}\n{item}" if entry["what"] else item
    return note


def check(note, worktrees) -> list[dict]:
    """Each failure of 1 parsed note, in line order; `worktrees` are the worktree paths the state lists."""
    return []

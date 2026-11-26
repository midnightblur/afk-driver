"""The milestone note: `parse(text)` reads 1 note into its fields, and `check(note, worktrees)` returns its failures.

The grammar and the rule codes are in NOTE-FORMAT.md of the skill folder. `parse` never refuses a note: it keeps
what it can read, with the line of each field, and `check` names each break as a failure
`{"code", "where", "reason"}`. Both return plain data, so a caller can print them as JSON.
"""

from __future__ import annotations

import os
import re

HEADER = "afkv2-note v1"
KINDS = ("milestone", "wrap")
CHANGE_KINDS = ("CK-1", "CK-2", "CK-3", "CK-4")
CODES = ("N-HEADER", "N-KIND", "N-NO-PATH", "N-PATH-OUTSIDE", "N-PATH-MISSING", "N-CK", "N-NO-USE", "N-NO-BEST-EFFORT",
         "N-NO-REDO", "N-NO-CHANGES")
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


def _key(path):
    return os.path.normcase(os.path.realpath(path))


def _under(path, worktrees):
    """True when `path` is absolute and lies inside 1 of the worktrees, after `..` and links resolve."""
    if not path or not os.path.isabs(path):
        return False
    target = _key(path)
    for worktree in worktrees:
        root = _key(worktree)
        try:
            if target != root and os.path.commonpath([target, root]) == root:
                return True
        except ValueError:
            continue
    return False


def _failure(code, line, reason):
    return {"code": code, "where": f"line {line}", "reason": reason}


def _milestone(note, worktrees, kind_line):
    failures = []
    if not note["changed"]:
        failures.append(_failure("N-NO-PATH", note["lines"].get("changed", kind_line), "a milestone names at least 1 changed row"))
    for row in note["changed"]:
        if row["kind"] not in CHANGE_KINDS:
            failures.append(_failure("N-CK", row["line"], f"change kind {row['kind'] or '(none)'} is not CK-1 to CK-4"))
        if not _under(row["path"], worktrees):
            failures.append(_failure("N-PATH-OUTSIDE", row["line"], f"{row['path'] or '(no path)'} is not under a worktree of this session"))
        elif row["action"] != "removed" and not os.path.exists(row["path"]):
            failures.append(_failure("N-PATH-MISSING", row["line"], f"{row['path']} does not exist"))
    if not note["use"]:
        failures.append(_failure("N-NO-USE", note["lines"].get("use", kind_line), "a milestone says how to try it in a use line"))
    told = {_key(entry["path"]) for entry in note["best_effort"] if entry["path"] and entry["what"]}
    for row in note["changed"]:
        if row["kind"] == "CK-4" and (not row["path"] or _key(row["path"]) not in told):
            failures.append(_failure("N-NO-BEST-EFFORT", row["line"], f"the CK-4 row {row['path']} has no best-effort line"))
    if not note["redo"]:
        failures.append(_failure("N-NO-REDO", note["lines"].get("redo", kind_line), "a milestone has a redo line; `redo: none` is valid"))
    return failures


def check(note, worktrees) -> list[dict]:
    """Each failure of 1 parsed note, in line order; `worktrees` are the worktree paths the state lists. A wrong
    header or kind is the only failure, because the other rules depend on them."""
    if note["header"] != HEADER:
        return [_failure("N-HEADER", 1, "line 1 is not the format header of NOTE-FORMAT.md")]
    kind_line = note["lines"].get("kind", 2)
    if note["kind"] not in KINDS:
        return [_failure("N-KIND", kind_line, f"kind {note['kind'] or '(none)'} is not milestone or wrap")]
    if note["kind"] == "wrap":
        if note["changes"]:
            return []
        return [_failure("N-NO-CHANGES", note["lines"].get("changes", kind_line), "a wrap names at least 1 Draft change")]
    failures = _milestone(note, list(worktrees), kind_line)
    return sorted(failures, key=lambda failure: int(failure["where"].split()[1]))

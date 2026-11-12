"""The plan folder as data: the frozen contract sections, the progress tracker, the graph, the rules switch.

`rules_of(plan_text)` is the one switch between the rule sets (design ADR-0003): 2 for a `> Rules: 2` header
line, 1 with no line, None for any other value. Every checker asks it.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PLUGIN / "ports"))

from tracker.envelope import Refusal  # noqa: E402

REQUIRED_SECTIONS = ("Goal", "Complexity", "Design refs", "Scope", "Seams", "Acceptance", "Produces", "Verification",
                     "Context excerpts", "Parent PRD", "Parent SDD", "Blocked by", "Conflict procedure")
OPTIONAL_SECTIONS = ("Review", "Consumes")
HEADING = re.compile(r"## (.+?)\s*")
FENCE = re.compile(r"\s*(```|~~~)")
SEPARATOR = re.compile(r":?-+:?")
NO_ID = {"none", "(none)", "-", "—"}
RULES_MARK = "> Rules:"
RULE_SETS = {"1": 1, "2": 2}
TIER_COLUMN, PLAN_ROW_COLUMN, CHECK_COLUMN, PROVES_COLUMN = "Tier", "Plan row", "Check", "Proves"


@dataclass(frozen=True)
class GateRow:
    tier: str
    check: str
    plan_row: str | None = None
    proves: str | None = None


@dataclass(frozen=True)
class Contract:
    id: str
    sections: dict

    def bullets(self, name):
        return [line[2:].strip() for line in self.sections.get(name, "").splitlines() if line.startswith("- ")]

    @property
    def blocked_by(self):
        ids = (bullet.split()[0] for bullet in self.bullets("Blocked by"))
        return [item for item in ids if item.lower() not in NO_ID]

    @property
    def produces(self):
        return [anchor for anchor in map(_anchor, self.bullets("Produces")) if anchor]

    @property
    def consumes(self):
        """(producer, file, anchor) of each `## Consumes` line."""
        found = []
        for bullet in self.bullets("Consumes"):
            producer, _, rest = bullet.partition(" ")
            anchor = _anchor(rest)
            if anchor:
                found.append((producer, *anchor))
        return found

    @property
    def rows(self):
        """Each `## Verification` row, read by header name; [] when the table has no `Tier` or `Check` column."""
        cells = table_rows(self.sections.get("Verification", ""))
        columns = verification_columns(cells[0] if cells else [])
        if columns is None:
            return []
        return [GateRow(**{field: row[index] if index is not None and index < len(row) else None for field, index in columns.items()})
                for row in cells[1:] if len(row) > max(columns["tier"], columns["check"])]


def verification_columns(header):
    """{field: column index} of a `## Verification` header, read by name; None without `Tier` or `Check`.

    The check column is the one whose header starts with `Check`. `plan_row` and `proves` are None when absent.
    """
    names = [cell.strip() for cell in header]
    tier = names.index(TIER_COLUMN) if TIER_COLUMN in names else None
    check = next((index for index, name in enumerate(names) if name.startswith(CHECK_COLUMN)), None)
    if tier is None or check is None:
        return None
    return {"tier": tier, "check": check, "plan_row": names.index(PLAN_ROW_COLUMN) if PLAN_ROW_COLUMN in names else None,
            "proves": names.index(PROVES_COLUMN) if PROVES_COLUMN in names else None}


def _anchor(text):
    """(file, anchor) of `<file>#<anchor> — words`; the first `#` ends the file, and ` — ` ends the anchor."""
    head = text.split(" — ", 1)[0].strip()
    path, mark, anchor = head.partition("#")
    return (path.strip(), anchor.strip()) if mark and path.strip() and anchor.strip() else None


def sections_of(text):
    """Each `## ` heading outside a code fence, with the text under it."""
    found, name, lines, fenced = {}, None, [], False
    for line in text.splitlines():
        if FENCE.match(line):
            fenced = not fenced
        heading = None if fenced else HEADING.fullmatch(line)
        if heading:
            if name is not None:
                found[name] = "\n".join(lines).strip()
            name, lines = heading.group(1), []
        elif name is not None:
            lines.append(line)
    if name is not None:
        found[name] = "\n".join(lines).strip()
    return found


def split_cells(line):
    """The cells of one table line. A `|` inside a code span stays in its cell."""
    cells, cell, in_code = [], [], False
    for char in line.strip().strip("|"):
        if char == "`":
            in_code = not in_code
        if char == "|" and not in_code:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
    cells.append("".join(cell).strip())
    return cells


def _is_separator(cells):
    return all(SEPARATOR.fullmatch(cell) for cell in cells)


def table_rows(text):
    """The rows of the first table in `text`, header first, with no separator line."""
    rows = []
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            if rows:
                break
            continue
        cells = split_cells(line)
        if not _is_separator(cells):
            rows.append(cells)
    return rows


def plan_file(plan):
    return Path(plan) / "PLAN.md"


def read_text(path):
    try:
        return Path(path).read_bytes().decode("utf-8")
    except OSError as error:
        raise Refusal("no-plan-file", f"cannot read {path}: {error}") from None
    except UnicodeDecodeError as error:
        raise Refusal("no-plan-file", f"{path} is not UTF-8: {error}") from None


def header_of(text):
    """The PLAN.md lines before the first `## ` heading."""
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            break
        lines.append(line)
    return lines


def rules_of(plan_text):
    """The rule set of a plan: 2 for a `> Rules: 2` header line, 1 with no line, None for any other value."""
    lines = [line for line in header_of(plan_text) if line.startswith(RULES_MARK)]
    if not lines:
        return 1
    return RULE_SETS.get(lines[0][len(RULES_MARK):].strip()) if len(lines) == 1 else None


def read_contract(plan, subtask):
    return Contract(subtask, sections_of(read_text(Path(plan) / f"{subtask}.md")))


def contract_failures(contract):
    """Each way this contract leaves the frozen section set."""
    missing = [name for name in REQUIRED_SECTIONS if name not in contract.sections]
    extra = [name for name in contract.sections if name not in REQUIRED_SECTIONS + OPTIONAL_SECTIONS]
    table = table_rows(contract.sections.get("Verification", ""))
    columns = [] if "Verification" in missing or verification_columns(table[0] if table else []) else [
        f"`## Verification` has no table with the columns `{TIER_COLUMN}` and `{CHECK_COLUMN}`"]
    return ([f"no section `## {name}`" for name in missing]
            + [f"section `## {name}` is not in the frozen contract" for name in extra] + columns)


def _tracker_table(text):
    """(line index of the header, column of `Subtask`, column of `Status`, lines of the file)."""
    lines = text.split("\n")
    start = next((index for index, line in enumerate(lines) if line.strip() == "## Progress tracker"), None)
    if start is None:
        raise Refusal("no-tracker", "PLAN.md has no `## Progress tracker` section")
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("## "):
            break
        if lines[index].lstrip().startswith("|"):
            cells = split_cells(lines[index])
            if "Subtask" in cells and "Status" in cells:
                return index, cells.index("Subtask"), cells.index("Status"), lines
            break
    raise Refusal("no-tracker", "the progress tracker has no table with the columns `Subtask` and `Status`")


def read_tracker(plan):
    """[(subtask, status)] in rank order."""
    header, id_column, status_column, lines = _tracker_table(read_text(plan_file(plan)))
    rows = []
    for line in lines[header + 1:]:
        if not line.lstrip().startswith("|"):
            break
        cells = split_cells(line)
        if not _is_separator(cells) and len(cells) > max(id_column, status_column):
            rows.append((cells[id_column], cells[status_column]))
    return rows


def write_atomic(path, text):
    temporary = Path(f"{path}.tmp")
    temporary.write_bytes(text.encode("utf-8"))
    os.replace(temporary, path)


def write_status(plan, subtask, status):
    """Set one `Status` cell and the date of the `Last updated` header line; nothing else changes."""
    path = plan_file(plan)
    header, id_column, status_column, lines = _tracker_table(read_text(path))
    clean = " ".join(status.replace("|", "/").split())
    for index in range(header + 1, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            raise Refusal("no-such-subtask", f"the progress tracker has no row {subtask}")
        end = "\r" if lines[index].endswith("\r") else ""
        cells = split_cells(lines[index])
        if len(cells) > max(id_column, status_column) and cells[id_column] == subtask:
            cells[status_column] = clean
            lines[index] = "| " + " | ".join(cells) + " |" + end
            break
    else:
        raise Refusal("no-such-subtask", f"the progress tracker has no row {subtask}")
    today = date.today().isoformat()
    for index, line in enumerate(lines):
        if line.startswith("## "):
            break
        lines[index] = re.sub(r"^(> Last updated: )\d{4}-\d{2}-\d{2}", rf"\g<1>{today}", line)
    write_atomic(path, "\n".join(lines))


def dependents(contracts, subtask, extra=()):
    """Every subtask that waits on `subtask`, directly or through another one, in rank order.

    `extra` holds (first, then) pairs that also count as `then` waiting on `first`.
    """
    waits = {item.id: set(item.blocked_by) for item in contracts}
    for first, then in extra:
        waits.setdefault(then, set()).add(first)
    found, grew = {subtask}, True
    while grew:
        grew = False
        for item, blockers in waits.items():
            if item not in found and blockers & found:
                found.add(item)
                grew = True
    circular = subtask in {item for item, blockers in waits.items() if blockers & found}
    found.discard(subtask)
    ordered = [item.id for item in contracts if item.id in found]
    return [subtask, *ordered] if circular else ordered


def cycle_of(contracts):
    """A subtask that waits on itself through the `## Blocked by` graph, or None."""
    for item in contracts:
        if item.id in dependents(contracts, item.id):
            return item.id
    return None

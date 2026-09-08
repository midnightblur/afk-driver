#!/usr/bin/env python3
"""Deterministic agenda-arithmetic check for a meeting plan.

This docstring is the canonical home of every rule below;
`MEETING-PLAN-FORMAT.md` "Agenda grammar" points here and restates none of it.

Usage: python3 validate_agenda.py <plan.md>   (Windows: py -3 validate_agenda.py <plan.md>)

Input: a meeting plan carrying one `## Agenda` section. That section holds a
`Profile:` line and one pipe table. Both meeting plans use the same shape, so
one checker serves both — a second checker would be a second home for one rule.

The profile line reads `Profile: company-meeting`. That profile is the only one
this check governs, and it is the fixed-hour shape: the budget totals exactly 60.
A plan budgeting to its own ceiling is not checked here — running this on one
would impose an hour nobody asked for.

The budget column is `Total min` when the table has one, else `Min`. A table
carrying `Presenter min` and `Objection min` is also checked row by row: the two
must add up to that row's `Total min`, which is where a single mistyped digit
hides.

Findings, one line each on stderr as `{RULE}: {detail}`:

  NO-AGENDA        no `## Agenda` section
  NO-PROFILE       the section states no `Profile: company-meeting` line
  NO-TABLE         the section holds no pipe table
  NO-BUDGET-COL    the table has neither `Total min` nor `Min`
  BAD-MINUTE       a budget cell is not a non-negative integer
  ROW-SUM          presenter + objection does not equal that row's total
  TOTAL            the budget does not match what the profile requires

Exit codes:
    0  the agenda adds up
    1  at least one finding
    2  the file is missing or unreadable

Standard library only.
"""

import re
import sys

COMPANY_MINUTES = 60


def agenda_section(text):
    """The lines under the `## Agenda` heading, to the next heading of that level.

    The heading may be numbered — a plan whose sections are numbered still has
    one agenda, and requiring a bare heading would fail the plans this checks.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^##\s+(?:\d+\.\s*)?Agenda\b", line.strip()):
            start = i + 1
            break
    if start is None:
        return None
    for j in range(start, len(lines)):
        if re.match(r"^##\s+\S", lines[j]):
            return lines[start:j]
    return lines[start:]


def is_company_meeting(section):
    """True when the agenda declares the fixed-hour profile."""
    return any(re.match(r"^\s*Profile:\s*company-meeting\s*$", line) for line in section)


def table(section):
    """(headers, rows) of the section's first pipe table, or None."""
    rows = []
    for line in section:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
        elif rows:
            break
    if len(rows) < 3:
        return None
    return rows[0], [r for r in rows[2:] if any(cell for cell in r)]


def column(headers, name):
    for i, header in enumerate(headers):
        if header.strip().lower() == name.lower():
            return i
    return None


def minutes(cell):
    """A budget cell as an integer, or None when it is not one."""
    return int(cell) if re.match(r"^\d+$", cell.strip()) else None


def check(text):
    """Every finding in the plan, as `{RULE}: {detail}` strings."""
    section = agenda_section(text)
    if section is None:
        return ["NO-AGENDA: the plan has no `## Agenda` section"]

    found = []
    company = is_company_meeting(section)
    if not company:
        found.append("NO-PROFILE: the agenda states no `Profile: company-meeting` line")

    parsed = table(section)
    if parsed is None:
        found.append("NO-TABLE: the agenda section holds no segment table")
        return found
    headers, rows = parsed

    budget_col = column(headers, "Total min")
    if budget_col is None:
        budget_col = column(headers, "Min")
    if budget_col is None:
        found.append("NO-BUDGET-COL: the table needs a `Total min` or `Min` column")
        return found

    presenter_col = column(headers, "Presenter min")
    objection_col = column(headers, "Objection min")
    total = 0
    for number, row in enumerate(rows, start=1):
        if budget_col >= len(row):
            found.append("BAD-MINUTE: row %d has no budget cell" % number)
            continue
        value = minutes(row[budget_col])
        if value is None:
            found.append("BAD-MINUTE: row %d budget is %r, not a whole number of "
                         "minutes" % (number, row[budget_col]))
            continue
        total += value
        if presenter_col is None or objection_col is None:
            continue
        if presenter_col >= len(row) or objection_col >= len(row):
            continue
        parts = [minutes(row[presenter_col]), minutes(row[objection_col])]
        if None in parts:
            found.append("BAD-MINUTE: row %d presenter/objection cells are not whole "
                         "minutes" % number)
        elif sum(parts) != value:
            found.append("ROW-SUM: row %d is %d presenter + %d objection = %d, but its "
                         "total says %d" % (number, parts[0], parts[1],
                                            sum(parts), value))

    if company and total != COMPANY_MINUTES:
        found.append("TOTAL: the agenda budgets %d minutes; the company meeting is "
                     "%d" % (total, COMPANY_MINUTES))
    return found


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        sys.stderr.write("usage: validate_agenda.py <plan.md>\n")
        return 2
    try:
        with open(argv[0], encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        sys.stderr.write("validate_agenda: cannot read %s: %s\n" % (argv[0], exc))
        return 2

    found = check(text)
    for finding in found:
        sys.stderr.write("%s: %s\n" % (argv[0], finding))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())

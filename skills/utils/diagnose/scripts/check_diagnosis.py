#!/usr/bin/env afk-python
"""Accept or refuse a DIAGNOSIS.md, and derive the bug's state from it.

Usage: check_diagnosis.py <path to DIAGNOSIS.md> [--format <DIAGNOSIS-FORMAT.md>]

The parts, the required parts per verdict, the certainty marks and the outside
write kinds come from the tables of DIAGNOSIS-FORMAT.md (beside this script's
folder). Nothing is written. Exit 0 accept, 1 refuse, 2 unreadable input.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosis_file import load_format, outside_write_kinds, sections, table  # noqa: E402

VERDICT = re.compile(r"^V-(\d+)\b")
ENTRY = re.compile(r"^[-*]\s+([a-z][a-z-]*):\s*(\S.*)$")
# First match wins: the order of the format file's State table.
STATES = ("In review", "Shipped", "Landed", "Approved", "Sent to a grill", "Stopped", "Diagnosed")
STATE_BY_KIND = (("in-review", "In review"), ("change", "Shipped"), ("push", "Landed"))
STATE_BY_VERDICT = {"V-1": "Diagnosed", "V-2": "Sent to a grill", "V-3": "Sent to a grill",
                    "V-4": "Stopped", "V-5": "Stopped"}


@dataclass
class Result:
    ok: bool
    verdict: str | None = None
    state: str | None = None
    missing: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def check_diagnosis(path, format_path=None) -> Result:
    """Path in -> accept, or refuse with the missing parts; the derived state."""
    fmt = load_format(format_path)
    parts = {row[0]: row for row in table(fmt, "Parts")}
    marked = [name for name, row in parts.items() if row[3].lower() == "yes"]
    required = {row[0]: [p.strip() for p in row[2].split(",") if p.strip()]
                for row in table(fmt, "Required parts per verdict")}
    marks = [row[0].strip("`") for row in table(fmt, "Certainty marks")]
    kinds = outside_write_kinds(fmt)

    found = sections(Path(path).read_text(encoding="utf-8"))
    body = {name: found.get(name.lower(), []) for name in parts}
    filled = {name for name, lines in body.items() if any(line.strip() for line in lines)}
    result = Result(ok=False)

    verdict_line = next((line.strip() for line in body["Verdict"] if line.strip()), "")
    match = VERDICT.match(verdict_line)
    if not verdict_line:
        result.missing.append("Verdict")
    elif not match or f"V-{match.group(1)}" not in required:
        result.problems.append(f"Verdict `{verdict_line}` is not one of V-1..V-5")
    else:
        result.verdict = f"V-{match.group(1)}"
        result.missing += [p for p in required[result.verdict] if p not in filled]
        if "Reproduction" not in filled and "Attempts" not in filled:
            result.problems.append("a verdict needs a reproduction or a recorded attempt")

    for name in marked:
        for line in _unmarked(body[name], marks):
            result.problems.append(f"{name}: fact without a certainty mark: `{line.strip()}`")

    entries = []
    for line in body["Outside writes"]:
        if not line.strip():
            continue
        entry = ENTRY.match(line.strip())
        if entry and entry.group(1) in kinds:
            entries.append(entry.group(1))
        else:
            result.problems.append(f"Outside writes: entry outside the grammar: `{line.strip()}`")

    result.missing = list(dict.fromkeys(result.missing))
    result.ok = not result.missing and not result.problems
    if result.verdict:
        result.state = _state(result.verdict, "Approval" in filled, entries)
    return result


def _unmarked(lines, marks):
    """Lines that open a fact without one of `marks`."""
    fenced = False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line.strip() or line[:1].isspace():
            continue
        item = re.match(r"^[-*]\s+(\[[^\]]*\])", line)
        if not item or item.group(1) not in marks:
            yield line


def _state(verdict, approved, kinds):
    for kind, state in STATE_BY_KIND:
        if kind in kinds:
            return state
    return "Approved" if approved else STATE_BY_VERDICT[verdict]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Accept or refuse a DIAGNOSIS.md.")
    parser.add_argument("path")
    parser.add_argument("--format", dest="format_path")
    args = parser.parse_args(argv)
    try:
        result = check_diagnosis(args.path, args.format_path)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"DIAGNOSIS: unreadable — {e}", file=sys.stderr)
        return 2
    if result.ok:
        print(f"DIAGNOSIS: accept — verdict {result.verdict}, state {result.state}")
        return 0
    print("DIAGNOSIS: refuse")
    for name in result.missing:
        print(f"missing: {name}")
    for problem in result.problems:
        print(f"problem: {problem}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

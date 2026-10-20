#!/usr/bin/env afk-python
"""Accept or refuse a DIAGNOSIS.md, and derive the bug's state from it.

Usage: check_diagnosis.py <path to DIAGNOSIS.md> [--format <DIAGNOSIS-FORMAT.md>]

The parts, the required parts per verdict, the certainty marks, the outside
write kinds and the state rows come from the tables of DIAGNOSIS-FORMAT.md
(beside this script's folder). Nothing is written. Exit 0 accept, 1 refuse,
2 unreadable input or format file.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from diagnosis_file import (  # noqa: E402
    entry_problem, load_format, outside_write_kinds, repeated, sections, table)

VERDICT = re.compile(r"^V-(\d+)\b")
ITEM = re.compile(r"^[-*]\s+(.*)$")


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
    rules = state_rules(fmt, kinds)

    text = Path(path).read_text(encoding="utf-8")
    found = sections(text)
    body = {name: found.get(name.lower(), []) for name in parts}
    filled = {name for name, lines in body.items() if any(line.strip() for line in lines)}
    result = Result(ok=False)
    lowered = {name.lower(): name for name in parts}
    for name in repeated(text):
        if name in lowered:
            result.problems.append(f"part `{lowered[name]}` appears more than once")

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
        item = ITEM.match(line.strip())
        problem = entry_problem(item.group(1), kinds) if item else "not a list item"
        if problem:
            result.problems.append(f"Outside writes: entry outside the grammar: `{line.strip()}` ({problem})")
        else:
            entries.append(item.group(1).split(":", 1)[0])

    if result.verdict:
        result.state = _state(rules, result.verdict, "Approval" in filled, entries)
        if result.state is None:
            result.problems.append(f"verdict {result.verdict} matches no row of the State table")
    result.missing = list(dict.fromkeys(result.missing))
    result.ok = not result.missing and not result.problems
    return result


def state_rules(fmt, kinds):
    """(state, outside-write kinds, verdicts, needs approval) per State row, in table order."""
    rules = []
    for state, source in table(fmt, "State"):
        named = set(re.findall(r"`([a-z][a-z-]*)`", source)) & kinds
        verdicts = set(re.findall(r"\bV-\d+\b", source))
        approval = "Approval" in source
        if not (named or verdicts or approval):
            raise ValueError(f"State row `{state}` names no outside-write kind, verdict or Approval")
        rules.append((state, named, verdicts, approval))
    return rules


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


def _state(rules, verdict, approved, kinds):
    """First State row that matches wins; None when no row does."""
    for state, named, verdicts, approval in rules:
        if named & set(kinds) or verdict in verdicts or (approval and approved):
            return state
    return None


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

#!/usr/bin/env python3
"""Check that every seam row of an SDD cites an investigation that closed.

Reads the §14 table of `SDD.md`, resolves each `INV-NNN` it cites against
`{spec-dir}/investigations/INV-NNN-*/COVERAGE.json`, and validates that ledger
with `validate_coverage.py` — the one checker of the ledger grammar
(`skills/utils/investigate/LEDGER-FORMAT.md`).

Usage:
  check_sdd_investigations.py --sdd SDD.md [--investigations DIR]

`--investigations` defaults to `investigations/` beside the SDD.

Exit codes:
  0  every row cites a ledger that closed. A ledger carrying `unverified`
     claims that are not load-bearing is printed, not refused.
  1  a row cites nothing, cites a ledger that is missing, structurally
     broken, `partial`, or carrying a load-bearing `unverified` claim.
  2  usage: the SDD is unreadable, or it has no §14 table.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

SECTION = re.compile(r"^##\s*§?14\b", re.M)
NEXT_SECTION = re.compile(r"^##\s", re.M)
CITATION = re.compile(r"INV-(\d{3,})")
CLOSED = ("closed", "closed-with-frontier")


def plugin_root() -> Path:
    """The installed plugin root, checked rather than counted to."""
    candidates = []
    env = os.environ.get("AFK_PLUGIN_ROOT")
    if env:
        candidates.append(Path(env))
    candidates += list(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "skills" / "utils" / "investigate" / "scripts"
                / "validate_coverage.py").is_file():
            return candidate
    raise RuntimeError("cannot locate the plugin root; set AFK_PLUGIN_ROOT")


def load_validator():
    path = (plugin_root() / "skills" / "utils" / "investigate" / "scripts"
            / "validate_coverage.py")
    spec = importlib.util.spec_from_file_location("validate_coverage", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seam_rows(text: str) -> list[str]:
    """The body rows of the §14 table, header and separator dropped."""
    match = SECTION.search(text)
    if not match:
        return []
    rest = text[match.end():]
    following = NEXT_SECTION.search(rest)
    body = rest[:following.start()] if following else rest
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells and cells[0].lower().startswith("seam"):
            continue
        rows.append(line)
    return rows


def ledger_of(root: Path, number: str) -> Path | None:
    matches = sorted(root.glob(f"INV-{number}-*/COVERAGE.json"))
    return matches[0] if matches else None


def check(sdd: Path, investigations: Path) -> tuple[list[str], list[str]]:
    """Returns the rows that refuse, and the notes that only print."""
    text = sdd.read_text(encoding="utf-8")
    rows = seam_rows(text)
    if not rows:
        raise RuntimeError(f"{sdd}: no §14 seam table to check")
    validator = load_validator()
    refusals: list[str] = []
    notes: list[str] = []
    for line in rows:
        name = [cell.strip() for cell in line.strip("|").split("|")][0]
        # One row may cite the same investigation in two cells; it is one
        # ledger, and one line about it.
        citations = list(dict.fromkeys(CITATION.findall(line)))
        if not citations:
            refusals.append(f"{name}: cites no investigation")
            continue
        for number in citations:
            path = ledger_of(investigations, number)
            if path is None:
                refusals.append(f"{name}: INV-{number} has no ledger under {investigations}")
                continue
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as problem:
                refusals.append(f"{name}: INV-{number} cannot be read: {problem}")
                continue
            defects, verdict = validator.validate(document)
            if defects:
                refusals.append(f"{name}: INV-{number} is structurally broken: {defects[0]}")
                continue
            if verdict not in CLOSED:
                refusals.append(f"{name}: INV-{number} is {verdict}")
                continue
            for claim in document.get("claims") or []:
                if not isinstance(claim, dict) or claim.get("kind") != "unverified":
                    continue
                if claim.get("load_bearing"):
                    refusals.append(
                        f"{name}: INV-{number} rests on an unverified claim: "
                        f"{claim.get('text')}")
                else:
                    notes.append(f"{name}: INV-{number} left unverified: {claim.get('text')}")
    return refusals, notes


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdd", required=True)
    parser.add_argument("--investigations")
    args = parser.parse_args(argv)
    sdd = Path(args.sdd)
    investigations = Path(args.investigations) if args.investigations \
        else sdd.parent / "investigations"
    try:
        refusals, notes = check(sdd, investigations)
    except (OSError, RuntimeError) as problem:
        print(f"check_sdd_investigations: {problem}", file=sys.stderr)
        return 2
    for note in notes:
        print(f"unverified, not load-bearing — {note}")
    if refusals:
        for refusal in refusals:
            print(f"blocker — {refusal}")
        print(f"check_sdd_investigations: {len(refusals)} seam rows do not carry a "
              "closed investigation")
        return 1
    print("check_sdd_investigations: every seam row cites a closed investigation")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

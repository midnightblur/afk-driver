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
  0  every row cites a ledger that closed. Notes print rather than refuse: an
     `unverified` claim nothing rests on, a class a ledger stopped at, and a
     ledger traced at a snapshot the tree has moved off.
  1  a row cites nothing, cites a ledger that is missing, ambiguous,
     structurally broken, `partial`, carrying a load-bearing `unverified`
     claim, or resting a load-bearing claim only on nodes the run never
     reached.
  2  usage: the SDD is unreadable, or its §14 table is missing or has drifted
     from `SDD-TEMPLATE.md`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SECTION = re.compile(r"^##\s*§?14\b", re.M)
NEXT_SECTION = re.compile(r"^##\s", re.M)
CITATION = re.compile(r"INV-(\d{3,})")
CLOSED = ("closed", "closed-with-frontier")

# What a seam row rests on: what the symbol is (Q1), what reaches it (Q2), and
# what changing it breaks (Q3). Question types are defined in `INVESTIGATION.md`.
SEAM_QUESTIONS = ("Q1", "Q2", "Q3")
# The §14 columns of `SDD-TEMPLATE.md`, lowercased; the first names the seam.
HEADER_CELLS = ("seam", "existing contract", "planned change", "impacted flows",
                "conventions", "verdict")
# The two cells a design cannot leave unclosed: what the seam is, and what else
# runs through it.
REQUIRE_CITATION = ("existing contract", "impacted flows")


class Ambiguous(RuntimeError):
    """One `INV-NNN` resolves to more than one ledger."""


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


def cells_of(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def seam_table(text: str) -> tuple[list[str], int]:
    """The §14 data rows and the column the seam is named in.

    The header is the one row above the `---` separator, and its cells are
    matched against the §14 columns of `SDD-TEMPLATE.md`; every row below the
    separator is data, whatever it starts with.
    """
    match = SECTION.search(text)
    if not match:
        return [], 0
    rest = text[match.end():]
    following = NEXT_SECTION.search(rest)
    body = rest[:following.start()] if following else rest
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith("|")]
    separators = [index for index, line in enumerate(lines) if set(line) <= set("|-: ")]
    if not separators:
        raise RuntimeError("the §14 table has no `---` separator row")
    separator = separators[0]
    if separator == 0:
        raise RuntimeError("the §14 table has no header row above its separator")
    header = [cell.lower() for cell in cells_of(lines[separator - 1])]
    missing = [column for column in HEADER_CELLS
               if not any(column in cell for cell in header)]
    if missing:
        raise RuntimeError(
            f"the §14 header names {header}, which does not carry "
            f"{', '.join(missing)}; it and `SDD-TEMPLATE.md` §14 have drifted apart")
    index_of = {column: next(index for index, cell in enumerate(header) if column in cell)
                for column in HEADER_CELLS}
    rows = [line for line in lines[separator + 1:] if not set(line) <= set("|-: ")]
    return rows, index_of


def ledger_of(root: Path, number: str) -> Path:
    """The one ledger `INV-NNN` names; two of them name nothing."""
    matches = sorted(root.glob(f"INV-{number}-*/COVERAGE.json"))
    if len(matches) > 1:
        raise Ambiguous(", ".join(sorted(path.parent.name for path in matches)))
    return matches[0] if matches else None


def subjects(document: dict) -> list[str]:
    """Every name the run answered under: its subjects and their declared forms."""
    run = document.get("run") or {}
    found: list[str] = []
    subject = run.get("subject")
    for item in ([subject] if isinstance(subject, str) else (subject or [])):
        if isinstance(item, str):
            found.append(item)
    found += [item for item in (run.get("roots") or []) if isinstance(item, str)]
    aliases = run.get("aliases")
    if isinstance(aliases, dict):
        for key, forms in aliases.items():
            found.append(key)
            for form in forms if isinstance(forms, list) else []:
                value = form.get("value") if isinstance(form, dict) else form
                if isinstance(value, str):
                    found.append(value)
    return [item for item in dict.fromkeys(found) if item.strip()]


def tokens(text: str) -> str:
    """The words of a name, so a match lands on a name and not on a fragment."""
    return " ".join(re.findall(r"[A-Za-z0-9_]+", text.lower()))


def names(document: dict, seam: str) -> bool:
    """Whether the ledger answered about the symbol this row names.

    Whole names only: a subject is this seam's, or a run of whole words inside
    it. A shared fragment is two names that start alike, not one answer.
    """
    haystack = tokens(seam)
    for item in subjects(document):
        for candidate in (item, item.rsplit(".", 1)[-1]):
            want = tokens(candidate)
            if want and re.search(rf"(?:^| ){re.escape(want)}(?: |$)", haystack):
                return True
    return False


def current_head(start: Path) -> str | None:
    """The snapshot the SDD is read against, when there is a repository to ask."""
    try:
        result = subprocess.run(["git", "-C", str(start), "rev-parse", "HEAD"],
                                capture_output=True, encoding="utf-8", errors="replace")
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def check(sdd: Path, investigations: Path) -> tuple[list[str], list[str]]:
    """Returns the rows that refuse, and the notes that only print."""
    try:
        text = sdd.read_text(encoding="utf-8")
    except UnicodeDecodeError as problem:
        raise RuntimeError(f"{sdd}: is not UTF-8 text: {problem}") from problem
    rows, index_of = seam_table(text)
    if not rows:
        raise RuntimeError(f"{sdd}: no §14 seam table to check")
    validator = load_validator()
    head = current_head(sdd.parent if sdd.parent.is_dir() else Path.cwd())
    refusals: list[str] = []
    notes: list[str] = []
    for line in rows:
        cells = cells_of(line)

        def cell(column: str) -> str:
            index = index_of[column]
            return cells[index] if index < len(cells) else ""

        name = cell(HEADER_CELLS[0]) or line
        # Each required cell answers for itself: one citation cannot close both
        # what the seam is today and what else runs through it.
        uncited = [column for column in REQUIRE_CITATION if not CITATION.search(cell(column))]
        if uncited:
            refusals.append(f"{name}: {' and '.join(uncited)} cites no investigation")
            continue
        # One row may cite the same investigation in two cells; it is one
        # ledger, and one line about it.
        citations = list(dict.fromkeys(CITATION.findall(line)))
        # A seam is what it is, what reaches it, and what changing it breaks.
        # One ledger may answer all three; between them the row's citations
        # have to.
        answered: set[str] = set()
        for number in citations:
            try:
                path = ledger_of(investigations, number)
            except Ambiguous as problem:
                refusals.append(
                    f"{name}: INV-{number} names more than one ledger ({problem}); "
                    "a citation resolves to one investigation")
                continue
            if path is None:
                refusals.append(f"{name}: INV-{number} has no ledger under {investigations}")
                continue
            try:
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as problem:
                refusals.append(f"{name}: INV-{number} cannot be read: {problem}")
                continue
            if not names(document, name):
                refusals.append(
                    f"{name}: INV-{number} investigated {', '.join(subjects(document)) or 'nothing named'}, "
                    "so its citation does not name this seam")
                continue
            answered.update(item for item in ((document.get("run") or {}).get("type") or [])
                            if isinstance(item, str))
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
                    notes.append(f"{name}: INV-{number} left unverified, not "
                                 f"load-bearing: {claim.get('text')}")
            frontier_nodes = {
                node.get("id") for node in document.get("nodes") or []
                if isinstance(node, dict)
                and (node.get("class") == "B14" or node.get("disposition") == "frontier")}
            for claim in document.get("claims") or []:
                if not isinstance(claim, dict) or not claim.get("load_bearing"):
                    continue
                supporting = [item for item in (claim.get("supporting_nodes") or [])
                              if isinstance(item, str)]
                outside = [item for item in supporting if item in frontier_nodes]
                if supporting and len(outside) == len(supporting):
                    refusals.append(
                        f"{name}: INV-{number} rests on a claim whose every support is "
                        f"outside what the run reached: {claim.get('text')}")
                elif outside:
                    notes.append(
                        f"{name}: INV-{number} rests partly outside what the run "
                        f"reached ({', '.join(outside)}): {claim.get('text')}")
            for row in document.get("boundaries") or []:
                if isinstance(row, dict) and row.get("status") == "frontier":
                    notes.append(f"{name}: INV-{number} stops at {row.get('class')}: "
                                 f"{row.get('reason') or 'declared out of scope'}")
            ledger_head = (document.get("run") or {}).get("head")
            if head and ledger_head and ledger_head != head:
                notes.append(f"{name}: INV-{number} was traced at {ledger_head[:12]}, "
                             f"and the tree is at {head[:12]}")
        unanswered = [item for item in SEAM_QUESTIONS if item not in answered]
        if citations and unanswered:
            refusals.append(
                f"{name}: its investigations answer no {', '.join(unanswered)} question; "
                "a seam row rests on what the symbol is, what reaches it, and what "
                "changing it breaks")
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
        print(f"note — {note}")
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

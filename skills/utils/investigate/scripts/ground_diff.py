#!/usr/bin/env python3
"""Compare two coverage ledgers over the ground they searched.

A cited investigation is a snapshot of one commit. This answers one question
about a later commit: does the tree still hold the lines that investigation
closed? It reads, compares, and reports — it never writes a ledger, because
`/afk:investigate` is the ledger's single writer.

Usage:
  ground_diff.py --cited CITED.json --current CURRENT.json [--class B1 ...]

Nodes are compared as a multiset keyed (`class`, file, `line_hash`) — the key
`LEDGER-FORMAT.md` § "Nodes" states. A count, not a set: two identical lines are
two hits, and losing one is drift. Nodes an agent read (`query_id: null`) carry
no matched line and are not ground.

Exit codes: 0 the ground held, 1 it moved (every difference printed), 2 usage
or a ledger that cannot be read.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


def load(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"{path}: cannot read: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: not JSON: {error}") from error
    if not isinstance(document, dict):
        raise ValueError(f"{path}: a ledger is one object")
    return document


def ground(document: dict, classes: list[str] | None) -> collections.Counter:
    """Every searched line the ledger holds, counted."""
    counted: collections.Counter = collections.Counter()
    for row in document.get("nodes") or []:
        if not isinstance(row, dict) or not row.get("line_hash"):
            continue
        klass, site = row.get("class"), row.get("site") or ""
        if classes and klass not in classes:
            continue
        counted[(klass, site.rsplit(":", 1)[0], row["line_hash"])] += 1
    return counted


def capped(document: dict, classes: list[str] | None) -> list[str]:
    """The classes whose row holds the cap rather than the ground."""
    return sorted({row.get("class") for row in document.get("boundaries") or []
                   if isinstance(row, dict) and row.get("truncated")
                   and (not classes or row.get("class") in classes)})


def differences(cited: dict, current: dict, classes: list[str] | None) -> list[str]:
    lines = [f"! {klass}: the cited row is truncated, so it holds the cap rather "
             "than the ground; re-trace the class" for klass in capped(cited, classes)]
    before, after = ground(cited, classes), ground(current, classes)
    for key in sorted(set(before) | set(after)):
        was, now = before[key], after[key]
        if was == now:
            continue
        klass, file, line = key
        mark = "+" if now > was else "-"
        lines.append(f"{mark} {klass} {file} {line}: {was} -> {now}")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cited", required=True, help="the ledger the design cites")
    parser.add_argument("--current", required=True,
                        help="a ledger or seed map taken at the current head")
    parser.add_argument("--class", dest="classes", action="append", default=[],
                        help="compare only this boundary class; repeat for each")
    args = parser.parse_args(argv)
    try:
        cited, current = load(Path(args.cited)), load(Path(args.current))
    except ValueError as problem:
        print(f"ground_diff: {problem}", file=sys.stderr)
        return 2
    lines = differences(cited, current, args.classes or None)
    if lines:
        for line in lines:
            print(line)
        print(f"ground_diff: the ground moved in {len(lines)} places")
        return 1
    print("ground_diff: the ground held")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

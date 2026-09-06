#!/usr/bin/env python3
"""Validate a coverage ledger before its answer is published as closed.

Checks the mechanical half of the completion contract `INVESTIGATION.md`
(plugin root) defines. Grammar of the file it reads: `LEDGER-FORMAT.md`
beside this script.

Usage: validate_coverage.py --ledger COVERAGE.json

Exit codes: 0 valid, 1 invalid (one defect per line on stderr), 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TABLES = ("run", "boundaries", "nodes", "queries", "claims", "counter_checks")
ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))
BOUNDARY_STATUSES = {"closed", "n/a", "frontier", "unverified", "judgment-only"}
TERMINAL_DISPOSITIONS = {"traced", "terminal", "irrelevant", "frontier", "unverified"}
CLAIM_KINDS = {"fact", "inference", "unverified"}
COUNTER_SEARCH_TYPES = {"Q2", "Q3", "Q5"}


def validate(ledger: dict) -> list[str]:
    defects: list[str] = []

    for table in TABLES:
        if table not in ledger:
            defects.append(f"{table}: table missing")
    if defects:
        return defects

    # `run` is a single object. A one-element array is the shape a writer
    # reaches for when the other five keys are arrays, so it is accepted and
    # named rather than failing the whole ledger on a wrapper.
    run = ledger["run"]
    if isinstance(run, list):
        defects.append("run: must be a single object, not an array")
        run = run[0] if run else {}
    elif not isinstance(run, dict):
        defects.append("run: must be a single object")
        run = {}
    for field in ("repository", "head", "question", "type", "roots", "aliases",
                  "inventory_hash", "inventory_count"):
        if run.get(field) in (None, "", []):
            defects.append(f"run.{field}: required")

    seen = {}
    for row in ledger["boundaries"]:
        klass = row.get("class")
        seen[klass] = row
        status = row.get("status")
        if status not in BOUNDARY_STATUSES:
            defects.append(f"boundaries.{klass}: {status!r} is not a boundary status")
        elif status != "closed" and not row.get("reason"):
            defects.append(f"boundaries.{klass}: status {status} needs a reason")
    for klass in ALL_CLASSES:
        if klass not in seen:
            defects.append(f"boundaries.{klass}: no verdict; a skipped class reads as an absence")

    node_ids = set()
    for row in ledger["nodes"]:
        node_id = row.get("id")
        node_ids.add(node_id)
        disposition = row.get("disposition")
        if disposition not in TERMINAL_DISPOSITIONS:
            defects.append(f"nodes.{node_id}: {disposition!r} is not a disposition")
        if disposition in ("irrelevant", "frontier", "unverified") and not row.get("evidence"):
            defects.append(f"nodes.{node_id}: disposition {disposition} needs evidence")
        if run.get("type") == "Q3" and row.get("verdict") not in ("breaks", "unchanged", "unverified"):
            defects.append(f"nodes.{node_id}: a Q3 node needs a breaks/unchanged/unverified verdict")
        if run.get("type") == "Q4" and row.get("verdict") not in ("code", "test", "gap"):
            defects.append(f"nodes.{node_id}: a Q4 node needs a code/test/gap verdict")

    for index, row in enumerate(ledger["claims"]):
        where = f"claims[{index}]"
        kind = row.get("kind")
        if kind not in CLAIM_KINDS:
            defects.append(f"{where}: {kind!r} is not a claim kind")
        if not row.get("load_bearing"):
            continue
        if kind == "fact" and not row.get("citations"):
            defects.append(f"{where}: a load-bearing fact needs at least one citation")
        if kind == "unverified" and not row.get("text"):
            defects.append(f"{where}: an unverified claim states its reason")
        for node in row.get("supporting_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: supporting node {node!r} is not in the nodes table")

    needs_counter = run.get("type") in COUNTER_SEARCH_TYPES or bool(run.get("design_phase"))
    checks = ledger["counter_checks"]
    if needs_counter and not checks:
        defects.append("counter_checks: this run type requires a counter-search; none recorded")
    for index, row in enumerate(checks):
        if row.get("state") not in ("pending", "complete"):
            defects.append(f"counter_checks[{index}]: state must be pending or complete")
        elif needs_counter and row.get("state") != "complete":
            defects.append(f"counter_checks[{index}]: still pending; the queue is not closed")

    return defects


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(add_help=True, description=__doc__)
    parser.add_argument("--ledger", required=True)
    args = parser.parse_args(argv)

    path = Path(args.ledger)
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as problem:
        sys.stderr.write(f"validate_coverage: cannot read {path}: {problem}\n")
        return 2

    defects = validate(ledger)
    for defect in defects:
        sys.stderr.write(f"validate_coverage: {defect}\n")
    if defects:
        sys.stdout.write(f"validate_coverage: invalid — {len(defects)} defect(s)\n")
        return 1
    boundaries = ledger["boundaries"]
    closed = sum(1 for row in boundaries if row.get("status") == "closed")
    sys.stdout.write(
        f"validate_coverage: valid — {closed}/{len(boundaries)} classes closed, "
        f"{len(ledger['nodes'])} nodes, {len(ledger['claims'])} claims\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

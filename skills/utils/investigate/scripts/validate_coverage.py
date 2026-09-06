#!/usr/bin/env python3
"""Validate a coverage ledger, and compute the verdict its answer may claim.

Checks the mechanical half of the completion contract `INVESTIGATION.md`
(plugin root) defines. Grammar of the file it reads: `LEDGER-FORMAT.md`
beside this script.

Usage: validate_coverage.py --ledger COVERAGE.json

Prints one `VERDICT: closed|closed-with-frontier|partial` line and one line per
defect. The reply keys on the VERDICT line, never on the exit code: a ledger
can be structurally perfect and still be `partial`.

Exit codes: 0 structurally valid (any verdict), 1 structurally invalid,
2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TABLES = ("run", "boundaries", "nodes", "queries", "claims", "counter_checks")
ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))

# `judgment-only` is a seed-stage status: a site an agent still has to read.
# A tracer resolves it to closed or unverified; it is never a final status.
FINAL_STATUSES = {"closed", "partial", "n/a", "frontier", "unverified"}
SEED_STATUSES = FINAL_STATUSES | {"judgment-only"}
DISPOSITIONS = {"traced", "terminal", "irrelevant", "frontier", "unverified"}
NEED_REASON = {"frontier", "unverified"}
NEED_EVIDENCE = {"irrelevant", "frontier", "unverified"}
CLAIM_KINDS = {"fact", "inference", "unverified"}
AGENT_COUNTER_TYPES = {"Q2", "Q3", "Q5"}
VERDICTS = ("closed", "closed-with-frontier", "partial")


def types_of(run: dict) -> list[str]:
    """`run.type` is a list — a question matching two types runs as both."""
    raw = run.get("type")
    if isinstance(raw, str):
        return [raw]
    return [item for item in (raw or []) if isinstance(item, str)]


def validate(ledger: dict) -> tuple[list[str], str]:
    defects: list[str] = []

    for table in TABLES:
        if table not in ledger:
            defects.append(f"{table}: table missing")
    if defects:
        return defects, "partial"

    # `run` is a single object. A one-element array is the shape a writer
    # reaches for when the other five keys are arrays, so it is named rather
    # than failing every downstream check on a wrapper.
    run = ledger["run"]
    if isinstance(run, list):
        defects.append("run: must be a single object, not an array")
        run = run[0] if run else {}
    elif not isinstance(run, dict):
        defects.append("run: must be a single object")
        run = {}
    for field in ("repository", "head", "question", "type", "roots", "aliases",
                  "inventory_hash", "inventory_count"):
        if run.get(field) in (None, "", [], {}):
            defects.append(f"run.{field}: required")
    qtypes = types_of(run)
    for qtype in qtypes:
        if qtype not in {f"Q{n}" for n in range(1, 6)}:
            defects.append(f"run.type: {qtype!r} is not Q1-Q5")

    nodes = ledger["nodes"]
    node_ids: set[str] = set()
    open_nodes = 0
    frontier_nodes = 0
    for index, row in enumerate(nodes):
        node_id = row.get("id")
        where = f"nodes.{node_id or index}"
        if not node_id:
            defects.append(f"nodes[{index}]: id required; boundary rows point at it")
        elif node_id in node_ids:
            defects.append(f"{where}: duplicate node id")
        node_ids.add(node_id)
        if not row.get("site"):
            defects.append(f"{where}: site required (file:line)")
        if row.get("class") not in ALL_CLASSES:
            defects.append(f"{where}: class must be one of B1-B14")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            defects.append(f"{where}: {disposition!r} is not a disposition")
        if disposition in NEED_REASON and not row.get("reason"):
            defects.append(f"{where}: disposition {disposition} needs a reason")
        if disposition in NEED_EVIDENCE and not row.get("evidence"):
            defects.append(f"{where}: disposition {disposition} needs evidence")
        if disposition == "unverified":
            open_nodes += 1
        if disposition == "frontier":
            frontier_nodes += 1
        # A node nobody has judged yet carries no verdict; a judged one must.
        if disposition != "unverified":
            if "Q3" in qtypes:
                if row.get("verdict") not in ("breaks", "unchanged", "unverified"):
                    defects.append(f"{where}: a Q3 node needs a breaks/unchanged/unverified verdict")
                if not row.get("pinned_by"):
                    defects.append(f"{where}: a Q3 node names the test that pins it, or `unguarded`")
            if "Q4" in qtypes and row.get("verdict") not in ("code", "test", "gap"):
                defects.append(f"{where}: a Q4 node needs a code/test/gap verdict")

    seen: dict[str, dict] = {}
    open_classes = 0
    frontier_classes = 0
    for row in ledger["boundaries"]:
        klass = row.get("class")
        seen[klass] = row
        status = row.get("status")
        if status not in SEED_STATUSES:
            defects.append(f"boundaries.{klass}: {status!r} is not a boundary status")
        elif status == "judgment-only":
            defects.append(
                f"boundaries.{klass}: judgment-only is a seed status; a tracer resolves it "
                "to closed or unverified before the ledger is published"
            )
        elif status != "closed" and not row.get("reason"):
            defects.append(f"boundaries.{klass}: status {status} needs a reason")
        if not isinstance(row.get("hits"), int):
            defects.append(f"boundaries.{klass}: hits is a count")
        for node_id in row.get("hit_ids") or []:
            if node_id not in node_ids:
                defects.append(f"boundaries.{klass}: hit_id {node_id!r} is not in the nodes table")
        if status in ("unverified", "partial", "judgment-only"):
            open_classes += 1
        elif status == "frontier":
            frontier_classes += 1
    for klass in ALL_CLASSES:
        if klass not in seen:
            defects.append(f"boundaries.{klass}: no verdict; a skipped class reads as an absence")

    claim_ids: set[str] = set()
    for index, row in enumerate(ledger["claims"]):
        claim_id = row.get("id")
        where = f"claims.{claim_id or index}"
        if not claim_id:
            defects.append(f"claims[{index}]: id required; a counter-check points at it")
        elif claim_id in claim_ids:
            defects.append(f"{where}: duplicate claim id")
        claim_ids.add(claim_id)
        kind = row.get("kind")
        if kind not in CLAIM_KINDS:
            defects.append(f"{where}: {kind!r} is not a claim kind")
        if not row.get("text"):
            defects.append(f"{where}: text required")
        for node in row.get("supporting_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: supporting node {node!r} is not in the nodes table")
        if not row.get("load_bearing"):
            continue
        if kind in ("fact", "inference") and not row.get("citations"):
            defects.append(
                f"{where}: a load-bearing {kind} names what it rests on — at least one citation"
            )

    checks = ledger["counter_checks"]
    complete = [row for row in checks if row.get("state") == "complete"]
    pending = 0
    for index, row in enumerate(checks):
        where = f"counter_checks[{index}]"
        if not row.get("method"):
            defects.append(f"{where}: method required — the different method that ran")
        if row.get("kind") not in ("deterministic", "agent"):
            defects.append(f"{where}: kind must be deterministic or agent")
        state = row.get("state")
        if state not in ("pending", "complete"):
            defects.append(f"{where}: state must be pending or complete")
        elif state == "pending":
            pending += 1
            if not row.get("reason"):
                defects.append(f"{where}: a pending counter-search states why it did not run")
        for node in row.get("new_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: new node {node!r} is not in the nodes table")
        for claim in row.get("targeted_claims") or []:
            if claim not in claim_ids:
                defects.append(f"{where}: targeted claim {claim!r} is not in the claims table")
    if not complete:
        defects.append(
            "counter_checks: every question type needs one complete counter-search; none recorded"
        )
    if (set(qtypes) & AGENT_COUNTER_TYPES) or run.get("design_phase"):
        if not [row for row in complete if row.get("kind") == "agent"]:
            defects.append(
                "counter_checks: this run needs a complete agent-driven counter-search "
                "(INVESTIGATION.md § Counter-search)"
            )

    if defects:
        verdict = "partial"
    elif open_classes or open_nodes or pending:
        verdict = "partial"
    elif frontier_classes or frontier_nodes:
        verdict = "closed-with-frontier"
    else:
        verdict = "closed"

    claimed = run.get("verdict")
    if claimed in VERDICTS and claimed != verdict:
        defects.append(f"run.verdict: says {claimed}, the ledger computes {verdict}")

    return defects, verdict


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

    defects, verdict = validate(ledger)
    for defect in defects:
        sys.stderr.write(f"validate_coverage: {defect}\n")
    sys.stdout.write(f"VERDICT: {verdict}\n")
    if defects:
        sys.stdout.write(f"validate_coverage: invalid — {len(defects)} defect(s)\n")
        return 1
    boundaries = ledger["boundaries"]
    closed = sum(1 for row in boundaries if row.get("status") in ("closed", "n/a"))
    sys.stdout.write(
        f"validate_coverage: valid — {closed}/{len(boundaries)} classes closed, "
        f"{len(ledger['nodes'])} nodes, {len(ledger['claims'])} claims\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

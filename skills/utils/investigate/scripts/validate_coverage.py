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
import re
import sys
from pathlib import Path

TABLES = ("run", "boundaries", "nodes", "queries", "claims", "counter_checks")
ALL_CLASSES = tuple(f"B{n}" for n in range(1, 15))
QTYPES = {f"Q{n}" for n in range(1, 6)}

# `judgment-only` is a seed-stage status: a site an agent still has to read.
# A tracer resolves it to closed or unverified; it is never a final status.
FINAL_STATUSES = {"closed", "partial", "n/a", "frontier", "unverified"}
SEED_STATUSES = FINAL_STATUSES | {"judgment-only"}
DISPOSITIONS = {"traced", "terminal", "irrelevant", "frontier", "unverified"}
NEED_REASON = {"frontier", "unverified"}
CLAIM_KINDS = {"fact", "inference", "unverified"}
AGENT_COUNTER_TYPES = {"Q2", "Q3", "Q5"}
IMPACT_VERDICTS = {"breaks", "unchanged", "unverified"}
COVERAGE_VERDICTS = {"code", "test", "gap"}
VERDICTS = ("closed", "closed-with-frontier", "partial")

# Every field the format defines, per table. A key nobody defined is a field
# nobody validates, so it is refused rather than carried.
KEYS = {
    "top": set(TABLES) | {"partition"},
    "run": {"repository", "head", "question", "type", "roots", "aliases", "inventory_hash",
            "inventory_count", "design_phase", "verdict", "started", "finished", "config"},
    "boundaries": {"class", "status", "method", "hits", "truncated", "hit_ids", "mechanism",
                   "reason", "universe", "sites", "modules", "name_forms"},
    "nodes": {"id", "class", "site", "disposition", "reason", "impact_verdict",
              "coverage_verdict", "pinned_by", "evidence", "parent"},
    "queries": {"id", "command", "universe", "count", "evidence"},
    "claims": {"id", "text", "kind", "load_bearing", "supporting_nodes", "citations"},
    "counter_checks": {"method", "kind", "targeted_claims", "new_nodes", "state", "reason"},
}

TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")


def types_of(run: dict) -> list[str]:
    raw = run.get("type")
    return [item for item in (raw or []) if isinstance(item, str)] if isinstance(raw, list) else []


def unknown(defects: list[str], table: str, where: str, row: dict) -> None:
    for key in sorted(set(row) - KEYS[table]):
        defects.append(f"{where}: {key!r} is not a field this format defines")


def validate(ledger: dict) -> tuple[list[str], str]:
    defects: list[str] = []

    for table in TABLES:
        if table not in ledger:
            defects.append(f"{table}: table missing")
    if defects:
        return defects, "partial"
    unknown(defects, "top", "ledger", ledger)

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
    unknown(defects, "run", "run", run)
    for field in ("repository", "head", "question", "type", "roots", "aliases",
                  "inventory_hash", "inventory_count", "started", "finished"):
        if run.get(field) in (None, "", [], {}):
            defects.append(f"run.{field}: required")
    for field in ("started", "finished"):
        stamp = run.get(field)
        if stamp and not TIMESTAMP.match(str(stamp)):
            defects.append(f"run.{field}: {stamp!r} is not an ISO-8601 timestamp")
    if not isinstance(run.get("type"), list):
        defects.append("run.type: a list of question types, even when there is one")
    qtypes = types_of(run)
    for qtype in qtypes:
        if qtype not in QTYPES:
            defects.append(f"run.type: {qtype!r} is not Q1-Q5")

    nodes = ledger["nodes"]
    node_ids: set[str] = set()
    parents: set[str] = set()
    open_nodes = 0
    frontier_nodes = 0
    unresolved_verdicts = 0
    for index, row in enumerate(nodes):
        node_id = row.get("id")
        where = f"nodes.{node_id or index}"
        unknown(defects, "nodes", where, row)
        if not node_id:
            defects.append(f"nodes[{index}]: id required; boundary rows point at it")
        elif node_id in node_ids:
            defects.append(f"{where}: duplicate node id")
        node_ids.add(node_id)
        if row.get("parent"):
            parents.add(row["parent"])
        if not row.get("site"):
            defects.append(f"{where}: site required (file:line)")
        if row.get("class") not in ALL_CLASSES:
            defects.append(f"{where}: class must be one of B1-B14")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            defects.append(f"{where}: {disposition!r} is not a disposition")
        if disposition in NEED_REASON and not row.get("reason"):
            defects.append(f"{where}: disposition {disposition} needs a reason")
        if disposition != "unverified" and not row.get("evidence"):
            defects.append(f"{where}: disposition {disposition} needs evidence")
        if disposition == "unverified":
            open_nodes += 1
        if disposition == "frontier":
            frontier_nodes += 1
        # A node nobody has judged yet carries no verdict; a judged one must.
        if disposition != "unverified":
            if "Q3" in qtypes:
                if row.get("impact_verdict") not in IMPACT_VERDICTS:
                    defects.append(
                        f"{where}: a Q3 node needs impact_verdict breaks/unchanged/unverified")
                if not row.get("pinned_by"):
                    defects.append(f"{where}: a Q3 node names the test that pins it, or `unguarded`")
            if "Q4" in qtypes and row.get("coverage_verdict") not in COVERAGE_VERDICTS:
                defects.append(f"{where}: a Q4 node needs coverage_verdict code/test/gap")
        if row.get("impact_verdict") == "unverified":
            unresolved_verdicts += 1
    for row in nodes:
        if row.get("disposition") == "traced" and row.get("id") not in parents:
            defects.append(
                f"nodes.{row.get('id')}: traced with no child node; an edge to nowhere is "
                "`terminal` or `unverified`, never traced"
            )
    for parent in sorted(parents - node_ids):
        defects.append(f"nodes: parent {parent!r} is not in the nodes table")

    seen: dict[str, dict] = {}
    open_classes = 0
    frontier_classes = 0
    for row in ledger["boundaries"]:
        klass = row.get("class")
        where = f"boundaries.{klass}"
        unknown(defects, "boundaries", where, row)
        if klass in seen:
            defects.append(f"{where}: more than one row for this class")
        seen[klass] = row
        status = row.get("status")
        if status not in SEED_STATUSES:
            defects.append(f"{where}: {status!r} is not a boundary status")
        elif status == "judgment-only":
            defects.append(
                f"{where}: judgment-only is a seed status; a tracer resolves it "
                "to closed or unverified before the ledger is published"
            )
        elif status != "closed" and not row.get("reason"):
            defects.append(f"{where}: status {status} needs a reason")
        hits = row.get("hits")
        hit_ids = row.get("hit_ids") or []
        if not isinstance(hits, int):
            defects.append(f"{where}: hits is a count")
        elif row.get("truncated"):
            if hits < len(hit_ids):
                defects.append(f"{where}: hits {hits} is below its own {len(hit_ids)} node ids")
        elif hits != len(hit_ids):
            defects.append(
                f"{where}: hits {hits} disagrees with {len(hit_ids)} node ids; "
                "a capped row says `truncated: true`"
            )
        if len(set(hit_ids)) != len(hit_ids):
            defects.append(f"{where}: the same node id appears twice in hit_ids")
        for node_id in hit_ids:
            if node_id not in node_ids:
                defects.append(f"{where}: hit_id {node_id!r} is not in the nodes table")
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
        unknown(defects, "claims", where, row)
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
        if not isinstance(row.get("load_bearing"), bool):
            defects.append(f"{where}: load_bearing is true or false, never absent")
        supporting = row.get("supporting_nodes") or []
        for node in supporting:
            if node not in node_ids:
                defects.append(f"{where}: supporting node {node!r} is not in the nodes table")
        if kind == "fact" and not supporting:
            defects.append(f"{where}: a fact names at least one supporting node")
        if not row.get("load_bearing"):
            continue
        if kind in ("fact", "inference") and not row.get("citations"):
            defects.append(
                f"{where}: a load-bearing {kind} names what it rests on — at least one citation"
            )

    for index, row in enumerate(ledger["queries"]):
        unknown(defects, "queries", f"queries[{index}]", row)

    checks = ledger["counter_checks"]
    complete = [row for row in checks if row.get("state") == "complete"]
    pending = 0
    for index, row in enumerate(checks):
        where = f"counter_checks[{index}]"
        unknown(defects, "counter_checks", where, row)
        if not row.get("method"):
            defects.append(f"{where}: method required — the different method that ran")
        if row.get("kind") not in ("deterministic", "agent"):
            defects.append(f"{where}: kind must be deterministic or agent")
        state = row.get("state")
        targets = row.get("targeted_claims") or []
        if state not in ("pending", "complete"):
            defects.append(f"{where}: state must be pending or complete")
        elif state == "pending":
            pending += 1
            if not row.get("reason"):
                defects.append(f"{where}: a pending counter-search states why it did not run")
        elif not targets:
            defects.append(
                f"{where}: targeted_claims required — a counter-search that aimed at nothing "
                "broke nothing"
            )
        for node in row.get("new_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: new node {node!r} is not in the nodes table")
        for claim in targets:
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
    elif open_classes or open_nodes or pending or unresolved_verdicts:
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

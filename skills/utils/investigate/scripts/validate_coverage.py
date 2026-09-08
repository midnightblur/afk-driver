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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import (ALL_CLASSES, HIT_CAP, LINE_HASH_CHARS,  # noqa: E402
                      QUERY_ORIGINS, stable_id)

TABLES = ("run", "boundaries", "nodes", "queries", "claims", "counter_checks")
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
SITE = re.compile(r"[^:]+(?::[1-9][0-9]*)?")
LINE_HASH = re.compile(f"[0-9a-f]{{{LINE_HASH_CHARS}}}")

KEYS = {
    "top": set(TABLES) | {"partition"},
    "run": {"repository", "head", "question", "type", "roots", "aliases", "inventory_hash",
            "inventory_count", "design_phase", "verdict", "started", "finished",
            "config", "merged_from", "config_warnings"},
    "boundaries": {"class", "status", "method", "hits", "truncated", "hit_ids", "query_ids",
                   "mechanism", "reason", "universe", "sites", "modules", "name_forms"},
    "nodes": {"id", "class", "site", "disposition", "reason", "impact_verdict",
              "coverage_verdict", "pinned_by", "evidence", "parent", "query_id",
              "line_hash"},
    "queries": {"id", "command", "universe", "count", "evidence", "origin"},
    "claims": {"id", "text", "kind", "load_bearing", "supporting_nodes", "citations"},
    "counter_checks": {"method", "kind", "targeted_claims", "new_nodes", "state",
                       "reason", "classes", "query_ids", "evidence_nodes"},
}

TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")

# The type each field carries where the format states one. A field of the wrong
# type is a defect line, never a traceback: a ledger is read by a program that
# has to say what is wrong with it, not stop on it.
TYPES = {
    "boundaries": {"class": str, "status": str, "method": str, "hits": int,
                   "truncated": bool, "hit_ids": list, "query_ids": list,
                   "mechanism": str, "reason": str, "universe": str, "sites": list,
                   "modules": dict, "name_forms": dict},
    "nodes": {"id": str, "class": str, "site": str, "disposition": str, "reason": str,
              "impact_verdict": str, "coverage_verdict": str, "pinned_by": str,
              "evidence": str, "parent": str, "query_id": str, "line_hash": str},
    "queries": {"id": str, "command": str, "universe": str, "count": int,
                "origin": str,
                "evidence": str},
    "claims": {"id": str, "text": str, "kind": str, "load_bearing": bool,
               "supporting_nodes": list, "citations": list},
    "counter_checks": {"method": str, "kind": str, "targeted_claims": list,
                       "new_nodes": list, "state": str, "reason": str, "classes": list,
                       "query_ids": list, "evidence_nodes": list},
}


def typed(defects: list[str], table: str, where: str, row: dict) -> None:
    """Every field the format types, checked before anything reads it."""
    for key, kind in TYPES[table].items():
        value = row.get(key)
        if value is None:
            continue
        if kind is int and isinstance(value, bool):
            defects.append(f"{where}: {key} is a {kind.__name__}")
        elif not isinstance(value, kind):
            defects.append(f"{where}: {key} is a {kind.__name__}, not "
                           f"{type(value).__name__}")


def rows_of(defects: list[str], ledger: dict, table: str) -> list[dict]:
    """The rows that are objects; anything else is named and dropped."""
    kept = []
    for index, row in enumerate(ledger[table]):
        if isinstance(row, dict):
            kept.append(row)
        else:
            defects.append(f"{table}[{index}]: must be an object, not "
                           f"{type(row).__name__}")
    return kept


def runs_nothing(command: str) -> bool:
    """A search that returns nothing whatever the tree holds.

    A grep with no expression, and an expression quantified away, both count 0
    by construction. A check standing only on those weighed nothing against
    anything, so it is `pending` — a method that did not run.
    """
    text = command.strip()
    if not text:
        return True
    if re.search(r"\{\s*0\s*\}", text):
        return True
    return text.startswith("git grep") and " -e " not in text


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
    for table in TABLES[1:]:
        if not isinstance(ledger[table], list):
            defects.append(f"{table}: must be an array of rows")
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
    if not isinstance(run.get("design_phase"), bool):
        defects.append("run.design_phase: true or false, never absent - it decides "
                       "whether an agent-driven counter-search is owed")
    config = run.get("config")
    if not isinstance(config, dict) or not config.get("path") or not config.get("sha256"):
        defects.append("run.config: the configuration behind the run, as "
                       "{path, sha256}; one question over two configurations "
                       "is two different searches")
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
    for entry in (run.get("type") or []) if isinstance(run.get("type"), list) else []:
        if not isinstance(entry, str):
            defects.append(f"run.type: {entry!r} is not a question type; the rules a run "
                           "owes are read off this list")

    nodes = rows_of(defects, ledger, "nodes")
    node_ids: set[str] = set()
    parents: set[str] = set()
    open_nodes = 0
    frontier_nodes = 0
    unresolved_verdicts = 0
    for index, row in enumerate(nodes):
        node_id = row.get("id")
        where = f"nodes.{node_id or index}"
        unknown(defects, "nodes", where, row)
        typed(defects, "nodes", where, row)
        if node_id and row.get("class") and row.get("site") \
                and node_id != f"{row['class']}:{row['site']}":
            defects.append(f"{where}: a node id is class:file:line, so this one is not "
                           "a key two fragments can merge on")
        if "query_id" not in row:
            defects.append(f"{where}: query_id required - the search that produced it, "
                           "or null when an agent read it")
        # A searched node is compared across runs on its line, not its id, and
        # a comparison needs both sides written the same way.
        if isinstance(row.get("query_id"), str):
            digest = row.get("line_hash")
            if not isinstance(digest, str) or not digest.strip():
                defects.append(f"{where}: line_hash required on a node a search produced; "
                               "an id alone moves with every line inserted above it")
            elif not LINE_HASH.fullmatch(digest):
                defects.append(f"{where}: line_hash {digest!r} is not "
                               f"{LINE_HASH_CHARS} lowercase hex characters")
        if not node_id:
            defects.append(f"nodes[{index}]: id required; boundary rows point at it")
        elif node_id in node_ids:
            defects.append(f"{where}: duplicate node id")
        node_ids.add(node_id)
        if row.get("parent"):
            parents.add(row["parent"])
        site = row.get("site")
        if not site:
            defects.append(f"{where}: site required (a path, or path:line)")
        elif not isinstance(site, str) or not SITE.fullmatch(site):
            defects.append(f"{where}: site {site!r} is neither a path nor a path:line "
                           "with a positive line number, so nothing can key on it")
        if row.get("class") not in ALL_CLASSES:
            defects.append(f"{where}: class must be one of B1-B14")
        disposition = row.get("disposition")
        if disposition not in DISPOSITIONS:
            defects.append(f"{where}: {disposition!r} is not a disposition")
        if disposition in NEED_REASON and not row.get("reason"):
            defects.append(f"{where}: disposition {disposition} needs a reason")
        if disposition != "unverified" and not str(row.get("evidence") or "").strip():
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

    query_index: dict[str, dict] = {}
    for index, row in enumerate(rows_of(defects, ledger, "queries")):
        query_id = row.get("id")
        where = f"queries.{query_id or index}"
        unknown(defects, "queries", where, row)
        typed(defects, "queries", where, row)
        if not query_id:
            defects.append(f"queries[{index}]: id required; a boundary row points at it")
            continue
        if query_id in query_index:
            defects.append(f"{where}: duplicate query id")
        command, universe = row.get("command"), row.get("universe")
        # A query row is the record of one execution, so it carries one: what
        # ran, over what, and how much came back.
        if not isinstance(command, str) or not command.strip():
            defects.append(f"{where}: command required — the invocation that ran")
        if row.get("origin") not in QUERY_ORIGINS:
            defects.append(f"{where}: origin must be one of {', '.join(QUERY_ORIGINS)}; "
                           "only a seed query can be run again by a later pre-pass")
        if not isinstance(universe, str) or not universe.strip():
            defects.append(f"{where}: universe required — what the invocation searched")
        count = row.get("count")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            defects.append(f"{where}: count is how many the query returned, zero or more")
        if isinstance(command, str) and isinstance(universe, str):
            if query_id != stable_id("q", command + universe):
                defects.append(f"{where}: a query id is the digest of its command and "
                               "universe; this one cannot be recomputed")
        query_index[query_id] = row

    seen: dict[str, dict] = {}
    open_classes = 0
    frontier_classes = 0
    # The nodes an agent read rather than searched, by site, so a boundary row
    # claiming a read can be checked against one.
    read_nodes = {
        (row.get("class"), row["site"])
        for row in nodes
        if isinstance(row.get("site"), str) and row.get("query_id") is None
        and row.get("disposition") in ("traced", "terminal", "irrelevant")
        and str(row.get("evidence") or "").strip()
    }

    # Which nodes carry evidence, so a check claiming it read one can be held
    # to a node that records the reading.
    node_evidence = {row["id"]: bool(str(row.get("evidence") or "").strip())
                     for row in nodes if isinstance(row.get("id"), str)}
    read_node_ids = {row["id"] for row in nodes
                     if isinstance(row.get("id"), str) and row.get("query_id") is None}

    searched: dict[str, str] = {}
    for row in rows_of(defects, ledger, "boundaries"):
        klass = row.get("class")
        where = f"boundaries.{klass}"
        unknown(defects, "boundaries", where, row)
        typed(defects, "boundaries", where, row)
        if not row.get("universe"):
            defects.append(f"{where}: universe required - what the method searched")
        if not isinstance(row.get("method"), str) or not row.get("method", "").strip():
            defects.append(f"{where}: method required - how the class was enumerated, "
                           "or `none` when nothing ran")
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
            if status == "closed":
                defects.append(
                    f"{where}: truncated and closed; a row listing a sample of its hits "
                    "cannot say it enumerated the class — partial at best"
                )
            if len(hit_ids) != HIT_CAP or hits <= HIT_CAP:
                defects.append(
                    f"{where}: truncated says the {HIT_CAP}-node cap was reached — "
                    f"{len(hit_ids)} ids for {hits} hits records neither the cap nor the count"
                )
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
            elif not str(node_id).startswith(f"{klass}:"):
                defects.append(f"{where}: hit_id {node_id!r} is not of its own class")
        query_ids = row.get("query_ids") or []
        # A class an agent closed by reading its declared site ran no query;
        # its `sites` field is what says so. That field switches off both the
        # query rule and the counter-search rule, so it is checked against the
        # rest of the row: a read names a read and produced no query, and a row
        # that produced queries did not close by reading.
        by_reading = isinstance(row.get("sites"), list) and bool(row.get("sites"))
        method = row.get("method")
        method_reads = (isinstance(method, str)
                        and method.strip().lower().startswith(("read", "judgment")))
        if by_reading and status in ("closed", "partial"):
            if not method_reads:
                defects.append(
                    f"{where}: carries sites, so its method names the read that closed "
                    "it — a method that starts with `read` or `judgment`"
                )
            if row.get("query_ids"):
                defects.append(
                    f"{where}: carries sites and query_ids; a class is closed by reading "
                    "its site or by searching, and the record says which"
                )
                by_reading = False
            # The structure alone is cheap to fake, so the sites are checked
            # against the nodes: a site closed by reading left a node an agent
            # produced — no query behind it, dispositioned, carrying evidence.
            for site in row.get("sites") or []:
                # A site is a path or a `path:line`, written the way a node
                # writes one — anything else keys to nothing and is compared
                # against nothing.
                if not isinstance(site, str) or not SITE.fullmatch(site):
                    defects.append(
                        f"{where}: site {site!r} is not a path or path:line, so no node "
                        "can be found under it"
                    )
                    continue
                if site.endswith("/") or "\\" in site:
                    defects.append(
                        f"{where}: site {site!r} is a directory; a site is one file, and a "
                        "directory to search belongs in the instance's `paths`"
                    )
                    continue
                # The node that read it answers for THIS class: a read of one
                # class's site says nothing about another's.
                if not any(node_class == klass
                           and (node_site == site
                                or node_site.startswith(site + ":")
                                or node_site.startswith(site + "/"))
                           for node_class, node_site in read_nodes):
                    defects.append(
                        f"{where}: site {site!r} closed the class with no node of {klass} "
                        "an agent read it into — a dispositioned node with evidence and "
                        "no query"
                    )
        needs_query = ((isinstance(hits, int) and hits > 0)
                       or (status in ("closed", "partial") and not by_reading))
        if needs_query and not query_ids:
            defects.append(
                f"{where}: no query_ids; a row a search closed, or a row carrying hits, "
                "names the queries behind it"
            )
        # A query that found nothing is the right citation for a row that
        # holds nothing: the absence is the result. It cannot, on its own,
        # account for a row that holds hits.
        if len(set(query_ids)) != len(query_ids):
            defects.append(f"{where}: the same query id appears twice in query_ids; "
                           "one execution counts once")
        counted = 0
        for query_id in query_ids:
            if query_id not in query_index:
                defects.append(f"{where}: query_id {query_id!r} is not in the queries table")
                continue
            count = query_index[query_id].get("count")
            if isinstance(count, int) and count > 0:
                counted += count
        if query_ids and isinstance(hits, int) and hits > 0 and counted == 0:
            defects.append(
                f"{where}: {hits} hits, and every query it cites found nothing"
            )
        elif query_ids and isinstance(hits, int) and counted and counted < hits:
            defects.append(
                f"{where}: {hits} is more hits than its queries found ({counted}); a row "
                "cannot hold what no query returned"
            )
        if status in ("closed", "partial") and query_ids and not by_reading:
            searched[klass] = row.get("method") or ""
        if status in ("unverified", "partial", "judgment-only"):
            open_classes += 1
        elif status == "frontier":
            frontier_classes += 1
    for klass in ALL_CLASSES:
        if klass not in seen:
            defects.append(f"boundaries.{klass}: no verdict; a skipped class reads as an absence")

    # A node a search produced is bound to that search, and the search is one
    # its own class says it ran. A node citing a query no row cites is a node
    # whose class row does not account for it.
    for row in nodes:
        query_id = row.get("query_id")
        if not isinstance(query_id, str):
            continue
        where = f"nodes.{row.get('id')}"
        if query_id not in query_index:
            defects.append(f"{where}: query_id {query_id!r} is not in the queries table")
            continue
        klass = row.get("class")
        owner = seen.get(klass)
        if owner is not None and query_id not in (owner.get("query_ids") or []):
            defects.append(
                f"{where}: query_id {query_id!r} is not in the query_ids of "
                f"boundaries.{klass}; the row does not account for its own node"
            )

    node_index = {row["id"]: row for row in nodes if isinstance(row.get("id"), str)}

    # A traced node says the path goes on, so the path has to end somewhere:
    # a chain that loops, or that walks off the table, describes nothing.
    for row in nodes:
        seen_ids: list[str] = []
        walker = row
        while isinstance(walker, dict) and walker.get("parent"):
            parent = walker["parent"]
            if parent in seen_ids or parent == row.get("id"):
                defects.append(f"nodes.{row.get('id')}: the parent chain is a cycle "
                               f"through {parent!r}, so it reaches no root")
                break
            seen_ids.append(parent)
            walker = node_index.get(parent)
            if walker is None:
                break

    claim_ids: set[str] = set()
    load_bearing_gaps = 0
    for index, row in enumerate(rows_of(defects, ledger, "claims")):
        claim_id = row.get("id")
        where = f"claims.{claim_id or index}"
        unknown(defects, "claims", where, row)
        typed(defects, "claims", where, row)
        text = row.get("text")
        if claim_id and isinstance(text, str) and text and claim_id != stable_id("c", text):
            defects.append(f"{where}: a claim id is the digest of its text; this one "
                           "cannot be recomputed")
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
        for citation in row.get("citations") or []:
            if not isinstance(citation, str) or not citation.strip():
                defects.append(f"{where}: citation {citation!r} is not a `file:line` or a "
                               "command; a claim rests on something readable")
        for node in supporting:
            if not isinstance(node, str):
                defects.append(f"{where}: supporting node {node!r} is not a node id")
                continue
            if node not in node_ids:
                defects.append(f"{where}: supporting node {node!r} is not in the nodes table")
                continue
            support = node_index.get(node) or {}
            owner = seen.get(support.get("class")) or {}
            if (isinstance(support.get("query_id"), str) and owner
                    and not owner.get("truncated")
                    and node not in (owner.get("hit_ids") or [])):
                defects.append(
                    f"{where}: supporting node {node!r} is not in the hit_ids of "
                    f"boundaries.{support.get('class')}; a claim rests on a hit its own "
                    "class row accounts for"
                )
        if kind == "fact" and not supporting:
            defects.append(f"{where}: a fact names at least one supporting node")
        if not row.get("load_bearing"):
            continue
        # A load-bearing claim nobody supported is not structurally broken; it
        # is a run that has not finished, so it lowers the verdict.
        if kind == "unverified" or not supporting:
            load_bearing_gaps += 1
        if kind in ("fact", "inference") and not row.get("citations"):
            defects.append(
                f"{where}: a load-bearing {kind} names what it rests on — at least one citation"
            )

    checks = rows_of(defects, ledger, "counter_checks")
    # Which query ids reached a class through a counter-search rather than
    # through the class's own enumeration.
    countered: dict[str, set[str]] = {klass: set() for klass in ALL_CLASSES}
    for row in checks:
        for klass in row.get("classes") or []:
            if isinstance(klass, str):
                countered.setdefault(klass, set()).update(
                    item for item in (row.get("query_ids") or []) if isinstance(item, str))
    complete = [row for row in checks if row.get("state") == "complete"]
    pending = 0
    for index, row in enumerate(checks):
        where = f"counter_checks[{index}]"
        unknown(defects, "counter_checks", where, row)
        typed(defects, "counter_checks", where, row)
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
        for klass in row.get("classes") or []:
            if klass not in ALL_CLASSES:
                defects.append(f"{where}: {klass!r} is not a boundary class")
            elif klass not in seen:
                defects.append(f"{where}: it answers for {klass}, which no boundary row "
                               "verdicted")
        if state == "complete":
            # A check that ran the class's own searches ran the same pass
            # twice; a counter-search is a different method by definition.
            own = {item for item in (row.get("query_ids") or []) if isinstance(item, str)}
            for klass in row.get("classes") or []:
                # A counter-search is a second method. When the class row names
                # no search this check did not run, the check IS the class's
                # method, and nothing was weighed against anything.
                primary = {item for item in ((seen.get(klass) or {}).get("query_ids") or [])
                           if isinstance(item, str)}
                if own and primary and primary <= own:
                    defects.append(
                        f"{where}: boundaries.{klass} names no search this check did not "
                        "run, so no different method reached the class"
                    )
            # `complete` says the method ran. A deterministic method ran as a
            # query; an agent-driven one ran as reading. Either way the record
            # names what it ran, and an empty `new_nodes` is then a result
            # rather than an absence of work.
            cited = [item for item in (row.get("query_ids") or []) if item in query_index
                     and not runs_nothing(query_index[item].get("command") or "")]
            read = [item for item in (row.get("evidence_nodes") or [])
                    if node_evidence.get(item) and item in read_node_ids]
            if row.get("kind") == "agent":
                if not read:
                    defects.append(
                        f"{where}: a complete agent-driven check names in evidence_nodes at "
                        "least one node it read, carrying evidence"
                    )
            elif not cited:
                defects.append(
                    f"{where}: a complete deterministic check names in query_ids at least "
                    "one query in the queries table that can match something"
                )
        for node in row.get("evidence_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: evidence node {node!r} is not in the nodes table")
        for node in row.get("new_nodes") or []:
            if node not in node_ids:
                defects.append(f"{where}: new node {node!r} is not in the nodes table")
        for claim in targets:
            if claim not in claim_ids:
                defects.append(f"{where}: targeted claim {claim!r} is not in the claims table")
    # A class a search closed is covered by a complete counter-search that used
    # a different method. A class whose universe is another class's hit set is
    # covered by that class's check naming it.
    covered: dict[str, list[str]] = {}
    for row in complete:
        for klass in row.get("classes") or []:
            covered.setdefault(klass, []).append(row.get("method") or "")
    # A counter-search recorded pending is a method that did not run, not a
    # record that contradicts itself: `pending` already forces `partial`.
    pending_cover: set[str] = set()
    for row in checks:
        if row.get("state") == "pending":
            pending_cover.update(item for item in row.get("classes") or []
                                 if isinstance(item, str))
    for klass, method in sorted(searched.items()):
        methods = covered.get(klass)
        if not methods and klass in pending_cover:
            continue
        if not methods:
            defects.append(
                f"boundaries.{klass}: closed by a search with no complete counter-search "
                "covering it; a search nobody tried to break is one method's answer"
            )
        elif all(item == method for item in methods):
            defects.append(
                f"boundaries.{klass}: its counter-search used the same method as its "
                "primary search, so it could not have returned anything new"
            )

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
    elif (open_classes or open_nodes or pending or unresolved_verdicts
          or load_bearing_gaps):
        verdict = "partial"
    elif frontier_classes or frontier_nodes:
        verdict = "closed-with-frontier"
    else:
        verdict = "closed"

    claimed = run.get("verdict")
    if claimed is not None:
        if claimed not in VERDICTS:
            defects.append(
                f"run.verdict: {claimed!r} is not one of {', '.join(VERDICTS)}")
        elif claimed != verdict:
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
    boundaries = [row for row in ledger["boundaries"] if isinstance(row, dict)]
    closed = sum(1 for row in boundaries if row.get("status") in ("closed", "n/a"))
    sys.stdout.write(
        f"validate_coverage: valid — {closed}/{len(boundaries)} classes closed, "
        f"{len(ledger['nodes'])} nodes, {len(ledger['claims'])} claims\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

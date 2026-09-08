#!/usr/bin/env python3
"""Compare two coverage ledgers over the ground they searched.

A cited investigation is a snapshot of one commit. This answers one question
about a later commit: does the tree still hold the lines that investigation
closed? It reads, compares, and reports — it never writes a ledger, because
`/afk:investigate` is the ledger's single writer.

Usage:
  ground_diff.py --cited CITED.json --current CURRENT.json [--class B1 ...]

Ground is a searched line the seed map can re-take: a node carrying a
`line_hash` and a `query_id` resolving to a query of `origin: seed`
(`LEDGER-FORMAT.md` § "Nodes"). Nodes are compared as a multiset keyed
(`class`, file, `line_hash`) — a count, not a set, so two identical lines are
two hits and losing one is drift. A node an agent read is a judgment, not
ground; a node a tracer widened to is counted in a note, never compared. A seed
query the cited run ran and the current run does not is itself drift: the search
that closed the class no longer runs.

Both runs must stand on the same configuration: a different `run.config.sha256`
means the two searched for different things, which is drift no class filter can
narrow away.

Exit codes: 0 the ground held, 1 it moved (every difference printed), 2 usage,
a ledger that cannot be read, or one that cannot be compared — no `run.head`,
no `run.config.sha256`, or a searched node with no `line_hash`.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path


class GroundError(ValueError):
    """The ledgers cannot be compared as they stand."""


def load(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise GroundError(f"{path}: cannot read: {error}") from error
    except json.JSONDecodeError as error:
        raise GroundError(f"{path}: not JSON: {error}") from error
    if not isinstance(document, dict):
        raise GroundError(f"{path}: a ledger is one object")
    return document


def stamp(document: dict, path: Path) -> str:
    """The configuration the run searched under, refused when it is absent."""
    run = document.get("run") or {}
    if not run.get("head"):
        raise GroundError(f"{path}: no run.head; a ledger that names no snapshot "
                          "cannot be compared with another")
    config = run.get("config") or {}
    sha = config.get("sha256") if isinstance(config, dict) else None
    if not isinstance(sha, str) or not sha.strip():
        raise GroundError(f"{path}: no run.config.sha256; a ledger that does not say "
                          "what it searched under cannot be compared with another")
    return sha


def site_key(site: str) -> str:
    """The file a site names: `path:line` keys to the path, `path` to itself."""
    head, sep, tail = site.rpartition(":")
    return head if sep and tail.isdigit() else site


def ground(document: dict, path: Path, classes: list[str] | None,
           seed_queries: set[str]) -> tuple[collections.Counter, int]:
    """Every searched line the ledger holds, counted, plus what it widened past."""
    counted: collections.Counter = collections.Counter()
    widened = 0
    for row in document.get("nodes") or []:
        if not isinstance(row, dict):
            continue
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id.strip():
            continue
        digest = row.get("line_hash")
        if not isinstance(digest, str) or not digest.strip():
            raise GroundError(f"{path}: node {row.get('id')} was produced by a search "
                              "and carries no line_hash, so the ground it stands on "
                              "cannot be read")
        klass, site = row.get("class"), row.get("site") or ""
        if classes and klass not in classes:
            continue
        if query_id not in seed_queries:
            widened += 1
            continue
        counted[(klass, site_key(site), digest)] += 1
    return counted, widened


def capped(document: dict, classes: list[str] | None) -> list[str]:
    """The classes whose row holds the cap rather than the ground."""
    return sorted({row.get("class") for row in document.get("boundaries") or []
                   if isinstance(row, dict) and row.get("truncated")
                   and (not classes or row.get("class") in classes)})


def seed_queries(document: dict) -> set[str]:
    """The searches the seed map ran, which a later seed map can run again."""
    return {row.get("id") for row in document.get("queries") or []
            if isinstance(row, dict) and isinstance(row.get("id"), str)
            and row.get("origin") == "seed"}


def differences(cited: dict, current: dict, classes: list[str] | None,
                cited_path: Path, current_path: Path) -> tuple[list[str], int]:
    lines: list[str] = []
    if stamp(cited, cited_path) != stamp(current, current_path):
        lines.append("! the configuration moved between the two runs, so they "
                     "searched for different things; re-investigate")
    lines += [f"! {klass}: the cited row is truncated, so it holds the cap rather "
              "than the ground; re-trace the class" for klass in capped(cited, classes)]
    cited_seed, current_seed = seed_queries(cited), seed_queries(current)
    for gone in sorted(cited_seed - current_seed):
        lines.append(f"! query {gone} no longer runs, so the search that closed its "
                     "class is gone; re-investigate")
    before, widened = ground(cited, cited_path, classes, cited_seed)
    after, _ = ground(current, current_path, classes, current_seed)
    for key in sorted(set(before) | set(after)):
        was, now = before[key], after[key]
        if was == now:
            continue
        klass, file, line = key
        mark = "+" if now > was else "-"
        lines.append(f"{mark} {klass} {file} {line}: {was} -> {now}")
    return lines, widened


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cited", required=True, help="the ledger the design cites")
    parser.add_argument("--current", required=True,
                        help="a ledger or seed map taken at the current head")
    parser.add_argument("--class", dest="classes", action="append", default=[],
                        help="compare only this boundary class; repeat for each")
    args = parser.parse_args(argv)
    cited_path, current_path = Path(args.cited), Path(args.current)
    try:
        cited, current = load(cited_path), load(current_path)
        lines, widened = differences(cited, current, args.classes or None,
                                     cited_path, current_path)
    except GroundError as problem:
        print(f"ground_diff: {problem}", file=sys.stderr)
        return 2
    if widened:
        print(f"note: {widened} tracer nodes not compared; a widening is not ground "
              "a seed map can re-take")
    if lines:
        for line in lines:
            print(line)
        print(f"ground_diff: the ground moved in {len(lines)} places")
        return 1
    print("ground_diff: the ground held")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

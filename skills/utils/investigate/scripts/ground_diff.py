#!/usr/bin/env python3
"""Compare two coverage ledgers over the ground they searched.

A cited investigation is a snapshot of one commit. This answers one question
about a later commit: does the tree still hold what that investigation closed?
It reads, compares, and reports — it never writes a ledger, because
`/afk:investigate` is the ledger's single writer.

Usage:
  ground_diff.py --repo REPO --cited CITED.json --current CURRENT.json
                 [--class B1 ...]

Ground is a searched line the seed map can re-take: a node carrying a
`line_hash` and a `query_id` resolving to a query of `origin: seed`
(`LEDGER-FORMAT.md` § "Nodes"). Nodes are compared as a multiset keyed
(`class`, file, `line_hash`) — a count, not a set, so two identical lines are
two hits and losing one is drift.

What the multiset cannot see is reported beside it. A node an agent read and a
node a tracer widened to are not ground a seed map re-takes, so their files are
checked against `git diff` between the two snapshots instead. A boundary status
that moved, a seed search that no longer runs, and a configuration that changed
are each drift on their own, whatever the lines say.

Exit codes: 0 the ground held, 1 it moved (every difference printed), 2 usage,
a ledger that cannot be read, or one that cannot be compared — no `run.head`,
no `run.config.sha256`, a current ledger taken at another commit, a searched
node with no `line_hash`, or a node citing a query its own ledger does not hold.
"""

from __future__ import annotations

import argparse
import collections
import json
import subprocess
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


def head_of(document: dict, path: Path) -> str:
    run = document.get("run") or {}
    if not run.get("head"):
        raise GroundError(f"{path}: no run.head; a ledger that names no snapshot "
                          "cannot be compared with another")
    return run["head"]


def stamp(document: dict, path: Path) -> str:
    """The configuration the run searched under, refused when it is absent."""
    config = (document.get("run") or {}).get("config") or {}
    sha = config.get("sha256") if isinstance(config, dict) else None
    if not isinstance(sha, str) or not sha.strip():
        raise GroundError(f"{path}: no run.config.sha256; a ledger that does not say "
                          "what it searched under cannot be compared with another")
    return sha


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args],
                            capture_output=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise GroundError(f"{repo}: git {' '.join(args)} failed: "
                          f"{result.stderr.strip() or result.returncode}")
    return result.stdout


def site_key(site: str) -> str:
    """The file a site names: `path:line` keys to the path, `path` to itself."""
    head, sep, tail = site.rpartition(":")
    return head if sep and tail.isdigit() else site


def queries_of(document: dict) -> dict[str, dict]:
    return {row["id"]: row for row in document.get("queries") or []
            if isinstance(row, dict) and isinstance(row.get("id"), str)}


def sort_nodes(document: dict, path: Path) -> tuple[list[dict], list[dict]]:
    """The ledger's nodes split into ground a seed map re-takes, and the rest.

    A node citing a query its own ledger does not hold cannot be classified at
    all, so the comparison stops rather than guessing which side it belongs on.
    """
    queries = queries_of(document)
    seed: list[dict] = []
    other: list[dict] = []
    for row in document.get("nodes") or []:
        if not isinstance(row, dict):
            continue
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id.strip():
            other.append(row)
            continue
        if query_id not in queries:
            raise GroundError(f"{path}: node {row.get('id')} cites query {query_id!r}, "
                              "which its own queries table does not hold")
        digest = row.get("line_hash")
        if not isinstance(digest, str) or not digest.strip():
            raise GroundError(f"{path}: node {row.get('id')} was produced by a search "
                              "and carries no line_hash, so the ground it stands on "
                              "cannot be read")
        (seed if queries[query_id].get("origin") == "seed" else other).append(row)
    return seed, other


def counted(nodes: list[dict], classes: list[str] | None) -> collections.Counter:
    tally: collections.Counter = collections.Counter()
    for row in nodes:
        if classes and row.get("class") not in classes:
            continue
        tally[(row.get("class"), site_key(row.get("site") or ""), row["line_hash"])] += 1
    return tally


def statuses(document: dict, classes: list[str] | None) -> dict[str, dict]:
    return {row["class"]: row for row in document.get("boundaries") or []
            if isinstance(row, dict) and isinstance(row.get("class"), str)
            and (not classes or row["class"] in classes)}


def seed_query_ids(document: dict) -> set[str]:
    return {key for key, row in queries_of(document).items() if row.get("origin") == "seed"}


def touched(repo: Path, before: str, after: str) -> set[str]:
    """The files git says moved between the two snapshots."""
    if before == after:
        return set()
    return {line.strip() for line
            in git(repo, "diff", "--name-only", f"{before}..{after}").splitlines()
            if line.strip()}


def differences(cited: dict, current: dict, classes: list[str] | None,
                cited_path: Path, current_path: Path,
                repo: Path) -> tuple[list[str], int]:
    cited_head, current_head = head_of(cited, cited_path), head_of(current, current_path)
    checkout = git(repo, "rev-parse", "HEAD").strip()
    if current_head != checkout:
        raise GroundError(f"{current_path}: run.head {current_head[:12]} is not this "
                          f"checkout ({checkout[:12]}); the current ledger describes "
                          "another snapshot")
    cited_seed, cited_other = sort_nodes(cited, cited_path)
    current_seed, _ = sort_nodes(current, current_path)

    lines: list[str] = []
    if stamp(cited, cited_path) != stamp(current, current_path):
        lines.append("! the configuration moved between the two runs, so they "
                     "searched for different things; re-investigate")

    before_rows, after_rows = statuses(cited, classes), statuses(current, classes)
    for klass in sorted(set(before_rows) | set(after_rows)):
        was = (before_rows.get(klass) or {}).get("status")
        now = (after_rows.get(klass) or {}).get("status")
        if was != now:
            lines.append(f"! {klass}: the class was {was}, and now it is {now}")

    for gone in sorted(seed_query_ids(cited) - seed_query_ids(current)):
        lines.append(f"! query {gone} no longer runs, so the search that closed its "
                     "class is gone; re-investigate")

    # A node nobody can re-search is watched through its file instead.
    moved = touched(repo, cited_head, current_head)
    unsearchable = {site_key(row.get("site") or "") for row in cited_other
                    if not classes or row.get("class") in classes}
    for file in sorted(unsearchable & moved):
        lines.append(f"! {file}: a site this run read, or a tracer widened to, "
                     "changed between the two snapshots")

    before, after = counted(cited_seed, classes), counted(current_seed, classes)
    for key in sorted(set(before) | set(after)):
        was, now = before[key], after[key]
        if was == now:
            continue
        klass, file, line = key
        mark = "+" if now > was else "-"
        lines.append(f"{mark} {klass} {file} {line}: {was} -> {now}")
    return lines, len(cited_other)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True,
                        help="the checkout the current ledger describes")
    parser.add_argument("--cited", required=True, help="the ledger the design cites")
    parser.add_argument("--current", required=True,
                        help="a ledger or seed map taken at the current head")
    parser.add_argument("--class", dest="classes", action="append", default=[],
                        help="compare only this boundary class; repeat for each")
    args = parser.parse_args(argv)
    cited_path, current_path = Path(args.cited), Path(args.current)
    try:
        cited, current = load(cited_path), load(current_path)
        lines, uncompared = differences(cited, current, args.classes or None,
                                        cited_path, current_path, Path(args.repo))
    except GroundError as problem:
        print(f"ground_diff: {problem}", file=sys.stderr)
        return 2
    if uncompared:
        print(f"note: {uncompared} tracer nodes not compared; a widening is not ground "
              "a seed map can re-take, so its files are watched instead")
    if lines:
        for line in lines:
            print(line)
        print(f"ground_diff: the ground moved in {len(lines)} places")
        return 1
    print("ground_diff: the ground held")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

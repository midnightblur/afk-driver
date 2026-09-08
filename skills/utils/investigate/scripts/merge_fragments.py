#!/usr/bin/env python3
"""Fold tracer fragments into one staging coverage ledger.

Every rule this applies is stated in `LEDGER-FORMAT.md` (beside this script)
§ "Tracer fragments" and § "Merging" — merge keys, the conflict rule, the
worst-status rule, and the truncation rule. This script is the one place they
run; it decides nothing the format does not state.

Usage:
  merge_fragments.py --staging LEDGER.json --fragment FRAG.json
                     [--fragment FRAG.json ...] --out MERGED.json

A fragment names its partition, and the same bytes folded twice fold once. A
second, different fragment of one partition is a delta and folds normally. A
Identity is what a fragment found — its partition and its tables — never when
or where it ran, so one partition traced twice folds once. A fragment taken against another `run.head`, one with no
`partition.id`, and one carrying a class its `partition.classes` does not
declare each abort the merge rather than answering for something they cannot.

Exit codes: 0 wrote the merged ledger, 2 usage, unreadable input, or a
snapshot mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contract import HIT_CAP, worst  # noqa: E402

TABLES = ("boundaries", "nodes", "queries", "claims", "counter_checks")


class MergeError(RuntimeError):
    """The inputs cannot be merged as they stand."""


def load(path: Path) -> dict:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise MergeError(f"{path}: cannot read: {error}") from error
    except json.JSONDecodeError as error:
        raise MergeError(f"{path}: not JSON: {error}") from error
    if not isinstance(document, dict):
        raise MergeError(f"{path}: a ledger is one object")
    return document


def rows(document: dict, table: str) -> list[dict]:
    return [row for row in (document.get(table) or []) if isinstance(row, dict)]


def union(first: list, second: list) -> list:
    """Both lists, in order, each value once."""
    merged: list = []
    for value in list(first) + list(second):
        if value not in merged:
            merged.append(value)
    return merged


def join_reasons(first, second) -> str | None:
    parts = [part for part in (first, second) if isinstance(part, str) and part.strip()]
    seen: list[str] = []
    for part in parts:
        for piece in part.split("; "):
            if piece and piece not in seen:
                seen.append(piece)
    return "; ".join(seen) or None


# What a fragment found, which is what decides whether it has been folded.
# When and where it ran is not part of it. Named in `LEDGER-FORMAT.md`
# § "Merging".
FINGERPRINTED = ("partition", *TABLES)


def fingerprint(fragment: dict) -> str:
    """The bytes that decide whether this fragment has already been folded."""
    body = {key: fragment.get(key) for key in FINGERPRINTED if key in fragment}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def merge_node(kept: dict, row: dict) -> dict:
    """Two fragments reached the same site; only a disagreement is news."""
    left, right = kept.get("disposition"), row.get("disposition")
    if left == right:
        merged = dict(kept)
        for key, value in row.items():
            if merged.get(key) in (None, "", []):
                merged[key] = value
        return merged
    merged = dict(kept)
    merged["disposition"] = "unverified"
    merged["reason"] = f"conflict: {left} vs {right}"
    merged["evidence"] = kept.get("evidence") or row.get("evidence")
    return merged


def merge_boundary(kept: dict, row: dict) -> dict:
    """The worst status wins, and a capped list cannot be counted back."""
    merged = dict(kept)
    merged["status"] = worst(kept.get("status"), row.get("status"))
    reason = join_reasons(kept.get("reason"), row.get("reason"))
    if reason:
        merged["reason"] = reason
    elif "reason" in merged:
        del merged["reason"]
    for key in ("hit_ids", "query_ids", "sites"):
        values = union(kept.get(key) or [], row.get(key) or [])
        if values or key in kept or key in row:
            merged[key] = values
    universe = [part for part in (kept.get("universe"), row.get("universe"))
                if isinstance(part, str) and part.strip()]
    merged["universe"] = ", ".join(dict.fromkeys(universe)) or kept.get("universe")
    hit_ids = merged.get("hit_ids") or []
    if kept.get("truncated") or row.get("truncated"):
        counts = [item.get("hits") for item in (kept, row) if isinstance(item.get("hits"), int)]
        merged["hits"] = sum(counts)
        merged["truncated"] = True
        merged["hit_ids"] = hit_ids[:HIT_CAP]
    else:
        merged["hits"] = len(hit_ids)
        merged["truncated"] = len(hit_ids) > HIT_CAP
        merged["hit_ids"] = hit_ids[:HIT_CAP] if merged["truncated"] else hit_ids
    return merged


def merge_claim(kept: dict, row: dict) -> dict:
    merged = dict(kept)
    for key in ("supporting_nodes", "citations"):
        merged[key] = union(kept.get(key) or [], row.get(key) or [])
    merged["load_bearing"] = bool(kept.get("load_bearing") or row.get("load_bearing"))
    return merged


def merge_check(kept: dict, row: dict) -> dict:
    merged = dict(kept)
    for key in ("new_nodes", "targeted_claims", "query_ids", "evidence_nodes"):
        values = union(kept.get(key) or [], row.get(key) or [])
        if values or key in kept or key in row:
            merged[key] = values
    if "pending" in (kept.get("state"), row.get("state")):
        merged["state"] = "pending"
        reason = join_reasons(kept.get("reason"), row.get("reason"))
        merged["reason"] = reason or "a fragment recorded this check as pending"
    return merged


def check_key(row: dict) -> tuple:
    classes = row.get("classes") or []
    return (row.get("method"), tuple(classes) if isinstance(classes, list) else classes)


def merge(staging: dict, fragments: list[tuple[Path, dict]]) -> dict:
    head = staging.get("run", {}).get("head")
    merged = {"run": dict(staging.get("run") or {})}
    tables = {
        "boundaries": ({row.get("class"): dict(row) for row in rows(staging, "boundaries")},
                       lambda row: row.get("class"), merge_boundary),
        "nodes": ({row.get("id"): dict(row) for row in rows(staging, "nodes")},
                  lambda row: row.get("id"), merge_node),
        "queries": ({row.get("id"): dict(row) for row in rows(staging, "queries")},
                    lambda row: row.get("id"), lambda kept, row: kept),
        "claims": ({row.get("id"): dict(row) for row in rows(staging, "claims")},
                   lambda row: row.get("id"), merge_claim),
        "counter_checks": ({check_key(row): dict(row) for row in rows(staging, "counter_checks")},
                           check_key, merge_check),
    }

    seen_bodies: set[str] = set()
    folded = 0
    skipped: list[str] = []
    warnings: list[str] = list(merged["run"].get("config_warnings") or [])
    for path, fragment in fragments:
        fragment_head = fragment.get("run", {}).get("head")
        if fragment_head != head:
            raise MergeError(
                f"{path}: run.head {fragment_head!r} is not the staging ledger's "
                f"{head!r}; two snapshots are two investigations"
            )
        partition = fragment.get("partition")
        partition_id = partition.get("id") if isinstance(partition, dict) else None
        if not partition_id:
            raise MergeError(
                f"{path}: no partition.id; a fragment nobody can name is a fragment "
                "nobody can fold twice safely"
            )
        # Two folds of one partition are two answers unless they are the same
        # bytes: a delta re-fold carries nodes the first pass never had. When a
        # fold ran is not what it found, so the clock is left out of the bytes.
        body = fingerprint(fragment)
        if body in seen_bodies:
            skipped.append(f"{path}: identical to a fragment already folded")
            continue
        seen_bodies.add(body)
        classes = partition.get("classes")
        classes = classes if isinstance(classes, list) else None
        if classes is not None:
            outside = sorted({row.get("class") for row in rows(fragment, "boundaries")
                              if row.get("class") not in classes})
            if outside:
                raise MergeError(
                    f"{path}: carries {', '.join(str(item) for item in outside)}, which its "
                    f"partition.classes does not declare; a fragment answers for its own "
                    "partition"
                )
        folded += 1
        for warning in fragment.get("run", {}).get("config_warnings") or []:
            if warning not in warnings:
                warnings.append(warning)
        for table, (index, key_of, fold) in tables.items():
            for row in rows(fragment, table):
                key = key_of(row)
                if key in index:
                    index[key] = fold(index[key], row)
                else:
                    index[key] = dict(row)

    for table, (index, _, _) in tables.items():
        merged[table] = list(index.values())
    merged["run"]["merged_from"] = folded
    if warnings:
        merged["run"]["config_warnings"] = warnings
    for line in skipped:
        print(f"merge_fragments: skipped {line}", file=sys.stderr)
    return merged


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging", required=True,
                        help="the ledger the fragments fold into")
    parser.add_argument("--fragment", action="append", default=[],
                        help="a tracer fragment; repeat for each")
    parser.add_argument("--out", required=True, help="where the merged ledger is written")
    args = parser.parse_args(argv)
    if not args.fragment:
        parser.error("--fragment is required at least once")
    try:
        staging = load(Path(args.staging))
        fragments = [(Path(path), load(Path(path))) for path in args.fragment]
        merged = merge(staging, fragments)
    except MergeError as error:
        print(f"merge_fragments: {error}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"merge_fragments: {merged['run']['merged_from']} fragments folded, "
          f"{len(merged['nodes'])} nodes -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

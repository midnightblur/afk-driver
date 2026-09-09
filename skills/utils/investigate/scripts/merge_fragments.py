#!/usr/bin/env python3
"""Fold tracer fragments into one staging coverage ledger.

Every rule this applies is stated in `LEDGER-FORMAT.md` (beside this script)
§ "Tracer fragments" and § "Merging" — merge keys, the conflict rule, the
worst-status rule, and the counting rule. This script is the one place they
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
import validate_coverage  # noqa: E402
from contract import HIT_LIMIT, worst  # noqa: E402

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
# Where a fragment was written is not what it found: two worktrees of one
# checkout name two paths and one result.
PATH_KEYS = ("seed",)


def fingerprint(fragment: dict) -> str:
    """The bytes that decide whether this fragment has already been folded."""
    body = {key: fragment.get(key) for key in FINGERPRINTED if key in fragment}
    partition = body.get("partition")
    if isinstance(partition, dict):
        body["partition"] = {key: value for key, value in partition.items()
                             if key not in PATH_KEYS}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def differing(kept: dict, row: dict, skip: tuple[str, ...] = ()) -> list[str]:
    """The fields both rows fill and fill differently."""
    return sorted(key for key in set(kept) & set(row)
                  if key not in skip
                  and kept.get(key) not in (None, "", [])
                  and row.get(key) not in (None, "", [])
                  and kept.get(key) != row.get(key))


def merge_node(kept: dict, row: dict) -> dict:
    """Two fragments reached the same site; only a disagreement is news."""
    for key in ("line_hash", "site", "class"):
        if kept.get(key) and row.get(key) and kept[key] != row[key]:
            raise MergeError(
                f"node {kept.get('id')}: two fragments give it a different {key} "
                f"({kept[key]!r} and {row[key]!r}); one id is one site"
            )
    left, right = kept.get("disposition"), row.get("disposition")
    if left == right:
        # The disposition is the one field a fold reconciles. Every other
        # disagreement under one id is two answers, and picking the first is
        # picking by arrival order.
        clash = differing(kept, row)
        if clash:
            raise MergeError(
                f"node {kept.get('id')}: two fragments disagree on "
                f"{', '.join(clash)}; one id is one node"
            )
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
    """The worst status wins, and the union of the hits is the count."""
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
    # The union is the class: a fragment's hits are its own node ids, so the
    # count is the length of what the fold holds, never a sum over overlaps.
    merged["hit_ids"] = hit_ids = merged.get("hit_ids") or []
    merged["hits"] = len(hit_ids)
    if len(hit_ids) > HIT_LIMIT:
        raise MergeError(
            f"boundaries.{merged.get('class')}: {len(hit_ids)} hits, past the "
            f"{HIT_LIMIT} a class may carry; the question is re-asked of a "
            "narrower subject, never published as noise"
        )
    return merged


CLAIM_ORDER = ("unverified", "inference", "fact")


def merge_query(kept: dict, row: dict) -> dict:
    """One id is one execution: two bodies under it are two searches.

    `count` is left out: it is the nodes citing the query in the ledger that
    carries it, so two partitions of one search carry two parts of one count.
    The fold recomputes it off the folded nodes table.
    """
    for key in ("command", "universe", "lines", "origin"):
        if key in kept and key in row and kept[key] != row[key]:
            raise MergeError(
                f"query {kept.get('id')}: two fragments give it a different {key} "
                f"({kept[key]!r} and {row[key]!r}); one id is one search"
            )
    return kept


def merge_claim(kept: dict, row: dict, said: list[str] | None = None) -> dict:
    """One id is one sentence: two texts under it are two claims."""
    if kept.get("text") != row.get("text"):
        raise MergeError(
            f"claim {kept.get('id')}: two fragments give it a different text "
            f"({kept.get('text')!r} and {row.get('text')!r}); one id is one claim"
        )
    merged = dict(kept)
    for key in ("supporting_nodes", "citations"):
        merged[key] = union(kept.get(key) or [], row.get(key) or [])
    merged["load_bearing"] = bool(kept.get("load_bearing") or row.get("load_bearing"))
    kinds = [item for item in (kept.get("kind"), row.get("kind")) if item in CLAIM_ORDER]
    if kinds:
        merged["kind"] = min(kinds, key=CLAIM_ORDER.index)
    if said is not None and (kept.get("kind") != row.get("kind")
                             or bool(kept.get("load_bearing")) != bool(row.get("load_bearing"))
                             or (kept.get("supporting_nodes") or [])
                             != (row.get("supporting_nodes") or [])):
        said.append(f"claim {kept.get('id')}: two fragments read it differently; kept "
                    f"{merged['kind']}, load-bearing {merged['load_bearing']}")
    return merged


# The four lists a fold accumulates: two fragments naming different nodes for
# one check are two parts of one record, not two records.
CHECK_LISTS = ("new_nodes", "targeted_claims", "query_ids", "evidence_nodes")


def merge_check(kept: dict, row: dict) -> dict:
    clash = differing(kept, row, skip=(*CHECK_LISTS, "state", "reason"))
    if clash:
        raise MergeError(
            f"counter_check {kept.get('method')!r}: two fragments disagree on "
            f"{', '.join(clash)}; one method over one class set is one check"
        )
    merged = dict(kept)
    for key in CHECK_LISTS:
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


# What a row of each table must carry before anything is folded into it.
REQUIRED = {
    "boundaries": ("class", "status"),
    "nodes": ("id", "class", "site"),
    "queries": ("id", "command", "universe"),
    "claims": ("id", "text", "kind"),
    "counter_checks": ("method", "classes", "state"),
}


def check_shapes(path: Path, fragment: dict) -> None:
    """A row nobody can key on cannot be folded; it is refused before it is."""
    for table, required in REQUIRED.items():
        rows_here = fragment.get(table)
        if rows_here is None:
            continue
        if not isinstance(rows_here, list):
            raise MergeError(f"{path}: {table} is a list of rows")
        for index, row in enumerate(rows_here):
            if not isinstance(row, dict):
                raise MergeError(f"{path}: {table}[{index}] is not a row")
            missing = [field for field in required if not row.get(field)]
            if missing:
                raise MergeError(f"{path}: {table}[{index}] carries no "
                                 f"{', '.join(missing)}, so nothing can fold onto it")


KEY_OF = {"boundaries": "class", "nodes": "id", "queries": "id", "claims": "id"}


def fragment_defects(staging: dict, fragment: dict) -> list[str]:
    """The fragment's own defects, checked before anything folds onto them.

    A fragment names rows the seed left in the staging ledger, so it is read
    twice — alone, and against the staging rows it refers back to. Only what
    both readings call a defect is the fragment's own.
    """
    # A query's count is the nodes citing it, and a fragment's count is its own
    # nodes: the fold recomputes it afterwards, and a number nobody could
    # recompute here is a number the fragment made up.
    own: list[str] = []
    citing: dict[str, int] = {}
    for row in rows(fragment, "nodes"):
        if isinstance(row.get("query_id"), str):
            citing[row["query_id"]] = citing.get(row["query_id"], 0) + 1
    for row in rows(fragment, "queries"):
        count, query_id = row.get("count"), row.get("id")
        if isinstance(count, int) and count != citing.get(query_id, 0):
            own.append(f"queries.{query_id}: count {count} disagrees with the "
                       f"{citing.get(query_id, 0)} nodes citing it")
    # A fragment answers for its own partition, so the row that accounts for a
    # node it searched is a row it carries: a node the staging ledger's row
    # would have to adopt is a node this fragment never accounted for.
    listed = {row.get("class"): (row.get("hit_ids") or [])
              for row in rows(fragment, "boundaries")}
    for row in rows(fragment, "nodes"):
        if not isinstance(row.get("query_id"), str):
            continue
        klass = row.get("class")
        if klass not in listed:
            own.append(f"nodes.{row.get('id')}: a searched node of {klass}, which this "
                       "fragment carries no row for")
        elif row.get("id") not in listed[klass]:
            own.append(f"nodes.{row.get('id')}: a searched node outside the hit_ids of "
                       f"its own boundaries.{klass}")
    alone, _ = validate_coverage.validate(fragment, scope="rows")
    if not alone:
        return own
    with_context = {"run": dict(fragment.get("run") or {})}
    if "partition" in fragment:
        with_context["partition"] = fragment["partition"]
    for table in TABLES:
        key = KEY_OF.get(table)
        if key is None:
            with_context[table] = union(rows(staging, table), rows(fragment, table))
            continue
        index = {row.get(key): row for row in rows(staging, table)}
        index.update({row.get(key): row for row in rows(fragment, table)})
        with_context[table] = list(index.values())
    against, _ = validate_coverage.validate(with_context, scope="rows")
    return own + [defect for defect in alone if defect in set(against)]


# What makes two runs one investigation. A fragment that answers a different
# question, of a different subject, under a different configuration, answers
# for a run this one is not. The repository path is not on the list: two
# worktrees of one checkout name two paths and one result.
IDENTITY = ("question", "type", "roots", "aliases")


def same(field: str, wanted, given) -> bool:
    """Whether two runs state the same thing. `type` is a set of questions."""
    if field == "type" and isinstance(wanted, list) and isinstance(given, list):
        return sorted(str(item) for item in wanted) == sorted(str(item) for item in given)
    return wanted == given


def identity(path: Path, staging_run: dict, fragment_run: dict) -> None:
    """Every identity field, stated on both sides and stating the same run.

    A field nobody stated is not a field that matched: a fragment that says
    nothing about the question it answers is folded on nothing.
    """
    for field in IDENTITY:
        wanted, given = staging_run.get(field), fragment_run.get(field)
        for side, value in (("staging ledger", wanted), (str(path), given)):
            if value in (None, "", [], {}):
                raise MergeError(
                    f"{path}: run.{field} is absent from the {side}; a fragment folds "
                    "on an identity both sides state"
                )
        if not same(field, wanted, given):
            raise MergeError(
                f"{path}: run.{field} is not the staging ledger's; a fragment of "
                "another run answers another question"
            )
    wanted = (staging_run.get("config") or {}).get("sha256")
    given = (fragment_run.get("config") or {}).get("sha256")
    for side, value in (("staging ledger", wanted), (str(path), given)):
        if not value:
            raise MergeError(
                f"{path}: run.config.sha256 is absent from the {side}; one question "
                "over two configurations is two different searches"
            )
    if given != wanted:
        raise MergeError(
            f"{path}: run.config.sha256 is not the staging ledger's; one question "
            "over two configurations is two different searches"
        )


def merge(staging: dict, fragments: list[tuple[Path, dict]]) -> dict:
    head = staging.get("run", {}).get("head")
    merged = {"run": dict(staging.get("run") or {})}
    tables = {
        "boundaries": ({row.get("class"): dict(row) for row in rows(staging, "boundaries")},
                       lambda row: row.get("class"), merge_boundary),
        "nodes": ({row.get("id"): dict(row) for row in rows(staging, "nodes")},
                  lambda row: row.get("id"), merge_node),
        "queries": ({row.get("id"): dict(row) for row in rows(staging, "queries")},
                    lambda row: row.get("id"), merge_query),
        "claims": ({row.get("id"): dict(row) for row in rows(staging, "claims")},
                   lambda row: row.get("id"), lambda kept, row: merge_claim(kept, row, said)),
        "counter_checks": ({check_key(row): dict(row) for row in rows(staging, "counter_checks")},
                           check_key, merge_check),
    }

    said: list[str] = []
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
        check_shapes(path, fragment)
        # A fragment is folded as it stands or not at all: a defect the fold
        # papers over is a defect nobody sees again, and the merged ledger is
        # what a reader trusts.
        row_defects = fragment_defects(staging, fragment)
        if row_defects:
            raise MergeError(
                f"{path}: {len(row_defects)} defect(s), first: {row_defects[0]}; "
                "a fragment is folded as its writer wrote it"
            )
        identity(path, staging.get("run") or {}, fragment.get("run") or {})
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
        if not isinstance(classes, list) or not classes:
            raise MergeError(
                f"{path}: partition.classes is absent; a fragment names the classes "
                "it answers for, and answers for nothing else"
            )
        if True:
            outside = sorted({row.get("class")
                              for table in ("boundaries", "nodes")
                              for row in rows(fragment, table)
                              if row.get("class") not in classes})
            if outside:
                raise MergeError(
                    f"{path}: carries {', '.join(str(item) for item in outside)}, which its "
                    f"partition.classes does not declare; a fragment answers for its own "
                    "partition"
                )
            declared = {row.get("class") for row in rows(staging, "boundaries")}
            beyond = sorted(item for item in classes if item not in declared)
            if beyond:
                raise MergeError(
                    f"{path}: partition.classes names {', '.join(str(item) for item in beyond)}, "
                    "which the staging ledger does not carry; a partition is a slice of the "
                    "run it folds into"
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
    # A query's count is the nodes citing it, so the fold reads it off the
    # folded nodes rather than adding up parts that overlap.
    citing: dict[str, int] = {}
    for row in merged["nodes"]:
        if isinstance(row.get("query_id"), str):
            citing[row["query_id"]] = citing.get(row["query_id"], 0) + 1
    for row in merged["queries"]:
        if "count" in row or row.get("id") in citing:
            row["count"] = citing.get(row.get("id"), 0)
    merged["run"]["merged_from"] = folded
    if warnings:
        merged["run"]["config_warnings"] = warnings
    for line in skipped:
        print(f"merge_fragments: skipped {line}", file=sys.stderr)
    for line in said:
        print(f"merge_fragments: {line}", file=sys.stderr)
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

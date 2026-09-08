#!/usr/bin/env python3
"""Rules for folding tracer fragments into one ledger.

Each case pins a way a merge could publish more than its parts held: a
fragment from another snapshot, a class one fragment left open and another
called closed, a capped list counted back into a total, two fragments that
disagree about one site, a counter-search recorded twice.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
_SCRIPTS = Path(os.environ.get("AFK_INVESTIGATE_SCRIPTS")
                or _ROOT / "skills" / "utils" / "investigate" / "scripts")
sys.path.insert(0, str(_TESTS))

_spec = importlib.util.spec_from_file_location(
    "merge_fragments", _SCRIPTS / "merge_fragments.py")
merge_fragments = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(merge_fragments)

from test_validate_coverage import CLAIM, QUERY, ledger, validate_coverage  # noqa: E402

HEAD = "0" * 40


def fragment(partition="p1", head=HEAD, classes=None, **tables) -> dict:
    """A fragment declaring the classes its own rows carry, unless told otherwise."""
    if classes is None:
        declared = [row["class"] for row in tables.get("boundaries") or []
                    if isinstance(row, dict) and row.get("class")]
        classes = sorted(set(declared)) or ["B1"]
    document = {"run": {"head": head}, "partition": {"id": partition, "classes": classes,
                                                     "seed": "seed.json"}}
    document.update({table: rows for table, rows in tables.items()})
    return document


class MergeFragmentsTest(unittest.TestCase):
    def merge(self, staging, *fragments):
        return merge_fragments.merge(
            staging, [(Path(f"fragment-{index}.json"), item)
                      for index, item in enumerate(fragments)])

    def run_script(self, staging, *fragments):
        """The command line, so the exit codes are the ones a caller sees."""
        work = Path(tempfile.mkdtemp(prefix="merge-"))
        staging_path = work / "staging.json"
        staging_path.write_text(json.dumps(staging), encoding="utf-8")
        args = []
        for index, item in enumerate(fragments):
            path = work / f"fragment-{index}.json"
            path.write_text(json.dumps(item), encoding="utf-8")
            args += ["--fragment", str(path)]
        out = work / "merged.json"
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "merge_fragments.py"),
             "--staging", str(staging_path), *args, "--out", str(out)],
            capture_output=True, encoding="utf-8", errors="replace")
        document = json.loads(out.read_text(encoding="utf-8")) if out.exists() else None
        return result.returncode, result.stderr, document

    # A fragment from another snapshot is another investigation.
    def test_a_head_mismatch_aborts_the_merge(self):
        code, stderr, document = self.run_script(
            ledger(), fragment(head="f" * 40, boundaries=[]))
        self.assertEqual(code, 2)
        self.assertIn("two investigations", stderr)
        self.assertIsNone(document)

    # The worst status wins: a class one fragment could not reach is not
    # closed because another fragment reached its own part of it.
    def test_the_worst_boundary_status_wins(self):
        merged = self.merge(ledger(), fragment(boundaries=[
            {"class": "B1", "status": "partial", "reason": "one form unenumerated",
             "method": "every name form", "hits": 0, "hit_ids": [], "query_ids": [QUERY],
             "universe": "tracked files"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["status"], "partial")
        self.assertIn("one form unenumerated", row["reason"])

    def test_reasons_from_both_fragments_survive(self):
        merged = self.merge(
            ledger(),
            fragment(partition="p1", boundaries=[
                {"class": "B3", "status": "partial", "reason": "first gap",
                 "method": "searched", "hits": 0, "hit_ids": [], "query_ids": [QUERY],
                 "universe": "tracked files"}]),
            fragment(partition="p2", boundaries=[
                {"class": "B3", "status": "partial", "reason": "second gap",
                 "method": "searched", "hits": 0, "hit_ids": [], "query_ids": [QUERY],
                 "universe": "tracked files"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B3")
        self.assertEqual(row["reason"], "first gap; second gap")

    # A capped list holds the cap, not the count, so it cannot be unioned
    # back into a total.
    def test_a_truncated_row_sums_rather_than_counts(self):
        staging = ledger()
        capped = [f"B1:alpha.java:{line}" for line in range(1000, 1000 + 200)]
        for row in staging["boundaries"]:
            if row["class"] == "B1":
                row.update({"hits": 900, "truncated": True, "hit_ids": capped})
        merged = self.merge(staging, fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 400, "truncated": True, "hit_ids": capped,
             "query_ids": [QUERY], "universe": "tracked files"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], 1300)
        self.assertTrue(row["truncated"])
        self.assertEqual(len(row["hit_ids"]), merge_fragments.HIT_CAP)

    def test_an_untruncated_row_counts_the_union(self):
        merged = self.merge(ledger(), fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 1, "hit_ids": ["B1:beta.java:4"], "query_ids": [QUERY],
             "universe": "tracked files"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(sorted(row["hit_ids"]), ["B1:alpha.java:2", "B1:beta.java:4"])
        self.assertEqual(row["hits"], 2)
        self.assertFalse(row["truncated"])

    # Two fragments that disagree about one site have not settled it.
    def test_a_node_two_fragments_dispositioned_differently_reopens(self):
        merged = self.merge(ledger(), fragment(nodes=[
            {"id": "B1:alpha.java:9", "class": "B1", "site": "alpha.java:9",
             "disposition": "irrelevant", "evidence": "the write", "parent": None,
             "query_id": QUERY}]))
        node = next(item for item in merged["nodes"] if item["id"] == "B1:alpha.java:9")
        self.assertEqual(node["disposition"], "unverified")
        self.assertIn("conflict: terminal vs irrelevant", node["reason"])

    def test_a_node_both_fragments_agree_on_stays_settled(self):
        merged = self.merge(ledger(), fragment(nodes=[
            {"id": "B1:alpha.java:9", "class": "B1", "site": "alpha.java:9",
             "disposition": "terminal", "evidence": "the write", "parent":
             "B1:alpha.java:2", "query_id": QUERY}]))
        node = next(item for item in merged["nodes"] if item["id"] == "B1:alpha.java:9")
        self.assertEqual(node["disposition"], "terminal")

    # One counter-search run in two partitions is one row.
    def test_the_same_counter_search_unions_rather_than_repeats(self):
        merged = self.merge(ledger(), fragment(counter_checks=[
            {"method": "a second name form", "kind": "deterministic",
             "targeted_claims": [CLAIM], "new_nodes": ["B1:alpha.java:9"],
             "state": "complete", "classes": list(validate_coverage.ALL_CLASSES),
             "query_ids": [QUERY]}]))
        self.assertEqual(len(merged["counter_checks"]), 1)
        self.assertEqual(merged["counter_checks"][0]["new_nodes"], ["B1:alpha.java:9"])

    def test_a_pending_fragment_check_beats_a_complete_one(self):
        merged = self.merge(ledger(), fragment(counter_checks=[
            {"method": "a second name form", "kind": "deterministic",
             "targeted_claims": [CLAIM], "new_nodes": [], "state": "pending",
             "reason": "the tracer did not run it",
             "classes": list(validate_coverage.ALL_CLASSES)}]))
        self.assertEqual(merged["counter_checks"][0]["state"], "pending")
        self.assertIn("did not run", merged["counter_checks"][0]["reason"])

    # Identical by construction, so one row.
    def test_a_duplicate_query_id_folds_into_one_row(self):
        merged = self.merge(ledger(), fragment(queries=[
            dict(ledger()["queries"][0])]))
        self.assertEqual(len(merged["queries"]), 1)

    def test_a_duplicate_claim_id_unions_its_support(self):
        merged = self.merge(ledger(), fragment(claims=[
            {"id": CLAIM, "text": "the path starts here", "kind": "fact",
             "load_bearing": True, "supporting_nodes": ["B1:alpha.java:9"],
             "citations": ["alpha.java:9"]}]))
        self.assertEqual(len(merged["claims"]), 1)
        self.assertEqual(merged["claims"][0]["supporting_nodes"],
                         ["B1:alpha.java:2", "B1:alpha.java:9"])
        self.assertEqual(merged["claims"][0]["citations"],
                         ["alpha.java:2", "alpha.java:9"])

    # The same partition of the same snapshot, folded twice, is one fragment.
    def test_the_same_fragment_folded_twice_counts_once(self):
        item = fragment(nodes=[
            {"id": "B1:beta.java:4", "class": "B1", "site": "beta.java:4",
             "disposition": "terminal", "evidence": "the call", "parent": None,
             "query_id": QUERY, "line_hash": "cccccccccccc"}])
        merged = self.merge(ledger(), item, dict(item))
        self.assertEqual(merged["run"]["merged_from"], 1)

    # A re-trace of one partition carries nodes the first pass never had, so a
    # second, different fragment of that partition is a delta, not a repeat.
    def test_a_second_different_fragment_of_one_partition_folds(self):
        first = fragment(partition="p1", nodes=[
            {"id": "B1:beta.java:4", "class": "B1", "site": "beta.java:4",
             "disposition": "terminal", "evidence": "the call", "parent": None,
             "query_id": QUERY, "line_hash": "cccccccccccc"}])
        second = fragment(partition="p1", nodes=[
            {"id": "B1:beta.java:9", "class": "B1", "site": "beta.java:9",
             "disposition": "terminal", "evidence": "the other call", "parent": None,
             "query_id": QUERY}])
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 2)
        self.assertIn("B1:beta.java:9", [row["id"] for row in merged["nodes"]])

    # Two folds of one fragment differ in when they ran, never in what they
    # found; a re-stamped copy is still the same fragment.
    def test_a_repeat_differing_only_in_timestamps_counts_once(self):
        first = fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 400, "truncated": True, "hit_ids": ["B1:alpha.java:2"],
             "query_ids": [QUERY], "universe": "tracked files"}])
        first["run"].update({"started": "2026-01-01T00:00:00+00:00",
                             "finished": "2026-01-01T00:01:00+00:00"})
        second = json.loads(json.dumps(first))
        second["run"].update({"started": "2026-01-02T00:00:00+00:00",
                              "finished": "2026-01-02T00:02:00+00:00"})
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 1)
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], 401)

    # One partition traced in two worktrees of one head is one answer: the run
    # block differs, what it found does not.
    def test_a_repeat_differing_only_in_the_run_block_counts_once(self):
        first = fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 400, "truncated": True, "hit_ids": ["B1:alpha.java:2"],
             "query_ids": [QUERY], "universe": "tracked files"}])
        first["run"]["repository"] = "/worktree-one"
        second = json.loads(json.dumps(first))
        second["run"]["repository"] = "/worktree-two"
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 1)
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], 401)

    # A skipped repeat is reported, never silently dropped.
    def test_a_skipped_repeat_is_named_on_stderr(self):
        item = fragment(nodes=[])
        code, stderr, document = self.run_script(ledger(), item, dict(item))
        self.assertEqual(code, 0, stderr)
        self.assertIn("skipped", stderr)
        self.assertEqual(document["run"]["merged_from"], 1)

    # A fragment nobody can name cannot be reasoned about.
    def test_a_fragment_without_a_partition_id_is_refused(self):
        item = fragment(nodes=[])
        item["partition"].pop("id")
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("partition.id", stderr)
        self.assertIsNone(document)

    # A fragment answers for its own partition and no other.
    def test_a_class_outside_the_partition_is_refused(self):
        code, stderr, document = self.run_script(ledger(), fragment(
            classes=["B1"],
            boundaries=[{"class": "B3", "status": "closed", "method": "searched",
                         "hits": 0, "hit_ids": [], "query_ids": [QUERY],
                         "universe": "tracked files"}]))
        self.assertEqual(code, 2)
        self.assertIn("B3", stderr)
        self.assertIsNone(document)

    # A warning a fragment recorded is a warning the run carries.
    def test_fragment_config_warnings_reach_the_run(self):
        item = fragment(nodes=[])
        item["run"]["config_warnings"] = ["a declared path matched nothing"]
        merged = self.merge(ledger(), item)
        self.assertIn("a declared path matched nothing",
                      merged["run"]["config_warnings"])

    # A merged row states the ground it was searched over.
    def test_a_merged_boundary_keeps_its_universe(self):
        merged = self.merge(ledger(), fragment(boundaries=[
            {"class": "B1", "status": "partial", "reason": "one form unenumerated",
             "method": "every name form", "hits": 0, "hit_ids": [], "query_ids": [QUERY],
             "universe": "tracked files"}]))
        for row in merged["boundaries"]:
            self.assertTrue(row.get("universe"), row["class"])

    # A merged ledger that cannot be validated is a merge defect.
    def test_the_merged_ledger_validates(self):
        code, stderr, document = self.run_script(ledger(), fragment(nodes=[
            {"id": "B1:beta.java:4", "class": "B1", "site": "beta.java:4",
             "disposition": "terminal", "evidence": "the call", "parent": None,
             "query_id": QUERY, "line_hash": "cccccccccccc"}]))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(document["run"]["merged_from"], 1)
        defects, verdict = validate_coverage.validate(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")


if __name__ == "__main__":
    unittest.main()

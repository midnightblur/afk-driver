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

from test_validate_coverage import (CLAIM, COMMAND, QUERY,  # noqa: E402
                                    ledger, validate_coverage)

HEAD = "0" * 40


def fragment(partition="p1", head=HEAD, classes=None, **tables) -> dict:
    """A fragment declaring the classes its own rows carry, unless told otherwise."""
    if classes is None:
        declared = [row["class"] for row in tables.get("boundaries") or []
                    if isinstance(row, dict) and row.get("class")]
        classes = sorted(set(declared)) or ["B1"]
    run = {"head": head}
    # Every identity field the fold checks, taken from the run these fragments
    # are parts of; a case that varies one overwrites it.
    for field in ("question", "type", "roots", "aliases", "config"):
        run[field] = ledger()["run"][field]
    document = {"run": run, "partition": {"id": partition, "classes": classes,
                                          "seed": "seed.json"}}
    document.update({table: rows for table, rows in tables.items()})
    # A fragment accounts for the nodes it searched, so unless a case says
    # otherwise it carries the row that holds them.
    if "boundaries" not in tables:
        searched = [row for row in document.get("nodes") or []
                    if isinstance(row, dict) and isinstance(row.get("query_id"), str)]
        by_class: dict = {}
        for row in searched:
            by_class.setdefault(row.get("class"), []).append(row.get("id"))
        document["boundaries"] = [
            {"class": klass, "status": "closed", "method": "every name form",
             "hits": len(ids), "hit_ids": ids, "query_ids": [QUERY],
             "universe": "tracked files"}
            for klass, ids in sorted(by_class.items())]
    return document


def hit(node_id, query=QUERY, line_hash="abcdef123456") -> dict:
    """A node a search produced, carrying what the format asks of one."""
    klass, _, site = node_id.partition(":")
    return {"id": node_id, "class": klass, "site": site, "line_hash": line_hash,
            "disposition": "terminal", "evidence": "the line the search returned",
            "parent": None, "query_id": query}


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

    # The spawn hands the tracer the staging ledger's run block; a fragment
    # that carries it back verbatim is the shape the prose asks for.
    def test_a_fragment_carrying_the_run_block_verbatim_folds(self):
        staging = ledger()
        piece = fragment(boundaries=[])
        piece["run"] = json.loads(json.dumps(staging["run"]))
        code, stderr, document = self.run_script(staging, piece)
        self.assertEqual(code, 0, stderr)
        self.assertIsNotNone(document)

    def test_a_fragment_without_a_run_block_is_refused(self):
        piece = fragment(boundaries=[])
        del piece["run"]
        code, stderr, document = self.run_script(ledger(), piece)
        self.assertEqual(code, 2)
        self.assertIn("run", stderr)
        self.assertIsNone(document)

    # `lines` is a record of one execution, not identity: two partitions of one
    # search returned two parts of it.
    def test_two_fragments_may_record_different_line_figures(self):
        staging = ledger()
        query = dict(staging["queries"][0])
        first = fragment(partition="p1", classes=["B1"], boundaries=[],
                         queries=[dict(query, lines=3, count=0)])
        second = fragment(partition="p2", classes=["B2"], boundaries=[],
                          queries=[dict(query, lines=9, count=0)])
        code, stderr, document = self.run_script(staging, first, second)
        self.assertEqual(code, 0, stderr)
        self.assertIsNotNone(document)

    def test_a_query_two_ledgers_carry_loses_its_line_figure(self):
        staging = ledger()
        staging["queries"][0]["lines"] = 4
        query = dict(staging["queries"][0])
        piece = fragment(classes=["B1"], boundaries=[],
                         queries=[dict(query, lines=9, count=0)])
        merged = self.merge(staging, piece)
        row = next(item for item in merged["queries"] if item["id"] == query["id"])
        self.assertNotIn("lines", row)

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

    # A hit both fragments found is one hit: the union counts, a sum invents.
    def test_an_overlapping_row_counts_the_union(self):
        staging = ledger()
        shared = [f"B1:alpha.java:{line}" for line in range(1000, 1000 + 200)]
        for row in staging["boundaries"]:
            if row["class"] == "B1":
                row.update({"hits": len(shared), "hit_ids": list(shared)})
        ids = shared + ["B1:beta.java:4"]
        merged = self.merge(staging, fragment(
            boundaries=[{"class": "B1", "status": "closed", "method": "every name form",
                         "hits": len(ids), "hit_ids": list(ids), "query_ids": [QUERY],
                         "universe": "tracked files"}],
            nodes=[hit(item) for item in ids],
            queries=[{"id": QUERY, "command": COMMAND, "universe": "tracked files",
                      "count": len(ids), "evidence": None, "origin": "seed"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], len(shared) + 1)
        self.assertEqual(len(row["hit_ids"]), len(shared) + 1)

    def test_a_disjoint_row_counts_the_union(self):
        merged = self.merge(ledger(), fragment(
            boundaries=[{"class": "B1", "status": "closed", "method": "every name form",
                         "hits": 1, "hit_ids": ["B1:beta.java:4"], "query_ids": [QUERY],
                         "universe": "tracked files"}],
            nodes=[hit("B1:beta.java:4")],
            queries=[{"id": QUERY, "command": COMMAND, "universe": "tracked files",
                      "count": 1, "evidence": None, "origin": "seed"}]))
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(sorted(row["hit_ids"]),
                         ["B1:alpha.java:2", "B1:alpha.java:9", "B1:beta.java:4"])
        self.assertEqual(row["hits"], 3)

    # Two fragments that disagree about one site have not settled it.
    def test_a_node_two_fragments_dispositioned_differently_reopens(self):
        merged = self.merge(ledger(), fragment(nodes=[
            {**hit("B1:alpha.java:9", line_hash="bbbbbbbbbbbb"),
             "disposition": "irrelevant", "evidence": "the write"}]))
        node = next(item for item in merged["nodes"] if item["id"] == "B1:alpha.java:9")
        self.assertEqual(node["disposition"], "unverified")
        self.assertIn("conflict: terminal vs irrelevant", node["reason"])

    def test_a_node_both_fragments_agree_on_stays_settled(self):
        merged = self.merge(ledger(), fragment(nodes=[
            {**hit("B1:alpha.java:9", line_hash="bbbbbbbbbbbb"),
             "evidence": "the write", "parent": "B1:alpha.java:2"}]))
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
        merged = self.merge(ledger(), fragment(
            queries=[{**ledger()["queries"][0], "count": 1}],
            nodes=[hit("B1:beta.java:4")]))
        self.assertEqual(len(merged["queries"]), len(ledger()["queries"]))

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
        first = fragment(partition="p1", nodes=[hit("B1:beta.java:4")])
        second = fragment(partition="p1", nodes=[hit("B1:beta.java:9")])
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 2)
        self.assertIn("B1:beta.java:9", [row["id"] for row in merged["nodes"]])

    # Two folds of one fragment differ in when they ran, never in what they
    # found; a re-stamped copy is still the same fragment.
    def test_a_repeat_differing_only_in_timestamps_counts_once(self):
        first = fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 1, "hit_ids": ["B1:alpha.java:2"],
             "query_ids": [QUERY], "universe": "tracked files"}])
        first["run"].update({"started": "2026-01-01T00:00:00+00:00",
                             "finished": "2026-01-01T00:01:00+00:00"})
        second = json.loads(json.dumps(first))
        second["run"].update({"started": "2026-01-02T00:00:00+00:00",
                              "finished": "2026-01-02T00:02:00+00:00"})
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 1)
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], 2)

    # One partition traced in two worktrees of one head is one answer: the run
    # block differs, what it found does not.
    def test_a_repeat_differing_only_in_the_run_block_counts_once(self):
        first = fragment(boundaries=[
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 1, "hit_ids": ["B1:alpha.java:2"],
             "query_ids": [QUERY], "universe": "tracked files"}])
        first["run"]["repository"] = "/worktree-one"
        second = json.loads(json.dumps(first))
        second["run"]["repository"] = "/worktree-two"
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 1)
        row = next(item for item in merged["boundaries"] if item["class"] == "B1")
        self.assertEqual(row["hits"], 2)

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

    # One id, two different searches: folding them keeps one and loses the other.
    def test_one_query_id_with_two_bodies_is_refused(self):
        clash = dict(ledger()["queries"][0])
        clash["origin"] = "tracer"
        code, stderr, document = self.run_script(ledger(), fragment(queries=[clash]))
        self.assertEqual(code, 2)
        self.assertIn(clash["id"], stderr)
        self.assertIsNone(document)

    def test_one_node_id_with_two_line_hashes_is_refused(self):
        code, stderr, document = self.run_script(ledger(), fragment(nodes=[
            {"id": "B1:alpha.java:2", "class": "B1", "site": "alpha.java:2",
             "disposition": "traced", "evidence": "the line", "parent": None,
             "query_id": QUERY, "line_hash": "ffffffffffff"}]))
        self.assertEqual(code, 2)
        self.assertIn("B1:alpha.java:2", stderr)
        self.assertIsNone(document)

    # Two readings of one claim are folded to the worse, and the fold says so.
    def test_two_readings_of_one_claim_take_the_worse(self):
        weaker = dict(ledger()["claims"][0])
        weaker.update({"kind": "unverified", "load_bearing": False})
        code, stderr, document = self.run_script(ledger(), fragment(claims=[weaker]))
        self.assertEqual(code, 0, stderr)
        claim = document["claims"][0]
        self.assertEqual(claim["kind"], "unverified")
        self.assertTrue(claim["load_bearing"])
        self.assertIn(claim["id"], stderr)

    # One id is the digest of one sentence: two sentences under it are forged.
    def test_one_claim_id_with_two_texts_is_refused(self):
        kept = dict(ledger()["claims"][0])
        forged = {**kept, "text": "the path starts somewhere else"}
        with self.assertRaises(merge_fragments.MergeError) as refused:
            merge_fragments.merge_claim(kept, forged)
        self.assertIn("one id is one claim", str(refused.exception))

    # A fragment whose claim id does not digest its text is refused before
    # anything folds onto it.
    def test_a_claim_id_that_does_not_digest_its_text_is_refused(self):
        forged = dict(ledger()["claims"][0])
        forged["text"] = "the path starts somewhere else"
        code, stderr, document = self.run_script(ledger(), fragment(claims=[forged]))
        self.assertEqual(code, 2)
        self.assertIn("cannot be recomputed", stderr)
        self.assertIsNone(document)

    # A fragment answering another question is another investigation.
    def test_another_question_aborts_the_merge(self):
        item = fragment(nodes=[])
        item["run"]["question"] = "something else entirely"
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("question", stderr)
        self.assertIsNone(document)

    def test_a_malformed_row_aborts_the_merge(self):
        code, stderr, document = self.run_script(ledger(), fragment(nodes=["a string"]))
        self.assertEqual(code, 2)
        self.assertIn("nodes", stderr)
        self.assertIsNone(document)

    def test_a_node_outside_the_partition_is_refused(self):
        code, stderr, document = self.run_script(ledger(), fragment(
            classes=["B1"],
            nodes=[{"id": "B3:beta.java:4", "class": "B3", "site": "beta.java:4",
                    "disposition": "terminal", "evidence": "the call", "parent": None,
                    "query_id": QUERY, "line_hash": "cccccccccccc"}]))
        self.assertEqual(code, 2)
        self.assertIn("B3", stderr)
        self.assertIsNone(document)

    # One partition traced in two worktrees names two seed paths and one result.
    def test_two_worktree_paths_fold_once(self):
        first = fragment(nodes=[])
        first["partition"]["seed"] = "/worktree-one/seed.json"
        second = json.loads(json.dumps(first))
        second["partition"]["seed"] = "/worktree-two/seed.json"
        merged = self.merge(ledger(), first, second)
        self.assertEqual(merged["run"]["merged_from"], 1)

    # A merged ledger that cannot be validated is a merge defect.
    def test_the_merged_ledger_validates(self):
        staging = ledger()
        staging["queries"][0]["count"] = 3
        code, stderr, document = self.run_script(staging, fragment(
            boundaries=[{"class": "B1", "status": "closed",
                         "method": "every name form", "hits": 1,
                         "hit_ids": ["B1:beta.java:4"], "query_ids": [QUERY],
                         "universe": "tracked files"}],
            nodes=[
                {"id": "B1:beta.java:4", "class": "B1", "site": "beta.java:4",
                 "disposition": "terminal", "evidence": "the call", "parent": None,
                 "query_id": QUERY, "line_hash": "cccccccccccc"}]))
        self.assertEqual(code, 0, stderr)
        self.assertEqual(document["run"]["merged_from"], 1)
        defects, verdict = validate_coverage.validate(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")
    # A fragment is folded as its writer wrote it, or not at all.
    def test_a_fragment_carrying_a_defect_is_refused_before_it_folds(self):
        loose = {**hit("B1:beta.java:4")}
        del loose["line_hash"]
        code, stderr, document = self.run_script(ledger(), fragment(nodes=[loose]))
        self.assertEqual(code, 2)
        self.assertIn("line_hash", stderr)
        self.assertIsNone(document)

    def test_a_fragment_defect_names_the_row_it_is_in(self):
        code, stderr, _ = self.run_script(ledger(), fragment(nodes=[
            {**hit("B1:beta.java:4"), "site": "beta.java:5"}]))
        self.assertEqual(code, 2)
        self.assertIn("B1:beta.java:4", stderr)

    # Two answers under one id are two answers; arrival order settles nothing.
    def test_one_node_id_with_two_evidence_lines_is_refused(self):
        code, stderr, document = self.run_script(ledger(), fragment(nodes=[
            {**hit("B1:alpha.java:9", line_hash="bbbbbbbbbbbb"),
             "evidence": "something else the reader saw"}]))
        self.assertEqual(code, 2)
        self.assertIn("one id is one node", stderr)
        self.assertIsNone(document)

    def test_one_counter_check_with_two_kinds_is_refused(self):
        clash = dict(ledger()["counter_checks"][0])
        clash["kind"] = "agent"
        with self.assertRaises(merge_fragments.MergeError) as refused:
            merge_fragments.merge_check(dict(ledger()["counter_checks"][0]), clash)
        self.assertIn("one method over one class set is one check",
                      str(refused.exception))

    # A fragment of another run answers for a run this one is not.
    def test_a_fragment_of_another_subject_is_refused(self):
        item = fragment(nodes=[])
        item["run"]["roots"] = ["some.other.Subject"]
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("run.roots", stderr)
        self.assertIsNone(document)

    def test_a_fragment_under_another_configuration_is_refused(self):
        item = fragment(nodes=[])
        item["run"]["config"] = {"path": ".afk/config.yaml", "sha256": "f" * 64}
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("run.config.sha256", stderr)
        self.assertIsNone(document)

    def test_a_partition_class_the_staging_ledger_never_carried_is_refused(self):
        item = fragment(classes=["B1", "B99"], nodes=[])
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("B99", stderr)
        self.assertIsNone(document)

    # A class past the ceiling is re-asked, never folded.
    def test_a_class_past_the_hit_limit_refuses_the_fold(self):
        limit = merge_fragments.HIT_LIMIT
        merge_fragments.HIT_LIMIT = 2
        try:
            ids = ["B1:beta.java:4", "B1:beta.java:5", "B1:beta.java:6"]
            with self.assertRaises(merge_fragments.MergeError) as refused:
                merge_fragments.merge_boundary(
                    {"class": "B1", "status": "closed", "hit_ids": [], "hits": 0},
                    {"class": "B1", "status": "closed", "hit_ids": ids,
                     "hits": len(ids)})
            self.assertIn("a class may carry", str(refused.exception))
        finally:
            merge_fragments.HIT_LIMIT = limit
    # An identity nobody stated is not an identity that matched.
    def test_a_fragment_missing_a_run_identity_field_is_refused(self):
        item = fragment(nodes=[])
        item["run"].update({"question": "the same question", "type": ["Q1"],
                            "aliases": {"Widget": []},
                            "config": {"path": ".afk/config.yaml", "sha256": "a" * 64}})
        staging = ledger()
        for field in ("question", "type", "roots", "aliases"):
            item["run"][field] = staging["run"][field]
        item["run"]["config"] = staging["run"]["config"]
        del item["run"]["roots"]
        code, stderr, document = self.run_script(staging, item)
        self.assertEqual(code, 2)
        self.assertIn("run.roots", stderr)
        self.assertIsNone(document)

    def test_a_fragment_without_partition_classes_is_refused(self):
        item = fragment(nodes=[])
        del item["partition"]["classes"]
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("partition.classes", stderr)
        self.assertIsNone(document)

    # A fragment's own count is checked before the fold recomputes anything.
    def test_a_fragment_whose_query_count_is_not_its_own_nodes_is_refused(self):
        item = fragment(
            nodes=[hit("B1:beta.java:4")],
            queries=[{"id": QUERY, "command": COMMAND, "universe": "tracked files",
                      "count": 99, "evidence": None, "origin": "seed"}])
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("nodes citing it", stderr)
        self.assertIsNone(document)
    # A fragment accounts for what it searched, before the fold does.
    def test_a_fragment_whose_row_does_not_hold_its_node_is_refused(self):
        item = fragment(
            nodes=[hit("B1:beta.java:4")],
            boundaries=[{"class": "B1", "status": "closed", "method": "every name form",
                         "hits": 0, "hit_ids": [], "query_ids": [QUERY],
                         "universe": "tracked files"}],
            queries=[{"id": QUERY, "command": COMMAND, "universe": "tracked files",
                      "count": 1, "evidence": None, "origin": "seed"}])
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("outside the hit_ids of its own boundaries.B1", stderr)
        self.assertIsNone(document)

    def test_a_fragment_carrying_a_node_of_a_class_it_has_no_row_for_is_refused(self):
        item = fragment(
            classes=["B1"],
            nodes=[hit("B1:beta.java:4")],
            boundaries=[],
            queries=[{"id": QUERY, "command": COMMAND, "universe": "tracked files",
                      "count": 1, "evidence": None, "origin": "seed"}])
        code, stderr, document = self.run_script(ledger(), item)
        self.assertEqual(code, 2)
        self.assertIn("carries no row for", stderr)
        self.assertIsNone(document)


if __name__ == "__main__":
    unittest.main()

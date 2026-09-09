#!/usr/bin/env python3
"""Adversarial cases for the validator: a malformed ledger that still passes.

Every case here starts from the same question — what shape could reach exit 0
while the record behind it is incomplete or inconsistent? A hit count that
disagrees with its own node list, a traced node leading nowhere, a claim with
nothing under it, a counter-search aimed at nothing, a key nobody defined.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_validate_coverage import CLAIM, QUERY, ledger, only, validate_coverage  # noqa: E402


READ_NODE = "B1:alpha.java:12"


def agent_check(document):
    """An agent-driven counter-search names the node it read."""
    document["nodes"].append(
        {"id": READ_NODE, "class": "B1", "site": "alpha.java:12",
         "disposition": "terminal", "evidence": "the registration line",
         "parent": None, "query_id": None, "impact_verdict": "unchanged",
         "pinned_by": "unguarded", "coverage_verdict": "test"})
    document["counter_checks"].append(
        {"method": "the registration site", "kind": "agent", "classes": ["B1"],
         "targeted_claims": [CLAIM], "new_nodes": [], "state": "complete",
         "evidence_nodes": [READ_NODE]})
    return document


def q3_ready(document):
    """A Q3 run also needs its agent-driven counter-search to be legal."""
    document["run"]["type"] = ["Q3"]
    return agent_check(document)


class LedgerShapeTest(unittest.TestCase):
    def check(self, document):
        return validate_coverage.validate(document)

    # 12 — a count that disagrees with its own node list.
    def test_12_hits_must_agree_with_hit_ids(self):
        document = only(ledger(), "B1", hits=7, hit_ids=["B1:alpha.java:2"])
        defects, _ = self.check(document)
        self.assertTrue(any("hits" in defect and "B1" in defect for defect in defects), defects)

    # A big class is carried whole: 250 hits are 250 nodes and 250 ids, and the
    # row closes honestly rather than on a sample.
    def test_12_a_large_row_carries_every_hit(self):
        size = 250
        document = ledger()
        document["nodes"] += [
            {"id": f"B1:bulk.java:{n}", "class": "B1", "site": f"bulk.java:{n}",
             "disposition": "terminal", "evidence": "the line", "parent": None,
             "query_id": QUERY, "line_hash": f"{n:012d}"}
            for n in range(1, size + 1)
        ]
        base = ["B1:alpha.java:2", "B1:alpha.java:9"]
        document["queries"][0]["count"] = size + len(base)
        document = only(document, "B1", hits=size + len(base),
                        hit_ids=base + [f"B1:bulk.java:{n}" for n in range(1, size + 1)])
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")

    # A node the row's count cannot see is a searched line the answer lost.
    def test_12_a_searched_node_outside_its_row_is_a_defect(self):
        document = ledger()
        document["nodes"].append(
            {"id": "B1:bulk.java:9", "class": "B1", "site": "bulk.java:9",
             "disposition": "terminal", "evidence": "the line", "parent": None,
             "query_id": QUERY, "line_hash": "e" * 12})
        defects, _ = self.check(document)
        self.assertTrue(any("hit_ids" in defect and "B1:bulk.java:9" in defect
                            for defect in defects), defects)

    # 13 — a node with no evidence is a node nobody can check.
    def test_13_a_traced_node_needs_evidence(self):
        document = ledger()
        document["nodes"][0].pop("evidence")
        defects, _ = self.check(document)
        self.assertTrue(any("evidence" in defect for defect in defects), defects)

    # 14 — an unverified per-node verdict is not closure.
    def test_14_an_unverified_node_verdict_downgrades_the_run(self):
        document = q3_ready(ledger())
        for node in document["nodes"]:
            node.update({"impact_verdict": "unverified", "pinned_by": "unguarded"})
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "partial")

    # 15 — one field cannot answer two questions at once.
    def test_15_a_combined_run_needs_both_verdict_fields(self):
        document = ledger()
        document["run"]["type"] = ["Q3", "Q4"]
        agent_check(document)
        for node in document["nodes"]:
            node.update({"impact_verdict": "unchanged", "pinned_by": "alpha_test:9"})
        defects, _ = self.check(document)
        self.assertTrue(any("coverage_verdict" in defect for defect in defects), defects)

    def test_15_both_verdict_fields_present_pass(self):
        document = ledger()
        document["run"]["type"] = ["Q3", "Q4"]
        agent_check(document)
        for node in document["nodes"]:
            node.update({"impact_verdict": "unchanged", "pinned_by": "alpha_test:9",
                         "coverage_verdict": "test"})
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")

    # 16 — a traced node that leads nowhere traced nothing.
    def test_16_a_traced_node_needs_a_child(self):
        document = ledger()
        defects, _ = self.check(document)
        self.assertEqual(defects, [])
        document["nodes"].append({"id": "B1:beta.java:4", "class": "B1", "site": "beta.java:4",
                                  "disposition": "traced", "evidence": "the line",
                                  "parent": None, "query_id": QUERY})
        defects, _ = self.check(document)
        self.assertTrue(any("beta.java:4" in defect for defect in defects), defects)

    def test_16_duplicate_boundary_rows_are_a_defect(self):
        document = ledger()
        document["boundaries"].append(dict(document["boundaries"][0]))
        defects, _ = self.check(document)
        self.assertTrue(any("more than one row" in defect for defect in defects), defects)

    # 17 — a fact with nothing under it.
    def test_17_a_fact_needs_a_supporting_node(self):
        document = ledger()
        document["claims"][0]["supporting_nodes"] = []
        defects, _ = self.check(document)
        self.assertTrue(any("supporting node" in defect for defect in defects), defects)

    def test_17_load_bearing_must_be_a_boolean(self):
        document = ledger()
        document["claims"][0]["load_bearing"] = "yes"
        defects, _ = self.check(document)
        self.assertTrue(any("load_bearing" in defect for defect in defects), defects)

    def test_17_a_missing_load_bearing_flag_is_a_defect(self):
        document = ledger()
        del document["claims"][0]["load_bearing"]
        defects, _ = self.check(document)
        self.assertTrue(any("load_bearing" in defect for defect in defects), defects)

    # 18 — a counter-search aimed at nothing tried to break nothing.
    def test_18_a_complete_counter_search_names_a_target(self):
        document = ledger()
        document["counter_checks"][0]["targeted_claims"] = []
        defects, _ = self.check(document)
        self.assertTrue(any("targeted_claims" in defect for defect in defects), defects)

    # 19 — the run header is the snapshot; it is not optional.
    def test_19_run_type_must_be_a_list(self):
        document = ledger()
        document["run"]["type"] = "Q1"
        defects, _ = self.check(document)
        self.assertTrue(any("run.type" in defect for defect in defects), defects)

    def test_19_timestamps_are_required(self):
        document = ledger()
        document["run"].pop("started", None)
        defects, _ = self.check(document)
        self.assertTrue(any("started" in defect for defect in defects), defects)

    def test_19_a_malformed_timestamp_is_a_defect(self):
        document = ledger()
        document["run"]["started"] = "yesterday"
        defects, _ = self.check(document)
        self.assertTrue(any("started" in defect for defect in defects), defects)

    # 20 — a key nobody defined is a field nobody validates.
    def test_20_an_unknown_key_is_a_defect(self):
        document = ledger()
        document["nodes"][0]["confidence"] = "high"
        defects, _ = self.check(document)
        self.assertTrue(any("confidence" in defect for defect in defects), defects)

    def test_20_an_unknown_run_key_is_a_defect(self):
        document = ledger()
        document["run"]["notes"] = "free text"
        defects, _ = self.check(document)
        self.assertTrue(any("notes" in defect for defect in defects), defects)

    # A searched node is compared across runs on its line, so it carries one.
    def test_a_searched_node_without_a_line_hash_is_a_defect(self):
        document = ledger()
        document["nodes"][0].pop("line_hash", None)
        defects, _ = self.check(document)
        self.assertTrue(any("line_hash" in defect for defect in defects), defects)

    # A node an agent read has no matched line to hash.
    def test_a_read_node_may_omit_the_line_hash(self):
        document = agent_check(ledger())
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # A claim rests on a hit its class row accounts for, or on nothing.
    def test_a_supporting_node_outside_its_class_row_is_a_defect(self):
        document = ledger()
        document["nodes"].append(
            {"id": "B3:gamma.java:4", "class": "B3", "site": "gamma.java:4",
             "disposition": "terminal", "evidence": "the call", "parent": None,
             "query_id": QUERY, "line_hash": "dddddddddddd"})
        document["claims"][0]["supporting_nodes"] = ["B3:gamma.java:4"]
        defects, _ = self.check(document)
        self.assertTrue(any("hit_ids" in defect for defect in defects), defects)

    # A parent chain that never ends, or loops, describes no path.
    def test_a_parent_cycle_is_a_defect(self):
        document = ledger()
        document["nodes"][0]["parent"] = "B1:alpha.java:9"
        document["nodes"][1]["disposition"] = "traced"
        defects, _ = self.check(document)
        self.assertTrue(any("cycle" in defect for defect in defects), defects)

    # A site names a file, or a line in one; anything else keys to nothing.
    def test_a_site_of_the_wrong_shape_is_a_defect(self):
        for value in ("alpha.java:", "alpha.java:0", "alpha.java:-3", "alpha.java:two",
                      "alpha.java:2:9", ":9"):
            document = ledger()
            document["nodes"][0]["site"] = value
            document["nodes"][0]["id"] = f"B1:{value}"
            document["boundaries"][0]["hit_ids"] = [f"B1:{value}"]
            document["nodes"][1]["parent"] = f"B1:{value}"
            document["claims"][0]["supporting_nodes"] = [f"B1:{value}"]
            defects, _ = self.check(document)
            self.assertTrue(any("site" in defect for defect in defects), (value, defects))

    def test_a_site_naming_a_whole_file_passes(self):
        document = ledger()
        document["nodes"][0].update({"site": "conf/queue.yml", "id": "B1:conf/queue.yml"})
        document["boundaries"][0]["hit_ids"] = ["B1:conf/queue.yml", "B1:alpha.java:9"]
        document["nodes"][1]["parent"] = "B1:conf/queue.yml"
        document["claims"][0]["supporting_nodes"] = ["B1:conf/queue.yml"]
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # The hash has one shape, so two runs compare the same thing.
    def test_a_line_hash_of_the_wrong_shape_is_a_defect(self):
        for value in ("AAAAAAAAAAAA", "abc", "0123456789abcd", "zzzzzzzzzzzz"):
            document = ledger()
            document["nodes"][0]["line_hash"] = value
            defects, _ = self.check(document)
            self.assertTrue(any("line_hash" in defect for defect in defects), (value, defects))

    # A node compared across runs on its line identity needs that to be text.
    def test_a_line_hash_must_be_a_string(self):
        document = ledger()
        document["nodes"][0]["line_hash"] = 12
        defects, _ = self.check(document)
        self.assertTrue(any("line_hash" in defect for defect in defects), defects)

    def test_a_line_hash_is_an_accepted_key(self):
        document = ledger()
        document["nodes"][0]["line_hash"] = "0123456789ab"
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    def test_20_a_parent_must_resolve(self):
        document = ledger()
        document["nodes"][0]["parent"] = "B1:ghost.java:1"
        defects, _ = self.check(document)
        self.assertTrue(any("parent" in defect for defect in defects), defects)


    # 2d.3 — a stamp outside the enum is not a verdict.
    def test_a_verdict_stamp_outside_the_enum_is_a_defect(self):
        document = ledger()
        document["run"]["verdict"] = "CLOSED"
        defects, _ = self.check(document)
        self.assertTrue(any("run.verdict" in defect for defect in defects), defects)

    def test_a_correct_verdict_stamp_passes(self):
        document = ledger()
        document["run"]["verdict"] = "closed"
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # 2d.4 — a hit id belongs to the class whose row points at it.
    def test_a_hit_id_of_another_class_is_a_defect(self):
        document = ledger()
        document["nodes"].append({"id": "B9:alpha.sql:1", "class": "B9", "site": "alpha.sql:1",
                                  "disposition": "terminal", "evidence": "the line",
                                  "parent": None, "query_id": QUERY})
        document = only(document, "B1", hits=1, hit_ids=["B9:alpha.sql:1"])
        defects, _ = self.check(document)
        self.assertTrue(any("its own class" in defect for defect in defects), defects)

    # 2d.7 — a table of the wrong type is a defect line, never a traceback.
    def test_a_table_of_the_wrong_type_is_a_defect(self):
        document = ledger()
        document["nodes"] = {}
        defects, verdict = self.check(document)
        self.assertTrue(any("nodes" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    # 2d.10 — a row searched into existence names the query that ran.
    def test_a_searched_row_needs_a_query(self):
        document = ledger()
        document["queries"] = []
        defects, _ = self.check(document)
        self.assertTrue(any("queries" in defect for defect in defects), defects)

    def test_a_searched_row_query_id_must_resolve(self):
        document = ledger()
        document = only(document, "B1", query_ids=["q-99999999"])
        defects, _ = self.check(document)
        self.assertTrue(any("q-99999999" in defect for defect in defects), defects)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Adversarial cases for the validator: a ledger whose parts do not bind.

Every case here starts from the same question — what could two tables say that
contradicts what a third says, while every table alone is well formed? A row
citing a query that found nothing, a node id that is not the site it names, a
claim id nobody can recompute, a class closed by a search no counter-search
ever tried to break.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_validate_coverage import CLAIM, COMMAND, QUERY, ledger, only, validate_coverage  # noqa: E402


class LedgerBindingTest(unittest.TestCase):
    def check(self, document):
        return validate_coverage.validate(document)

    # C1 — a cited query must account for the hits the row claims.
    def test_a_row_citing_a_query_that_found_nothing_is_a_defect(self):
        document = ledger()
        document["queries"][0]["count"] = 0
        defects, _ = self.check(document)
        self.assertTrue(any("every query it cites found nothing" in defect
                            for defect in defects), defects)

    def test_a_zero_hit_row_may_cite_a_query_that_found_nothing(self):
        document = ledger()
        document["queries"].append(
            {"id": validate_coverage.stable_id("q", "git grep -e Ghosttracked files"),
             "command": "git grep -e Ghost", "universe": "tracked files",
             "count": 0, "evidence": None})
        document = only(document, "B3", query_ids=[document["queries"][-1]["id"]])
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    def test_a_row_claiming_more_hits_than_its_queries_found_is_a_defect(self):
        document = ledger()
        document["nodes"].append(
            {"id": "B1:alpha.java:3", "class": "B1", "site": "alpha.java:3",
             "disposition": "terminal", "evidence": "the line", "parent": None,
             "query_id": QUERY})
        document = only(document, "B1", hits=2,
                        hit_ids=["B1:alpha.java:2", "B1:alpha.java:3"])
        defects, _ = self.check(document)
        self.assertTrue(any("more hits than" in defect for defect in defects), defects)

    def test_a_closed_row_with_no_hits_still_names_its_query(self):
        document = only(ledger(), "B3", query_ids=[])
        defects, _ = self.check(document)
        self.assertTrue(any("B3" in defect and "query" in defect for defect in defects),
                        defects)

    # C2 — a malformed row is a defect line, never a traceback.
    def test_a_row_that_is_not_an_object_is_a_defect(self):
        document = ledger()
        document["boundaries"].append("B1")
        defects, verdict = self.check(document)
        self.assertTrue(any("must be an object" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    def test_a_field_of_the_wrong_type_is_a_defect(self):
        document = only(ledger(), "B1", method=["every name form"])
        defects, _ = self.check(document)
        self.assertTrue(any("method" in defect for defect in defects), defects)

    # C3 — a load-bearing claim nobody supported is not closure.
    def test_a_load_bearing_inference_with_no_support_is_partial(self):
        document = ledger()
        document["claims"][0].update({"kind": "inference", "supporting_nodes": []})
        _, verdict = self.check(document)
        self.assertEqual(verdict, "partial")

    def test_a_load_bearing_unverified_claim_is_partial(self):
        document = ledger()
        document["claims"][0].update({"kind": "unverified", "load_bearing": True})
        _, verdict = self.check(document)
        self.assertEqual(verdict, "partial")

    # C4 — a key nobody can recompute is a key nobody can merge on.
    def test_a_node_id_that_is_not_its_own_site_is_a_defect(self):
        document = ledger()
        document["nodes"][0]["site"] = "beta.java:2"
        defects, _ = self.check(document)
        self.assertTrue(any("class:file:line" in defect for defect in defects), defects)

    def test_a_claim_id_that_is_not_its_own_digest_is_a_defect(self):
        document = ledger()
        document["claims"][0]["text"] = "a different sentence"
        defects, _ = self.check(document)
        self.assertTrue(any("digest of its text" in defect for defect in defects), defects)

    def test_a_query_id_that_is_not_its_own_digest_is_a_defect(self):
        document = ledger()
        document["queries"][0]["universe"] = "some other universe"
        defects, _ = self.check(document)
        self.assertTrue(any("digest of its command" in defect for defect in defects), defects)

    def test_a_duplicate_query_id_is_a_defect(self):
        document = ledger()
        document["queries"].append(dict(document["queries"][0]))
        defects, _ = self.check(document)
        self.assertTrue(any("duplicate query id" in defect for defect in defects), defects)

    # C5 — a class closed by a search names the counter-search that tried it.
    def test_a_searched_class_needs_a_counter_search_covering_it(self):
        document = ledger()
        document["counter_checks"][0]["classes"] = ["B1"]
        defects, _ = self.check(document)
        self.assertTrue(any("B7" in defect and "counter-search" in defect
                            for defect in defects), defects)

    def test_a_counter_search_repeating_the_primary_method_does_not_cover(self):
        document = only(ledger(), "B1", method="a second name form")
        defects, _ = self.check(document)
        self.assertTrue(any("same method" in defect for defect in defects), defects)

    def test_an_unverified_class_needs_no_counter_search(self):
        document = only(ledger(), "B7", status="unverified", reason="no method",
                        query_ids=[])
        document["counter_checks"][0]["classes"] = [k for k in validate_coverage.ALL_CLASSES
                                                    if k != "B7"]
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # C6 — the run header answers the questions the rules ask of it.
    def test_a_missing_design_phase_flag_is_a_defect(self):
        document = ledger()
        del document["run"]["design_phase"]
        defects, _ = self.check(document)
        self.assertTrue(any("design_phase" in defect for defect in defects), defects)

    def test_a_design_phase_that_is_not_a_boolean_is_a_defect(self):
        document = ledger()
        document["run"]["design_phase"] = "yes"
        defects, _ = self.check(document)
        self.assertTrue(any("design_phase" in defect for defect in defects), defects)

    def test_a_config_without_a_hash_is_a_defect(self):
        document = ledger()
        document["run"]["config"] = "defaults only"
        defects, _ = self.check(document)
        self.assertTrue(any("config" in defect for defect in defects), defects)

    # B2 — a node a search produced names that search.
    def test_a_search_node_without_a_query_id_is_a_defect(self):
        document = ledger()
        del document["nodes"][0]["query_id"]
        defects, _ = self.check(document)
        self.assertTrue(any("query_id" in defect for defect in defects), defects)

    def test_a_read_node_carries_a_null_query_id(self):
        document = ledger()
        document["nodes"][1]["query_id"] = None
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # B5 — every row says what it searched.
    def test_a_row_without_a_universe_is_a_defect(self):
        document = ledger()
        for item in document["boundaries"]:
            item.pop("universe", None)
        defects, _ = self.check(document)
        self.assertTrue(any("universe" in defect for defect in defects), defects)

    def test_a_frontier_row_with_hits_still_names_its_query(self):
        document = only(ledger(), "B14", status="frontier", reason="another repository",
                        hits=1, hit_ids=["B1:alpha.java:2"], query_ids=[])
        defects, _ = self.check(document)
        self.assertTrue(any("B14" in defect and "quer" in defect for defect in defects),
                        defects)

    # 2e self-review — a class closed by reading a site ran no query.
    def test_a_class_closed_by_reading_a_site_needs_no_query(self):
        document = only(ledger(), "B3", status="closed", query_ids=[],
                        sites=["alpha/Entry.java"], method="the registration site read")
        document["counter_checks"][0]["classes"] = [k for k in validate_coverage.ALL_CLASSES
                                                    if k != "B3"]
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # B6 — one cap, not two literals.
    def test_the_cap_is_one_constant(self):
        import importlib.util

        scripts = Path(validate_coverage.__file__).resolve().parent
        spec = importlib.util.spec_from_file_location("contract", scripts / "contract.py")
        contract = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(contract)
        self.assertEqual(validate_coverage.HIT_CAP, contract.HIT_CAP)


if __name__ == "__main__":
    unittest.main()

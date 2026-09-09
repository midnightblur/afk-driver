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

from test_validate_coverage import (CLAIM, COMMAND, COUNTER_QUERY, QUERY,  # noqa: E402
                                    ledger, only, validate_coverage)


def read_closed(document, klass):
    """One class closed the way an agent closes one: by reading its site."""
    document = only(document, klass, status="closed", query_ids=[],
                    sites=[f"alpha/{klass}.java"],
                    method="read the declared site")
    document["counter_checks"][0]["classes"] = [
        item for item in validate_coverage.ALL_CLASSES if item != klass]
    return document


def read_evidence(document, klass):
    """The node an agent leaves behind when it reads a declared site."""
    document["nodes"].append(
        {"id": f"{klass}:alpha/{klass}.java:4", "class": klass,
         "site": f"alpha/{klass}.java:4", "disposition": "terminal",
         "evidence": "the line an agent read", "parent": None, "query_id": None})
    return document


class LedgerBindingTest(unittest.TestCase):
    def check(self, document):
        return validate_coverage.validate(document)

    # C1 — a query's count is the nodes citing it, and a row's hits are the
    # nodes its own searches produced. Two numbers for one search is a defect.
    def test_a_query_counting_more_than_the_nodes_citing_it_is_a_defect(self):
        document = ledger()
        document["queries"][0]["count"] = 7
        defects, _ = self.check(document)
        self.assertTrue(any("disagrees with the 2 nodes citing it" in defect
                            for defect in defects), defects)

    def test_a_zero_hit_row_may_cite_a_query_that_found_nothing(self):
        document = ledger()
        document["queries"].append(
            {"id": validate_coverage.stable_id("q", "git grep -e Ghosttracked files"),
             "command": "git grep -e Ghost", "universe": "tracked files",
             "count": 0, "evidence": None, "origin": "seed"})
        document = only(document, "B3", query_ids=[document["queries"][-1]["id"]])
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # A site is a string in the node grammar, or the match compares nothing.
    def test_a_non_string_site_is_a_defect(self):
        document = ledger()
        document["nodes"].append(
            {"id": "B3:1", "class": "B3", "site": "1", "disposition": "terminal",
             "evidence": "the read", "parent": None, "query_id": None})
        document = only(document, "B3", sites=[1], method="read the registry",
                        query_ids=[], hits=0, hit_ids=[])
        defects, _ = self.check(document)
        self.assertTrue(any("site" in defect for defect in defects), defects)

    # A path git never writes is a site nobody can re-take.
    def test_a_backslash_site_is_a_defect(self):
        document = ledger()
        document["nodes"][0].update({"site": "alpha\\Beta.java:3",
                                     "id": "B1:alpha\\Beta.java:3"})
        document["boundaries"][0]["hit_ids"] = ["B1:alpha\\Beta.java:3",
                                                "B1:alpha.java:9"]
        document["claims"][0]["supporting_nodes"] = ["B1:alpha\\Beta.java:3"]
        document["nodes"][1]["parent"] = "B1:alpha\\Beta.java:3"
        defects, _ = self.check(document)
        self.assertTrue(any("site" in defect for defect in defects), defects)

    # A counter-search that ran the class's own queries ran the same pass twice.
    def test_a_counter_check_repeating_the_primary_queries_is_a_defect(self):
        document = ledger()
        document["counter_checks"][0].update({"classes": ["B1"], "query_ids": [QUERY]})
        defects, _ = self.check(document)
        self.assertTrue(any("different method" in defect or "same" in defect
                            for defect in defects), defects)

    # A subset is not a second method: the class already ran every search this
    # check cites, so nothing weighed against anything.
    def test_a_counter_check_citing_a_subset_of_the_primary_is_a_defect(self):
        document = ledger()
        for row in document["boundaries"]:
            if row["class"] == "B1":
                row["query_ids"] = [QUERY, COUNTER_QUERY]
        document["counter_checks"][0].update({"query_ids": [COUNTER_QUERY]})
        defects, _ = self.check(document)
        self.assertTrue(any("no command boundaries.B1 does not already run" in defect
                            for defect in defects), defects)

    # A check that answers for a class nobody verdicted answers for nothing.
    def test_a_counter_check_naming_an_unknown_class_is_a_defect(self):
        document = ledger()
        document["counter_checks"][0]["classes"] = ["B99"]
        defects, _ = self.check(document)
        self.assertTrue(any("B99" in defect for defect in defects), defects)

    def test_a_row_holding_a_node_its_own_searches_never_produced_is_a_defect(self):
        document = ledger()
        stray = {"id": validate_coverage.stable_id("q", "git grep -e Othertracked files"),
                 "command": "git grep -e Other", "universe": "tracked files",
                 "count": 1, "evidence": None, "origin": "seed"}
        document["queries"].append(stray)
        document["nodes"].append(
            {"id": "B1:alpha.java:3", "class": "B1", "site": "alpha.java:3",
             "line_hash": "abcdef123456", "disposition": "terminal",
             "evidence": "the line", "parent": None, "query_id": stray["id"]})
        document = only(document, "B1", hits=3,
                        hit_ids=["B1:alpha.java:2", "B1:alpha.java:9",
                                 "B1:alpha.java:3"])
        defects, _ = self.check(document)
        self.assertTrue(any("neither this row nor a counter-search" in defect
                            for defect in defects), defects)

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

    def test_a_gap_that_lowers_the_verdict_is_said_out_loud(self):
        document = ledger()
        document["claims"][0].update({"kind": "inference", "supporting_nodes": []})
        notes = []
        defects, verdict = validate_coverage.validate(document, notes=notes)
        self.assertEqual((defects, verdict), ([], "partial"))
        self.assertTrue(any("no node supports it" in note for note in notes), notes)
        claim = document["claims"][0]
        self.assertTrue(any(claim["id"] in note and claim["text"] in note
                            for note in notes), notes)

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
        document = read_evidence(ledger(), "B1")
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

    # 2f — `sites` switches two rules off, so it is not a field a writer may
    # set beside the evidence of the searching it says did not happen.
    def test_a_row_claiming_both_a_read_and_a_search_is_a_defect(self):
        document = read_closed(ledger(), "B3")
        document = only(document, "B3", query_ids=[QUERY])
        defects, _ = self.check(document)
        self.assertTrue(any("B3" in defect and "sites" in defect for defect in defects),
                        defects)

    def test_a_read_row_needs_an_evidence_node_per_site(self):
        document = read_closed(ledger(), "B3")
        defects, _ = self.check(document)
        self.assertTrue(any("alpha/B3.java" in defect for defect in defects), defects)

    def test_a_read_row_with_its_evidence_nodes_is_valid(self):
        document = read_evidence(read_closed(ledger(), "B3"), "B3")
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")

    def test_a_read_nodes_query_id_must_be_null(self):
        document = read_evidence(read_closed(ledger(), "B3"), "B3")
        document["nodes"][-1]["query_id"] = QUERY
        defects, verdict = self.check(document)
        self.assertTrue(any("alpha/B3.java" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    def test_a_read_node_without_evidence_does_not_close_the_site(self):
        document = read_evidence(read_closed(ledger(), "B3"), "B3")
        document["nodes"][-1].update({"disposition": "unverified",
                                      "reason": "not yet read", "evidence": None})
        defects, verdict = self.check(document)
        self.assertTrue(any("alpha/B3.java" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    # 2f self-review — a path that merely starts the same way is another file.
    def test_a_node_in_a_neighbouring_path_does_not_close_the_site(self):
        document = read_closed(ledger(), "B3")
        document["nodes"].append(
            {"id": "B3:alpha/B3.javax:4", "class": "B3", "site": "alpha/B3.javax:4",
             "disposition": "terminal", "evidence": "a line in another file",
             "parent": None, "query_id": None})
        defects, _ = self.check(document)
        self.assertTrue(any("alpha/B3.java'" in defect for defect in defects), defects)

    def test_a_read_row_whose_method_is_not_a_read_is_a_defect(self):
        document = read_closed(ledger(), "B3")
        document = only(document, "B3", method="every name form")
        defects, _ = self.check(document)
        self.assertTrue(any("B3" in defect and "names the read" in defect
                            for defect in defects), defects)

    # 2f — a node names the search that produced it, and that search is one the
    # class's own row says it ran.
    def second_query(self, document, command="git grep -e Other"):
        query_id = validate_coverage.stable_id("q", command + "tracked files")
        document["queries"].append({"id": query_id, "command": command,
                                    "universe": "tracked files", "count": 1,
                                    "evidence": None})
        return query_id

    def test_a_node_query_id_outside_the_queries_table_is_a_defect(self):
        document = ledger()
        document["nodes"][0]["query_id"] = "q-deadbeef"
        defects, _ = self.check(document)
        self.assertTrue(any("q-deadbeef" in defect for defect in defects), defects)

    def test_a_node_query_its_own_class_row_does_not_cite_is_a_defect(self):
        document = ledger()
        document["nodes"][0]["query_id"] = self.second_query(document)
        defects, _ = self.check(document)
        self.assertTrue(any("B1" in defect and "query_ids" in defect
                            for defect in defects), defects)

    # 2f — a query row is the record of one execution, so it carries one.
    def test_a_query_without_a_command_is_a_defect(self):
        document = ledger()
        del document["queries"][0]["command"]
        defects, _ = self.check(document)
        self.assertTrue(any("command" in defect for defect in defects), defects)

    def test_a_negative_query_count_is_a_defect(self):
        document = ledger()
        document["queries"][0]["count"] = -1
        defects, _ = self.check(document)
        self.assertTrue(any("count" in defect for defect in defects), defects)

    def test_a_negative_line_figure_is_a_defect(self):
        document = ledger()
        document["queries"][0]["lines"] = -1
        defects, _ = self.check(document)
        self.assertTrue(any("lines is how many lines" in defect for defect in defects),
                        defects)

    def test_a_query_may_leave_the_line_figure_out(self):
        document = ledger()
        document["queries"][0].pop("lines", None)
        defects, _ = self.check(document)
        self.assertFalse(any("lines" in defect for defect in defects), defects)

    def test_a_row_citing_the_same_query_twice_is_a_defect(self):
        document = only(ledger(), "B1", query_ids=[QUERY, QUERY])
        defects, _ = self.check(document)
        self.assertTrue(any("B1" in defect and "twice" in defect for defect in defects),
                        defects)

    # 2f — a counter-search recorded complete names the execution behind it.
    def test_a_complete_deterministic_check_without_a_query_is_a_defect(self):
        document = ledger()
        document["counter_checks"][0].pop("query_ids", None)
        defects, _ = self.check(document)
        self.assertTrue(any("counter_checks[0]" in defect and "quer" in defect
                            for defect in defects), defects)

    def test_a_complete_agent_check_without_a_node_it_read_is_a_defect(self):
        document = ledger()
        document["counter_checks"][0].update({"kind": "agent", "query_ids": []})
        defects, _ = self.check(document)
        self.assertTrue(any("counter_checks[0]" in defect and "read" in defect
                            for defect in defects), defects)

    def test_a_complete_agent_check_naming_a_node_it_read_is_valid(self):
        document = read_evidence(ledger(), "B1")
        document["counter_checks"].append(
            {"method": "read the registration site", "kind": "agent", "query_ids": [],
             "classes": ["B1"], "targeted_claims": [CLAIM], "new_nodes": [],
             "state": "complete", "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    def test_a_complete_agent_check_naming_an_evidence_free_node_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document["nodes"][-1].update({"disposition": "unverified",
                                      "reason": "not read", "evidence": None})
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [],
             "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertTrue(any("counter_checks[0]" in defect for defect in defects), defects)

    # 2f — a value the format states is checked, never carried.
    def test_a_question_type_that_is_not_a_string_is_a_defect(self):
        document = ledger()
        document["run"]["type"] = ["Q1", 3]
        defects, _ = self.check(document)
        self.assertTrue(any("run.type" in defect for defect in defects), defects)

    def test_a_boundary_row_without_a_method_is_a_defect(self):
        document = only(ledger(), "B3", method="  ")
        defects, _ = self.check(document)
        self.assertTrue(any("B3" in defect and "method" in defect for defect in defects),
                        defects)

    def test_a_citation_that_is_not_a_string_is_a_defect(self):
        document = ledger()
        document["claims"][0]["citations"] = [{"file": "alpha.java"}]
        defects, _ = self.check(document)
        self.assertTrue(any("citation" in defect for defect in defects), defects)

    # 3-A8 — a field that is present but says nothing is not evidence, and a
    # field of the wrong shape is a defect line rather than a traceback.
    def test_blank_evidence_does_not_disposition_a_node(self):
        document = ledger()
        document["nodes"][1]["evidence"] = "   "
        defects, _ = self.check(document)
        self.assertTrue(any("evidence" in defect for defect in defects), defects)

    def test_an_agent_checks_evidence_node_carries_no_query(self):
        document = ledger()
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [], "evidence_nodes": ["B1:alpha.java:9"]})
        defects, _ = self.check(document)
        self.assertTrue(any("counter_checks[0]" in defect and "read" in defect
                            for defect in defects), defects)

    def test_a_sites_field_that_is_not_a_list_is_a_defect(self):
        document = only(ledger(), "B3", sites=True, method="read the declared site",
                        query_ids=[])
        defects, _ = self.check(document)
        self.assertTrue(any("sites" in defect for defect in defects), defects)

    def test_a_directory_site_is_a_defect(self):
        document = read_closed(ledger(), "B3")
        document = only(document, "B3", sites=["alpha/"],
                        method="read the declared site", query_ids=[])
        defects, _ = self.check(document)
        self.assertTrue(any("paths" in defect for defect in defects), defects)

    # C6 — a row's arithmetic is the nodes table, and a class has a ceiling.
    def test_a_row_counting_a_node_no_search_produced_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document = only(document, "B1", hits=3,
                        hit_ids=["B1:alpha.java:2", "B1:alpha.java:9",
                                 "B1:alpha/B1.java:4"])
        defects, _ = self.check(document)
        self.assertTrue(any("nodes its searches produced" in defect
                            for defect in defects), defects)

    def test_a_class_past_the_hit_limit_is_a_defect(self):
        document = ledger()
        document = only(document, "B1", hits=validate_coverage.HIT_LIMIT + 1)
        defects, _ = self.check(document)
        self.assertTrue(any("past the" in defect and "a class may carry" in defect
                            for defect in defects), defects)

    def test_a_terminal_node_the_table_reaches_on_from_is_a_defect(self):
        document = ledger()
        parent = next(item for item in document["nodes"]
                      if item["id"] == "B1:alpha.java:2")
        parent["disposition"] = "terminal"
        defects, _ = self.check(document)
        self.assertTrue(any("the table reaches on from it" in defect
                            for defect in defects), defects)

    def test_an_agent_check_naming_no_class_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [], "classes": [],
             "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertTrue(any("names the classes it answers for" in defect
                            for defect in defects), defects)

    def test_an_agent_check_citing_a_node_of_another_class_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [], "classes": ["B2"],
             "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertTrue(any("which this check does not answer for" in defect
                            for defect in defects), defects)
    # C7 — evidence answers for the class it is of, and for every class the
    # check covers; one read closes one class.
    def test_an_agent_check_covering_a_class_it_read_nothing_of_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [], "classes": ["B1", "B2"],
             "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertTrue(any("read nothing of B2" in defect for defect in defects),
                        defects)

    def test_an_agent_check_whose_only_read_is_irrelevant_is_a_defect(self):
        document = read_evidence(ledger(), "B1")
        document["nodes"][-1].update({"disposition": "irrelevant"})
        document["counter_checks"][0].update(
            {"kind": "agent", "query_ids": [], "classes": ["B1"],
             "evidence_nodes": ["B1:alpha/B1.java:4"]})
        defects, _ = self.check(document)
        self.assertTrue(any("read nothing of B1" in defect for defect in defects),
                        defects)

    # A claim standing only on sites nobody followed is a claim the run has
    # not finished, so the verdict says so.
    def test_a_load_bearing_claim_supported_only_by_a_frontier_node_is_partial(self):
        document = ledger()
        document["nodes"].append(
            {"id": "B14:other-repo:1", "class": "B14", "site": "other-repo:1",
             "disposition": "frontier", "reason": "another repository",
             "evidence": "the caller lives elsewhere", "parent": None,
             "query_id": None})
        document["claims"][0].update({"load_bearing": True, "kind": "inference",
                                      "supporting_nodes": ["B14:other-repo:1"],
                                      "citations": ["other-repo:1"]})
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "partial")

    # Two spellings of one command are one command.
    def test_a_counter_check_rerunning_the_primary_command_respaced_is_a_defect(self):
        document = ledger()
        primary = document["queries"][0]
        respaced = {**primary, "universe": "tracked files, case-blind", "count": 0,
                    "command": primary["command"].replace(" ", "  ")}
        respaced["id"] = validate_coverage.stable_id(
            "q", respaced["command"] + respaced["universe"])
        document["queries"].append(respaced)
        document["counter_checks"][0].update({"query_ids": [respaced["id"]]})
        defects, _ = self.check(document)
        self.assertTrue(any("no command boundaries.B1 does not already run" in defect
                            for defect in defects), defects)
    def rerun(self, document, command):
        """The primary, re-run under another spelling, as a counter-search."""
        again = {**document["queries"][0], "universe": "tracked files, case-blind",
                 "count": 0, "command": command}
        again["id"] = validate_coverage.stable_id("q", command + again["universe"])
        document["queries"].append(again)
        document["counter_checks"][0].update({"query_ids": [again["id"]]})
        return self.check(document)[0]

    # One option, two spellings, one method.
    def test_a_counter_check_spelling_the_same_options_out_long_is_a_defect(self):
        document = ledger()
        defects = self.rerun(document, "git grep --line-number -I "
                             "--extended-regexp --regexp Widget")
        self.assertTrue(any("no command boundaries.B1 does not already run" in defect
                            for defect in defects), defects)

    def test_the_short_and_long_spelling_of_one_option_are_one_search(self):
        self.assertEqual(validate_coverage.normalized("git grep -i -n -e A"),
                         validate_coverage.normalized(
                             "git grep --ignore-case --line-number --regexp A"))

    # The fixed flags carry no order; the Boolean expression is the search.
    def test_the_fixed_flags_are_order_blind_and_the_boolean_terms_are_not(self):
        self.assertEqual(validate_coverage.normalized("git grep -n -E -e A"),
                         validate_coverage.normalized("git grep -E -n -e A"))
        self.assertNotEqual(
            validate_coverage.normalized("git grep --not -e A --and -e B"),
            validate_coverage.normalized("git grep --not -e B --and -e A"))

    # Paths narrow a search; they do not make it another method.
    def test_a_counter_check_rerunning_the_primary_over_fewer_files_is_a_defect(self):
        document = ledger()
        defects = self.rerun(document,
                             "git grep -n -I -E -e Widget -- alpha/Widget.java")
        self.assertTrue(any("no command boundaries.B1 does not already run" in defect
                            for defect in defects), defects)

    def test_a_counter_check_rerunning_the_primary_command_requoted_is_a_defect(self):
        document = ledger()
        primary = document["queries"][0]
        requoted = {**primary, "universe": "tracked files, case-blind", "count": 0,
                    "command": primary["command"].replace("-e ", "-e '") + "'"}
        requoted["id"] = validate_coverage.stable_id(
            "q", requoted["command"] + requoted["universe"])
        document["queries"].append(requoted)
        document["counter_checks"][0].update({"query_ids": [requoted["id"]]})
        defects, _ = self.check(document)
        self.assertTrue(any("no command boundaries.B1 does not already run" in defect
                            for defect in defects), defects)


if __name__ == "__main__":
    unittest.main()

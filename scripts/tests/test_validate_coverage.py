#!/usr/bin/env python3
"""Rule tests for the coverage-ledger validator.

Each case pins one way a ledger could publish more certainty than it holds:
a class with no verdict, a seed status left in a published ledger, a
load-bearing claim with nothing under it, a dangling reference, a
counter-search that never ran, a verdict that overstates the record.
"""

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_SCRIPTS = Path(os.environ.get("AFK_INVESTIGATE_SCRIPTS")
                or Path(__file__).resolve().parent.parent.parent
                / "skills" / "utils" / "investigate" / "scripts")
_spec = importlib.util.spec_from_file_location(
    "validate_coverage", _SCRIPTS / "validate_coverage.py"
)
validate_coverage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_coverage)

ALL = validate_coverage.ALL_CLASSES

# The fixture's stable keys, computed the way the format defines them, so a
# test never pins an id the validator would have to accept blindly.
COMMAND = "git grep -n -I -E -e Widget"
QUERY = validate_coverage.stable_id("q", COMMAND + "tracked files")
CLAIM = validate_coverage.stable_id("c", "the path starts here")


def ledger(**overrides) -> dict:
    """A minimal ledger that is structurally valid and fully closed."""
    document = {
        "run": {
            "repository": "/fixture", "head": "0" * 40, "question": "how does it work",
            "type": ["Q1"], "roots": ["Widget"], "aliases": {"Widget": []},
            "inventory_hash": "a" * 64, "inventory_count": 3,
            "started": "2026-01-01T00:00:00+00:00", "finished": "2026-01-01T00:01:00+00:00",
            "design_phase": False, "config": {"path": "defaults", "sha256": "b" * 64},
        },
        "boundaries": [
            {"class": "B1", "status": "closed", "method": "every name form",
             "hits": 1, "hit_ids": ["B1:alpha.java:2"], "query_ids": [QUERY],
             "universe": "tracked files"},
            *[
                {"class": klass, "status": "closed", "method": "searched",
                 "hits": 0, "hit_ids": [], "query_ids": [QUERY],
                 "universe": "tracked files"}
                for klass in ALL[1:]
            ],
        ],
        "nodes": [
            {"id": "B1:alpha.java:2", "class": "B1", "site": "alpha.java:2",
             "disposition": "traced", "evidence": "the line", "parent": None,
             "query_id": QUERY},
            {"id": "B1:alpha.java:9", "class": "B1", "site": "alpha.java:9",
             "disposition": "terminal", "evidence": "the write",
             "parent": "B1:alpha.java:2", "query_id": QUERY},
        ],
        "queries": [{"id": QUERY, "command": COMMAND,
                     "universe": "tracked files", "count": 1, "evidence": None}],
        "claims": [{"id": CLAIM, "text": "the path starts here", "kind": "fact",
                    "load_bearing": True, "supporting_nodes": ["B1:alpha.java:2"],
                    "citations": ["alpha.java:2"]}],
        "counter_checks": [{"method": "a second name form", "kind": "deterministic",
                            "targeted_claims": [CLAIM], "new_nodes": [],
                            "state": "complete", "classes": list(ALL),
                            "query_ids": [QUERY]}],
    }
    document.update(overrides)
    return document


def only(document, klass, **fields):
    """Replace one boundary row, keeping the rest closed."""
    document = copy.deepcopy(document)
    for row in document["boundaries"]:
        if row["class"] == klass:
            row.update(fields)
    return document


class ValidateCoverageTest(unittest.TestCase):
    def check(self, document):
        return validate_coverage.validate(document)

    def test_a_complete_ledger_is_closed(self):
        defects, verdict = self.check(ledger())
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed")

    # V1 — required fields and referential integrity.
    def test_a_missing_run_field_is_a_defect(self):
        document = ledger()
        document["run"]["head"] = ""
        defects, _ = self.check(document)
        self.assertIn("run.head: required", defects)

    def test_a_class_without_a_row_is_a_defect(self):
        document = ledger()
        document["boundaries"] = document["boundaries"][:-1]
        defects, _ = self.check(document)
        self.assertTrue(any("B14" in defect for defect in defects), defects)

    def test_a_dangling_hit_id_is_a_defect(self):
        document = only(ledger(), "B1", hit_ids=["B1:ghost.java:9"])
        defects, _ = self.check(document)
        self.assertTrue(any("ghost.java" in defect for defect in defects), defects)

    def test_a_dangling_supporting_node_is_a_defect(self):
        document = ledger()
        document["claims"][0]["supporting_nodes"] = ["B1:ghost.java:9"]
        defects, _ = self.check(document)
        self.assertTrue(any("supporting node" in defect for defect in defects), defects)

    def test_a_dangling_targeted_claim_is_a_defect(self):
        document = ledger()
        document["counter_checks"][0]["targeted_claims"] = ["c-99999999"]
        defects, _ = self.check(document)
        self.assertTrue(any("targeted claim" in defect for defect in defects), defects)

    # L2 — claims carry ids, and the ids are unique.
    def test_a_claim_without_an_id_is_a_defect(self):
        document = ledger()
        del document["claims"][0]["id"]
        defects, _ = self.check(document)
        self.assertTrue(any("id required" in defect for defect in defects), defects)

    # L3 — a node that was not crossed says why.
    def test_a_frontier_node_without_a_reason_is_a_defect(self):
        document = ledger()
        document["nodes"][0].update({"disposition": "frontier", "evidence": "the line"})
        defects, _ = self.check(document)
        self.assertTrue(any("needs a reason" in defect for defect in defects), defects)

    def test_a_judged_q3_node_needs_a_verdict_and_a_pin(self):
        document = ledger()
        document["run"]["type"] = ["Q3"]
        document["counter_checks"].append(
            {"method": "the registration site", "kind": "agent", "targeted_claims": [],
             "new_nodes": [], "state": "complete"})
        defects, _ = self.check(document)
        self.assertTrue(any("Q3 node needs" in defect for defect in defects), defects)
        self.assertTrue(any("pins it" in defect for defect in defects), defects)

    def test_an_untriaged_node_needs_no_verdict(self):
        document = ledger()
        document["run"]["type"] = ["Q3"]
        for node in document["nodes"]:
            node.update({"disposition": "unverified", "reason": "not yet triaged"})
        document["nodes"].append(
            {"id": "B1:alpha.java:12", "class": "B1", "site": "alpha.java:12",
             "disposition": "terminal", "evidence": "the registration line",
             "parent": None, "query_id": None, "impact_verdict": "unchanged",
             "pinned_by": "unguarded"})
        document["counter_checks"].append(
            {"method": "the registration site", "kind": "agent", "targeted_claims": [CLAIM],
             "new_nodes": [], "state": "complete",
             "evidence_nodes": ["B1:alpha.java:12"]})
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "partial")

    # V2 — the seed status never publishes, and load-bearing claims are cited.
    def test_judgment_only_is_rejected_as_a_final_status(self):
        document = only(ledger(), "B3", status="judgment-only", reason="a site to read")
        defects, verdict = self.check(document)
        self.assertTrue(any("judgment-only" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    def test_an_uncited_load_bearing_inference_is_a_defect(self):
        document = ledger()
        document["claims"][0].update({"kind": "inference", "citations": []})
        defects, _ = self.check(document)
        self.assertTrue(any("names what it rests on" in defect for defect in defects), defects)

    def test_an_uncited_claim_that_is_not_load_bearing_passes(self):
        document = ledger()
        document["claims"][0].update({"kind": "inference", "citations": [],
                                      "load_bearing": False})
        defects, _ = self.check(document)
        self.assertEqual(defects, [])

    # V3 — every question type needs a counter-search; some need an agent's.
    def test_no_complete_counter_search_is_a_defect(self):
        document = ledger()
        document["counter_checks"] = []
        defects, _ = self.check(document)
        self.assertTrue(any("complete counter-search" in defect for defect in defects), defects)

    def test_q2_needs_an_agent_driven_counter_search(self):
        document = ledger()
        document["run"]["type"] = ["Q2"]
        defects, _ = self.check(document)
        self.assertTrue(any("agent-driven" in defect for defect in defects), defects)

    def test_a_design_phase_run_needs_an_agent_driven_counter_search(self):
        document = ledger()
        document["run"]["design_phase"] = True
        defects, _ = self.check(document)
        self.assertTrue(any("agent-driven" in defect for defect in defects), defects)

    def test_a_pending_counter_search_states_why(self):
        document = ledger()
        document["counter_checks"].append(
            {"method": "a wire form", "kind": "deterministic", "targeted_claims": [],
             "new_nodes": [], "state": "pending"})
        defects, verdict = self.check(document)
        self.assertTrue(any("states why" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    # V4 / L5 — the verdict the record supports.
    def test_a_frontier_class_downgrades_to_closed_with_frontier(self):
        document = only(ledger(), "B14", status="frontier", reason="another repository")
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "closed-with-frontier")

    def test_an_unverified_class_downgrades_to_partial(self):
        document = only(ledger(), "B3", status="unverified", reason="no enumeration method")
        defects, verdict = self.check(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "partial")

    def test_an_overstated_verdict_is_a_defect(self):
        document = only(ledger(), "B3", status="unverified", reason="no enumeration method")
        document["run"]["verdict"] = "closed"
        defects, verdict = self.check(document)
        self.assertTrue(any("run.verdict" in defect for defect in defects), defects)
        self.assertEqual(verdict, "partial")

    def test_the_command_prints_the_verdict_and_exits_zero_when_valid(self):
        path = Path(tempfile.mkdtemp(prefix="ledger-")) / "COVERAGE.json"
        path.write_text(json.dumps(ledger()), encoding="utf-8")
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = validate_coverage.main(["--ledger", str(path)])
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: closed", buffer.getvalue())

    def test_the_command_exits_one_when_structurally_invalid(self):
        path = Path(tempfile.mkdtemp(prefix="ledger-")) / "COVERAGE.json"
        broken = ledger()
        broken["boundaries"] = broken["boundaries"][:-1]
        path.write_text(json.dumps(broken), encoding="utf-8")
        import io
        from contextlib import redirect_stdout, redirect_stderr

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = validate_coverage.main(["--ledger", str(path)])
        self.assertEqual(code, 1)
        self.assertIn("VERDICT: partial", out.getvalue())

    def test_an_unreadable_ledger_exits_two(self):
        import io
        from contextlib import redirect_stderr

        with redirect_stderr(io.StringIO()):
            code = validate_coverage.main(["--ledger", "no/such/COVERAGE.json"])
        self.assertEqual(code, 2)

    def test_a_missing_table_is_a_defect(self):
        document = ledger()
        del document["queries"]
        defects, verdict = self.check(document)
        self.assertIn("queries: table missing", defects)
        self.assertEqual(verdict, "partial")


if __name__ == "__main__":
    unittest.main()

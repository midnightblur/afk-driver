#!/usr/bin/env python3
"""Rules for the SDD seam gate: a row is only as settled as its ledger.

Each case pins a way a design could publish a seam nobody closed — a row
citing nothing, a citation resolving to no ledger, a ledger that stopped at
`partial`, a ledger whose load-bearing claim was never verified.
"""

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
sys.path.insert(0, str(_TESTS))

_spec = importlib.util.spec_from_file_location(
    "check_sdd_investigations",
    _ROOT / "skills" / "afk" / "to-sdd" / "scripts" / "check_sdd_investigations.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

from test_validate_coverage import ledger, only  # noqa: E402

SDD = """# SDD

## §13 Open questions

nothing open.

## §14 L9 — Implementation Seams & Change Impact

| Seam (class/method/contract) | Existing contract (INV-NNN) | Planned change | Impacted flows (INV-NNN) | Conventions / landmines | Verdict |
|---|---|---|---|---|---|
{rows}

Below the table: nothing accepted.
"""

ROW = "| the widget port | INV-001 | one new method | none (INV-001) | none | fits |"


class SddInvestigationGateTest(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="sddgate-"))
        self.addCleanup(shutil.rmtree, self.work, ignore_errors=True)

    def write(self, rows=ROW, document=None, folder="INV-001-the-widget-port"):
        sdd = self.work / "SDD.md"
        sdd.write_text(SDD.format(rows=rows), encoding="utf-8")
        if document is not None:
            target = self.work / "investigations" / folder
            target.mkdir(parents=True, exist_ok=True)
            (target / "COVERAGE.json").write_text(json.dumps(document), encoding="utf-8")
        return sdd

    def run_gate(self, *args):
        return gate.main([str(arg) for arg in args])

    def closed(self):
        document = ledger()
        document["run"]["verdict"] = "closed"
        return document

    def test_a_row_citing_a_closed_ledger_passes(self):
        sdd = self.write(document=self.closed())
        self.assertEqual(self.run_gate("--sdd", sdd), 0)

    def test_a_row_citing_nothing_is_a_blocker(self):
        sdd = self.write(rows="| the widget port | read the class | one new method | none | none | fits |",
                         document=self.closed())
        self.assertEqual(self.run_gate("--sdd", sdd), 1)

    def test_a_citation_with_no_ledger_is_a_blocker(self):
        sdd = self.write(document=None)
        self.assertEqual(self.run_gate("--sdd", sdd), 1)

    def test_a_partial_ledger_is_a_blocker(self):
        document = only(self.closed(), "B3", status="partial", reason="one form unenumerated")
        sdd = self.write(document=document)
        self.assertEqual(self.run_gate("--sdd", sdd), 1)

    def test_a_frontier_ledger_passes(self):
        document = only(self.closed(), "B14", status="frontier",
                        reason="another repository", query_ids=[])
        document["counter_checks"][0]["classes"] = [
            item for item in gate.load_validator().ALL_CLASSES if item != "B14"]
        document["run"]["verdict"] = "closed-with-frontier"
        sdd = self.write(document=document)
        self.assertEqual(self.run_gate("--sdd", sdd), 0)

    def test_a_load_bearing_unverified_claim_is_a_blocker(self):
        document = self.closed()
        document["claims"][0].update({"kind": "unverified", "load_bearing": True})
        sdd = self.write(document=document)
        self.assertEqual(self.run_gate("--sdd", sdd), 1)

    def test_an_unverified_claim_that_carries_nothing_only_prints(self):
        document = self.closed()
        document["claims"].append(
            {"id": gate.load_validator().stable_id("c", "a side note"),
             "text": "a side note", "kind": "unverified", "load_bearing": False,
             "supporting_nodes": [], "citations": []})
        sdd = self.write(document=document)
        self.assertEqual(self.run_gate("--sdd", sdd), 0)

    def test_a_structurally_broken_ledger_is_a_blocker(self):
        document = self.closed()
        del document["run"]["design_phase"]
        sdd = self.write(document=document)
        self.assertEqual(self.run_gate("--sdd", sdd), 1)

    def test_an_sdd_without_a_seam_table_is_a_usage_error(self):
        sdd = self.work / "SDD.md"
        sdd.write_text("# SDD\n\n## §13 Open questions\n\nnothing.\n", encoding="utf-8")
        self.assertEqual(self.run_gate("--sdd", sdd), 2)


if __name__ == "__main__":
    unittest.main()

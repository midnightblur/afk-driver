#!/usr/bin/env python3
"""Rules for the ground diff: has the code moved under a cited investigation?

Each case pins a way a comparison could report calm ground that moved — two
identical lines collapsing into one key, a site that vanished, a row that holds
the cap rather than the ground.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
_SCRIPTS = _ROOT / "skills" / "utils" / "investigate" / "scripts"
sys.path.insert(0, str(_TESTS))

_spec = importlib.util.spec_from_file_location("ground_diff", _SCRIPTS / "ground_diff.py")
ground_diff = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ground_diff)


def node(line: int, line_hash: str, klass: str = "B1", file: str = "alpha.java") -> dict:
    return {"id": f"{klass}:{file}:{line}", "class": klass, "site": f"{file}:{line}",
            "disposition": "terminal", "evidence": "the line", "parent": None,
            "query_id": "q-11111111", "line_hash": line_hash}


def ledger(nodes: list[dict], truncated: list[str] = ()) -> dict:
    classes = sorted({item["class"] for item in nodes} | set(truncated))
    return {
        "run": {"head": "0" * 40},
        "boundaries": [{"class": klass, "status": "closed", "method": "searched",
                        "hits": 1, "truncated": klass in truncated, "hit_ids": [],
                        "query_ids": [], "universe": "tracked files"}
                       for klass in classes],
        "nodes": nodes,
    }


class GroundDiffTest(unittest.TestCase):
    def diff(self, cited, current):
        work = Path(tempfile.mkdtemp(prefix="grounddiff-"))
        left, right = work / "cited.json", work / "current.json"
        left.write_text(json.dumps(cited), encoding="utf-8")
        right.write_text(json.dumps(current), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "ground_diff.py"),
             "--cited", str(left), "--current", str(right)],
            capture_output=True, encoding="utf-8", errors="replace")
        return result.returncode, result.stdout + result.stderr

    def test_the_same_ground_is_no_drift(self):
        document = ledger([node(2, "aaaaaaaaaaaa"), node(9, "bbbbbbbbbbbb")])
        code, output = self.diff(document, json.loads(json.dumps(document)))
        self.assertEqual(code, 0, output)

    # A key set collapses two identical lines into one; a multiset does not.
    def test_a_second_identical_line_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        current = ledger([node(2, "aaaaaaaaaaaa"), node(40, "aaaaaaaaaaaa")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("aaaaaaaaaaaa", output)

    # A site the cited ledger held and the tree no longer has is drift, and the
    # comparison must never answer "proceed" to it.
    def test_a_vanished_site_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa"), node(9, "bbbbbbbbbbbb")])
        current = ledger([node(2, "aaaaaaaaaaaa")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("bbbbbbbbbbbb", output)

    # A line edited in place keeps its number and changes its identity.
    def test_an_edited_line_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        current = ledger([node(2, "cccccccccccc")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)

    # A capped row holds the cap, not the ground: it cannot answer the question.
    def test_a_truncated_cited_row_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")], truncated=["B1"])
        code, output = self.diff(cited, json.loads(json.dumps(cited)))
        self.assertEqual(code, 1)
        self.assertIn("B1", output)
        self.assertIn("truncated", output)

    # A node an agent read carries no matched line, so it is not ground.
    def test_a_read_node_is_not_compared(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        current = ledger([node(2, "aaaaaaaaaaaa")])
        read = {"id": "B1:alpha.java:77", "class": "B1", "site": "alpha.java:77",
                "disposition": "terminal", "evidence": "the registration",
                "parent": None, "query_id": None}
        current["nodes"].append(read)
        code, output = self.diff(cited, current)
        self.assertEqual(code, 0, output)

    def test_an_unreadable_ledger_is_a_usage_error(self):
        work = Path(tempfile.mkdtemp(prefix="grounddiff-"))
        missing = work / "gone.json"
        present = work / "cited.json"
        present.write_text(json.dumps(ledger([node(2, "aaaaaaaaaaaa")])), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "ground_diff.py"),
             "--cited", str(present), "--current", str(missing)],
            capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

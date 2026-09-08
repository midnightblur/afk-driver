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


QUERY = "q-11111111"
TRACER_QUERY = "q-99999999"


def ledger(nodes: list[dict], truncated: list[str] = (), config: str = "c" * 64,
           queries: list[str] = (QUERY,), tracer_queries: list[str] = ()) -> dict:
    classes = sorted({item["class"] for item in nodes} | set(truncated))
    return {
        "run": {"head": "0" * 40, "config": {"path": "defaults", "sha256": config}},
        "boundaries": [{"class": klass, "status": "closed", "method": "searched",
                        "hits": 1, "truncated": klass in truncated, "hit_ids": [],
                        "query_ids": [], "universe": "tracked files"}
                       for klass in classes],
        "nodes": nodes,
        "queries": [{"id": item, "command": "git grep", "universe": "tracked files",
                     "count": 1, "evidence": None, "origin": origin}
                    for origin, group in (("seed", queries), ("tracer", tracer_queries))
                    for item in group],
    }


class GroundDiffTest(unittest.TestCase):
    def diff(self, cited, current):
        return self.run_diff(cited, current)

    def run_diff(self, cited, current, *extra):
        work = Path(tempfile.mkdtemp(prefix="grounddiff-"))
        left, right = work / "cited.json", work / "current.json"
        left.write_text(json.dumps(cited), encoding="utf-8")
        right.write_text(json.dumps(current), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "ground_diff.py"),
             "--cited", str(left), "--current", str(right), *extra],
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

    # The two runs must have searched under the same configuration, or the
    # comparison is between two different questions.
    def test_a_configuration_change_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa", klass="B11")])
        current = ledger([node(2, "aaaaaaaaaaaa", klass="B11")], config="d" * 64)
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("configuration", output)

    # A class filter narrows the nodes, never the ground the run stood on.
    def test_a_class_filter_cannot_mask_a_configuration_change(self):
        cited = ledger([node(2, "aaaaaaaaaaaa", klass="B11")])
        current = ledger([node(2, "aaaaaaaaaaaa", klass="B11")], config="d" * 64)
        code, output = self.run_diff(cited, current, "--class", "B1")
        self.assertEqual(code, 1)
        self.assertIn("configuration", output)

    # A ledger that does not say what it searched under cannot be compared.
    def test_a_ledger_without_a_config_stamp_is_a_usage_error(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        cited["run"].pop("config")
        code, output = self.diff(cited, ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)

    def test_a_ledger_without_a_head_is_a_usage_error(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        cited["run"].pop("head")
        code, output = self.diff(cited, ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)

    # A searched node with no line hash makes the ground unreadable.
    def test_a_cited_searched_node_without_a_hash_is_a_usage_error(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        cited["nodes"][0].pop("line_hash")
        code, output = self.diff(cited, ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)
        self.assertIn("B1:alpha.java:2", output)

    # A hash on a node an agent read is not ground either way.
    def test_a_read_node_carrying_a_hash_is_not_ground(self):
        cited = ledger([node(2, "aaaaaaaaaaaa")])
        current = ledger([node(2, "aaaaaaaaaaaa")])
        widened = node(50, "dddddddddddd")
        widened["query_id"] = None
        current["nodes"].append(widened)
        code, output = self.diff(cited, current)
        self.assertEqual(code, 0, output)

    # A tracer widened past the seed map's searches; those nodes are not ground
    # the seed map can re-take, so they are counted, not compared.
    def test_tracer_widened_nodes_are_counted_not_compared(self):
        widened = node(80, "eeeeeeeeeeee")
        widened["query_id"] = TRACER_QUERY
        cited = ledger([node(2, "aaaaaaaaaaaa"), widened],
                       tracer_queries=(TRACER_QUERY,))
        code, output = self.diff(cited, ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 0, output)
        self.assertIn("1 tracer nodes not compared", output)

    # A seed search the current run no longer runs is drift, not a quiet drop:
    # the pattern that closed the class is gone.
    def test_a_seed_query_that_no_longer_runs_is_drift(self):
        cited = ledger([node(2, "aaaaaaaaaaaa", klass="B11")],
                       queries=(QUERY, "q-22222222"))
        current = ledger([node(2, "aaaaaaaaaaaa", klass="B11")], queries=(QUERY,))
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("q-22222222", output)
        self.assertIn("no longer runs", output)

    # A site with no line keys to its path, not to its last segment.
    def test_a_site_without_a_line_keys_to_its_path(self):
        left = node(1, "aaaaaaaaaaaa")
        left["site"] = "conf/queue.yml"
        left["id"] = "B1:conf/queue.yml"
        right = json.loads(json.dumps(left))
        code, output = self.diff(ledger([left]), ledger([right]))
        self.assertEqual(code, 0, output)
        moved = json.loads(json.dumps(left))
        moved["site"] = "other/queue.yml"
        code, output = self.diff(ledger([left]), ledger([moved]))
        self.assertEqual(code, 1)
        self.assertIn("conf/queue.yml", output)

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

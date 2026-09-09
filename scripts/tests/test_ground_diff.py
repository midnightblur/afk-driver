#!/usr/bin/env python3
"""Rules for the ground diff: has the code moved under a cited investigation?

Each case pins a way a comparison could report calm ground that moved — two
identical lines collapsing into one key, a site that vanished, a class whose
status slipped, a file only an agent ever read, a configuration that changed
under both runs.
"""

import importlib.util
import json
import shutil
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

QUERY = "q-11111111"
TRACER_QUERY = "q-99999999"


def git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, encoding="utf-8", errors="replace")


def head(repo) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), check=True,
                          capture_output=True, encoding="utf-8").stdout.strip()


def node(line: int, line_hash: str, klass: str = "B1", file: str = "alpha.java",
         query: str = QUERY) -> dict:
    return {"id": f"{klass}:{file}:{line}", "class": klass, "site": f"{file}:{line}",
            "disposition": "terminal", "evidence": "the line", "parent": None,
            "query_id": query, "line_hash": line_hash}


def read_node(file: str = "conf/queue.yml", klass: str = "B1") -> dict:
    return {"id": f"{klass}:{file}", "class": klass, "site": file,
            "disposition": "terminal", "evidence": "the registration", "parent": None,
            "query_id": None}


class GroundDiffTest(unittest.TestCase):
    """Two snapshots of one throwaway repository, so the git checks are real."""

    @classmethod
    def setUpClass(cls):
        cls.repo = Path(tempfile.mkdtemp(prefix="grounddiff-repo-"))
        git(cls.repo, "init", "-q")
        git(cls.repo, "config", "user.email", "fixture@example.invalid")
        git(cls.repo, "config", "user.name", "fixture")
        (cls.repo / "alpha.java").write_text("class Widget {}\n", encoding="utf-8")
        (cls.repo / "conf").mkdir()
        (cls.repo / "conf" / "queue.yml").write_text("topic: widget\n", encoding="utf-8")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "first")
        cls.before = head(cls.repo)
        (cls.repo / "alpha.java").write_text("class Widget { }\n", encoding="utf-8")
        git(cls.repo, "add", "-A")
        git(cls.repo, "commit", "-qm", "second")
        cls.after = head(cls.repo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)

    def ledger(self, nodes, config="c" * 64, queries=(QUERY,),
               tracer_queries=(), snapshot=None, statuses=None) -> dict:
        classes = sorted({item["class"] for item in nodes} | set(statuses or {}))
        return {
            "run": {"head": snapshot or self.after,
                    "config": {"path": "defaults", "sha256": config}},
            "boundaries": [{"class": klass,
                            "status": (statuses or {}).get(klass, "closed"),
                            "method": "searched", "hits": 1, "hit_ids": [],
                            "query_ids": [], "universe": "tracked files"}
                           for klass in classes],
            "nodes": nodes,
            "queries": [{"id": item, "command": "git grep", "universe": "tracked files",
                         "count": 1, "evidence": None, "origin": origin}
                        for origin, group in (("seed", queries),
                                              ("tracer", tracer_queries))
                        for item in group],
        }

    def diff(self, cited, current, *extra):
        work = Path(tempfile.mkdtemp(prefix="grounddiff-"))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        left, right = work / "cited.json", work / "current.json"
        left.write_text(json.dumps(cited), encoding="utf-8")
        right.write_text(json.dumps(current), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "ground_diff.py"), "--repo", str(self.repo),
             "--cited", str(left), "--current", str(right), *extra],
            capture_output=True, encoding="utf-8", errors="replace")
        return result.returncode, result.stdout + result.stderr

    def test_the_same_ground_is_no_drift(self):
        document = self.ledger([node(2, "aaaaaaaaaaaa"), node(9, "bbbbbbbbbbbb")])
        code, output = self.diff(document, json.loads(json.dumps(document)))
        self.assertEqual(code, 0, output)

    # A key set collapses two identical lines into one; a multiset does not.
    def test_a_second_identical_line_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        current = self.ledger([node(2, "aaaaaaaaaaaa"), node(40, "aaaaaaaaaaaa")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("aaaaaaaaaaaa", output)

    def test_a_vanished_site_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa"), node(9, "bbbbbbbbbbbb")])
        current = self.ledger([node(2, "aaaaaaaaaaaa")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("bbbbbbbbbbbb", output)

    def test_an_edited_line_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        current = self.ledger([node(2, "cccccccccccc")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)

    # A class that no longer closes is drift even when every line matches.
    def test_a_boundary_status_change_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        current = self.ledger([node(2, "aaaaaaaaaaaa")], statuses={"B1": "partial"})
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("was closed, and now it is partial", output)

    # The two runs must have searched under the same configuration.
    def test_a_configuration_change_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")])
        current = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")], config="d" * 64)
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("configuration", output)

    def test_a_class_filter_cannot_mask_a_configuration_change(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")])
        current = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")], config="d" * 64)
        code, output = self.diff(cited, current, "--class", "B1")
        self.assertEqual(code, 1)
        self.assertIn("configuration", output)

    def test_a_ledger_without_a_config_stamp_is_a_usage_error(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        cited["run"].pop("config")
        code, _ = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)

    def test_a_ledger_without_a_head_is_a_usage_error(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        cited["run"].pop("head")
        code, _ = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)

    # The current ledger must describe the checkout it is compared in.
    def test_a_current_ledger_from_another_checkout_is_a_usage_error(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        current = self.ledger([node(2, "aaaaaaaaaaaa")], snapshot=self.before)
        code, output = self.diff(cited, current)
        self.assertEqual(code, 2)
        self.assertIn("another snapshot", output)

    def test_a_cited_searched_node_without_a_hash_is_a_usage_error(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        cited["nodes"][0].pop("line_hash")
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)
        self.assertIn("B1:alpha.java:2", output)

    # A node citing a query nobody holds cannot be classified at all.
    def test_a_node_citing_an_unknown_query_is_a_usage_error(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa", query="q-deadbeef")])
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 2)
        self.assertIn("q-deadbeef", output)

    def test_a_read_node_is_not_compared(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa")])
        current = self.ledger([node(2, "aaaaaaaaaaaa"), read_node("beta.java")])
        code, output = self.diff(cited, current)
        self.assertEqual(code, 0, output)

    # A widening is counted, and its file is watched instead of re-searched.
    def test_tracer_widened_nodes_are_counted_not_compared(self):
        widened = node(80, "eeeeeeeeeeee", file="beta.java", query=TRACER_QUERY)
        cited = self.ledger([node(2, "aaaaaaaaaaaa"), widened],
                            tracer_queries=(TRACER_QUERY,))
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 0, output)
        self.assertIn("1 tracer nodes not compared", output)

    # A file only a read node stands on is watched through git.
    def test_a_changed_read_site_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa"), read_node("alpha.java")],
                            snapshot=self.before)
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 1)
        self.assertIn("alpha.java: a site this run read", output)

    # A tracer's file is watched the same way, which catches a node it lost.
    def test_a_changed_tracer_site_is_drift(self):
        widened = node(4, "eeeeeeeeeeee", file="alpha.java", query=TRACER_QUERY)
        cited = self.ledger([widened], tracer_queries=(TRACER_QUERY,),
                            snapshot=self.before)
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 1)
        self.assertIn("changed between the two snapshots", output)

    def test_an_untouched_read_site_is_not_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa"), read_node("conf/queue.yml")],
                            snapshot=self.before)
        code, output = self.diff(cited, self.ledger([node(2, "aaaaaaaaaaaa")]))
        self.assertEqual(code, 0, output)

    # A seed search the current run no longer runs is drift, not a quiet drop.
    def test_a_seed_query_that_no_longer_runs_is_drift(self):
        cited = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")],
                            queries=(QUERY, "q-22222222"))
        current = self.ledger([node(2, "aaaaaaaaaaaa", klass="B11")], queries=(QUERY,))
        code, output = self.diff(cited, current)
        self.assertEqual(code, 1)
        self.assertIn("q-22222222", output)
        self.assertIn("no longer runs", output)

    # A site with no line keys to its path, not to its last segment.
    def test_a_site_without_a_line_keys_to_its_path(self):
        left = node(1, "aaaaaaaaaaaa")
        left.update({"site": "conf/queue.yml", "id": "B1:conf/queue.yml"})
        code, output = self.diff(self.ledger([left]),
                                 self.ledger([json.loads(json.dumps(left))]))
        self.assertEqual(code, 0, output)
        moved = json.loads(json.dumps(left))
        moved["site"] = "other/queue.yml"
        code, output = self.diff(self.ledger([left]), self.ledger([moved]))
        self.assertEqual(code, 1)
        self.assertIn("conf/queue.yml", output)

    def test_an_unreadable_ledger_is_a_usage_error(self):
        work = Path(tempfile.mkdtemp(prefix="grounddiff-"))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        present = work / "cited.json"
        present.write_text(json.dumps(self.ledger([node(2, "aaaaaaaaaaaa")])),
                           encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "ground_diff.py"), "--repo", str(self.repo),
             "--cited", str(present), "--current", str(work / "gone.json")],
            capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()

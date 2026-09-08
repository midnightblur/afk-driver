#!/usr/bin/env python3
"""Adversarial cases for the seed map: closure claimed over an unreached set.

Every case here starts from the same question — what did the pre-pass NOT
search before it wrote `closed`? A skipped file, a class whose universe is
another class's incomplete hit set, a pattern that escaped its path scope, a
manifest nobody could parse, a line too long to compare. Fixtures are
throwaway git repositories.
"""

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_seed_map import row, run, seed_map, write_config, make_repo  # noqa: E402


def check(document, needle):
    """The counter-search whose method says what it did — never a position."""
    found = [item for item in document["counter_checks"]
             if needle in item["method"] and "own expressions" not in item["method"]]
    assert len(found) == 1, f"{needle}: {[item['method'] for item in document['counter_checks']]}"
    return found[0]


class SeedMapReachTest(unittest.TestCase):
    def setUp(self):
        self.trash = []

    def tearDown(self):
        for path in self.trash:
            shutil.rmtree(path, ignore_errors=True)

    def repo(self, files, commit=True):
        root = make_repo(files, commit)
        self.trash.append(root)
        return root

    # 1 — a filter class searches B1's hits, so it cannot close while B1 is open.
    def test_1_filter_classes_inherit_an_incomplete_b1(self):
        repo = self.repo({"notes/widget.md": "Widget is described here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B1")["status"], "partial")
        self.assertEqual(row(document, "B13")["status"], "partial")
        self.assertIn("B1", row(document, "B13")["reason"])

    def test_1_filter_classes_close_when_b1_closes(self):
        repo = self.repo({"notes/widget.md": "Widget is described here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=W")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B13")["status"], "closed")

    # 2 — a file the walk skipped is a file nobody searched.
    def test_2_unread_generated_files_keep_b6_partial(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        built = repo / "build-output"
        built.mkdir()
        (built / "huge.txt").write_text("x" * (seed_map.MAX_WALK_BYTES + 10), encoding="utf-8")
        (built / "binaryish.txt").write_bytes(b"\xff\xfe Widget \x00\x01")
        config = write_config(repo, "investigation:\n  generated:\n    - build-output\n")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B6")["status"], "partial")
        self.assertIn("unread", row(document, "B6")["reason"])

    # 3 — an unexpected failure is one error line and exit 2, never a traceback.
    def test_3_an_unexpected_failure_exits_two(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(repo))
        self.assertEqual(code, 2)
        self.assertIsNone(document)

    # 4 — a declared pattern runs beside a class's own method, never instead of it.
    def test_4_declared_patterns_run_on_special_classes(self):
        repo = self.repo({"ops/deploy.txt": "Widget ships here\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: deployment-manifest\n"
            "      class: B14\n"
            "      pattern: 'Widget ships'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertGreater(row(document, "B14")["hits"], 0)

    # 5 — each declared pattern keeps its own path scope.
    def test_5_each_pattern_keeps_its_own_paths(self):
        repo = self.repo({
            "alpha/one.txt": "BETA lives in the wrong tree\n",
            "beta/two.txt": "ALPHA lives in the wrong tree\n",
            "alpha/three.txt": "ALPHA lives in its own tree\n",
            "beta/four.txt": "BETA lives in its own tree\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: alpha-key\n"
            "      class: B4\n"
            "      pattern: 'ALPHA'\n"
            "      paths:\n"
            "        - 'alpha/*'\n"
            "    - name: beta-key\n"
            "      class: B4\n"
            "      pattern: 'BETA'\n"
            "      paths:\n"
            "        - 'beta/*'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        sites = {node["site"].split(":")[0] for node in document["nodes"]
                 if node["class"] == "B4"}
        self.assertEqual(sites, {"alpha/three.txt", "beta/four.txt"},
                         "a pattern escaped its own path scope, or never ran in it")

    # 6 — a missing site is a gap in one method, not a gag on the others.
    def test_6_a_missing_site_keeps_the_other_searches(self):
        repo = self.repo({"conf/app.yml": "key: findme\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: builder\n"
            "      class: B4\n"
            "      judgment-only: true\n"
            "      site: no/such/builder.java\n"
            "    - name: literal-key\n"
            "      class: B4\n"
            "      pattern: 'findme'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertGreater(row(document, "B4")["hits"], 0)
        self.assertEqual(row(document, "B4")["status"], "partial")
        self.assertIn("site missing", row(document, "B4")["reason"])

    # 7 — generated output is searched for every name form, not the simple one.
    def test_7_generated_output_is_searched_for_every_form(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        built = repo / "build-output"
        built.mkdir()
        (built / "wire.json").write_text('{"topic": "widget-created"}\n', encoding="utf-8")
        config = write_config(repo, "investigation:\n  generated:\n    - build-output\n")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=widget-created", "--alias", "import-alias=W",
                             config=str(config))
        self.assertEqual(code, 0)
        self.assertGreater(row(document, "B6")["hits"], 0)

    # 8 — a manifest nobody can parse cannot close the build graph.
    def test_8_an_unparsable_reactor_manifest_is_unverified(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "pom.xml": "<project><modules><module>a</module>\n",
        })
        config = write_config(repo, "investigation:\n  reactor:\n    - pom.xml\n")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B7")["status"], "unverified")
        self.assertIn("unparsable", row(document, "B7")["reason"])

    def test_8_an_unsupported_reactor_manifest_is_unverified(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "build-modules.txt": "a\nb\n",
        })
        config = write_config(repo, "investigation:\n  reactor:\n    - build-modules.txt\n")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B7")["status"], "unverified")

    # 10— the recorded universe says what was searched, and no more.
    def test_10_the_wide_universe_does_not_claim_ignored_files(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        wide = [query for query in document["queries"] if "--untracked" in query["command"]]
        self.assertTrue(wide)
        self.assertIn("not ignored", wide[0]["universe"])

    # 2d.1 — a declared alias is a name form every name-shaped class searches.
    def test_alias_forms_reach_the_pattern_classes(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {\n}\n",
            "alpha/Alias.java": "class Alias extends W {\n}\n",
            "conf/queue.yml": 'topic: "widget-wire"\n',
        })
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=widget-wire", "--alias", "import-alias=W")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B1")["status"], "closed")
        self.assertGreater(row(document, "B2")["hits"], 0,
                           "the alias never entered the declaration pattern")
        self.assertGreater(row(document, "B4")["hits"], 0,
                           "the wire name never entered the string-literal pattern")

    def test_pattern_classes_inherit_an_incomplete_b1(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {\n}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B1")["status"], "partial")
        self.assertEqual(row(document, "B4")["status"], "partial")
        self.assertIn("B1", row(document, "B4")["reason"])

    # 2d.5 — a declared registration pattern keeps its own scope.
    def test_a_declared_registration_pattern_is_not_narrowed_to_named_files(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "listeners/Handler.java": "@KafkaListener\nvoid onMessage() {}\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: queue-listener\n"
            "      class: B11\n"
            "      pattern: '@KafkaListener'\n"
            "      paths:\n"
            "        - 'listeners/*'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertGreater(row(document, "B11")["hits"], 0,
                           "a registration naming no form was dropped")

    # 2d.6 — every row says what it searched.
    def test_every_row_records_a_universe(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  generated:\n"
            "    - build-output\n"
            "  reactor:\n"
            "    - pom.xml\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        for item in document["boundaries"]:
            self.assertTrue(item.get("universe"), f"{item['class']} records no universe")

    # 2d.10 — a row closed by a search points at the query that ran it.
    def test_a_searched_row_points_at_its_query(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        ids = {query["id"] for query in document["queries"]}
        searched = row(document, "B1")
        self.assertTrue(searched.get("query_ids"))
        self.assertTrue(set(searched["query_ids"]) <= ids)

    # 2d self-review — a class with a short-circuit still owes its site gap.
    def test_a_missing_site_downgrades_a_short_circuit_class(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  reactor:\n"
            "    - pom.xml\n"
            "  boundaries:\n"
            "    - name: entry-point\n"
            "      class: B1\n"
            "      judgment-only: true\n"
            "      site: no/such/entry.java\n"
            "    - name: aggregator\n"
            "      class: B7\n"
            "      judgment-only: true\n"
            "      site: no/such/build.java\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=W",
                             config=str(config))
        self.assertEqual(code, 0)
        self.assertNotEqual(row(document, "B1")["status"], "closed")
        self.assertNotEqual(row(document, "B7")["status"], "closed")

    def test_a_live_site_downgrades_a_short_circuit_class(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "alpha/Entry.java": "class Entry {}\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: entry-point\n"
            "      class: B1\n"
            "      judgment-only: true\n"
            "      site: alpha/Entry.java\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=W",
                             config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B1")["status"], "judgment-only")

    # 11 — a match past the storage cap is still an exact match.
    def test_11_a_late_match_is_not_mistaken_for_a_counter_hit(self):
        padding = "// " + ("pad " * 60)
        repo = self.repo({"alpha/long.java": padding + "Widget here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        found = [node for node in document["nodes"] if "alpha/long.java" in node["site"]]
        self.assertTrue(found)
        wide_check = check(document, "case-blind")
        self.assertFalse([node for node in wide_check["new_nodes"] if "alpha/long.java" in node],
                         "an exact match was recorded as a second-universe discovery")


if __name__ == "__main__":
    unittest.main()

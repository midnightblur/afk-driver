#!/usr/bin/env python3
"""Adversarial cases for the seed map: a row bound to nothing it can prove.

Every case here starts from the same question — what does a row assert that
the record underneath it cannot support? A universe narrower than the class it
inherits, a status that hid a worse gap, an absence that never ran a search, a
query id that two different searches share, an alias that matched inside a
longer identifier. Fixtures are throwaway git repositories.
"""

import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_seed_map import row, run, seed_map, write_config, make_repo  # noqa: E402
from test_seed_map_reach import check  # noqa: E402


def sites(document, klass):
    return {node["site"].split(":")[0] for node in document["nodes"]
            if node["class"] == klass}


def query(document, query_id):
    return next(item for item in document["queries"] if item["id"] == query_id)


class SeedMapBindingTest(unittest.TestCase):
    def setUp(self):
        self.trash = []

    def tearDown(self):
        for path in self.trash:
            shutil.rmtree(path, ignore_errors=True)

    def repo(self, files, commit=True):
        root = make_repo(files, commit)
        self.trash.append(root)
        return root

    # A1 — the alias pass searches the universe the simple pass searched.
    def test_the_alias_pass_reaches_untracked_files(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        (repo / "staged.json").write_text('{"topic": "w-created"}\n', encoding="utf-8")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt")
        self.assertEqual(code, 0)
        self.assertIn("staged.json", sites(document, "B1"),
                      "an untracked file carrying only the wire form was never searched")

    # A2 — a declared B1 pattern widens the set every derived class searches.
    def test_a_declared_b1_pattern_widens_the_derived_classes(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "notes/handbook.md": "the SPECIAL entry point\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: entry-point\n"
            "      class: B1\n"
            "      pattern: 'SPECIAL'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt",
                             config=str(config))
        self.assertEqual(code, 0)
        self.assertIn("notes/handbook.md", sites(document, "B13"),
                      "the documents class searched a hit set the B1 pattern had widened")

    # A3 — a site gap is a gap under every status, not only under `closed`.
    def test_a_missing_site_downgrades_a_frontier_row(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  generated:\n"
            "    - build-output\n"
            "  boundaries:\n"
            "    - name: consumer\n"
            "      class: B14\n"
            "      judgment-only: true\n"
            "      site: no/such/consumer.java\n"
            "    - name: bundle\n"
            "      class: B6\n"
            "      judgment-only: true\n"
            "      site: no/such/bundle.js\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B14")["status"], "partial")
        self.assertEqual(row(document, "B6")["status"], "partial")

    # A4 — a search that ran and returned nothing is an absence, not a gap.
    def test_a_zero_hit_declared_search_is_not_an_absent_method(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: bundle-marker\n"
            "      class: B6\n"
            "      pattern: 'NOTHINGMATCHESTHIS'\n"
            "      paths:\n"
            "        - 'alpha/*'\n"
            "    - name: module-marker\n"
            "      class: B7\n"
            "      pattern: 'NOTHINGMATCHESTHIS'\n"
            "      paths:\n"
            "        - 'alpha/*'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        for klass in ("B6", "B7"):
            self.assertEqual(row(document, klass)["hits"], 0)
            self.assertNotEqual(row(document, klass)["status"], "unverified",
                                f"{klass}: a search that ran was reported as no method")

    # A5 — a dot-leading path is a path, not a relative prefix.
    def test_a_dot_leading_site_is_found(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            ".github/workflows/ci.yml": "on: push\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: pipeline\n"
            "      class: B14\n"
            "      judgment-only: true\n"
            "      site: .github/workflows/ci.yml\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertNotIn("site missing", row(document, "B14").get("reason", ""))

    # A6 — the second universe is a discriminating method in its own right.
    def test_an_undiscriminating_alias_is_covered_by_the_second_universe(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=Widget-created")
        self.assertEqual(code, 0)
        counter = check(document, "carrying no simple name")
        self.assertEqual(counter["state"], "complete")
        self.assertIn("case-blind", counter["method"])

    # A7 — a short alias is a whole name, never a fragment of a longer one.
    def test_an_alias_does_not_match_inside_a_longer_identifier(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "alpha/Other.java": "class Other { int Wonder; }\n",
        })
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=W")
        self.assertEqual(code, 0)
        self.assertNotIn("alpha/Other.java", sites(document, "B1"),
                         "the alias matched inside a longer identifier")

    def test_an_alias_starting_with_a_symbol_still_reaches_b2(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "alpha/Sub.java": "class Sub extends $Alias {\n}\n",
        })
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=$Alias")
        self.assertEqual(code, 0)
        self.assertIn("alpha/Sub.java", sites(document, "B2"),
                      "a word boundary before a symbol can never match")

    # A8 — the design-phase flag the validator asks about has a producer.
    def test_the_design_phase_flag_is_recorded(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertIs(document["run"]["design_phase"], False)
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", "--design-phase")
        self.assertEqual(code, 0)
        self.assertIs(document["run"]["design_phase"], True)

    # A9 — a class closed by parsing still says what it parsed.
    def test_a_parsed_build_graph_records_its_query(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "pom.xml": "<project><modules><module>alpha</module></modules></project>\n",
        })
        config = write_config(repo, "investigation:\n  reactor:\n    - pom.xml\n")
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        b7 = row(document, "B7")
        self.assertEqual(b7["status"], "closed")
        self.assertTrue(b7["query_ids"])
        self.assertIn("parse", query(document, b7["query_ids"][0])["command"])

    # A10 — two different searches are two different queries.
    def test_two_alias_sets_do_not_share_one_query_id(self):
        files = {"alpha/Widget.java": "class Widget {}\n"}
        first = run(self.repo(files), "--subject", "Widget", "--type", "Q1",
                    "--alias", "import-alias=Wgt", "--alias", "wire=w-one")[1]
        second = run(self.repo(files), "--subject", "Widget", "--type", "Q1",
                     "--alias", "import-alias=Other", "--alias", "wire=w-two")[1]
        self.assertNotEqual(set(row(first, "B2")["query_ids"]),
                            set(row(second, "B2")["query_ids"]),
                            "two alias sets collided on one query id")

    # A11 — a subject-blind registration pattern over-matches; say so once.
    def test_a_subject_blind_registration_pattern_warns(self):
        import io
        from contextlib import redirect_stderr

        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "listeners/Handler.java": "@KafkaListener\nvoid on() {}\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: queue-listener\n"
            "      class: B11\n"
            "      pattern: '@KafkaListener'\n"
        ))
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                                 config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().count("queue-listener"), 1, buffer.getvalue())
        self.assertIn("subject", buffer.getvalue())

    # 2e self-review — a default pattern that cannot match here did not run.
    def test_a_pattern_that_cannot_match_downgrades_a_declared_class(self):
        repo = self.repo({"notes/handbook.md": "Widget is described here\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: doc-marker\n"
            "      class: B2\n"
            "      pattern: 'described'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt",
                             config=str(config))
        self.assertEqual(code, 0)
        self.assertGreater(row(document, "B2")["hits"], 0)
        self.assertEqual(row(document, "B2")["status"], "partial")
        self.assertIn("cannot match", row(document, "B2")["reason"])

    # B2 — a node found by a search names the search that found it.
    def test_every_seed_node_names_its_query(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        ids = {item["id"] for item in document["queries"]}
        self.assertTrue(document["nodes"])
        for node in document["nodes"]:
            self.assertIn(node.get("query_id"), ids, f"{node['id']} names no query")

    # B3 — a counter-search says which classes it covers.
    def test_counter_checks_name_the_classes_they_cover(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt")
        self.assertEqual(code, 0)
        covered = set()
        for item in document["counter_checks"]:
            if item["state"] == "complete":
                covered |= set(item.get("classes") or [])
        searched = {item["class"] for item in document["boundaries"]
                    if item["status"] in ("closed", "partial") and item["query_ids"]}
        self.assertTrue(searched)
        self.assertTrue(searched <= covered, f"uncovered: {sorted(searched - covered)}")


if __name__ == "__main__":
    unittest.main()

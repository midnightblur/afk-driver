#!/usr/bin/env python3
"""Adversarial cases for the seed map: a row bound to nothing it can prove.

Every case here starts from the same question — what does a row assert that
the record underneath it cannot support? A universe narrower than the class it
inherits, a status that hid a worse gap, an absence that never ran a search, a
query id that two different searches share, an alias that matched inside a
longer identifier. Fixtures are throwaway git repositories.
"""

import shutil
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_seed_map import (row, run, seed_map, validate_coverage,  # noqa: E402
                           write_config, make_repo)
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

    # 2f — a case-blind pass over a pattern holding no letter discriminates
    # nothing, so it is a counter-search that did not run.
    def test_a_letterless_pattern_gets_a_pending_counter_row(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "conf/ports.txt": "8080-9090\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: port-range\n"
            "      class: B10\n"
            "      pattern: '[0-9]+-[0-9]+'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt",
                             config=str(config))
        self.assertEqual(code, 0)
        by_class = {}
        for item in document["counter_checks"]:
            for klass in item.get("classes") or []:
                by_class.setdefault(klass, []).append(item)
        letterless = [item for item in by_class["B10"] if "own expressions" in item["method"]]
        self.assertTrue(letterless)
        self.assertEqual(letterless[0]["state"], "pending")
        self.assertIn("not discriminating", letterless[0]["reason"])
        lettered = [item for item in by_class["B2"] if "own expressions" in item["method"]]
        self.assertTrue(lettered)
        self.assertEqual(lettered[0]["state"], "complete")

    # 2g — a letter inside a bracket expression is already both cases, so a
    # pattern whose only letters sit there discriminates nothing either.
    def test_a_bracketed_only_pattern_gets_a_pending_counter_row(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: bracketed\n"
            "      class: B10\n"
            "      pattern: '[Ww][Ii][Dd]'\n"
            "    - name: half-bracketed\n"
            "      class: B9\n"
            "      pattern: '[Ww]idget'\n"
            "    - name: escaped\n"
            "      class: B3\n"
            "      pattern: '\\bW\\b'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias", "import-alias=Wgt",
                             config=str(config))
        self.assertEqual(code, 0)
        states = {}
        for item in document["counter_checks"]:
            if "own expressions" in item["method"]:
                for klass in item.get("classes") or []:
                    states.setdefault(klass, item["state"])
        self.assertEqual(states.get("B10"), "pending")
        self.assertEqual(states.get("B9"), "complete")
        self.assertEqual(states.get("B3"), "complete")

    # 3-A2 — the stamp is of the configuration that ran, not of the bytes it
    # was written in: two files that resolve to one block are one search.
    def test_the_config_stamp_hashes_the_resolved_block(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        block = ("investigation:\n"
                 "  boundaries:\n"
                 "    - name: doc-marker\n"
                 "      class: B13\n"
                 "      pattern: '{simple}'\n")
        first = write_config(repo, block, name="first.yaml")
        second = write_config(repo, "# a comment the reader drops\n" + block,
                              name="second.yaml")
        _, one = run(repo, "--subject", "Widget", "--type", "Q1", config=str(first))
        _, two = run(repo, "--subject", "Widget", "--type", "Q1", config=str(second))
        self.assertEqual(one["run"]["config"]["sha256"], two["run"]["config"]["sha256"])
        self.assertNotEqual(one["run"]["config"]["path"], two["run"]["config"]["path"])

    # 3-A7 — a class searching B1's hit set cites every search behind that
    # set, so the nodes it carries are ones its own row accounts for.
    def test_a_two_scope_config_produces_a_clean_ledger(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "notes/handbook.md": "the SPECIAL entry point\n",
            "conf/service.yml": "marker: OTHERMARK\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: doc-mention\n"
            "      class: B1\n"
            "      pattern: 'SPECIAL'\n"
            "      paths:\n"
            "        - 'notes/*'\n"
            "    - name: config-mention\n"
            "      class: B1\n"
            "      pattern: 'OTHERMARK'\n"
            "      paths:\n"
            "        - 'conf/*'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             config=str(config))
        self.assertEqual(code, 0)
        defects, _ = validate_coverage.validate(document)
        self.assertEqual(defects, [])

    # 3-A3 — a seed-only run on a repository with the declared build graph and
    # generated output states no defect; its gaps are honest ones.
    def test_a_declared_build_graph_and_generated_output_validate(self):
        repo = self.repo({
            "pom.xml": ("<project><modules><module>alpha</module>"
                        "</modules></project>\n"),
            "alpha/pom.xml": "<project></project>\n",
            "alpha/Widget.java": "class Widget {}\n",
            "target/typescript/widget.ts": "export class Widget {}\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  generated:\n"
            "    - target/typescript\n"
            "  reactor:\n"
            "    - pom.xml\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             config=str(config))
        self.assertEqual(code, 0)
        defects, _ = validate_coverage.validate(document)
        self.assertEqual(defects, [])
        self.assertEqual(row(document, "B7")["status"], "closed")
        self.assertEqual(row(document, "B6")["status"], "closed")

    # 3-A4 — the query id is the digest of the invocation, so the same search
    # collides across fragments and a different one does not.
    def test_a_query_id_follows_the_invocation_it_names(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        _, document = run(repo, "--subject", "Widget", "--type", "Q1")
        for item in document["queries"]:
            self.assertEqual(
                item["id"],
                seed_map.stable_id("q", item["command"] + item["universe"]))
        first = seed_map.stable_id("q", "git grep -n -I -E -e 'A' -e 'B'" + "tracked files")
        second = seed_map.stable_id("q", "git grep -n -I -E -e 'B' -e 'A'" + "tracked files")
        self.assertNotEqual(first, second)
        self.assertEqual(
            first, seed_map.stable_id("q", "git grep -n -I -E -e 'A' -e 'B'" + "tracked files"))

    # 3-A8 — the case-blind guard reads both spellings of the flag.
    def test_a_case_blind_primary_owes_no_case_blind_counter(self):
        self.assertFalse(seed_map.discriminating(["Widget"], ["-i"]))
        self.assertFalse(seed_map.discriminating(["Widget"], ["--ignore-case"]))
        self.assertTrue(seed_map.discriminating(["Widget"], []))

    def test_a_letter_range_inside_brackets_counts_as_a_letter(self):
        self.assertTrue(seed_map.discriminating(["[a-z]+"], []))
        self.assertFalse(seed_map.discriminating(["[Ww][Ii]"], []))

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

    # B4 — a recorded command is the command that ran, and it runs verbatim.
    def test_the_recorded_search_reruns_and_returns_what_cites_it(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n",
                          "alpha/other.java": "no name here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        primary = next(item for item in document["queries"]
                       if item["command"].startswith("git grep")
                       and "--untracked" not in item["command"])
        result = subprocess.run(primary["command"], cwd=repo, shell=True,
                                capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        returned = {line.split(":", 2)[0] + ":" + line.split(":", 2)[1]
                    for line in result.stdout.splitlines() if line.count(":") >= 2}
        cited = {node["site"] for node in document["nodes"]
                 if node.get("query_id") == primary["id"]}
        self.assertEqual(returned, cited)

    # B4b — every recorded command, not just the primary: re-executed, each
    # returns the line figure its own row carries.
    def test_every_recorded_query_reruns_to_the_lines_it_recorded(self):
        # One file names the subject and registers, one registers without
        # naming it: a class scoped to the named files must not count the
        # second, and must not record a command that returns it either.
        files = {"alpha/Widget.java": "class Widget {}\n",
                 "alpha/WidgetModule.java": "@KafkaListener\nvoid onWidget() {}\n",
                 "alpha/Other.java": "@KafkaListener\nvoid onOther() {}\n"}
        repo = self.repo(files)
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        checked = 0
        for row in document["queries"]:
            if "lines" not in row or not row["command"].startswith("git grep"):
                continue
            result = subprocess.run(shlex.split(row["command"]), cwd=repo,
                                    capture_output=True, encoding="utf-8",
                                    errors="replace")
            self.assertIn(result.returncode, (0, 1), result.stderr)
            returned = [line for line in result.stdout.splitlines()
                        if line.count(":") >= 2]
            self.assertEqual(len(returned), row["lines"], row["command"])
            checked += 1
        self.assertTrue(checked >= 2, document["queries"])

    # B4c — a subject no file names still gets an answer: the classes that
    # search B1’s file set are closed on nothing, on B1’s own searches.
    def test_a_subject_no_file_names_closes_the_derived_classes(self):
        repo = self.repo({"alpha/plain.java": "class Other {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created", "--alias",
                             "import-alias=Wgt")
        self.assertEqual(code, 0)
        defects, _ = validate_coverage.validate(document)
        self.assertEqual(defects, [])
        rows = {item["class"]: item for item in document["boundaries"]}
        self.assertEqual(rows["B11"]["hits"], 0)
        self.assertEqual(rows["B11"]["status"], "closed")
        self.assertTrue(rows["B11"]["query_ids"], rows["B11"])
        for check in document["counter_checks"]:
            if check.get("state") == "complete":
                self.assertTrue(check.get("query_ids") or check.get("evidence_nodes"),
                                check)

    def test_a_path_list_past_the_budget_runs_as_several_commands(self):
        paths = [f"alpha/File{index:04d}.java" for index in range(900)]
        chunks = seed_map.chunk_pathspecs(paths)
        self.assertTrue(len(chunks) > 1, len(chunks))
        self.assertEqual(sorted(item for chunk in chunks for item in chunk),
                         sorted(paths))
        for chunk in chunks:
            self.assertTrue(sum(len(shlex.quote(item)) + 1 for item in chunk)
                            <= seed_map.PATHSPEC_BUDGET, len(chunk))
        self.assertEqual(chunks, seed_map.chunk_pathspecs(list(reversed(paths))))

    # B5 — the two numbers a query carries say two different things.
    def test_a_query_counts_its_nodes_and_records_the_lines_it_returned(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        citing = {}
        for node in document["nodes"]:
            if isinstance(node.get("query_id"), str):
                citing[node["query_id"]] = citing.get(node["query_id"], 0) + 1
        for item in document["queries"]:
            self.assertEqual(item["count"], citing.get(item["id"], 0), item["command"])
            self.assertIsInstance(item["lines"], int)


if __name__ == "__main__":
    unittest.main()

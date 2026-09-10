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

    # C4 — the config reader accepts a directory written with a trailing
    # slash, a doubled slash, or backslashes; the seed map must not die on one.
    def test_a_declared_path_spelled_loosely_still_runs(self):
        for spelling in ("gen/", "gen//", "." + chr(92) + "gen"):
            repo = self.repo({
                "alpha/Widget.java": "class Widget {}" + chr(10),
                "gen/widget.ts": "export class Widget {}" + chr(10),
            })
            config = write_config(repo, (
                "investigation:" + chr(10)
                + "  generated:" + chr(10)
                + "    - " + chr(39) + spelling + chr(39) + chr(10)
            ))
            code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                                 config=str(config))
            self.assertEqual(code, 0, spelling)
            self.assertEqual(row(document, "B6")["status"], "closed", spelling)
            walks = [item["command"] for item in document["queries"]
                     if item["command"].startswith("in-process walk of")]
            self.assertIn("in-process walk of -- gen", walks, spelling)

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

    # B4d — every command a run records is one a reader can place, and every
    # search is written in the one grammar.
    def test_every_recorded_command_belongs_to_a_declared_family(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=w-created")
        self.assertEqual(code, 0)
        for row in document["queries"]:
            self.assertIsNotNone(seed_map.contract.family(row["command"]),
                                 row["command"])
            if row["command"].startswith("git grep"):
                self.assertIsNotNone(
                    seed_map.contract.parse_canonical(row["command"]), row["command"])

    def test_a_built_command_parses_back_to_what_built_it(self):
        build = seed_map.contract.build_command
        parse = seed_map.contract.parse_canonical
        cases = [(["Widget"], None, []),
                 (["a b", "c|d"], None, ["-i"]),
                 (["Widget"], ["alpha/Widget.java", "beta/x.java"], ["-i", "--untracked"]),
                 (["Widget"], None, ["--untracked", "-i"])]
        for expressions, paths, flags in cases:
            parsed = parse(build(expressions, paths, flags))
            self.assertIsNotNone(parsed, (expressions, paths, flags))
            self.assertEqual(parsed[0], frozenset(flags))
            self.assertEqual(parsed[1], frozenset(expressions))
            self.assertEqual(list(parsed[2]), list(paths or []))

    def test_a_command_outside_the_grammar_does_not_parse(self):
        parse = seed_map.contract.parse_canonical
        for command in ("git grep -inE -e Widget",
                        "git grep -n -I -E -F -e Widget",
                        "git grep -n -I -G -e Widget",
                        "git grep -n -I -E --and -e Widget",
                        "git grep -n -I -E --untracked -i -e Widget",
                        "git grep -n -I -E"):
            self.assertIsNone(parse(command), command)

    def test_a_command_no_shell_can_split_does_not_parse(self):
        contract = seed_map.contract
        broken = "git grep -n -I -E -e 'Widget"
        self.assertIsNone(contract.argv(broken))
        self.assertIsNone(contract.parse_canonical(broken))
        self.assertIsNone(contract.family(broken))

    # The whole tree is not a path, so no path list can spell it.
    def test_the_all_files_sentinel_is_out_of_band(self):
        contract = seed_map.contract
        whole = contract.searched_paths("git grep -n -I -E -e Widget")
        spelled = contract.searched_paths(
            "git grep -n -I -E -e Widget -- '<every tracked file>'")
        self.assertIs(whole, contract.ALL_FILES)
        self.assertIsNot(spelled, contract.ALL_FILES)
        self.assertNotEqual(whole, spelled)
        self.assertEqual(spelled, ("<every tracked file>",))

    # A family that lists paths is one method however the list is ordered.
    def test_a_listing_family_keys_on_its_paths_not_their_order(self):
        key = seed_map.contract.command_key
        self.assertEqual(key("git ls-files -- target build"),
                         key("git ls-files -- build target"))
        self.assertEqual(key("parse -- alpha/pom.xml beta/pom.xml"),
                         key("parse -- beta/pom.xml alpha/pom.xml"))
        self.assertNotEqual(key("parse -- alpha/pom.xml"),
                            key("list the directories beside -- alpha/pom.xml"))

    # A hint is offered for spelling alone; anything that changes the question
    # gets none, because a hint that runs another search is worse than silence.
    def test_no_hint_where_an_option_changes_what_the_search_means(self):
        respell = seed_map.contract.respell
        for command in ("git grep -v -e Widget",
                        "git grep -n -I -F -e Widget",
                        "git grep -n -I -G -e Widget",
                        "git grep -n -I -P -e Widget",
                        "git grep -n -I -E -e A --and -e B"):
            self.assertIsNone(respell(command), command)

    def test_a_hint_where_only_the_spelling_differs(self):
        respell = seed_map.contract.respell
        canonical = "git grep -n -I -E -i -e Widget"
        for command in ("git grep --ignore-case --regexp Widget",
                        "git grep -inE -e Widget",
                        "git grep --ignore-case --regexp=Widget"):
            self.assertEqual(respell(command), canonical, command)

    def test_the_grammar_is_written_once(self):
        source = (Path(seed_map.__file__).resolve().parent / "contract.py").read_text(
            encoding="utf-8")
        self.assertEqual(source.count("(-e <expression>)+"), 1, "the grammar is stated twice")
        # R3 — the doc line is the sanctioned copy, so it is the same line.
        doc = (Path(seed_map.__file__).resolve().parent.parent
               / "LEDGER-FORMAT.md").read_text(encoding="utf-8")
        self.assertIn(seed_map.contract.CANONICAL, doc)

    # R1 — a path list is tokens, not prose: a path holding a comma survives.
    def test_a_listed_path_holding_a_comma_round_trips(self):
        contract = seed_map.contract
        command = contract.build_listing("manifest parse", ["odd, name/pom.xml",
                                                            "alpha/pom.xml"])
        self.assertEqual(contract.family(command), "manifest parse")
        self.assertEqual(contract.command_key(command),
                         ("manifest parse", ("alpha/pom.xml", "odd, name/pom.xml")))

    # C1 — canonicalization lives in the builder, so the parser refuses every
    # other spelling of one path rather than quietly folding it.
    def test_the_alias_spelling_of_a_path_is_not_canonical(self):
        contract = seed_map.contract
        self.assertEqual(contract.family("parse -- alpha/pom.xml"), "manifest parse")
        self.assertIsNone(contract.family("parse -- ./alpha/pom.xml"))

    # C1 — a family is what the builder writes: a command is in one only when
    # rebuilding it from its parts returns the same bytes.
    def test_a_family_is_what_its_builder_writes(self):
        contract = seed_map.contract
        built = {
            "search": contract.build_command(["Widget"], ["alpha/Widget.java"]),
            "built-output walk": contract.build_listing("built-output walk", ["gen"]),
            "tracked listing": contract.build_listing("tracked listing", ["gen"]),
            "manifest parse": contract.build_listing("manifest parse", ["alpha/pom.xml"]),
            "sibling listing": contract.build_listing("sibling listing", ["alpha/pom.xml"]),
        }
        for name, command in built.items():
            self.assertEqual(contract.family(command), name, command)

    # C1 — a token a shell would have expanded is legal only in the quoted
    # spelling the builder emits, so a path named `A$B.java` stays reachable.
    def test_a_prose_family_takes_the_builders_quoting_only(self):
        contract = seed_map.contract
        self.assertIsNone(contract.family("parse -- $MANIFEST"))
        self.assertEqual(contract.family(contract.build_listing("manifest parse",
                                                                ["$MANIFEST"])),
                         "manifest parse")
        self.assertEqual(contract.family(contract.build_listing("manifest parse",
                                                                ["A$B/pom.xml"])),
                         "manifest parse")

    # C1 — the prefix ends at exactly one space; a path glued to it is no path.
    def test_a_path_glued_to_the_prefix_is_no_family(self):
        self.assertIsNone(seed_map.contract.family("parse --alpha/pom.xml"))

    # C1 — the parts keep the command's own order, and the key does not.
    def test_a_prose_family_keys_on_its_paths_not_their_order(self):
        contract = seed_map.contract
        first = contract.build_listing("manifest parse", ["b/pom.xml", "a/pom.xml"])
        second = contract.build_listing("manifest parse", ["a/pom.xml", "b/pom.xml"])
        self.assertNotEqual(first, second)
        self.assertEqual(contract.family(first), "manifest parse")
        self.assertEqual(contract.command_key(first), contract.command_key(second))

    # C2 — a search path is a repository path: one that is not is not a search.
    def test_a_search_path_outside_the_repository_is_not_canonical(self):
        contract = seed_map.contract
        for command in ("git grep -n -I -E -e Widget -- ../x",
                        "git grep -n -I -E -e Widget -- /etc/x",
                        "git grep -n -I -E -e Widget -- alpha/",
                        "git grep -n -I -E -e Widget -- ./alpha/Widget.java"):
            self.assertIsNone(contract.parse_canonical(command), command)
            self.assertIsNone(contract.family(command), command)

    # C3 — a path spelled another way is a spelling difference, so it hints.
    def test_a_hint_where_only_the_path_spelling_differs(self):
        respell = seed_map.contract.respell
        self.assertEqual(respell("git grep -n -I -E -e Widget -- ./alpha/Widget.java"),
                         "git grep -n -I -E -e Widget -- alpha/Widget.java")
        self.assertIsNone(respell("git grep -n -I -E -e Widget -- ../x"))

    def test_a_path_no_repository_can_hold_is_a_parse_failure(self):
        contract = seed_map.contract
        for command in ("parse -- ../outside/pom.xml",
                        "parse -- /etc/pom.xml",
                        "parse -- C:/tree/pom.xml",
                        "parse -- alpha" + chr(92) + "pom.xml",
                        "parse -- alpha/",
                        "parse --"):
            self.assertIsNone(contract.family(command), command)

    # R2 — a token a shell would expand is a token that ran as something else.
    def test_a_command_carrying_shell_expansion_is_not_canonical(self):
        parse = seed_map.contract.parse_canonical
        for command in ("git grep -n -I -E -e $PATTERN",
                        "git grep -n -I -E -e Widget -- src/*.java",
                        "git grep -n -I -E -e `cat pattern`",
                        'git grep -n -I -E -e "Widget"'):
            self.assertIsNone(parse(command), command)
        self.assertIsNotNone(parse("git grep -n -I -E -e '$PATTERN'"))

    def test_the_expressions_of_one_search_carry_no_order(self):
        key = seed_map.contract.command_key
        self.assertEqual(key("git grep -n -I -E -e A -e B"),
                         key("git grep -n -I -E -e B -e A"))

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

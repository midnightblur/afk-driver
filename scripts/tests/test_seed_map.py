#!/usr/bin/env python3
"""Behaviour tests for the investigation seed map — real git, no network.

Every case pins a way the pre-pass could lie: an alternation that leaks, a
counter-search that cannot fail, a name form nobody searched, a path git
escapes, a declared site that is gone, a manifest that is gone, a default
pattern with no file it could match. The fixtures are throwaway git
repositories built per test.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
# The scripts under test. Overridable so the suite can be pointed at an
# earlier checkout, which is how an adversarial case proves it fails there.
_SCRIPTS = Path(os.environ.get("AFK_INVESTIGATE_SCRIPTS")
                or _ROOT / "skills" / "utils" / "investigate" / "scripts")
sys.path.insert(0, str(_SCRIPTS))

import importlib.util

_spec = importlib.util.spec_from_file_location("seed_map", _SCRIPTS / "seed_map.py")
seed_map = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(seed_map)

_vspec = importlib.util.spec_from_file_location(
    "validate_coverage", _SCRIPTS / "validate_coverage.py"
)
validate_coverage = importlib.util.module_from_spec(_vspec)
_vspec.loader.exec_module(validate_coverage)


def git(repo, *args):
    subprocess.run(["git", *args], cwd=str(repo), check=True,
                   capture_output=True, encoding="utf-8", errors="replace")


def make_repo(files: dict, commit: bool = True) -> Path:
    root = Path(tempfile.mkdtemp(prefix="seedmap-"))
    git(root, "init", "-q")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "fixture")
    for name, body in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
    if commit:
        git(root, "add", "-A")
        git(root, "commit", "-qm", "fixture")
    return root


def write_config(root: Path, body: str) -> Path:
    path = root / "fixture-config.yaml"
    path.write_text("schema: 1\n" + body, encoding="utf-8")
    return path


def run(repo: Path, *args: str, config: str | None = None):
    """Invoke the script the way a skill does, and return its parsed output."""
    out = Path(tempfile.mkdtemp(prefix="seedout-")) / "seed.json"
    argv = ["--repo", str(repo), "--out", str(out), *args]
    if config:
        argv += ["--config", config]
    code = seed_map.main(argv)
    if code != 0:
        return code, None
    return code, json.loads(out.read_text(encoding="utf-8"))


def row(document, klass):
    return next(item for item in document["boundaries"] if item["class"] == klass)


class SeedMapTest(unittest.TestCase):
    def setUp(self):
        self.trash = []

    def tearDown(self):
        for path in self.trash:
            shutil.rmtree(path, ignore_errors=True)

    def repo(self, files, commit=True):
        root = make_repo(files, commit)
        self.trash.append(root)
        return root

    # S1 — a multi-subject alternation must not leak outside its group.
    def test_two_subjects_do_not_leak_across_the_alternation(self):
        repo = self.repo({
            "alpha/Sub.java": "class Sub extends Widget {\n}\n",
            "beta/prose.java": "// Gadget is mentioned here, declared nowhere\n",
        })
        code, document = run(repo, "--subject", "Widget", "--subject", "Gadget", "--type", "Q1")
        self.assertEqual(code, 0)
        sites = [node["site"] for node in document["nodes"] if node["class"] == "B2"]
        self.assertTrue(any("alpha/Sub.java" in site for site in sites), sites)
        self.assertFalse([site for site in sites if "beta/prose.java" in site],
                         "a bare second subject matched the declaration pattern")

    # S2 + S3 — the counter-search runs a form the primary pass cannot return,
    # and an unsearched form keeps B1 short of closed.
    def test_wire_form_surfaces_only_through_the_counter_search(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {\n}\n",
            "conf/queue.yml": "topic: widget-created\n",
        })
        code, plain = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertEqual(row(plain, "B1")["status"], "partial")
        self.assertIn("wire", row(plain, "B1")["reason"])
        self.assertEqual(plain["counter_checks"][0]["state"], "pending")

        code, declared = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=widget-created")
        self.assertEqual(code, 0)
        check = declared["counter_checks"][0]
        self.assertEqual(check["state"], "complete")
        self.assertTrue([node for node in check["new_nodes"] if "conf/queue.yml" in node],
                        "the wire-form hit did not surface")
        self.assertEqual(row(declared, "B1")["status"], "partial")
        self.assertIn("import-alias", row(declared, "B1")["reason"])

    def test_every_form_enumerated_closes_b1(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {\n}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1",
                             "--alias", "wire=widget-created", "--alias", "import-alias=W")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B1")["status"], "closed")

    # S6 — a non-ASCII path comes back verbatim, not octal-escaped.
    def test_non_ascii_paths_are_not_escaped(self):
        repo = self.repo({"délta/Wïdget-note.md": "Widget is described here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        sites = [node["site"] for node in document["nodes"]]
        self.assertTrue(any("délta" in site for site in sites), sites)
        self.assertFalse([site for site in sites if "\\3" in site], sites)
        self.assertGreater(row(document, "B13")["hits"], 0)

    # S6 — a git failure is an error, never an empty inventory reported as closed.
    def test_a_git_failure_exits_two(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"}, commit=False)
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 2)
        self.assertIsNone(document)

    # S4 — a declared instance adds a search; it never removes the default one.
    def test_declared_patterns_merge_with_the_defaults(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {\n}\n",
            "conf/app.yml": "key: \"Widget\"\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: literal-key\n"
            "      class: B4\n"
            "      pattern: 'key: '\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        method = row(document, "B4")["method"]
        self.assertIn("declared instance patterns", method)
        self.assertIn("string literal", method)

    # S7 — a declared judgment-only site that is gone is not evidence.
    def test_a_missing_judgment_site_is_unverified(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: scanner\n"
            "      class: B3\n"
            "      judgment-only: true\n"
            "      site: no/such/scanner.java\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B3")["status"], "unverified")
        self.assertIn("site missing", row(document, "B3")["reason"])

    def test_a_present_judgment_site_is_judgment_only(self):
        repo = self.repo({
            "alpha/Widget.java": "class Widget {}\n",
            "alpha/Scanner.java": "// scans the classpath\n",
        })
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: scanner\n"
            "      class: B3\n"
            "      judgment-only: true\n"
            "      site: alpha/Scanner.java\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B3")["status"], "judgment-only")

    # S9 — a reactor manifest that is gone cannot close the build graph.
    def test_a_missing_reactor_manifest_is_unverified(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  reactor:\n"
            "    - no-such-pom.xml\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B7")["status"], "unverified")
        self.assertIn("reactor manifest missing", row(document, "B7")["reason"])

    # S8 — built output git does not track is still searched.
    def test_untracked_generated_output_is_searched(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        built = repo / "build-output"
        built.mkdir()
        (built / "Widget.g.java").write_text("class WidgetStub {}\n", encoding="utf-8")
        config = write_config(repo, (
            "investigation:\n"
            "  generated:\n"
            "    - build-output\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B6")["status"], "closed")
        self.assertGreater(row(document, "B6")["hits"], 0)

    # S11 — a default pattern with no file it could match is not a closed zero.
    def test_a_pattern_with_no_matching_language_is_unverified(self):
        repo = self.repo({"notes/widget.md": "Widget is described here\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertEqual(row(document, "B2")["status"], "unverified")
        self.assertIn("pattern cannot match", row(document, "B2")["reason"])

    # S5 — a configuration that does not validate stops the run.
    def test_an_invalid_configuration_exits_two(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        config = write_config(repo, (
            "investigation:\n"
            "  boundaries:\n"
            "    - name: broken\n"
            "      class: B99\n"
            "      pattern: 'x'\n"
        ))
        code, document = run(repo, "--subject", "Widget", "--type", "Q1", config=str(config))
        self.assertEqual(code, 2)
        self.assertIsNone(document)

    # L1 — the seed map's own output is a ledger the validator accepts.
    def test_the_seed_map_output_validates_as_partial(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        defects, verdict = validate_coverage.validate(document)
        self.assertEqual(defects, [])
        self.assertEqual(verdict, "partial")

    def test_every_class_carries_a_row_and_the_nodes_resolve(self):
        repo = self.repo({"alpha/Widget.java": "class Widget {}\n"})
        code, document = run(repo, "--subject", "Widget", "--type", "Q1")
        self.assertEqual(code, 0)
        self.assertEqual([item["class"] for item in document["boundaries"]],
                         list(seed_map.ALL_CLASSES))
        ids = {node["id"] for node in document["nodes"]}
        for item in document["boundaries"]:
            self.assertTrue(set(item.get("hit_ids") or []) <= ids, item["class"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env afk-python
"""Rules for publishing REPORT.md beside a validated ledger.

The header line is arithmetic over the ledger, so the script writes it; the
agent supplies only the body, and a body past the cap is refused.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent.parent
_SCRIPTS = Path(os.environ.get("AFK_INVESTIGATE_SCRIPTS")
                or _ROOT / "skills" / "utils" / "investigate" / "scripts")
sys.path.insert(0, str(_TESTS))

from test_validate_coverage import ledger  # noqa: E402

BODY = "## Answer\n\nIt works — every path.\n\n## Sites\n\n- `alpha.java:2`\n"


class WriteReportTest(unittest.TestCase):
    def publish(self, document, body=BODY, stamp=True):
        folder = Path(tempfile.mkdtemp(prefix="report-")) / "INV-001-how-it-works"
        folder.mkdir()
        if stamp:
            document["run"]["verdict"] = "closed"
        path = folder / "COVERAGE.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "write_report.py"), "--ledger", str(path)],
            input=body, capture_output=True, encoding="utf-8", errors="replace")
        report = folder / "REPORT.md"
        text = report.read_text(encoding="utf-8") if report.exists() else None
        return result.returncode, result.stderr, text, path

    def test_the_header_is_computed_from_the_ledger(self):
        code, stderr, text, path = self.publish(ledger())
        self.assertEqual(code, 0, stderr)
        header = text.splitlines()[0]
        self.assertEqual(
            header,
            f"/fixture@{'0' * 40} · closed · boundaries 14/14 · unverified 0 "
            f"(load-bearing 0) · ledger: {path.as_posix()}")
        self.assertIn("## Answer", text)
        self.assertIn("It works — every path.\n\n## Sites", text)

    def test_unverified_claims_are_counted_with_their_load_bearing_share(self):
        document = ledger()
        document["claims"][0]["kind"] = "unverified"
        document["run"]["verdict"] = "partial"
        code, stderr, text, _ = self.publish(document, stamp=False)
        self.assertEqual(code, 0, stderr)
        self.assertIn("· partial ·", text.splitlines()[0])
        self.assertIn("unverified 1 (load-bearing 1)", text.splitlines()[0])

    def test_an_unstamped_ledger_is_refused(self):
        code, stderr, text, _ = self.publish(ledger(), stamp=False)
        self.assertEqual(code, 1)
        self.assertIn("verdict", stderr)
        self.assertIsNone(text)

    def test_a_ledger_the_validator_rejects_is_refused(self):
        document = ledger()
        document["boundaries"] = document["boundaries"][:-1]
        code, stderr, text, _ = self.publish(document)
        self.assertEqual(code, 1)
        self.assertIn("B14", stderr)
        self.assertIsNone(text)

    def test_a_body_past_forty_lines_is_refused(self):
        code, stderr, text, _ = self.publish(ledger(), body="- a line\n" * 41)
        self.assertEqual(code, 1)
        self.assertIn("40", stderr)
        self.assertIsNone(text)

    def test_the_body_may_come_from_a_file(self):
        folder = Path(tempfile.mkdtemp(prefix="report-"))
        document = ledger()
        document["run"]["verdict"] = "closed"
        ledger_path = folder / "COVERAGE.json"
        ledger_path.write_text(json.dumps(document), encoding="utf-8")
        body = folder / "report-body.txt"
        body.write_text(BODY, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "write_report.py"), "--ledger",
             str(ledger_path), "--body", str(body)],
            input="", capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("It works", (folder / "REPORT.md").read_text(encoding="utf-8"))

    # A reader opens the change on the forge, so the header names the forge
    # repository and a path inside it, never one machine's checkout.
    def test_the_header_names_the_remote_and_a_repository_path(self):
        repo = Path(tempfile.mkdtemp(prefix="report-repo-"))
        for args in (["init", "-q"],
                     ["remote", "add", "origin", "git@example.invalid:owner/name.git"]):
            subprocess.run(["git", *args], cwd=str(repo), check=True,
                           capture_output=True)
        folder = repo / "docs" / "feature" / "investigations" / "INV-001-how-it-works"
        folder.mkdir(parents=True)
        document = ledger()
        document["run"].update({"repository": str(repo), "verdict": "closed"})
        path = folder / "COVERAGE.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "write_report.py"), "--ledger", str(path)],
            input=BODY, capture_output=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stderr)
        header = (folder / "REPORT.md").read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(header.startswith(f"owner/name@{'0' * 40} · "), header)
        self.assertTrue(header.endswith(
            "ledger: docs/feature/investigations/INV-001-how-it-works/COVERAGE.json"),
            header)

    def test_an_empty_body_is_refused(self):
        code, stderr, text, _ = self.publish(ledger(), body="\n")
        self.assertEqual(code, 1)
        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()

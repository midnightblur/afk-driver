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

    def test_an_empty_body_is_refused(self):
        code, stderr, text, _ = self.publish(ledger(), body="\n")
        self.assertEqual(code, 1)
        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()

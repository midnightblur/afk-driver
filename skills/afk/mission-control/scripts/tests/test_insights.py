"""Insights: journal exit statuses surface as action-level items."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mc.sections import insights  # noqa: E402

_JOURNAL = (
    "# Journal - append-only event log "
    "(format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.\n\n"
    "2026-07-07 09:00 | execute | 0001-sample | exit rationale_unposted: "
    "1 rationale comment not receipted\n"
)


class RationaleUnpostedInsight(unittest.TestCase):
    def test_the_exit_status_is_an_action_level_exit_insight(self):
        with tempfile.TemporaryDirectory() as tmp:
            spec_dir = Path(tmp)
            (spec_dir / "plan").mkdir()
            (spec_dir / "plan" / "JOURNAL.md").write_text(_JOURNAL, encoding="utf-8")
            view = insights.parse(spec_dir)
        items = view.data["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "exit")
        self.assertEqual(items[0]["severity"], "act")
        self.assertEqual(items[0]["subject"], "0001-sample")


if __name__ == "__main__":
    unittest.main()

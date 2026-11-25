"""The Codex Stop hook on a page with no page document: 1 line per note with its element (ADR-0003 of ticket 207)."""

from __future__ import annotations

import json
import sys
from functools import partial
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for folder in (PLUGIN / "scripts", PLUGIN / "engine", PLUGIN / "hooks"):
    sys.path.insert(0, str(folder))

import codex_stop  # noqa: E402
import engine  # noqa: E402
import launcher  # noqa: E402

# A lavish 0.1.86 poll with 2 notes pinned on elements, as the host prints it.
TWO_NOTES = """session:
  file: "C:\\\\repo\\\\docs\\\\PROJ-7\\\\prototype\\\\orders.html"
  status: feedback
  session_ended: false
prompts[2]{uid,prompt,selector,tag,text}:
  "1","Put Open first in the filter bar",#filters > button:nth-of-type(2),button,Open
  "2",Make the total bold,td.total,td,42.00
next_step: Reply to the user.
dom_snapshot: ""
"""


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    home = tmp_path / "local"
    home.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    return home


def stop(monkeypatch, document, poll_output=TWO_NOTES):
    """The hook output for a waiting record with `document`, after one recorded host poll."""
    launcher.write_waiting_record(codex_stop.data_folder(), "t-1", document, "orders.html")
    monkeypatch.setattr(launcher, "run", lambda argv: (0, poll_output))
    monkeypatch.setattr(codex_stop, "wait_for_answer", partial(codex_stop.wait_for_answer, poll=launcher.poll_status))
    return json.loads(codex_stop.main(json.dumps({"session_id": "t-1"})))


def test_a_null_document_prints_one_line_per_note_with_its_tag_and_selector(data_home, monkeypatch):
    out = stop(monkeypatch, None)
    assert out["decision"] == "block"
    lines = out["reason"].splitlines()
    assert len(lines) == 2
    for line, words, tag, selector, text in [
            (lines[0], "Put Open first in the filter bar", "button", "#filters > button:nth-of-type(2)", "Open"),
            (lines[1], "Make the total bold", "td", "td.total", "42.00")]:
        assert words in line and f"<{tag}>" in line and selector in line and text in line


def test_a_note_without_an_element_or_with_line_breaks_stays_one_line():
    lines = codex_stop._note_lines([{"prompt": "first\nsecond"}, {"prompt": "x", "tag": "p", "selector": None}])
    assert lines == "first second\nx"


def test_a_page_document_gives_the_raw_response_as_today(data_home, monkeypatch):
    seen = []

    def poll_raw(document, prompts):
        seen.append((document, [p["prompt"] for p in prompts]))
        return "RAW"

    monkeypatch.setattr(engine, "poll_raw", poll_raw)
    assert stop(monkeypatch, "d.json") == {"decision": "block", "reason": "RAW"}
    assert seen == [("d.json", ["Put Open first in the filter bar", "Make the total bold"])]


def test_a_page_document_that_does_not_resolve_gives_the_joined_note_words_as_today(data_home, monkeypatch):
    out = stop(monkeypatch, str(data_home / "missing.json"))
    assert out == {"decision": "block", "reason": "Put Open first in the filter bar\nMake the total bold"}

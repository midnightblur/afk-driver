"""The design files of propose-solution: take-over, note sync, the gate lists and refusals, the ADR Driven by section
(SDD §3 rows S-3, S-4, S-5; §6 I-6, I-8; ADR-0004 and ADR-0007 design; PRD AC-011, AC-031, AC-032, AC-034, AC-035)."""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "skills" / "propose-solution" / "scripts"))

import design_files  # noqa: E402
from grill_common import Refusal  # noqa: E402

LOG_HEAD = "# Grill log — PROJ-1\n\n## Requirements grill\n- Policy: x\n\n## Solution design\n- Premise: a → pending\n"
LOG_TAIL = "\n## Other\nkept\n"


def note(note_id, text, round_n=1, target="c-1", deleted=False):
    return {"id": note_id, "round": round_n, "target": target, "item": target, "text": text, "deleted": deleted}


@pytest.fixture
def files(tmp_path):
    log, doc = tmp_path / "GRILL-LOG.md", tmp_path / "pages" / "propose-solution-s-1.json"
    log.write_text(LOG_HEAD + LOG_TAIL, "utf-8")
    doc.parent.mkdir()
    return log, doc


def write_doc(doc, notes):
    doc.write_text(json.dumps({"session": {"id": "s-1"}, "rounds": [], "notes": notes}), "utf-8")


def test_sync_copies_each_new_note_word_for_word_and_skips_a_note_already_there(files):
    log, doc = files
    words = 'Keep the "old" table,\nand drop the cache.'
    write_doc(doc, [note("N-1-c-1-1", words), note("N-1-c-1-2", "gone", deleted=True)])
    assert design_files.sync_notes(doc, log) == {"ok": True, "notes": 1, "rows": 1}
    text = log.read_text("utf-8")
    row = f"- Note: N-1-c-1-1 · R1 · on c-1: {json.dumps(words, ensure_ascii=False)}"
    assert row in text and json.loads(row.split(": ", 2)[2]) == words
    head = LOG_HEAD.split("- Premise")[0]
    assert text.startswith(head) and f"- Premise: a → pending\n{row}\n" in text
    assert text.endswith(LOG_TAIL) and "gone" not in text
    write_doc(doc, [note("N-1-c-1-1", "edited later"), note("N-2-c-2-1", "Second.", 2, "c-2")])
    assert design_files.sync_notes(doc, log) == {"ok": True, "notes": 1, "rows": 2}
    text = log.read_text("utf-8")
    assert row in text and "edited later" not in text and '- Note: N-2-c-2-1 · R2 · on c-2: "Second."' in text


def test_sync_is_a_verb_and_refuses_a_missing_file(files):
    log, doc = files
    write_doc(doc, [])
    assert design_files.main(["sync", "--doc", str(doc), "--log", str(log)])["notes"] == 0
    with pytest.raises(Refusal) as refused:
        design_files.main(["sync", "--doc", str(doc.with_name("none.json")), "--log", str(log)])
    assert refused.value.code == "missing-input"

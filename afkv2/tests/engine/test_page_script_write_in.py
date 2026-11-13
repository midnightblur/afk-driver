"""A write-in carries the words the human types (card write-in box, runtime.js, prompt_lines.py): the queued mark
holds them, the engine's poll turns them into the card's first note, and ingest gives the write-in signal that
text. A write-in with no words is never sent. The shipped runtime.js runs in Node against the rendered page; the
queued prompts carry the data tail that the lavish bridge appends, as lavish-axi's `queuePrompt` does."""

import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
for folder in (PLUGIN / "scripts", PLUGIN / "engine", Path(__file__).resolve().parent):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
import prompt_lines  # noqa: E402
from test_page_parts_v2 import document  # noqa: E402
from test_page_script_ticks import answers, ingest, run  # noqa: E402

CARD = "i-closed"
WORDS = "Use the vendor's own currency.\nNot the company's."
EMPTY_STATUS = f"Type your words for {CARD}: a write-in with no words is not sent."


def mark(token, card=CARD):
    return {"do": "mark", "card": card, "token": token}


def words(text, card=CARD):
    return {"do": "words", "card": card, "text": text}


def bridged(prompt):
    """The prompt as the lavish bridge hands it to the poll: the data tail after the prompt's own text."""
    return prompt["prompt"] + prompt_lines.CONTEXT_DATA + json.dumps(prompt["data"], indent=2)


def send(tmp_path, queued, doc=None):
    """The raw response the engine's poll makes of the queued prompts, and the document path."""
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc or document()), encoding="utf-8")
    prompts = [{"uid": str(n), "prompt": bridged(p), "selector": f"#{p['element']}", "tag": p["tag"], "text": ""}
               for n, p in enumerate(answers(queued))]
    return path, engine.poll_raw(str(path), prompts)


def test_the_typed_words_reach_the_send_and_the_ingest_signal(tmp_path):
    out = run([mark("write-in"), words(WORDS)])
    [queued] = answers(out["queued"])
    assert queued["prompt"] == f"{CARD} write-in\n{WORDS}"
    assert queued["data"] == {"item": CARD, "mark": "write-in", "words": WORDS}
    path, raw = send(tmp_path, out["queued"])
    assert raw.splitlines() == ["[round R-3]", f"{CARD} write-in", f"{CARD} note 1",
                                "  Use the vendor's own currency.", "  Not the company's."]
    code, result = ingest(path, raw)
    assert code == 0, result
    [signal] = result["signals"]
    assert (signal["item"], signal["mark"], signal["text"]) == (CARD, "write-in", WORDS)
    assert signal["note"] and result["needs_reading"] == [CARD]


def test_words_typed_before_the_pick_go_with_the_write_in(tmp_path):
    out = run([words(WORDS), mark("write-in")])
    assert answers(out["queued"])[-1]["prompt"] == f"{CARD} write-in\n{WORDS}"


def test_a_write_in_with_no_words_is_not_sent_and_replaces_an_earlier_mark(tmp_path):
    out = run([mark("accept"), mark("write-in")])
    assert out["status"] == EMPTY_STATUS
    [queued] = answers(out["queued"])
    assert queued["data"] == {"item": CARD, "mark": "write-in", "words": ""}
    assert send(tmp_path, out["queued"])[1].splitlines() == ["[round R-3]"]
    cleared = run([mark("write-in"), words(WORDS), words("  \n ")])
    assert cleared["status"] == EMPTY_STATUS
    assert send(tmp_path, cleared["queued"])[1].splitlines() == ["[round R-3]"]


def test_a_bare_write_in_from_a_page_without_the_words_field_still_sends_its_line(tmp_path):
    """A page rendered before this change queues `<card> write-in` with data `{item, mark}` only."""
    old = [{"prompt": f"{CARD} write-in", "tag": prompt_lines.MARK_TAG, "queueKey": "k", "element": CARD,
            "data": {"item": CARD, "mark": "write-in"}}]
    assert send(tmp_path, old)[1].splitlines() == ["[round R-3]", f"{CARD} write-in"]


def test_the_write_in_words_come_before_an_annotation_on_the_same_card(tmp_path):
    out = run([mark("write-in"), words("Mine.")])
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(document()), encoding="utf-8")
    prompts = [{"uid": "0", "prompt": "A side remark.", "selector": f"#{CARD}", "tag": "", "text": ""},
               {"uid": "1", "prompt": bridged(answers(out["queued"])[0]), "selector": f"#{CARD}",
                "tag": prompt_lines.MARK_TAG, "text": ""}]
    raw = engine.poll_raw(str(path), prompts)
    assert raw.splitlines() == ["[round R-3]", f"{CARD} write-in", f"{CARD} note 1", "  Mine.",
                                         f"{CARD} note 2", "  A side remark."]
    code, result = ingest(path, raw)
    assert code == 0, result
    assert [s["text"] for s in result["signals"] if s["mark"] == "write-in"] == ["Mine."]


def test_a_reload_keeps_the_typed_words():
    first = run([mark("write-in"), words(WORDS)])
    again = run([mark("write-in")], held={"name": first["name"], "storage": first["storage"]})
    assert answers(again["queued"])[-1]["prompt"] == f"{CARD} write-in\n{WORDS}"


def test_copy_the_response_holds_the_words_as_note_1_and_skips_an_empty_write_in():
    out = run([mark("write-in"), words(WORDS)], lavish=False)
    out = run([{"do": "copy"}], lavish=False, held={"name": out["name"], "storage": out["storage"]})
    assert out["copied"] == [f"[round R-3]\n{CARD} write-in\n{CARD} note 1\n"
                             "  Use the vendor's own currency.\n  Not the company's."]
    empty = run([mark("write-in"), {"do": "copy"}], lavish=False)
    assert empty["copied"] == ["[round R-3]"]

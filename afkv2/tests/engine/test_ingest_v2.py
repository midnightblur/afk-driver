"""Ingest on a version 2 page (SDD §3, §6, §14; ADR-0004, ADR-0005 design): a tick records a signal in
`questions_to_read` and changes no state; a note on a section, story, example or question is a plain note owned
by that entry; a note on a settled card waits in `settled_notes_to_read`. Version 1 pages ingest as before."""

import copy
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
import prompt_lines  # noqa: E402

V1, V2 = "afkv2.page/1", "afkv2.page/2"


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}"), **extra}


def accepted(item_id, n=1):
    return card(item_id, state="settled_by_mark", settled={"by": "mark", "round": n, "signal": "accept"})


def round_of(n, *items, state="current"):
    return {"n": n, "state": state, "banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items)}


def line(n=1):
    return {"round": n, "cause": "finding", "text": "Wrote the part."}


def options(*ids, several=False):
    return {"options": [{"id": option, "text": f"Option {option}"} for option in ids], "several": several}


def question(question_id, **extra):
    return {"id": question_id, "who": ["product owner"], "question": "Which formats?", "context": "The export.",
            "why": "It sets the scope.", "origin": {"card": "i-old"}, "state": "open", "changes": [line()], **extra}


def v2_document():
    """Round 1 settled with an accepted card; round 2 current with an open card; one entry of each list."""
    return {"schema": V2,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "sections": [{"id": "s-intro", "title": "Intro", "state": "current",
                          "body": text("Text of the intro.", id="s-intro-text"), "changes": [line()]}],
            "stories": [{"id": "st-1", "text": "As a user, I export.", "changes": [line()]}],
            "examples": [{"id": "ex-1", "title": "A plain export", "kind": "frequent", "stories": ["st-1"],
                          "body": text("From 3 rows to 1 file."), "changes": [line()]}],
            "questions": [question("q-one", choices=options("csv", "xls")),
                          question("q-many", choices=options("csv", "xls", "pdf", several=True)),
                          question("q-free")],
            "rounds": [round_of(1, accepted("i-old"), state="settled"), round_of(2, card("i-new"))]}


def v1_document():
    doc = v2_document()
    for kind in ("sections", "stories", "examples", "questions"):
        del doc[kind]
    doc["schema"] = V1
    return doc


@pytest.fixture
def path(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path / "doc.json"


def save(path, doc):
    path.write_bytes(json.dumps(doc).encode("utf-8"))
    return path


def call(path, raw):
    """Run the verb in this process and answer `(exit code, answer, document)`."""
    raw_file = path.parent / "raw.txt"
    raw_file.write_bytes(raw.encode("utf-8"))
    out = []
    original = print
    try:
        engine.print = out.append
        code = engine.main(["ingest", str(path), "--raw-file", str(raw_file)])
    finally:
        engine.print = original
    return code, json.loads(out[0]), json.loads(path.read_bytes().decode("utf-8"))


def ingested(path, doc, raw):
    code, answer, after = call(save(path, doc), raw)
    assert code == 0, answer
    return answer, after


def refused(path, doc, raw, code):
    status, answer, after = call(save(path, doc), raw)
    assert status == 1 and answer["error"]["code"] == code, answer
    return answer["error"]["reason"]


def item_of(doc, item_id):
    return next(i for r in doc["rounds"] for i in r["items"] if i["id"] == item_id)


def note_of(doc, note_id):
    return next(note for note in doc.get("notes") or [] if note["id"] == note_id)


def checks(path):
    out = []
    original = print
    try:
        engine.print = out.append
        return engine.main(["check", str(path)])
    finally:
        engine.print = original


# --- a tick records a signal (ADR-0004 design)


def test_a_tick_parses_on_the_engine_version_2_key():
    assert prompt_lines.FORMAT_2 == engine.SCHEMA_V2


def test_a_tick_lands_in_questions_to_read_and_changes_no_state(path):
    doc = v2_document()
    answer, after = ingested(path, doc, "[round R-2]\nq-many tick csv pdf")
    [signal] = answer["questions_to_read"]
    assert signal["target"] == "q-many" and signal["mark"] == "tick" and signal["choices"] == ["csv", "pdf"]
    assert signal["stamp"] and answer["signals"] == [signal]
    assert after["questions"] == doc["questions"] and after["rounds"][1]["items"] == doc["rounds"][1]["items"]
    assert answer["settled_by_mark"] == answer["needs_reading"] == answer["reopened"] == answer["steers"] == []
    assert answer["settled_notes_to_read"] == [] and not after.get("notes")
    assert checks(path) == 0


def test_a_tick_beside_marks_and_notes_keeps_each_signal_and_its_order(path):
    raw = "[round R-2]\ni-new accept\nq-one tick xls\ni-old note 1\n  Agreed."
    answer, after = ingested(path, v2_document(), raw)
    assert [s["target"] for s in answer["signals"]] == ["i-new", "q-one", "i-old"]
    assert [s["target"] for s in answer["questions_to_read"]] == ["q-one"]
    assert item_of(after, "i-new")["state"] == "settled_by_mark"


def test_a_tick_answer_signal_passes_the_document_check(path):
    """D-1: an answer whose signal is `tick` rests on the tick signal ingest wrote in that round."""
    _, after = ingested(path, v2_document(), "[round R-2]\nq-one tick csv")
    after["questions"][0].update(state="answered", answer={"text": "CSV.", "choices": ["csv"], "role": "tester",
                                                           "date": "2026-11-06", "signal": "tick", "round": 2})
    assert checks(save(path, after)) == 0


@pytest.mark.parametrize("raw, why", [
    ("q-nobody tick csv", "q-nobody"),
    ("i-new tick csv", "i-new"),
    ("q-one tick doc", "doc"),
    ("q-free tick csv", "csv"),
    ("q-one tick", "at least 1"),
    ("q-one tick csv xls", "1 option"),
    ("q-many tick csv csv", "csv"),
    ("q-one tick csv\nq-one tick xls", "q-one"),
])
def test_bad_tick_refuses_an_unknown_question_or_option(path, raw, why):
    doc = v2_document()
    reason = refused(path, doc, f"[round R-2]\n{raw}", "bad-tick")
    assert why in reason
    assert json.loads(path.read_bytes().decode("utf-8")) == doc


def test_a_tick_line_on_a_version_1_page_is_no_line_of_the_grammar(path):
    refused(path, v1_document(), "[round R-2]\ni-new tick csv", "bad-response")


# --- a note off every card is a plain note of its entry (SDD §14 row "Note off every card")


@pytest.mark.parametrize("target, owner", [("s-intro", "s-intro"), ("s-intro-text", "s-intro"),
                                           ("st-1", "st-1"), ("ex-1", "ex-1")])
def test_a_note_on_an_entry_is_a_plain_note_of_that_entry_not_a_steer(path, target, owner):
    answer, after = ingested(path, v2_document(), f"[round R-2]\n{target} note 1\n  Say it shorter.")
    note_id = f"N-2-{owner}-1"
    assert note_of(after, note_id) == {"id": note_id, "round": 2, "target": target, "item": owner,
                                       "text": "Say it shorter.", "deleted": False}
    [signal] = answer["signals"]
    assert signal["item"] == owner and signal["note"] == note_id and "steer" not in signal
    assert answer["steers"] == [] and answer["notes"] == [note_id] and answer["questions_to_read"] == []
    assert checks(path) == 0


def test_a_note_on_a_question_is_a_plain_note_and_lands_in_questions_to_read(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\nq-free note 1\n  Ask the tester team.")
    assert note_of(after, "N-2-q-free-1")["item"] == "q-free"
    [signal] = answer["questions_to_read"]
    assert signal["note"] == "N-2-q-free-1" and signal["item"] == "q-free" and answer["steers"] == []
    assert after["questions"][2]["state"] == "open"
    assert checks(path) == 0


def test_an_edit_of_a_note_on_an_entry_keeps_its_owner(path):
    _, after = ingested(path, v2_document(), "[round R-2]\nq-free note 1\n  First words.")
    answer, after = ingested(path, after, "[round R-2]\nN-2-q-free-1 edit\n  Better words.")
    assert note_of(after, "N-2-q-free-1")["text"] == "Better words."
    [signal] = answer["questions_to_read"]
    assert signal["item"] == "q-free" and signal["action"] == "edit" and "steer" not in signal
    assert checks(path) == 0


def test_a_note_on_the_banner_stays_a_steer(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\nR-2 note 1\n  Go faster.")
    assert answer["steers"] == ["R-2"] and note_of(after, "N-2-R-2-1")["item"] is None


# --- a note on a settled card waits for the reading (ADR-0005 design)


def test_a_note_on_a_settled_card_keeps_it_settled_and_lists_the_note(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\ni-old note 1\n  Agreed, nice.")
    point = item_of(after, "i-old")
    assert point["state"] == "settled_by_mark" and point["settled"]["signal"] == "accept"
    assert answer["settled_notes_to_read"] == ["N-2-i-old-1"] and answer["reopened"] == []
    assert note_of(after, "N-2-i-old-1")["item"] == "i-old"
    assert answer["signals"][0]["state"] == "settled_by_mark" and answer["signals"][0]["reopened"] is False
    assert checks(path) == 0


def test_two_notes_and_an_edit_on_a_settled_card_all_wait(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\ni-old note 1\n  One.\ni-old note 2\n  Two.")
    assert answer["settled_notes_to_read"] == ["N-2-i-old-1", "N-2-i-old-2"]
    answer, after = ingested(path, after, "[round R-2]\nN-2-i-old-1 edit\n  One, fixed.")
    assert item_of(after, "i-old")["state"] == "settled_by_mark"
    assert answer["settled_notes_to_read"] == ["N-2-i-old-1"]


def test_a_reopen_mark_on_a_settled_card_still_opens_it(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\ni-old reopen\ni-old note 1\n  Changed my mind.")
    assert item_of(after, "i-old")["state"] == "open" and answer["reopened"] == ["i-old"]
    assert answer["settled_notes_to_read"] == []


def test_a_lone_settling_mark_on_an_open_card_still_settles_it(path):
    answer, after = ingested(path, v2_document(), "[round R-2]\ni-new accept")
    assert item_of(after, "i-new")["state"] == "settled_by_mark" and answer["settled_by_mark"] == ["i-new"]


def test_a_version_1_page_with_a_note_on_a_settled_card_still_opens_it(path):
    answer, after = ingested(path, v1_document(), "[round R-2]\ni-old note 1\n  Agreed.")
    assert item_of(after, "i-old")["state"] == "open" and answer["reopened"] == ["i-old"]
    assert "settled_notes_to_read" not in answer and "questions_to_read" not in answer


# --- the send line of a tick (SDD §3 row "the page's send")


def tick(line_, uid="t1"):
    return {"uid": uid, "prompt": line_, "selector": "", "tag": prompt_lines.TICK_TAG, "text": ""}


def ids_of(doc):
    return engine._element_ids(doc)[1]


def test_a_queued_tick_becomes_1_send_line_and_the_last_one_per_question_wins():
    doc = v2_document()
    prompts = [tick("q-many tick csv xls", "t1"), {"uid": "m1", "prompt": "i-new accept", "selector": "",
                                                   "tag": prompt_lines.MARK_TAG, "text": ""},
               tick("q-many tick pdf", "t2"), tick("q-one tick xls", "t3")]
    raw = prompt_lines.raw_from_prompts(doc, prompts, ids_of(doc))
    assert raw == "[round R-2]\nq-many tick pdf\ni-new accept\nq-one tick xls"


def test_a_queued_tick_with_no_option_sends_nothing():
    doc = v2_document()
    raw = prompt_lines.raw_from_prompts(doc, [tick("q-many tick")], ids_of(doc))
    assert raw == "[round R-2]"


def test_the_send_line_of_a_tick_ingests(path):
    doc = v2_document()
    raw = prompt_lines.raw_from_prompts(copy.deepcopy(doc), [tick("q-many tick xls pdf")], ids_of(doc))
    answer, _ = ingested(path, doc, raw)
    assert answer["questions_to_read"][0]["choices"] == ["xls", "pdf"]

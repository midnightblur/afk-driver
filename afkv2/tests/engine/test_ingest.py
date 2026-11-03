"""Ingest, notes and replies: the mark table, conflicts, reopen, steers, note ids and the saved document.

`stress_document()` is the page the live browser test in `afkv2/tests/live/test_page_live.md` shows.
"""

import copy
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
ENGINE = ENGINE_DIR / "engine.py"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402
import ingest  # noqa: E402
from schema import invariants  # noqa: E402
from shell import page  # noqa: E402

SCHEMA = "afkv2.page/0"
NOTES_CSS = (ENGINE_DIR / "shell" / "notes.css").read_text("utf-8")


EMPTY_SLOT = '<section class="afkv2-notes-replies" id="afkv2-notes-replies"></section>'
TABLE = 'class="afkv2-nr-table"'
EARLIER = 'id="afkv2-nr-earlier"'
ROUND_3 = 'data-afkv2-nr-round="3"'
ROUND_2 = 'data-afkv2-nr-round="2"'
ROUND_1 = 'data-afkv2-nr-round="1"'
CURRENT = 'data-afkv2-state="current"'
ROUND_ATTR = 'data-afkv2-round="1"'
BY_NOTE = "afkv2-state--settled_by_note"
BY_MARK = "afkv2-state--settled_by_mark"
SLOT = 'id="afkv2-notes-replies"'
MAPS = 'id="afkv2-maps"'
FORM = 'id="afkv2-answer-form"'
BAR = 'id="afkv2-copy"'
EDIT_BUTTON = "data-afkv2-note-edit"
DELETE_BUTTON = "data-afkv2-note-delete"
QUOTED_ONE = '<q class="afkv2-nr-text">note of round one</q>'
NOTE_ROW_A, NOTE_ROW_B = "afkv2-nr-N-1-i-a", "afkv2-nr-N-2-i-b"
REPLY_ROW = "afkv2-nr-reply-3-1"
NOTE_ACTION = 'data-lavish-action="afkv2-note"'


def lacks_note_action(html):
    return NOTE_ACTION not in html


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}"), **extra}


def by_mark(item_id, round_n=1, kind="confirm", signal="accept"):
    return card(item_id, kind, state="settled_by_mark", settled={"by": "mark", "round": round_n, "signal": signal})


def banner():
    return {"settled": [], "unlocks": [], "parked": []}


def document(*rounds, maps=None):
    doc = {"schema": SCHEMA, "session": {"id": "s1", "skill": "grill", "feature": "Feature", "ticket": "T-1",
                                         "started": "2026-01-05T10:00:00Z"}, "rounds": list(rounds)}
    if maps:
        doc["maps"] = maps
    return doc


def round_of(n, *items, state="current"):
    return {"n": n, "state": state, "banner": banner(), "items": list(items)}


def one_round(*items):
    return document(round_of(1, *items))


def later_round(old, *items):
    return document(round_of(1, old, state="settled"), round_of(2, *items))


def node(node_id, round_n=1, state="open"):
    return {"id": node_id, "label": f"Label {node_id}", "state": state, "round": round_n}


def a_map(*node_ids, map_id="m-1"):
    return {"type": "map", "id": map_id, "props": {"nodes": [node(n) for n in node_ids]}}


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


def item_of(doc, item_id):
    return next(i for r in doc["rounds"] for i in r["items"] if i["id"] == item_id)


def check(path):
    return engine.main(["check", str(path)])


def refused(path, doc, raw):
    before = json.dumps(doc)
    code, answer, after = call(save(path, doc), raw)
    assert code == 1, answer
    assert json.dumps(after) == before
    return answer["error"]


# --- the verb


def test_ingest_appends_raw_and_signals_to_the_current_round(path):
    raw = "[round R-1]\ni-a accept\ni-b —"
    answer, after = ingested(path, one_round(card("i-a"), card("i-b")), raw)
    response = after["rounds"][0]["responses"][0]
    assert response["raw"] == raw and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", response["received"])
    assert [s["target"] for s in response["signals"]] == ["i-a"]
    assert answer["ok"] and answer["verb"] == "ingest" and answer["round"] == 1
    assert answer["signals"] == response["signals"]
    assert check(path) == 0


def test_each_signal_carries_the_stamp_of_ingest(path):
    raw = "[round R-1]\ni-a accept"
    _, after = ingested(path, one_round(card("i-a")), raw)
    response = after["rounds"][0]["responses"][0]
    signal = response["signals"][0]
    assert signal["stamp"] == invariants.ingest_stamp("s1", 1, response["received"], raw, signal)


def test_a_later_response_of_the_round_is_appended(path):
    doc = one_round(card("i-a"), card("i-b"))
    _, after = ingested(path, doc, "[round R-1]\ni-a accept\ni-b —")
    _, after = ingested(path, after, "[round R-1]\ni-b accept")
    assert len(after["rounds"][0]["responses"]) == 2
    assert item_of(after, "i-b")["state"] == "settled_by_mark"


def test_the_stored_raw_keeps_every_byte_of_a_multi_line_note(path):
    note = 'C:\\Users\\x back\\slash "q" trailing  \n\n  second line\ttab | pipe é 中文 \\\\double'
    raw = f"[round R-1]\ni-a accept | {note}\ni-b —"
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), raw)
    assert after["rounds"][0]["responses"][0]["raw"] == raw
    assert item_of(after, "i-a")["notes"][0]["text"] == note


def test_the_command_reads_the_raw_file_and_answers_one_object(path):
    save(path, one_round(card("i-a")))
    raw_file = path.parent / "r.txt"
    raw_file.write_bytes("[round R-1]\ni-a accept | é".encode("utf-8"))
    run = subprocess.run([sys.executable, str(ENGINE), "ingest", str(path), "--raw-file", str(raw_file)],
                         capture_output=True, text=True, timeout=60, encoding="utf-8")
    assert run.returncode == 0 and json.loads(run.stdout)["ok"] is True
    assert item_of(json.loads(path.read_bytes().decode("utf-8")), "i-a")["notes"][0]["text"] == "é"


@pytest.mark.parametrize("content", [None, b"\xff\xfe"])
def test_an_unreadable_raw_file_is_exit_2(path, content):
    save(path, one_round(card("i-a")))
    raw_file = path.parent / "r.txt"
    if content:
        raw_file.write_bytes(content)
    run = subprocess.run([sys.executable, str(ENGINE), "ingest", str(path), "--raw-file", str(raw_file)],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 2 and json.loads(run.stdout)["error"]["code"] == "unreadable"


def test_ingest_without_a_raw_file_is_a_usage_refusal(path):
    run = subprocess.run([sys.executable, str(ENGINE), "ingest", str(save(path, one_round(card("i-a"))))],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 2 and json.loads(run.stdout)["error"]["code"] == "usage"


@pytest.mark.parametrize("raw, code, part", [
    ("i-a accept", "bad-response", "line 1"),
    ("", "bad-response", "line 1"),
    ("[round R-1]\ngarbage", "bad-response", "line 2"),
    ("[round R-1]\ni-a accept\nnot a line of any card", "bad-response", "line 3"),
    ("[round R-1]\ni-a sign", "bad-response", "line 2"),
    ("[round R-1]\nN-1-i-a edit", "bad-response", "line 2"),
    ("[round R-2]\ni-a accept", "stale-round", "round 1"),
    ("[round R-1]\ni-a —", "no-signal", "no signal"),
    ("[round R-1]", "no-signal", "no signal"),
])
def test_a_response_that_is_not_the_grammar_writes_nothing(path, raw, code, part):
    error = refused(path, one_round(card("i-a")), raw)
    assert error["code"] == code and part in error["reason"]


def test_an_invalid_document_is_refused_before_any_change(path):
    doc = one_round(card("i-a"), card("i-a"))
    error = refused(path, doc, "[round R-1]\ni-a accept")
    assert error["code"] == "invariant"


def test_a_crlf_response_keeps_its_raw_and_parses(path):
    raw = "[round R-1]\r\ni-a accept\r\ni-b — | one\r\ntwo\r\n"
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), raw)
    assert after["rounds"][0]["responses"][0]["raw"] == raw
    assert item_of(after, "i-b")["notes"][0]["text"] == "one\ntwo"


# --- the mark table


@pytest.mark.parametrize("kind, mark", [("decided", "accept"), ("confirm", "accept"), ("signoff", "sign"), ("debate", "a")])
def test_a_lone_accept_sign_or_option_mark_settles_by_mark(path, kind, mark):
    body = {"type": "table", "props": {"columns": ["A"], "rows": [[text("x", id="i-a-opt-a")]]}}
    item = {**card("i-a", kind), "body": body}
    answer, after = ingested(path, one_round(item), f"[round R-1]\ni-a {mark}")
    point = item_of(after, "i-a")
    assert point["state"] == "settled_by_mark"
    assert point["settled"] == {"by": "mark", "round": 1, "signal": mark}
    assert answer["settled_by_mark"] == ["i-a"]
    assert check(path) == 0


@pytest.mark.parametrize("line", [
    "i-a — | a note",
    "i-a accept | a mark plus a note",
    "i-a reopen",
    "i-a write-in",
    "i-a write-in | my text",
])
def test_everything_else_goes_to_needs_reading(path, line):
    answer, after = ingested(path, one_round(card("i-a")), f"[round R-1]\n{line}")
    point = item_of(after, "i-a")
    assert point["state"] == "needs_reading" and "settled" not in point
    assert answer["needs_reading"] == ["i-a"]
    assert check(path) == 0


def test_a_changes_mark_goes_to_needs_reading(path):
    _, after = ingested(path, one_round(card("i-a", "signoff")), "[round R-1]\ni-a changes")
    assert item_of(after, "i-a")["state"] == "needs_reading"


def test_two_lines_for_one_item_are_a_conflict(path):
    raw = "[round R-1]\ni-a accept\ni-a reopen"
    answer, after = ingested(path, one_round(card("i-a")), raw)
    assert item_of(after, "i-a")["state"] == "needs_reading"
    assert answer["conflicts"] == ["i-a"]
    assert [s["conflict"] for s in answer["signals"]] == [True, True]


def test_a_mark_and_a_note_on_a_part_of_the_card_are_a_conflict(path):
    item = {**card("i-a"), "body": text("x", id="i-a-part")}
    answer, after = ingested(path, one_round(item), "[round R-1]\ni-a accept\ni-a-part — | not this part")
    point = item_of(after, "i-a")
    assert point["state"] == "needs_reading" and answer["conflicts"] == ["i-a"]
    assert point["notes"][0]["target"] == "i-a-part"


def test_a_blocked_point_follows_the_same_table(path):
    _, after = ingested(path, one_round(card("i-a", state="blocked"), card("i-b", state="blocked")),
                        "[round R-1]\ni-a accept\ni-b — | hm")
    assert item_of(after, "i-a")["state"] == "settled_by_mark"
    assert item_of(after, "i-b")["state"] == "needs_reading"


def test_a_needs_reading_point_stays_until_the_agent_reads_it(path):
    _, after = ingested(path, one_round(card("i-a", state="needs_reading")), "[round R-1]\ni-a accept")
    assert item_of(after, "i-a")["state"] == "needs_reading" and "settled" not in item_of(after, "i-a")


def test_a_silent_card_stays_as_it_is(path):
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), "[round R-1]\ni-a accept\ni-b —")
    assert item_of(after, "i-b").get("state", "open") == "open"


def test_apply_mark_table_is_a_pure_table():
    mark, note = ingest.Line("i", "accept", None, 2), ingest.Line("i", "—", "t", 3)
    assert ingest.apply_mark_table("open", [mark], None) == "settled_by_mark"
    assert ingest.apply_mark_table("open", [note], None) == "needs_reading"
    assert ingest.apply_mark_table("settled_by_mark", [note], "accept") == "open"
    assert ingest.apply_mark_table("settled_by_mark", [mark], "accept") == "settled_by_mark"
    assert ingest.apply_mark_table("settled_by_mark", [ingest.Line("i", "b", None, 2)], "a") == "open"
    assert ingest.apply_mark_table("settled_by_note", [mark], "N-1-i") == "settled_by_note"


# --- settled by note: the agent's reading


def reading(doc, item_id, note_id, text_="Picks CSV.", round_n=1):
    point = item_of(doc, item_id)
    point["state"] = "settled_by_note"
    point["settled"] = {"by": "note", "round": round_n, "signal": note_id, "reading": text_}


def test_the_agent_reading_settles_by_note_and_shows_a_different_state(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a — | CSV please")
    reading(after, "i-a", "N-1-i-a")
    assert check(save(path, after)) == 0
    html = page.build(after)
    assert BY_NOTE in html and "settled by note" in html and "Picks CSV." in html
    _, marked = ingested(path, one_round(card("i-b")), "[round R-1]\ni-b accept")
    assert BY_MARK in page.build(marked) and "settled by note" not in page.build(marked)


def test_settled_by_note_needs_a_note_id_and_a_reading(path, capsys):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a accept | CSV")
    reading(after, "i-a", "N-1-i-a", text_="")
    assert check(save(path, after)) == 1
    assert "reading" in capsys.readouterr().out
    reading(after, "i-a", "N-1-other")
    assert check(save(path, after)) == 1


def test_the_agent_returns_an_unclear_point_to_open(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a accept\ni-a reopen")
    item_of(after, "i-a")["state"] = "open"
    assert check(save(path, after)) == 0
    assert 'name="choice:i-a"' in page.build(after)


# --- WE-02 rounds 3 and 4


def test_we_02_a_note_settles_then_a_mark_and_a_note_reopen(path):
    doc = document(round_of(1, card("i-1"), state="settled"), round_of(2, card("i-2"), state="settled"),
                   round_of(3, card("V-5"), card("i-3")))
    _, after = ingested(path, doc, "[round R-3]\nV-5 — | yes, notes can settle it\ni-3 accept")
    assert item_of(after, "V-5")["state"] == "needs_reading"
    reading(after, "V-5", "N-3-V-5", "notes may settle a point", 3)
    after["rounds"][2]["replies"] = [{"text": "settled by your note: notes may settle a point", "about": ["V-5"]}]
    after["rounds"][2]["state"] = "settled"
    after["rounds"].append(round_of(4, card("i-4")))
    assert check(save(path, after)) == 0
    engine.save_settled_copy(path, after)

    answer, after = ingested(path, after, "[round R-4]\nV-5 accept | only for terms\ni-4 —")
    point = item_of(after, "V-5")
    assert point["state"] == "open" and "settled" not in point
    assert answer["reopened"] == ["V-5"]
    signal = answer["signals"][0]
    assert signal["mark"] == "accept" and signal["text"] == "only for terms" and signal["note"] == "N-4-V-5"
    assert [n["id"] for n in point["notes"]] == ["N-3-V-5", "N-4-V-5"]
    assert check(path) == 0
    html = page.build(after)
    assert "only for terms" in html and "yes, notes can settle it" in html and "accept" in html


# --- a note on a settled item, a steer on a map node


def test_a_note_on_a_settled_item_reopens_it_in_the_next_round(path):
    doc = later_round(by_mark("i-old"), card("i-new"))
    answer, after = ingested(path, doc, "[round R-2]\ni-old — | Not any more\ni-new —")
    point = item_of(after, "i-old")
    assert point["state"] == "open" and "settled" not in point
    assert point["notes"][0] == {"id": "N-2-i-old", "round": 2, "target": "i-old", "text": "Not any more", "deleted": False}
    assert after["rounds"][0]["state"] == "settled" and "responses" not in after["rounds"][0]
    signal = after["rounds"][1]["responses"][0]["signals"][0]
    assert signal["reopened"] is True and signal["item"] == "i-old" and answer["reopened"] == ["i-old"]


def test_the_late_note_saves_the_copy_so_the_next_check_passes(path, capsys):
    doc = later_round(by_mark("i-old"), card("i-new"))
    engine.save_settled_copy(save(path, doc), doc)
    ingested(path, doc, "[round R-2]\ni-old — | Late\ni-new —")
    assert check(path) == 0
    capsys.readouterr()
    after = json.loads(path.read_bytes().decode("utf-8"))
    after["rounds"][0]["items"][0]["notes"][0]["text"] = "rewritten by hand"
    assert check(save(path, after)) == 1
    assert "never rewritten" in capsys.readouterr().out


def test_a_reopen_mark_reopens_a_settled_item(path):
    answer, after = ingested(path, later_round(by_mark("i-old"), card("i-new")), "[round R-2]\ni-old reopen\ni-new —")
    assert item_of(after, "i-old")["state"] == "open" and answer["reopened"] == ["i-old"]


def test_a_lone_mark_on_a_settled_item_is_recorded_and_changes_nothing_when_it_agrees(path):
    doc = later_round(by_mark("i-old"), card("i-new"))
    answer, after = ingested(path, doc, "[round R-2]\ni-old accept\ni-new —")
    assert item_of(after, "i-old")["state"] == "settled_by_mark" and answer["signals"][0]["mark"] == "accept"
    assert answer["reopened"] == [] and answer["settled_by_mark"] == []


def test_a_settled_card_of_the_current_round_reopens_in_place(path):
    answer, after = ingested(path, one_round(by_mark("i-a")), "[round R-1]\ni-a — | Second thoughts")
    assert item_of(after, "i-a")["state"] == "open" and answer["reopened"] == ["i-a"]
    assert check(path) == 0


def test_a_note_on_a_settled_signoff_card_loses_the_sign_mark(path):
    """Owner ruling R-3: the note reopens the settled card, and the card asks for a sign mark again."""
    old = by_mark("i-s", kind="signoff", signal="sign")
    _, after = ingested(path, later_round(old, card("i-new")), "[round R-2]\ni-s — | Say 30 days\ni-new —")
    assert item_of(after, "i-s")["state"] == "open" and "settled" not in item_of(after, "i-s")
    assert check(path) == 0


def test_a_sign_mark_with_a_wording_note_comes_back_for_a_sign_mark(path):
    _, after = ingested(path, one_round(card("i-s", "signoff")), "[round R-1]\ni-s sign | Say 30 days")
    assert item_of(after, "i-s")["state"] == "needs_reading"
    item_of(after, "i-s")["state"] = "open"
    assert check(save(path, after)) == 0
    assert 'name="choice:i-s" value="sign"' in page.build(after)


def test_a_note_on_a_map_node_is_a_steer_and_settles_nothing(path):
    doc = one_round(card("i-a", node="n-1"), card("i-b"))
    doc["maps"] = [a_map("n-1", "n-2")]
    answer, after = ingested(path, doc, "[round R-1]\ni-a —\ni-b —\nn-1 — | Look at this first")
    point = item_of(after, "i-a")
    assert point["notes"] == [{"id": "N-1-i-a", "round": 1, "target": "n-1", "text": "Look at this first", "deleted": False}]
    assert point.get("state", "open") == "open"
    assert answer["steers"] == ["n-1"] and answer["needs_reading"] == []
    assert answer["signals"][0]["steer"] is True
    assert check(path) == 0


def test_a_steer_does_not_reopen_a_settled_linked_card(path):
    doc = later_round(by_mark("i-old", 1) | {"node": "n-1"}, card("i-new"))
    doc["maps"] = [a_map("n-1")]
    answer, after = ingested(path, doc, "[round R-2]\ni-new —\nn-1 — | steer")
    assert item_of(after, "i-old")["state"] == "settled_by_mark" and answer["reopened"] == []
    assert check(path) == 0


def test_a_steer_and_a_note_on_the_linked_card_each_keep_their_note(path):
    doc = one_round(card("i-a", node="n-1"), card("i-b"))
    doc["maps"] = [a_map("n-1")]
    _, after = ingested(path, doc, "[round R-1]\nn-1 — | steer\ni-a — | card note\ni-b —")
    assert item_of(after, "i-a")["notes"][0]["target"] == "i-a"
    assert item_of(after, "i-b")["notes"][0]["target"] == "n-1"
    assert item_of(after, "i-b")["notes"][0]["id"] == "N-1-i-b"
    assert check(path) == 0


def test_a_steer_with_no_linked_card_finds_a_home_in_the_current_round(path):
    doc = later_round(by_mark("i-old"), card("i-new"))
    doc["maps"] = [a_map("n-1")]
    _, after = ingested(path, doc, "[round R-2]\ni-new —\nn-1 — | steer")
    assert item_of(after, "i-new")["notes"][0]["target"] == "n-1"


def test_a_steer_with_no_free_note_is_folded_and_stays_in_the_signals(path):
    doc = one_round(card("i-a"))
    doc["maps"] = [a_map("n-1")]
    answer, after = ingested(path, doc, "[round R-1]\ni-a — | card\nn-1 — | steer")
    notes = item_of(after, "i-a")["notes"]
    assert len(notes) == 1 and notes[0]["text"] == "card\n\nsteer"
    assert [s for s in answer["signals"] if s.get("steer")][0]["target"] == "n-1"
    assert check(path) == 0


def test_a_steer_on_a_page_with_no_card_is_refused(path):
    doc = one_round()
    doc["maps"] = [a_map("n-1")]
    assert refused(path, doc, "[round R-1]\nn-1 — | steer")["code"] == "bad-response"


def test_a_note_on_the_map_itself_is_recorded_and_settles_nothing(path):
    doc = one_round(card("i-a"))
    doc["maps"] = [a_map("n-1")]
    answer, after = ingested(path, doc, "[round R-1]\nm-1 — | The map is wrong\ni-a —")
    assert item_of(after, "i-a")["notes"][0]["target"] == "m-1"
    assert item_of(after, "i-a").get("state", "open") == "open" and answer["steers"] == ["m-1"]


# --- a map held in a card or a table cell counts as a map (D-43, D-48)


def held_in_card(item_id, *node_ids, map_id):
    return {**card(item_id), "body": a_map(*node_ids, map_id=map_id)}


def held_in_cell(item_id, *node_ids, map_id):
    return {**card(item_id), "body": {"type": "table", "props": {"columns": ["Map"], "rows": [[a_map(*node_ids, map_id=map_id)]]}}}


@pytest.mark.parametrize("holder", [held_in_card, held_in_cell])
def test_a_note_on_a_held_map_node_is_accepted_as_a_steer(path, holder):
    doc = one_round(holder("i-a", "n-1", map_id="m-1"), card("i-b"))
    answer, after = ingested(path, doc, "[round R-1]\nn-1 — | steer\ni-a —\ni-b —")
    assert answer["steers"] == ["n-1"]
    assert item_of(after, "i-a")["notes"][0]["target"] == "n-1"
    assert item_of(after, "i-a").get("state", "open") == "open"
    assert check(path) == 0


@pytest.mark.parametrize("holder", [held_in_card, held_in_cell])
def test_an_item_can_link_to_a_held_map_node(path, holder):
    doc = one_round(holder("i-a", "n-1", map_id="m-1"), card("i-b", node="n-1"))
    assert check(save(path, doc)) == 0


@pytest.mark.parametrize("holder", [held_in_card, held_in_cell])
def test_two_held_maps_with_one_node_id_fail_the_check(path, holder, capsys):
    doc = one_round(holder("i-a", "n-1", map_id="m-1"), holder("i-b", "n-1", map_id="m-2"))
    assert check(save(path, doc)) == 1
    assert "'n-1' is not unique" in capsys.readouterr().out


def test_a_held_map_and_a_listed_map_with_one_node_id_fail_the_check(path, capsys):
    doc = one_round(held_in_card("i-a", "n-1", map_id="m-1"))
    doc["maps"] = [a_map("n-1", map_id="m-2")]
    assert check(save(path, doc)) == 1
    assert "'n-1' is not unique" in capsys.readouterr().out


def test_a_held_map_node_with_an_item_id_fails_the_check(path, capsys):
    doc = one_round(held_in_card("i-a", "i-b", map_id="m-1"), card("i-b"))
    assert check(save(path, doc)) == 1
    assert "'i-b' is not unique" in capsys.readouterr().out


@pytest.mark.parametrize("holder", [held_in_card, held_in_cell])
def test_a_held_node_round_past_the_last_round_fails_the_check(path, holder, capsys):
    item = holder("i-a", "n-1", map_id="m-1")
    nodes = (item["body"]["props"] if holder is held_in_card else item["body"]["props"]["rows"][0][0]["props"])["nodes"]
    nodes[0]["round"] = 99
    assert check(save(path, one_round(item))) == 1
    out = capsys.readouterr().out
    assert "item i-a" in out and "must be a round from 1 to 1" in out


def test_a_map_held_in_a_map_label_counts_too(path, capsys):
    inner = a_map("n-in", map_id="m-in")
    outer = {"type": "map", "id": "m-out", "props": {"nodes": [{**node("n-out"), "label": inner}]}}
    answer, after = ingested(path, one_round(card("i-a"), {**card("i-b"), "body": outer}),
                             "[round R-1]\nn-in — | steer\ni-a —\ni-b —")
    assert answer["steers"] == ["n-in"] and after["rounds"][0]["items"]


def test_a_settled_by_note_cannot_rest_on_a_steer_on_a_held_node(path):
    doc = one_round(held_in_card("i-a", "n-1", map_id="m-1"))
    _, after = ingested(path, doc, "[round R-1]\nn-1 — | steer")
    reading(after, "i-a", "N-1-i-a")
    assert check(save(path, after)) == 1


# --- note ids, edit and delete


def test_a_note_id_is_round_and_item(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a — | x")
    assert item_of(after, "i-a")["notes"][0]["id"] == "N-1-i-a"


def test_notes_on_every_kind_of_element_are_accepted(path):
    freestyle = {"type": "freestyle", "id": "f-1", "html": "<svg></svg>", "props": {"reason": "why"}}
    graph = {"type": "graph", "id": "g-1", "props": {"nodes": [{"id": "x", "label": "X"}]}}
    doc = document(round_of(1, by_mark("i-done"), state="settled"),
                   round_of(2, {**card("i-f"), "body": freestyle}, {**card("i-g"), "body": graph}, card("i-c"), card("i-free")))
    doc["maps"] = [a_map("n-1")]
    raw = "[round R-2]\ni-c — | card\nf-1 — | fragment\ng-1 — | diagram\ni-done — | settled\nn-1 — | node\ni-f —\ni-g —"
    answer, after = ingested(path, doc, raw)
    targets = {n["target"] for r in after["rounds"] for i in r["items"] for n in i.get("notes") or []}
    assert targets == {"i-c", "f-1", "g-1", "i-done", "n-1"}
    assert answer["steers"] == ["n-1"]
    assert check(path) == 0


def test_editing_a_note_keeps_its_id_and_needs_a_new_reading(path):
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), "[round R-1]\ni-a — | first\ni-b —")
    reading(after, "i-a", "N-1-i-a")
    answer, after = ingested(path, after, "[round R-1]\nN-1-i-a edit | second\nline two\ni-b —")
    point = item_of(after, "i-a")
    assert point["notes"] == [{"id": "N-1-i-a", "round": 1, "target": "i-a", "text": "second\nline two", "deleted": False}]
    assert point["state"] == "open" and "settled" not in point and answer["reopened"] == ["i-a"]
    assert answer["signals"][0]["action"] == "edit"
    assert check(path) == 0


def test_deleting_a_note_keeps_its_id_with_deleted(path):
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), "[round R-1]\ni-a — | first\ni-b —")
    answer, after = ingested(path, after, "[round R-1]\nN-1-i-a delete")
    assert item_of(after, "i-a")["notes"] == [
        {"id": "N-1-i-a", "round": 1, "target": "i-a", "text": "first", "deleted": True}]
    assert answer["signals"][0]["action"] == "delete"
    assert check(path) == 0


def test_deleting_the_note_a_point_rests_on_reopens_the_point(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a — | first")
    reading(after, "i-a", "N-1-i-a")
    answer, after = ingested(path, after, "[round R-1]\nN-1-i-a delete")
    assert item_of(after, "i-a")["state"] == "open" and answer["reopened"] == ["i-a"]
    assert check(path) == 0


def test_a_new_note_after_a_delete_reuses_the_id(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a — | first")
    _, after = ingested(path, after, "[round R-1]\nN-1-i-a delete")
    _, after = ingested(path, after, "[round R-1]\ni-a — | again")
    assert item_of(after, "i-a")["notes"] == [{"id": "N-1-i-a", "round": 1, "target": "i-a", "text": "again", "deleted": False}]


def test_a_second_note_on_one_item_in_one_round_is_folded(path):
    item = {**card("i-a"), "body": text("x", id="i-a-part")}
    _, after = ingested(path, one_round(item), "[round R-1]\ni-a — | one\ni-a-part — | two")
    notes = item_of(after, "i-a")["notes"]
    assert len(notes) == 1 and notes[0]["text"] == "one\n\ntwo" and notes[0]["target"] == "i-a"
    assert check(path) == 0


def test_the_same_note_sent_twice_is_one_note(path):
    _, after = ingested(path, one_round(card("i-a")), "[round R-1]\ni-a — | one")
    _, after = ingested(path, after, "[round R-1]\ni-a — | one")
    assert item_of(after, "i-a")["notes"][0]["text"] == "one"


def test_editing_a_note_of_an_older_round_saves_the_copy(path):
    _, after = ingested(path, later_round(card("i-old", state="open"), card("i-new")), "[round R-2]\ni-old — | x\ni-new —")
    item_of(after, "i-old")["state"] = "open"
    after["rounds"][1]["state"] = "settled"
    after["rounds"].append(round_of(3, card("i-3")))
    save(path, after)
    engine.save_settled_copy(path, after)
    _, after = ingested(path, after, "[round R-3]\nN-2-i-old edit | y\ni-3 —")
    assert item_of(after, "i-old")["notes"][0]["id"] == "N-2-i-old"
    assert check(path) == 0


def test_a_note_line_that_reads_like_a_card_line_never_settles_a_card(path):
    """A known limit of the grammar (D-49): the line counts as a line, so the card has a conflict."""
    raw = "[round R-1]\ni-a — | first line\ni-b accept\ni-b —"
    answer, after = ingested(path, one_round(card("i-a"), card("i-b")), raw)
    assert item_of(after, "i-b")["state"] == "needs_reading" and answer["settled_by_mark"] == []
    assert answer["conflicts"] == ["i-b"]


def test_a_note_line_that_only_starts_like_a_card_stays_in_the_note(path):
    raw = "[round R-1]\ni-a — | first\ni-b is wrong\ni-b accepted\ni-a nonsense\ni-b —"
    _, after = ingested(path, one_round(card("i-a"), card("i-b")), raw)
    assert item_of(after, "i-a")["notes"][0]["text"] == "first\ni-b is wrong\ni-b accepted\ni-a nonsense"


def test_a_settled_card_of_an_older_round_is_never_read_as_a_new_round_card(path):
    assert refused(path, later_round(by_mark("i-old"), card("i-new")), "[round R-1]\ni-old accept")["code"] == "stale-round"


# --- notes and replies on the page


def noted_document():
    doc = document(round_of(1, by_mark("i-a"), state="settled"), round_of(2, card("i-b"), state="settled"), round_of(3, card("i-c")))
    item_of(doc, "i-a")["notes"] = [{"id": "N-1-i-a", "round": 1, "target": "i-a", "text": "note of round one", "deleted": False}]
    item_of(doc, "i-b")["notes"] = [{"id": "N-2-i-b", "round": 2, "target": "i-b", "text": "<b>note of round two</b>", "deleted": False}]
    item_of(doc, "i-c")["notes"] = [{"id": "N-3-i-c", "round": 3, "target": "i-c", "text": "gone", "deleted": True}]
    doc["rounds"][0]["replies"] = [{"text": "reply of round one", "about": ["i-a"]}]
    doc["rounds"][2]["replies"] = [{"text": "reply of round three", "about": ["i-c"]}, {"text": "another reply"}]
    return doc


def slot(html):
    start = html.index(SLOT)
    return html[start:html.index(MAPS)]


def row(html, row_id):
    start = html.index(f'id="{row_id}"')
    return html[start:html.index("</tr>", start)]


def test_the_rows_come_newest_round_first_and_older_rounds_fold():
    html = slot(page.build(noted_document()))
    places = [html.index(mark) for mark in (TABLE, ROUND_3, "reply of round three", "another reply",
                                            ROUND_2, "note of round two", EARLIER, ROUND_1, "note of round one")]
    assert places == sorted(places)
    assert html.count("<details") == 1 and "<details open" not in html and html.count("<table") == 2


def test_two_rounds_stay_open_and_have_no_fold():
    doc = noted_document()
    doc["rounds"] = doc["rounds"][:2]
    doc["rounds"][1]["state"] = "current"
    html = slot(page.build(doc))
    assert "<details" not in html and ROUND_1 in html and ROUND_2 in html


def test_a_note_row_holds_the_quoted_note_and_the_reply_that_answers_it():
    html = slot(page.build(noted_document()))
    note_row = row(html, "afkv2-nr-N-1-i-a")
    assert QUOTED_ONE in note_row and "reply of round one" in note_row
    assert 'title="N-1-i-a">R1.1<' in note_row and 'href="#i-a"' in note_row
    assert "No answer yet" in row(html, NOTE_ROW_B)


def test_a_reply_of_the_next_round_answers_the_note_of_the_round_before():
    doc = noted_document()
    doc["rounds"][2]["replies"].append({"text": "read as two", "about": ["N-2-i-b"]})
    doc["rounds"][1]["replies"] = [{"text": "same round first", "about": ["i-b"]}]
    note_row = row(slot(page.build(doc)), "afkv2-nr-N-2-i-b")
    assert note_row.index("same round first") < note_row.index("read as two")


def test_a_reply_that_answers_no_note_has_its_own_row():
    html = slot(page.build(noted_document()))
    alone = row(html, "afkv2-nr-reply-3-2")
    assert "another reply" in alone and "From me" in alone and "<q" not in alone
    assert 'href="#i-c"' in row(html, REPLY_ROW)


def test_a_deleted_note_is_not_shown_and_no_row_has_a_control():
    html = slot(page.build(noted_document()))
    assert "gone" not in html and "N-3-i-c" not in html
    assert EDIT_BUTTON not in html and DELETE_BUTTON not in html and "<button" not in html


def test_note_text_is_escaped():
    assert "&lt;b&gt;note of round two&lt;/b&gt;" in slot(page.build(noted_document()))


def test_the_row_names_the_card_title_and_the_element():
    doc = one_round({**card("i-a"), "title": "Export format", "body": text("The format of the file.", id="i-a-words")})
    item_of(doc, "i-a")["notes"] = [{"id": "N-1-i-a", "round": 1, "target": "i-a-words", "text": "x", "deleted": False}]
    note_row = row(slot(page.build(doc)), "afkv2-nr-N-1-i-a")
    assert "Export format" in note_row and "The format of the file." in note_row and 'href="#i-a"' in note_row


def test_a_page_with_no_note_and_no_reply_has_an_empty_slot():
    assert EMPTY_SLOT in page.build(one_round(card("i-a")))


def test_the_signals_of_a_response_are_not_shown(path):
    answer, after = ingested(path, later_round(by_mark("i-old"), card("i-new")),
                             "[round R-2]\ni-old accept | only for terms\ni-new —")
    html = slot(page.build(after))
    assert "What you sent" not in html and "mark accept" not in html and "only for terms" in html
    assert answer["reopened"] == ["i-old"]


def test_a_steer_names_the_map_and_links_to_the_node():
    doc = one_round(card("i-a"))
    doc["maps"] = [a_map("n-1")]
    item_of(doc, "i-a")["notes"] = [{"id": "N-1-i-a", "round": 1, "target": "n-1", "text": "go", "deleted": False}]
    note_row = row(slot(page.build(doc)), "afkv2-nr-N-1-i-a")
    assert "Map: m-1" in note_row and "Label n-1" in note_row and 'href="#n-1"' in note_row
    assert page.slot_targets(doc) == {"afkv2-nr-N-1-i-a": "n-1"}


def test_a_steer_on_a_held_node_names_the_map():
    doc = one_round(held_in_card("i-a", "n-1", map_id="m-1"))
    item_of(doc, "i-a")["notes"] = [{"id": "N-1-i-a", "round": 1, "target": "n-1", "text": "go", "deleted": False}]
    assert 'href="#n-1"' in row(slot(page.build(doc)), NOTE_ROW_A)
    assert page.slot_targets(doc) == {"afkv2-nr-N-1-i-a": "n-1"}


def test_a_note_row_stands_for_its_card():
    assert page.slot_targets(noted_document()) == {"afkv2-nr-N-1-i-a": "i-a", "afkv2-nr-N-2-i-b": "i-b"}


def test_every_row_id_is_unique():
    ids = re.findall(r' id="([^"]+)"', slot(page.build(stress_document())))
    assert len(ids) == len(set(ids)) and len(ids) > 40


def test_a_settled_page_has_no_form_and_no_copy_bar():
    html = page.build(one_round(by_mark("i-a")))
    assert FORM not in html and BAR not in html
    assert CURRENT in html and ROUND_ATTR in html


def test_a_live_page_has_one_copy_bar_and_no_form():
    html = page.build(document(round_of(1, by_mark("i-a"), card("i-b"))))
    assert FORM not in html and html.count(BAR) == 1
    assert EMPTY_SLOT in html


def test_the_same_document_gives_the_same_notes_bytes():
    assert page.build(noted_document()) == page.build(noted_document())


def test_long_text_and_a_note_wrap():
    assert "overflow-wrap: anywhere" in NOTES_CSS and "white-space: pre-wrap" in NOTES_CSS
    assert "table-layout: fixed" in NOTES_CSS


# --- notes come from lavish annotations: the page has no note controls of its own


def test_the_page_has_no_note_controls():
    html = page.build(one_round(card("i-a")))
    assert "+ note" not in html and "Your unsent notes" not in html and "<textarea" not in html
    assert lacks_note_action(html)


# --- a saved document opens to read or to continue (AC-039)


def in_home(tmp_path, doc):
    repo = tmp_path / "repo"
    (repo / ".afkv2").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    pages = repo / "specs" / "f" / "pages"
    pages.mkdir(parents=True)
    return save(pages / "grill-s1.json", doc)


def run_engine(*args, env=None):
    run = subprocess.run([sys.executable, str(ENGINE), *map(str, args)], capture_output=True, text=True, timeout=60,
                         encoding="utf-8", env=env)
    return run.returncode, json.loads(run.stdout)


def test_a_saved_session_reopens_to_read_and_to_continue(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    document_path = in_home(tmp_path, noted_document())
    raw_file = tmp_path / "raw.txt"
    assert run_engine("render", document_path)[0] == 0
    html_path = document_path.with_suffix(".html")
    first = html_path.read_bytes()
    assert b"note of round one" in first
    html_path.unlink()

    code, answer = run_engine("check", document_path)
    assert code == 0 and answer["saved_copy"] == "compared"
    assert run_engine("render", document_path)[0] == 0
    assert html_path.read_bytes() == first

    raw_file.write_bytes("[round R-3]\ni-c accept".encode("utf-8"))
    code, answer = run_engine("ingest", document_path, "--raw-file", raw_file)
    assert code == 0 and answer["settled_by_mark"] == ["i-c"]
    assert run_engine("check", document_path)[0] == 0
    assert run_engine("render", document_path)[0] == 0
    assert b"settled by mark" in html_path.read_bytes()


def test_an_unknown_schema_is_refused_by_ingest_with_its_version(path):
    doc = one_round(card("i-a"))
    doc["schema"] = "afkv2.page/9"
    error = refused(path, doc, "[round R-1]\ni-a accept")
    assert error["code"] == "unknown-schema" and "afkv2.page/9" in error["reason"]


def test_a_rewritten_settled_round_is_refused_before_ingest(path):
    doc = later_round(by_mark("i-old"), card("i-new"))
    engine.save_settled_copy(save(path, doc), doc)
    changed = copy.deepcopy(doc)
    item_of(changed, "i-old")["kind"] = "decided"
    assert refused(path, changed, "[round R-2]\ni-new accept")["code"] == "invariant"


# --- the page of the live browser test


LONG_WORD = "x" * 4000


def _settled_round(n):
    items = [by_mark(f"i-{n}-{c}", n) for c in range(6)]
    for c, item in enumerate(items):
        item["notes"] = [{"id": f"N-{n}-{item['id']}", "round": n, "target": item["id"],
                          "text": f"Note {c} of round {n}. " + "Long text of the note. " * 40, "deleted": c == 5}]
    round_ = round_of(n, *items, state="settled")
    round_["replies"] = [{"text": f"Reply {r} of round {n}. " + "Words of the reply. " * 30, "about": [items[r]["id"]]}
                         for r in range(3)]
    return round_


def _big_map(last_round=8):
    nodes = [node(f"n-{i}", 1 + i % last_round, ("settled", "open", "focus")[i % 3]) for i in range(40)]
    edges = [{"from": f"n-{i}", "to": f"n-{i // 2}"} for i in range(1, 40)]
    return {"type": "map", "id": "m-big", "props": {"title": "Big map", "nodes": nodes, "edges": edges}}


def _big_graph():
    nodes = [{"id": f"g-{i}", "label": f"Service {i} with a long name"} for i in range(40)]
    edges = [{"from": f"g-{i}", "to": f"g-{(i * 3 + 1) % 40}", "label": f"call {i}"} for i in range(40)]
    return {"type": "graph", "id": "d-graph", "props": {"title": "Big graph", "direction": "right", "nodes": nodes, "edges": edges}}


def _big_sequence():
    actors = [{"id": f"a-{i}", "label": f"Actor {i}"} for i in range(12)]
    messages = [{"from": f"a-{i % 12}", "to": f"a-{(i + 5) % 12}", "text": f"message {i} " + "words " * 12} for i in range(30)]
    return {"type": "sequence", "id": "d-seq", "props": {"title": "Big sequence", "actors": actors, "messages": messages}}


def _wide_table():
    columns = [f"Column {c}" for c in range(40)]
    rows = [[f"Row {r} cell {c}" for c in columns] for r in range(12)]
    rows[0][1] = LONG_WORD
    return {"type": "table", "id": "d-table", "props": {"columns": columns, "rows": rows}}


def stress_document():
    """Many notes, long text, wide tables, many rounds and big diagrams, with every element a note can target."""
    current = round_of(
        9,
        {**card("c-decided", "decided"), "body": _wide_table()},
        {**card("c-confirm", "confirm"), "body": text("Long text. " * 400 + LONG_WORD)},
        {**card("c-signoff", "signoff"), "body": text("The exact wording to sign.", id="c-signoff-words")},
        {**card("c-debate", "debate"), "body": {"type": "table", "props": {"columns": ["Option A", "Option B"], "rows": [
            [text("Keep it", id="c-debate-opt-a"), text("Drop it", id="c-debate-opt-b")]]}}},
        {**card("c-info", "info"), "body": _big_sequence()},
        {**card("c-graph", "confirm"), "body": _big_graph()},
        {**card("c-free", "confirm"), "body": {"type": "freestyle", "id": "d-free", "props": {"reason": "A wide drawing"},
                                               "html": '<svg width="1800" height="60"><text x="10" y="30">Wide fragment</text></svg>'}},
        {**card("c-note-only", "confirm"), "body": text("A card the human answers with a note only.")},
        {**card("c-spare", "confirm"), "body": text("A card the human leaves unanswered.")},
        {**card("c-held", "confirm"), "body": {"type": "map", "id": "m-held", "props": {"nodes": [node("n-held")]}}},
    )
    current["replies"] = [{"text": "The newest reply of the agent. " * 20, "about": ["c-confirm"]}]
    return document(*[_settled_round(n) for n in range(1, 9)], current, maps=[_big_map()])


def test_the_stress_page_passes_the_check_and_renders(path):
    doc = stress_document()
    assert check(save(path, doc)) == 0
    html = page.build(doc)
    assert LONG_WORD in html and html.count("<details") == 1
    notes = sum(len(i.get("notes") or []) for r in doc["rounds"] for i in r["items"])
    assert notes == 48 and len(doc["rounds"]) == 9


def diagram_document():
    """Only the diagram parts, so the host's layout audit, which reads the first 800 elements, sees them all."""
    strip = {"type": "run-strip", "id": "d-run", "props": {"current": [{"label": f"Step {i}"} for i in range(12)],
                                                           "proposed": [{"label": f"New step {i}", "detail": "Some detail " * 8, "tone": "new"}
                                                                        for i in range(8)]}}
    round_ = round_of(1, {**card("c-graph"), "body": _big_graph()}, {**card("c-seq"), "body": _big_sequence()},
                      {**card("c-run"), "body": strip})
    doc = document(round_, maps=[_big_map(1)])
    doc["session"]["id"] = "s2"
    return doc


def test_the_diagram_page_passes_the_check_and_renders(path):
    assert check(save(path, diagram_document())) == 0
    assert page.build(diagram_document())


if __name__ == "__main__":
    print(json.dumps({"stress": stress_document(), "diagrams": diagram_document()}))

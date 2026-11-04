"""Page format 1 (SDD §4, §6, §14): the schema file, the format 0 reader, the session note list, the raw
answer grammar of format 1, the refusing invariants and the home of an ad-hoc page."""

import copy
import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
for folder in (PLUGIN / "scripts", ENGINE_DIR):
    sys.path.insert(0, str(folder))

import engine  # noqa: E402

V0, V1 = "afkv2.page/0", "afkv2.page/1"


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}"), **extra}


def banner():
    return {"settled": [], "unlocks": [], "parked": []}


def round_of(n, *items, state="current", **extra):
    return {"n": n, "state": state, "banner": banner(), "items": list(items), **extra}


def v1_document(*rounds, notes=None, **session):
    return {"schema": V1,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill", **session},
            "maps": [], "notes": notes or [],
            "rounds": list(rounds) or [round_of(1, card("i-a"))]}


def save(path, doc):
    path.write_text(json.dumps(doc), "utf-8")
    return path


def call(capsys, *args):
    code = engine.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def check(capsys, tmp_path, doc):
    return call(capsys, "check", save(tmp_path / "doc.json", doc))


def refused(capsys, tmp_path, doc):
    code, answer = check(capsys, tmp_path, doc)
    assert code == 1 and answer["ok"] is False, answer
    return answer["error"]


# --- the schema file and the reader by schema value


def test_the_engine_reads_format_1_and_format_0(capsys, tmp_path):
    assert check(capsys, tmp_path, v1_document())[0] == 0
    assert set(engine.READERS) == set(engine.SCHEMA_FILES) == {V0, V1}
    schema = json.loads(engine.SCHEMA_FILES[V1].read_text("utf-8"))
    assert schema["properties"]["schema"] == {"const": V1}


@pytest.mark.parametrize("value", ["afkv2.page/2", "afkv2.page/10", 1, None])
def test_any_other_schema_value_is_refused(capsys, tmp_path, value):
    doc = v1_document()
    doc["schema"] = value
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "unknown-schema" and V0 in error["reason"] and V1 in error["reason"]


@pytest.mark.parametrize("skill", ["grill", "propose-solution", "to-subtasks", "use-lavish"])
def test_a_format_1_session_names_one_of_4_page_writers(capsys, tmp_path, skill):
    assert check(capsys, tmp_path, v1_document(skill=skill))[0] == 0


def test_a_format_1_session_holds_the_new_fields(capsys, tmp_path):
    doc = v1_document(short_title="x" * 40, step="y" * 40, private=True,
                      takeovers=[{"round": 1, "at": "2026-01-06T10:00:00Z"}])
    assert check(capsys, tmp_path, doc)[0] == 0
    no_ticket = v1_document()
    del no_ticket["session"]["ticket"]
    assert check(capsys, tmp_path, no_ticket)[0] == 0
    assert check(capsys, tmp_path, v1_document(ticket=None, short_title=None))[0] == 0


@pytest.mark.parametrize("change, field", [
    (lambda s: s.update(skill="propose-verification"), "skill"),
    (lambda s: s.update(short_title="x" * 41), "short_title"),
    (lambda s: s.update(step="y" * 41), "step"),
    (lambda s: s.pop("step"), "step"),
    (lambda s: s.update(private="no"), "private"),
    (lambda s: s.update(takeovers=[{"round": 1}]), "takeovers[0].at"),
    (lambda s: s.update(takeovers=[{"round": 0, "at": "2026-01-06T10:00:00Z"}]), "takeovers[0].round"),
])
def test_a_bad_session_field_is_refused(capsys, tmp_path, change, field):
    doc = v1_document()
    change(doc["session"])
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "schema" and f"field {field}" in error["reason"]


def test_a_component_tip_holds_at_most_300_characters(capsys, tmp_path):
    doc = v1_document(round_of(1, card("i-a", body=text("Body", tip="t" * 300))))
    assert check(capsys, tmp_path, doc)[0] == 0
    doc["rounds"][0]["items"][0]["body"]["tip"] = "t" * 301
    assert "field body.tip" in refused(capsys, tmp_path, doc)["reason"]


def test_value_sets_name_their_values_and_order(capsys, tmp_path):
    doc = v1_document()
    doc["value_sets"] = {"risk": {"values": ["low", "high"], "ordered": True}}
    assert check(capsys, tmp_path, doc)[0] == 0
    doc["value_sets"]["size"] = {"values": "small", "ordered": False}
    assert "field value_sets.size.values" in refused(capsys, tmp_path, doc)["reason"]


def test_a_note_quote_holds_at_most_300_characters(capsys, tmp_path):
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "item": "i-a", "quote": "q" * 300, "text": "why",
            "deleted": False}
    assert check(capsys, tmp_path, v1_document(notes=[note]))[0] == 0
    note["quote"] = "q" * 301
    assert "field notes[0].quote" in refused(capsys, tmp_path, v1_document(notes=[note]))["reason"]


def test_a_round_and_an_answer_hold_their_change_lists(capsys, tmp_path):
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "item": "i-a", "text": "why", "deleted": False}
    answer = {"id": "A-1-1", "text": "Because.", "notes": ["N-1-i-a-1"], "changed": ["i-a"]}
    doc = v1_document(round_of(1, card("i-a"), replies=[answer], changed=["i-a"]), notes=[note])
    assert check(capsys, tmp_path, doc)[0] == 0

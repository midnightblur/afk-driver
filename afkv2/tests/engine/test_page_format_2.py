"""Page format 2 (SDD §4, §5, §6, §14): the schema file with sections, stories, examples and questions for
others, the changed card, note and reply shapes, the document checks that guard them, and the reader."""

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
import registry  # noqa: E402
from schema import invariants  # noqa: E402

V2 = "afkv2.page/2"
STORED_PAGES = [FIXTURES / "v0-page-with-notes.json", FIXTURES / "v0-sdd-pass.json",
                PLUGIN / "skills" / "visualize" / "examples" / "all-components.json",
                PLUGIN / "skills" / "visualize" / "examples" / "page-owned-tips.json"]


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def card(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}"), **extra}


def accepted(item_id, n=1):
    return card(item_id, state="settled_by_mark", settled={"by": "mark", "round": n, "signal": "accept"})


def round_of(n, *items, state="current", **extra):
    return {"n": n, "state": state, "banner": {"settled": [], "unlocks": [], "parked": []}, "items": list(items),
            **extra}


def note(note_id, n, target, item=None, deleted=False):
    return {"id": note_id, "round": n, "target": target, "item": item, "text": "words", "deleted": deleted}


def line(n=1, cause="finding", text_="Wrote the part.", **extra):
    return {"round": n, "cause": cause, "text": text_, **extra}


def section(section_id, state="current", **extra):
    return {"id": section_id, "title": f"Part {section_id}", "state": state, "body": text(f"Text of {section_id}"),
            "changes": [line()], **extra}


def question(question_id, state="open", **extra):
    return {"id": question_id, "who": ["product owner"], "question": "Which formats?", "context": "The export.",
            "why": "It sets the scope.", "origin": {"card": "i-a"}, "state": state, "changes": [line()], **extra}


def answer(signal="N-1-q-ans-1", n=1, role="tester"):
    return {"text": "CSV.", "choices": [], "role": role, "date": "2026-11-06", "signal": signal, "round": n}


def v2_document():
    """A valid version 2 page: each list filled, each question state present, one round."""
    sections = [section("s-intro", links=["s-rules"]), section("s-rules"),
                section("s-old", state="merged", merged_into="s-intro"),
                section("s-gone", state="removed", reason="Out of scope."),
                section("s-later", state="not_reached", changes=[])]
    stories = [{"id": "st-1", "text": "As a user, I export.", "changes": [line()]}]
    examples = [{"id": "ex-1", "title": "A plain export", "kind": "frequent", "stories": ["st-1"],
                 "body": text("From 3 rows to 1 file."), "changes": [line()]}]
    questions = [
        question("q-open", links=["s-intro"],
                 choices={"options": [{"id": "csv", "text": "CSV"}, {"id": "xls", "text": "Excel"}], "several": True}),
        question("q-ans", state="answered", answer=answer(), waits_on="q-open"),
        question("q-drop", state="dropped", dropped={"reason": "Not needed.", "note": "N-1-q-drop-1", "round": 1}),
        question("q-assume", state="assumed", assumption={"text": "CSV only.", "card": "i-assume", "round": 1}),
    ]
    notes = [note("N-1-q-ans-1", 1, "q-ans", "q-ans"), note("N-1-q-drop-1", 1, "q-drop", "q-drop"),
             note("N-1-s-intro-1", 1, "s-intro", "s-intro")]
    return {"schema": V2,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
            "maps": [], "notes": notes, "sections": sections, "stories": stories, "examples": examples,
            "questions": questions,
            "rounds": [round_of(1, card("i-a", section="s-intro"), accepted("i-assume"),
                                replies=[{"id": "A-1-1", "text": "Done.", "notes": ["N-1-s-intro-1"]}])]}


def entry(doc, kind, entry_id):
    return next(e for e in doc[kind] if e["id"] == entry_id)


def save(path, doc):
    path.write_text(json.dumps(doc), "utf-8")
    return path


def call(capsys, *args):
    code = engine.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def check(capsys, tmp_path, doc):
    return call(capsys, "check", save(tmp_path / "doc.json", doc))


def refused(capsys, tmp_path, doc, code=None):
    status, result = check(capsys, tmp_path, doc)
    assert status == 1 and result["ok"] is False, result
    if code is not None:
        assert result["error"]["code"] == code, result
    return result["error"]


# --- the schema file, the reader and the newest value


def test_a_valid_version_2_page_passes_check(capsys, tmp_path):
    code, result = check(capsys, tmp_path, v2_document())
    assert code == 0, result


def test_the_engine_keeps_a_reader_and_a_schema_file_for_0_1_and_2():
    assert engine.SCHEMA_V2 == registry.NEWEST_SCHEMA == V2
    assert {"afkv2.page/0", "afkv2.page/1", V2} <= set(engine.READERS) == set(engine.SCHEMA_FILES)
    schema = json.loads(engine.SCHEMA_FILES[V2].read_text("utf-8"))
    assert schema["properties"]["schema"] == {"const": V2}


@pytest.mark.parametrize("value", ["afkv2.page/3", "afkv2.page/20", 2, None])
def test_an_unknown_schema_value_is_refused_by_name(capsys, tmp_path, value):
    doc = v2_document()
    doc["schema"] = value
    error = refused(capsys, tmp_path, doc, "unknown-schema")
    assert repr(value) in error["reason"] and V2 in error["reason"]


@pytest.mark.parametrize("path", STORED_PAGES, ids=lambda p: p.name)
def test_every_stored_version_0_and_1_page_still_passes_check_unchanged(capsys, tmp_path, path):
    target = tmp_path / path.name
    target.write_bytes(path.read_bytes())
    code, result = call(capsys, "check", target)
    assert code == 0, result
    assert target.read_bytes() == path.read_bytes()


def test_a_version_1_page_refuses_the_version_2_lists(capsys, tmp_path):
    doc = v2_document()
    doc["schema"] = "afkv2.page/1"
    for kind in ("sections", "stories", "examples", "questions"):
        doc.pop(kind)
    doc["rounds"][0]["items"][0]["section"] = "s-intro"
    refused(capsys, tmp_path, doc, "schema")


# --- questions for others


def test_a_question_with_no_one_to_ask_is_refused(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-open")["who"] = []
    refused(capsys, tmp_path, doc, "schema")


@pytest.mark.parametrize("role", ["everyone", "Everyone", "EVERYONE"])
def test_an_answer_from_everyone_is_refused(capsys, tmp_path, role):
    doc = v2_document()
    entry(doc, "questions", "q-ans")["answer"]["role"] = role
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "everyone-answered" in error["reason"]


def test_everyone_may_be_asked(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-open")["who"] = ["everyone"]
    assert check(capsys, tmp_path, doc)[0] == 0


@pytest.mark.parametrize("reason", ["", "   "])
def test_a_drop_with_no_reason_is_refused(capsys, tmp_path, reason):
    doc = v2_document()
    entry(doc, "questions", "q-drop")["dropped"]["reason"] = reason
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "drop-no-reason" in error["reason"]


@pytest.mark.parametrize("card_state", ["open", "needs_reading", "note", "missing", "write-in"])
def test_an_assumption_without_a_card_settled_by_accept_is_refused(capsys, tmp_path, card_state):
    doc = v2_document()
    items = doc["rounds"][0]["items"]
    if card_state == "missing":
        entry(doc, "questions", "q-assume")["assumption"]["card"] = "i-none"
    elif card_state == "note":
        doc["notes"].append(note("N-1-i-assume-1", 1, "i-assume", "i-assume"))
        items[1] = card("i-assume", state="settled_by_note",
                        settled={"by": "note", "round": 1, "signal": "N-1-i-assume-1", "reading": "Yes."})
    elif card_state == "write-in":
        items[1]["settled"]["signal"] = "a"
    else:
        items[1] = card("i-assume", state=card_state)
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "assume-no-card" in error["reason"]


def test_an_assumption_stays_after_its_answer(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-assume").update(state="answered", answer=answer())
    assert check(capsys, tmp_path, doc)[0] == 0


@pytest.mark.parametrize("change", ["no-note", "other-round", "deleted", "no-tick"])
def test_an_answer_without_the_developers_signal_of_its_round_is_refused(capsys, tmp_path, change):
    doc = v2_document()
    given = entry(doc, "questions", "q-ans")["answer"]
    if change == "no-note":
        given["signal"] = "N-1-q-none-1"
    elif change == "other-round":
        given["round"] = 2
        doc["rounds"] = [round_of(1, state="settled"), round_of(2, *doc["rounds"][0]["items"])]
    elif change == "deleted":
        doc["notes"][0]["deleted"] = True
    else:
        given["signal"] = "tick"
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "answer-no-signal" in error["reason"]


def test_an_answer_may_rest_on_the_developers_tick_of_its_round(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-ans")["answer"].update(signal="tick", choices=["csv"])
    entry(doc, "questions", "q-ans")["choices"] = {"options": [{"id": "csv", "text": "CSV"},
                                                                 {"id": "xls", "text": "Excel"}], "several": False}
    raw = "[round R-1]\nq-ans tick csv"
    signal = {"target": "q-ans", "item": None, "mark": "tick", "choices": ["csv"]}
    signal["stamp"] = invariants.ingest_stamp("s1", 1, "2026-11-06T10:00:00Z", raw, signal)
    doc["rounds"][0]["responses"] = [{"received": "2026-11-06T10:00:00Z", "raw": raw, "signals": [signal]}]
    code, result = check(capsys, tmp_path, doc)
    assert code == 0, result


@pytest.mark.parametrize("state, field", [("answered", "answer"), ("dropped", "dropped"),
                                          ("assumed", "assumption")])
def test_a_closed_question_holds_what_closed_it(capsys, tmp_path, state, field):
    doc = v2_document()
    entry(doc, "questions", "q-open")["state"] = state
    error = refused(capsys, tmp_path, doc, "invariant")
    assert f"field {field}: is required when the state is {state}" in error["reason"]


def test_an_open_question_holds_no_answer(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-open")["answer"] = answer()
    assert "a question in state open holds no answer" in refused(capsys, tmp_path, doc, "invariant")["reason"]


def test_a_question_waits_only_on_an_earlier_question(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-open")["waits_on"] = "q-ans"
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "field waits_on: 'q-ans' is no question earlier in the list" in error["reason"]


def test_a_question_link_to_no_section_is_refused(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "questions", "q-open")["links"] = ["s-none"]
    refused(capsys, tmp_path, doc, "bad-link")


# --- sections and the saved copy


def test_a_section_links_only_other_sections(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "sections", "s-intro")["links"] = ["s-intro"]
    assert "a section never links itself" in refused(capsys, tmp_path, doc, "invariant")["reason"]


def test_a_section_merges_only_into_a_current_section(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "sections", "s-old")["merged_into"] = "s-gone"
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "must name a current section, found 's-gone'" in error["reason"]


def test_a_removed_section_holds_its_reason(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "sections", "s-gone").pop("reason")
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "section s-gone, field reason: is required when the state is removed" in error["reason"]


def test_change_lines_hold_at_most_1_line_per_round_and_never_go_down(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "sections", "s-intro")["changes"] = [line(), line()]
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "round 1 follows round 1; rounds go up" in error["reason"]


def two_rounds():
    doc = v2_document()
    doc["rounds"] = [round_of(1, *doc["rounds"][0]["items"], state="settled",
                              replies=doc["rounds"][0]["replies"]), round_of(2)]
    return doc


@pytest.mark.parametrize("lines, why", [
    ([line(2), line(1)], "changes[1].round: round 1 follows round 2; rounds go up"),
    ([line(3)], "changes[0].round: round 3 does not exist"),
    ([line(cause="answer")], "changes[0].card: is required when the cause is answer"),
    ([line(cause="answer_from")], "changes[0].question: is required when the cause is answer_from"),
    ([line(cause="answer_from", question="q-open")], "changes[0].question: 'q-open' is not answered"),
], ids=["down", "no-such-round", "answer-no-card", "answer-from-no-question", "unanswered-question"])
def test_a_change_line_is_refused_for_each_broken_rule(capsys, tmp_path, lines, why):
    doc = two_rounds()
    entry(doc, "sections", "s-intro")["changes"] = lines
    assert why in refused(capsys, tmp_path, doc, "invariant")["reason"]


def test_a_change_line_from_an_answered_question_passes(capsys, tmp_path):
    doc = two_rounds()
    entry(doc, "sections", "s-intro")["changes"] = [line(), line(2, cause="answer_from", question="q-ans")]
    code, result = check(capsys, tmp_path, doc)
    assert code == 0, result


def test_a_change_line_by_note_names_a_note(capsys, tmp_path):
    doc = v2_document()
    entry(doc, "sections", "s-intro")["changes"] = [line(cause="note")]
    refused(capsys, tmp_path, doc, "invariant")
    entry(doc, "sections", "s-intro")["changes"] = [line(cause="note", notes=["N-1-none"])]
    refused(capsys, tmp_path, doc, "bad-link")
    entry(doc, "sections", "s-intro")["changes"] = [line(cause="note", notes=["N-1-s-intro-1"])]
    assert check(capsys, tmp_path, doc)[0] == 0


def saved_then(capsys, tmp_path, change):
    """Save the copy of a 2-round page whose round 1 settled, apply `change`, and check again."""
    doc = v2_document()
    doc["rounds"] = [round_of(1, *doc["rounds"][0]["items"], state="settled",
                              replies=doc["rounds"][0]["replies"]), round_of(2)]
    path = save(tmp_path / "doc.json", doc)
    assert call(capsys, "check", path)[0] == 0
    engine.save_settled_copy(path, doc)
    later = copy.deepcopy(doc)
    change(later)
    return call(capsys, "check", save(path, later))


def test_a_change_line_of_a_settled_round_that_differs_from_the_saved_copy_is_refused(capsys, tmp_path):
    def rewrite(doc):
        entry(doc, "sections", "s-intro")["changes"][0]["text"] = "Wrote it otherwise."
    code, result = saved_then(capsys, tmp_path, rewrite)
    assert code == 1 and result["error"]["code"] == "invariant", result
    assert "s-intro" in result["error"]["reason"] and "round 1" in result["error"]["reason"]


def test_a_change_line_added_to_a_settled_round_with_no_lines_is_refused(capsys, tmp_path):
    doc = v2_document()
    doc["rounds"] = [round_of(1, *doc["rounds"][0]["items"], state="settled", replies=doc["rounds"][0]["replies"]),
                     round_of(2, state="settled"), round_of(3)]
    path = save(tmp_path / "doc.json", doc)
    assert call(capsys, "check", path)[0] == 0
    engine.save_settled_copy(path, doc)
    entry(doc, "stories", "st-1")["changes"].append(line(2, text_="Added late."))
    code, result = call(capsys, "check", save(path, doc))
    assert code == 1 and result["error"]["code"] == "invariant", result
    assert "st-1" in result["error"]["reason"] and "settled round 2" in result["error"]["reason"]


def test_a_new_change_line_of_the_current_round_passes_against_the_saved_copy(capsys, tmp_path):
    def grow(doc):
        entry(doc, "sections", "s-intro")["changes"].append(line(2, text_="Grew."))
        entry(doc, "sections", "s-intro")["body"] = text("New text.")
    code, result = saved_then(capsys, tmp_path, grow)
    assert code == 0 and result["saved_copy"] == "compared", result


@pytest.mark.parametrize("closed", ["s-old", "s-gone"])
def test_a_merged_or_removed_section_never_returns_to_current(capsys, tmp_path, closed):
    def reopen(doc):
        part = entry(doc, "sections", closed)
        part["state"] = "current"
        part.pop("merged_into", None)
        part.pop("reason", None)
    code, result = saved_then(capsys, tmp_path, reopen)
    assert code == 1 and result["error"]["code"] == "invariant", result
    assert closed in result["error"]["reason"]


# --- worked examples


@pytest.mark.parametrize("kind", ["rare", "Frequent", ""])
def test_an_example_of_another_kind_is_refused(capsys, tmp_path, kind):
    doc = v2_document()
    doc["examples"][0]["kind"] = kind
    refused(capsys, tmp_path, doc, "schema")


def test_an_example_that_covers_no_story_is_refused(capsys, tmp_path):
    doc = v2_document()
    doc["examples"][0]["stories"] = []
    refused(capsys, tmp_path, doc, "schema")
    doc["examples"][0]["stories"] = ["st-none"]
    refused(capsys, tmp_path, doc, "bad-link")


# --- cards, notes and replies


def test_a_note_on_a_section_is_owned_by_that_section(capsys, tmp_path):
    doc = v2_document()
    doc["notes"].append(note("N-1-ex-1-1", 1, "ex-1", "ex-1"))
    assert check(capsys, tmp_path, doc)[0] == 0


def test_a_card_names_only_a_real_section(capsys, tmp_path):
    doc = v2_document()
    doc["rounds"][0]["items"][0]["section"] = "s-none"
    refused(capsys, tmp_path, doc, "bad-link")


def test_a_reply_that_names_2_notes_is_refused_on_a_version_2_page(capsys, tmp_path):
    doc = v2_document()
    doc["rounds"][0]["replies"][0]["notes"] = ["N-1-s-intro-1", "N-1-q-ans-1"]
    error = refused(capsys, tmp_path, doc, "invariant")
    assert "reply-many-notes" in error["reason"]


def test_a_reply_that_names_2_notes_passes_on_a_version_1_page(capsys, tmp_path):
    doc = v2_document()
    doc["schema"] = "afkv2.page/1"
    for kind in ("sections", "stories", "examples", "questions"):
        doc.pop(kind)
    doc["rounds"][0]["items"][0].pop("section")
    doc["notes"] = [note("N-1-i-a-1", 1, "i-a", "i-a"), note("N-1-i-assume-1", 1, "i-assume", "i-assume")]
    doc["rounds"][0]["replies"] = [{"id": "A-1-1", "text": "Both.", "notes": ["N-1-i-a-1", "N-1-i-assume-1"]}]
    code, result = check(capsys, tmp_path, doc)
    assert code == 0, result


def an_upgraded_page(upgraded=None):
    """Round 1 is a settled round of the old format with a reply that names 2 notes; round 2 is current."""
    doc = v2_document()
    doc["notes"].append(note("N-1-i-a-1", 1, "i-a", "i-a"))
    doc["rounds"][0]["state"] = "settled"
    doc["rounds"][0]["replies"].append({"id": "A-1-2", "text": "Both.", "notes": ["N-1-i-a-1", "N-1-s-intro-1"]})
    doc["rounds"].append(round_of(2, card("i-b")))
    if upgraded is not None:
        doc["session"]["upgraded"] = upgraded
    return doc


def test_an_upgraded_page_checks_the_1_note_rule_only_from_its_first_version_2_round(capsys, tmp_path):
    code, result = check(capsys, tmp_path, an_upgraded_page(upgraded=2))
    assert code == 0, result
    doc = an_upgraded_page(upgraded=2)
    doc["notes"].append(note("N-2-i-b-1", 2, "i-b", "i-b"))
    doc["rounds"][1]["replies"] = [{"id": "A-2-1", "text": "Both.", "notes": ["N-2-i-b-1", "N-1-i-a-1"]}]
    assert "reply-many-notes" in refused(capsys, tmp_path, doc, "invariant")["reason"]


@pytest.mark.parametrize("upgraded", [None, 1])
def test_a_page_not_upgraded_after_the_reply_checks_the_1_note_rule_on_every_round(capsys, tmp_path, upgraded):
    error = refused(capsys, tmp_path, an_upgraded_page(upgraded), "invariant")
    assert "reply-many-notes" in error["reason"]


@pytest.mark.parametrize("value", [0, "2", None])
def test_upgraded_is_a_round_number(capsys, tmp_path, value):
    doc = an_upgraded_page(upgraded=2)
    doc["session"]["upgraded"] = value
    refused(capsys, tmp_path, doc, "schema")


def test_entry_ids_are_unique_in_the_document(capsys, tmp_path):
    doc = v2_document()
    doc["stories"][0]["id"] = "s-intro"
    assert "id 's-intro' is not unique" in refused(capsys, tmp_path, doc, "invariant")["reason"]

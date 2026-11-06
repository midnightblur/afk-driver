"""The round builder and the reading tool on a version 2 page (SDD §3 rows "round builder `build`" and "reading
tool `apply-readings`", §4 Migration and backfill, §14 rows "Builder's version" and "Reply for a card's notes")."""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for _folder in (PLUGIN / "skills" / "use-lavish" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import engine  # noqa: E402
import page_round  # noqa: E402
import round_document as rd  # noqa: E402
from grill_common import Refusal  # noqa: E402

V1, V2 = "afkv2.page/1", "afkv2.page/2"
SESSION = {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1"}


def card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "body": {"type": "text", "id": f"{item_id}-body", "props": {"text": "x"}},
            **extra}


def round_input(*item_ids, **extra):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": [card(i) for i in item_ids], **extra}


def options(*ids, several=False):
    return {"options": [{"id": option, "text": f"Option {option}"} for option in ids], "several": several}


def question(question_id, **extra):
    return {"id": question_id, "who": ["product owner"], "question": "Which formats?", "context": "The export.",
            "why": "It sets the scope.", "origin": {"card": "i-a"}, "state": "open", **extra}


def read(path):
    return json.loads(Path(path).read_text("utf-8"))


def write(path, doc):
    Path(path).write_text(json.dumps(doc), "utf-8")


def check(path):
    out = []
    original = print
    try:
        engine.print = out.append
        code = engine.main(["check", str(path)])
    finally:
        engine.print = original
    return code, json.loads(out[0])


def ingest(path, raw):
    raw_file = Path(path).with_name("raw.txt")
    raw_file.write_text(raw, "utf-8")
    return page_round.ingest(path, raw_file)


def as_version_2(path, **lists):
    """Rewrite a built version 1 page as the version 2 page of the same session, with the given lists."""
    doc = read(path)
    doc["schema"] = V2
    doc.update(lists)
    write(path, doc)
    assert check(path)[0] == 0, check(path)


@pytest.fixture
def path(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    return tmp_path / "pages" / "grill-s-1.json"


def settled_round_1(path, *more):
    """Round 1 settles card i-a by an accept mark; round 2 is current with the cards `more`."""
    rd.build_round_document(path, SESSION, round_input("i-a"))
    ingest(path, "[round R-1]\ni-a accept")
    rd.build_round_document(path, SESSION, round_input(*more))


# ---- ingest passes on what the agent must read (decision D-9)


def test_ingest_passes_on_the_questions_and_the_settled_notes_to_read_on_a_version_2_page(path):
    settled_round_1(path, "i-b")
    line = {"round": 1, "cause": "finding", "text": "Asked."}
    as_version_2(path, questions=[{**question("q-one", choices=options("csv", "xls")), "changes": [line]}])
    answer = ingest(path, "[round R-2]\ni-a note 1\n  Fine as it is.\nq-one tick csv")
    assert [signal["target"] for signal in answer["questions_to_read"]] == ["q-one"]
    assert answer["questions_to_read"][0]["choices"] == ["csv"]
    assert answer["settled_notes_to_read"] == ["N-2-i-a-1"]


def test_ingest_on_a_version_1_page_answers_as_before(path):
    settled_round_1(path, "i-b")
    answer = ingest(path, "[round R-2]\ni-b accept")
    assert "questions_to_read" not in answer and "settled_notes_to_read" not in answer


# ---- the builder writes the page's own version (SDD §14 row "Builder's version")

import page_home  # noqa: E402


def test_a_version_2_page_stays_version_2_at_its_next_write(path):
    settled_round_1(path, "i-b")
    as_version_2(path)
    ingest(path, "[round R-2]\ni-b accept")
    rd.build_round_document(path, SESSION, round_input("i-c"))
    assert read(path)["schema"] == V2
    assert check(path)[0] == 0


def test_a_version_1_page_stays_version_1_at_its_next_write(path):
    settled_round_1(path, "i-b")
    assert read(path)["schema"] == V1


def test_take_over_and_track_keep_a_version_2_page(path, tmp_path, monkeypatch):
    settled_round_1(path, "i-b")
    as_version_2(path)
    assert page_round.take_over(path)["round"] == 2
    assert read(path)["schema"] == V2
    monkeypatch.setattr(page_home, "_spec_pages", lambda ticket: tmp_path / "spec" / "pages")
    tracked = page_home.track_page(str(path), "PROJ-1")
    assert read(tracked["doc"])["schema"] == V2


# ---- the 4 lists merge by id: only the entries that changed, each with 1 change line (SDD §3 row "build")

FINDING = {"cause": "finding", "text": "Wrote the part."}


def section(section_id, text="Text.", **extra):
    return {"id": section_id, "title": f"Title of {section_id}", "state": "current",
            "body": {"type": "text", "id": f"{section_id}-text", "props": {"text": text}}, **extra}


def entries_round(*items, **lists):
    """A round input with the given lists; each entry carries `change` unless it holds one already."""
    sent = {kind: [{"change": FINDING, **entry} for entry in value] for kind, value in lists.items()}
    return round_input(*items, **sent)


@pytest.fixture
def page(path):
    """A version 2 page: round 1 settled card i-a by an accept mark, round 2 current with i-b, sent."""
    settled_round_1(path, "i-b")
    as_version_2(path)
    ingest(path, "[round R-2]\ni-b accept")
    return path


def next_round(path, item, raw=None, **lists):
    answer = rd.build_round_document(path, SESSION, entries_round(item, **lists))
    assert check(path)[0] == 0, check(path)
    if raw is not None:
        ingest(path, raw)
    return answer


def test_a_new_entry_of_each_list_is_stored_with_1_change_line_of_the_round(page):
    story = {"id": "st-1", "text": "As a user, I export."}
    example = {"id": "ex-1", "title": "A plain export", "kind": "frequent", "stories": ["st-1"],
               "body": {"type": "text", "props": {"text": "From 3 rows to 1 file."}}}
    answer = next_round(page, "i-c", sections=[section("s-intro")], stories=[story], examples=[example],
                        questions=[question("q-one")])
    doc = read(page)
    assert answer["entries"] == ["s-intro", "st-1", "ex-1", "q-one"]
    for kind, sent in (("sections", section("s-intro")), ("stories", story), ("examples", example),
                       ("questions", question("q-one"))):
        assert doc[kind] == [{**sent, "changes": [{"round": 3, **FINDING}]}], kind


def test_a_section_left_out_keeps_its_text_exactly_and_gains_no_change_line(page):
    next_round(page, "i-c", "[round R-3]\ni-c accept", sections=[section("s-intro"), section("s-scope")])
    before = read(page)["sections"]
    next_round(page, "i-d", sections=[section("s-scope", "New text.")])
    after = read(page)["sections"]
    assert after[0] == before[0]
    assert after[1]["body"]["props"]["text"] == "New text."
    assert after[1]["changes"] == [{"round": 3, **FINDING}, {"round": 4, **FINDING}]


def test_a_section_sent_with_the_same_text_is_refused_and_nothing_is_written(page):
    next_round(page, "i-c", "[round R-3]\ni-c accept", sections=[section("s-intro")])
    before = page.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(page, SESSION, entries_round("i-d", sections=[section("s-intro")]))
    assert refused.value.code == "unchanged-entry" and "s-intro" in refused.value.reason
    assert page.read_bytes() == before


@pytest.mark.parametrize("change", [None, [FINDING, FINDING], {**FINDING, "round": 2}])
def test_a_changed_entry_without_exactly_1_change_line_for_the_round_is_refused(page, change):
    entry = section("s-intro") if change is None else {**section("s-intro"), "change": change}
    sent = round_input("i-c", sections=[entry])
    before = page.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(page, SESSION, sent)
    assert refused.value.code == "no-change-line" and "s-intro" in refused.value.reason
    assert page.read_bytes() == before


def test_an_entry_that_sends_its_own_change_list_is_refused(page):
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(page, SESSION, entries_round("i-c", sections=[{**section("s-intro"), "changes": []}]))
    assert refused.value.code == "bad-entry"


def test_a_question_sent_with_after_lands_right_after_the_named_question(page):
    next_round(page, "i-c", "[round R-3]\ni-c accept", questions=[question("q-1"), question("q-2")])
    next_round(page, "i-d", questions=[{**question("q-3"), "after": "q-1"}])
    assert [q["id"] for q in read(page)["questions"]] == ["q-1", "q-3", "q-2"]
    assert all("after" not in q for q in read(page)["questions"])


def test_a_question_moved_by_after_holds_its_new_place(page):
    next_round(page, "i-c", "[round R-3]\ni-c accept", questions=[question("q-1"), question("q-2"), question("q-3")])
    next_round(page, "i-d", questions=[{**question("q-3"), "after": "q-1"}])
    doc = read(page)
    assert [q["id"] for q in doc["questions"]] == ["q-1", "q-3", "q-2"]
    assert doc["questions"][1]["changes"] == [{"round": 3, **FINDING}, {"round": 4, **FINDING}]


@pytest.mark.parametrize("after", ["q-none", "q-1"])
def test_after_that_names_no_other_question_is_refused(page, after):
    next_round(page, "i-c", "[round R-3]\ni-c accept", questions=[question("q-1")])
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(page, SESSION, entries_round("i-d", questions=[{**question("q-1", why="New."),
                                                                                 "after": after}]))
    assert refused.value.code == "bad-entry" and after in refused.value.reason


def test_a_card_names_its_section_on_a_version_2_page(page):
    rd.build_round_document(page, SESSION, round_input(sections=[{**section("s-intro"), "change": FINDING}],
                                                       items=[card("i-c", section="s-intro")]))
    assert read(page)["rounds"][-1]["items"][0]["section"] == "s-intro"
    assert check(page)[0] == 0


def test_a_version_1_page_refuses_the_version_2_fields_by_name(path):
    settled_round_1(path, "i-b")
    ingest(path, "[round R-2]\ni-b accept")
    before = path.read_bytes()
    for sent, field in ((entries_round("i-c", sections=[section("s-intro")]), "sections"),
                        (entries_round("i-c", questions=[question("q-1")]), "questions"),
                        (round_input(items=[card("i-c", section="s-intro")]), "section")):
        with pytest.raises(Refusal) as refused:
            rd.build_round_document(path, SESSION, sent)
        assert field in refused.value.reason
        assert path.read_bytes() == before


def test_a_build_the_document_check_refuses_is_refused_by_its_rule_and_writes_nothing(page):
    answered = question("q-1", state="answered", answer={"text": "Yes.", "choices": [], "role": "Everyone",
                                                          "date": "2026-11-06", "signal": "tick", "round": 2})
    before = page.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(page, SESSION, entries_round("i-c", questions=[answered]))
    assert refused.value.code == "everyone-answered"
    assert page.read_bytes() == before


# ---- 1 reply per note on version 2 (SDD §14 row "Reply for a card's notes"; §6 "Each note gets its own reply")

TWO_NOTES = "[round R-3]\ni-c note 1\n  Why this one?\ni-c note 2\n  And how?"


@pytest.fixture
def noted(page):
    """Round 3 current with card i-c, which holds 2 notes of round 3 and needs reading."""
    next_round(page, "i-c", TWO_NOTES)
    return page


def replies_of(path, n):
    return read(path)["rounds"][n - 1].get("replies") or []


@pytest.mark.parametrize("where", ["readings", "round input"])
def test_a_reply_that_names_2_notes_on_a_version_2_page_is_refused(noted, where):
    reply = {"text": "Both at once.", "notes": ["N-3-i-c-1", "N-3-i-c-2"]}
    before = noted.read_bytes()
    with pytest.raises(Refusal) as refused:
        if where == "readings":
            rd.apply_readings(noted, {"replies": [reply]})
        else:
            rd.apply_readings(noted, {"open": [{"item": "i-c", "reply": "Asked again."}]})
            before = noted.read_bytes()
            rd.build_round_document(noted, SESSION, round_input(items=[card("i-d", carries=["i-c"])],
                                                                replies=[reply]))
    assert refused.value.code == "reply-many-notes"
    assert "N-3-i-c-1" in refused.value.reason and "N-3-i-c-2" in refused.value.reason
    assert noted.read_bytes() == before


def test_open_on_a_version_2_page_names_only_the_note_its_reply_answers(noted):
    rd.apply_readings(noted, {"open": [{"item": "i-c", "reply": "It returns: the why needs a picture.",
                                        "note": "N-3-i-c-1"}],
                              "replies": [{"text": "The how comes in the next card.", "notes": ["N-3-i-c-2"]}]})
    assert [reply.get("notes") for reply in replies_of(noted, 3)] == [["N-3-i-c-1"], ["N-3-i-c-2"]]
    assert check(noted)[0] == 0


def test_open_on_a_version_2_page_with_no_note_names_none(noted):
    rd.apply_readings(noted, {"open": [{"item": "i-c", "reply": "It returns."}]})
    assert replies_of(noted, 3) == [{"id": "A-3-1", "text": "It returns."}]


def test_open_with_a_note_of_another_card_is_refused(noted):
    with pytest.raises(Refusal) as refused:
        rd.apply_readings(noted, {"open": [{"item": "i-c", "reply": "It returns.", "note": "N-1-i-a-1"}]})
    assert refused.value.code == "no-note"


def test_a_note_with_no_reply_refuses_the_next_round_on_version_2_by_its_id(noted):
    rd.apply_readings(noted, {"open": [{"item": "i-c", "reply": "It returns.", "note": "N-3-i-c-1"}]})
    before = noted.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(noted, SESSION, round_input("i-d", items=[card("i-d", carries=["i-c"])]))
    assert refused.value.code == "unanswered-note" and "N-3-i-c-2" in refused.value.reason
    assert "N-3-i-c-1" not in refused.value.reason
    assert noted.read_bytes() == before
    rd.build_round_document(noted, SESSION, round_input(items=[card("i-d", carries=["i-c"])],
                                                        replies=[{"text": "Asked in the next card.",
                                                                  "notes": ["N-3-i-c-2"]}]))
    assert check(noted)[0] == 0

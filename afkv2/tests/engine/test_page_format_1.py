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
    assert set(engine.READERS) == set(engine.SCHEMA_FILES) == {V0, V1, "afkv2.page/2"}
    schema = json.loads(engine.SCHEMA_FILES[V1].read_text("utf-8"))
    assert schema["properties"]["schema"] == {"const": V1}


@pytest.mark.parametrize("value", ["afkv2.page/3", "afkv2.page/10", 1, None])
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


# --- the format 0 reader: format 1 in memory, the file never rewritten


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    (root / "specs" / "feature" / "pages").mkdir(parents=True)
    return root


def v0_document():
    """A format 0 page with notes in both id forms, a steer, an answer with only `about` and a settled round."""
    old = card("i-old", state="settled_by_note",
               settled={"by": "note", "round": 1, "signal": "N-1-i-old", "reading": "Yes."},
               notes=[{"id": "N-1-i-old", "round": 1, "target": "i-old", "text": 'why (on: "a b")', "deleted": False},
                      {"id": "N-2-i-old-1", "round": 2, "target": "i-old", "text": "late", "deleted": False}])
    new = card("i-new", notes=[{"id": "N-2-i-new-1", "round": 2, "target": "i-new", "text": "one", "deleted": False},
                               {"id": "N-2-i-new-2", "round": 2, "target": "i-new", "text": "two", "deleted": True}])
    steer = {"id": "N-2-R-2-1", "round": 2, "target": "R-2", "text": "steer", "deleted": False}
    return {"schema": V0,
            "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                        "started": "2026-01-05T09:00:00Z"},
            "rounds": [round_of(1, old, state="settled", replies=[{"text": "Read.", "about": ["i-old"]}]),
                       round_of(2, new, notes=[steer], replies=[{"text": "Ok.", "about": ["N-2-R-2-1"]}])]}


def test_the_reader_moves_card_notes_and_steers_into_the_session_list():
    raw = v0_document()
    before = copy.deepcopy(raw)
    doc = engine.read_v0_as_v1(raw)
    assert raw == before
    assert doc["schema"] == V1
    assert [(n["id"], n["item"]) for n in doc["notes"]] == [
        ("N-1-i-old", "i-old"), ("N-2-i-old-1", "i-old"), ("N-2-i-new-1", "i-new"), ("N-2-i-new-2", "i-new"),
        ("N-2-R-2-1", None)]
    assert doc["notes"][0]["text"] == 'why (on: "a b")' and doc["notes"][3]["deleted"] is True
    assert all("notes" not in r and all("notes" not in i for i in r["items"]) for r in doc["rounds"])
    assert doc["rounds"][1]["replies"] == [{"text": "Ok.", "about": ["N-2-R-2-1"]}]
    session = doc["session"]
    assert session["short_title"] is None and session["step"] == "Requirements grill"
    assert session["private"] is False and session["takeovers"] == []


def test_a_format_0_page_checks_and_renders_and_its_bytes_do_not_change(capsys, repo):
    raw = v0_document()
    path = repo / "specs" / "feature" / "pages" / "grill-s1.json"
    path.write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    before = path.read_bytes()
    assert call(capsys, "check", path)[0] == 0
    code, answer = call(capsys, "render", path)
    assert code == 0, answer
    assert call(capsys, "check", path)[1]["saved_copy"] == "compared"
    assert path.read_bytes() == before
    html = Path(answer["page"]).read_text("utf-8")
    assert "late" in html and "steer" in html


def test_a_real_format_0_page_with_notes_renders_and_stays_as_it_is(capsys, repo):
    source = FIXTURES / "v0-page-with-notes.json"
    session = json.loads(source.read_text("utf-8"))["session"]
    path = repo / "specs" / "feature" / "pages" / f"{session['skill']}-{session['id']}.json"
    path.write_bytes(source.read_bytes())
    assert call(capsys, "render", path)[0] == 0
    assert call(capsys, "check", path)[0] == 0
    assert path.read_bytes() == source.read_bytes()


def test_a_settled_copy_saved_in_the_format_0_form_still_compares(capsys, repo):
    raw = v0_document()
    path = repo / "specs" / "feature" / "pages" / "grill-s1.json"
    path.write_text(json.dumps(raw), "utf-8")
    old_copy = {"document": str(path), "rounds": {"1": engine.invariants.canonical(raw["rounds"][0])}}
    copy_path = engine._copy_path(path)
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    copy_path.write_text(json.dumps(old_copy), "utf-8")
    code, answer = call(capsys, "check", path)
    assert code == 0 and answer["saved_copy"] == "compared", answer


def test_a_format_1_note_settles_its_card_from_the_session_list(capsys, tmp_path):
    settled = {"by": "note", "round": 1, "signal": "N-1-i-a-1", "reading": "Yes."}
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "item": "i-a", "text": "why", "deleted": False}
    doc = v1_document(round_of(1, card("i-a", state="settled_by_note", settled=settled)), notes=[note])
    assert check(capsys, tmp_path, doc)[0] == 0
    note["deleted"] = True
    assert "field settled.signal" in refused(capsys, tmp_path, doc)["reason"]


# --- the raw answer text of format 1, and ingest into the session list


def raw_of(doc, prompts):
    raw_doc = doc
    doc = engine.READERS[raw_doc["schema"]](raw_doc)
    _, ids, _ = engine._element_ids(doc)
    return engine.prompt_lines.raw_from_prompts(doc, prompts, ids, None, raw_doc["schema"])


def annotation(words, selector="article#i-a", tag="p", seen=""):
    return {"uid": words, "prompt": words, "selector": selector, "tag": tag, "text": seen}


def mark(line):
    return {"uid": line, "prompt": line, "selector": "", "tag": "afkv2-mark", "text": ""}


def ingest(capsys, tmp_path, doc, raw):
    path = save(tmp_path / "doc.json", doc)
    raw_file = tmp_path / "raw.txt"
    raw_file.write_bytes(raw.encode("utf-8"))
    code, answer = call(capsys, "ingest", path, "--raw-file", raw_file)
    return code, answer, json.loads(path.read_text("utf-8"))


def test_format_1_gives_each_note_its_own_entry():
    prompts = [mark("i-a accept"), annotation("one"), annotation("two\nlines"),
               annotation("three", tag="text", seen="the  selected\ntext")]
    assert raw_of(v1_document(), prompts) == "\n".join([
        "[round R-1]", "i-a accept",
        "i-a note 1", "  one",
        "i-a note 2", "  two", "  lines",
        "i-a note 3", '  on: "the selected text"', "  three"])


def test_a_format_0_page_keeps_its_format_0_grammar():
    doc = v0_document()
    prompts = [annotation("one", selector="article#i-new"), annotation("two", selector="article#i-new")]
    assert raw_of(doc, prompts) == "[round R-2]\ni-new — | one\ni-new — | two"


def test_3_notes_on_one_element_are_3_notes_in_the_session_list(capsys, tmp_path):
    raw = raw_of(v1_document(), [annotation("one"), annotation("two"), annotation("three")])
    code, answer, after = ingest(capsys, tmp_path, v1_document(), raw)
    assert code == 0, answer
    assert [(n["id"], n["item"], n["text"]) for n in after["notes"]] == [
        ("N-1-i-a-1", "i-a", "one"), ("N-1-i-a-2", "i-a", "two"), ("N-1-i-a-3", "i-a", "three")]
    assert answer["notes"] == ["N-1-i-a-1", "N-1-i-a-2", "N-1-i-a-3"]
    assert all("notes" not in item for r in after["rounds"] for item in r["items"])
    assert after["schema"] == V1 and check(capsys, tmp_path, after)[0] == 0


def test_a_note_on_a_selection_keeps_the_noted_text_apart(capsys, tmp_path):
    seen = "word " * 100
    raw = raw_of(v1_document(), [annotation("my words", tag="text", seen=seen)])
    _, answer, after = ingest(capsys, tmp_path, v1_document(), raw)
    note = after["notes"][0]
    assert note["text"] == "my words" and len(note["quote"]) == 300 and note["quote"].startswith("word word")
    assert answer["signals"][0]["quote"] == note["quote"]


def test_ingest_parses_the_format_1_entries(capsys, tmp_path):
    doc = v1_document(round_of(1, card("i-a"), card("i-b")))
    raw = "\n".join(["[round R-1]", "i-a accept", "i-a note 1", '  on: "a "quoted" bit"', "  first", "    indented",
                     "  ", "  last", "i-b note 1", "  only words", "R-1 note 1", "  a steer"])
    code, answer, after = ingest(capsys, tmp_path, doc, raw)
    assert code == 0, answer
    first, second, steer = after["notes"]
    assert first["quote"] == 'a "quoted" bit' and first["text"] == "first\n  indented\n\nlast"
    assert second.get("quote") is None and second["text"] == "only words"
    assert steer["item"] is None and steer["id"] == "N-1-R-1-1"
    assert answer["conflicts"] == [] and answer["needs_reading"] == ["i-a", "i-b"]
    assert answer["signals"][0]["mark"] == "accept" and answer["signals"][0]["note"] == "N-1-i-a-1"


def test_a_note_entry_can_hold_only_the_noted_text(capsys, tmp_path):
    raw = "[round R-1]\ni-a note 1\n  on: \"just this\""
    code, answer, after = ingest(capsys, tmp_path, v1_document(), raw)
    assert code == 0, answer
    assert after["notes"][0]["quote"] == "just this" and after["notes"][0]["text"] == ""


@pytest.mark.parametrize("raw", ["[round R-1]\ni-a — | old form", "[round R-1]\ni-a note 1\nnot indented",
                                 "[round R-1]\nnope note 1\n  x"])
def test_a_format_1_page_refuses_a_line_of_another_grammar(capsys, tmp_path, raw):
    code, answer, _ = ingest(capsys, tmp_path, v1_document(), raw)
    assert code == 1 and answer["error"]["code"] == "bad-response", answer


def test_a_live_format_0_page_ingests_its_format_0_grammar_and_is_written_as_format_1(capsys, tmp_path):
    raw = "[round R-2]\ni-new — | three"
    code, answer, after = ingest(capsys, tmp_path, v0_document(), raw)
    assert code == 0, answer
    assert after["schema"] == V1 and answer["notes"] == ["N-2-i-new-3"]
    assert [n["id"] for n in after["notes"]][-1] == "N-2-i-new-3"


def test_a_note_edit_in_format_1_takes_the_indented_words(capsys, tmp_path):
    _, _, after = ingest(capsys, tmp_path, v1_document(), "[round R-1]\ni-a note 1\n  first")
    code, answer, after = ingest(capsys, tmp_path, after, "[round R-1]\nN-1-i-a-1 edit\n  second")
    assert code == 0, answer
    assert after["notes"][0]["text"] == "second" and answer["notes"] == []


# --- the 3 refusing invariants (SDD §6); no page rule or answer rule refuses


def answered_document(answer, **round_extra):
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "item": "i-a", "text": "why", "deleted": False}
    return v1_document(round_of(1, card("i-a"), replies=[answer], **round_extra), notes=[note])


@pytest.mark.parametrize("answer, extra, field", [
    ({"id": "A-1-1", "text": "x", "notes": ["N-1-i-a-9"]}, {}, "replies[0].notes[0]"),
    ({"id": "A-1-1", "text": "x", "notes": ["N-1-i-a-1"], "changed": ["i-gone"]}, {}, "replies[0].changed[0]"),
    ({"id": "A-1-1", "text": "x", "notes": ["N-1-i-a-1"]}, {"changed": ["i-gone"]}, "changed[0]"),
    ({"text": "x", "about": ["i-gone"]}, {}, "replies[0].about[0]"),
])
def test_an_answer_link_that_names_nothing_is_refused_as_bad_link(capsys, tmp_path, answer, extra, field):
    error = refused(capsys, tmp_path, answered_document(answer, **extra))
    assert error["code"] == "bad-link" and f"round 1, field {field}" in error["reason"], error


def test_an_answer_id_is_unique_in_the_document(capsys, tmp_path):
    answer = {"id": "A-1-1", "text": "x", "notes": ["N-1-i-a-1"]}
    doc = answered_document(answer)
    doc["rounds"][0]["replies"].append(dict(answer))
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "invariant" and "'A-1-1' is not unique" in error["reason"]


def test_a_duplicate_note_id_is_refused(capsys, tmp_path):
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "item": "i-a", "text": "why", "deleted": False}
    error = refused(capsys, tmp_path, v1_document(notes=[note, dict(note)]))
    assert error["code"] == "invariant" and "is not unique" in error["reason"]


def test_a_note_names_a_card_that_exists(capsys, tmp_path):
    note = {"id": "N-1-i-x-1", "round": 1, "target": "i-a", "item": "i-x", "text": "why", "deleted": False}
    assert "'i-x' is no card" in refused(capsys, tmp_path, v1_document(notes=[note]))["reason"]


def test_no_check_refuses_a_page_rule_or_an_answer_rule_break(capsys, tmp_path):
    """A note with no answer and an answer that names one of 2 notes are rules for the agent, not the check."""
    notes = [{"id": f"N-1-i-a-{k}", "round": 1, "target": "i-a", "item": "i-a", "text": "why", "deleted": False}
             for k in (1, 2)]
    doc = v1_document(round_of(1, card("i-a"), replies=[{"id": "A-1-1", "text": "x", "notes": ["N-1-i-a-1"]}]),
                      notes=notes)
    assert check(capsys, tmp_path, doc)[0] == 0
    assert check(capsys, tmp_path, v1_document(notes=notes))[0] == 0


# --- where a page may live (SDD §14 row "Where a page may live")


def data_page(name="grill-s1.json", repository="my-repo"):
    folder = engine.data_folder() / "pages" / repository
    folder.mkdir(parents=True, exist_ok=True)
    return folder / name


def home(path, doc):
    """The home check alone: the page title of a page with no ticket belongs to the page shell."""
    return engine._require_home(str(save(path, doc)), doc)


@pytest.mark.parametrize("skill", ["use-lavish", "to-subtasks", "grill"])
def test_a_page_with_no_ticket_lives_in_the_data_folder(skill):
    doc = v1_document(skill=skill, ticket=None)
    path = data_page(f"{skill}-s1.json")
    assert home(path, doc) == path.resolve()
    del doc["session"]["ticket"]
    assert home(path, doc) == path.resolve()


def test_a_private_page_with_a_ticket_lives_in_the_data_folder(capsys):
    path = save(data_page(), v1_document(private=True))
    assert call(capsys, "render", path)[0] == 0


def test_a_ticket_page_lives_only_under_its_spec_folder(capsys, repo):
    code, answer = call(capsys, "render", save(data_page(), v1_document()))
    assert code == 1 and answer["error"]["code"] == "bad-location", answer
    assert call(capsys, "render", save(repo / "specs" / "feature" / "pages" / "grill-s1.json", v1_document()))[0] == 0


def test_a_data_folder_page_sits_in_a_repository_folder_and_keeps_its_name():
    folder = engine.data_folder() / "pages"
    folder.mkdir(parents=True)
    doc = v1_document(ticket=None)
    with pytest.raises(engine.Refusal) as refused_here:
        home(folder / "grill-s1.json", doc)
    assert refused_here.value.code == "bad-location"
    with pytest.raises(engine.Refusal) as refused_here:
        home(data_page("grill-other.json"), doc)
    assert "must be named grill-s1.json" in refused_here.value.reason

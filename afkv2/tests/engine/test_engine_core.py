"""Page engine core: check, render, show, poll, the registry, the launcher and the Codex Stop hook.

Set AFKV2_TEST_LAVISH_DIR to a folder holding a local lavish-axi 0.1.80 install and playwright-core
to run the live seam test. It uses its own port and state folder and never stops a server.
"""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from functools import partial
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
ENGINE_DIR = PLUGIN / "engine"
ENGINE = ENGINE_DIR / "engine.py"
STOP_HOOK = PLUGIN / "hooks" / "codex_stop.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
for folder in (PLUGIN / "scripts", ENGINE_DIR, PLUGIN / "hooks"):
    sys.path.insert(0, str(folder))

import codex_stop  # noqa: E402
import engine  # noqa: E402
import launcher  # noqa: E402
import registry  # noqa: E402
from schema import invariants  # noqa: E402
from shell import inject, page  # noqa: E402

SCHEMA = "afkv2.page/0"


def text(value, **extra):
    return {"type": "text", "props": {"text": value}, **extra}


def item(item_id, kind="confirm", **extra):
    return {"id": item_id, "kind": kind, "body": text(f"Body of {item_id}"), **extra}


def banner(*settled):
    return {"settled": list(settled), "unlocks": [], "parked": []}


def document(*rounds):
    return {
        "schema": SCHEMA,
        "session": {"id": "s1", "skill": "grill", "feature": "export", "ticket": "PROJ-1",
                    "started": "2026-01-05T09:00:00Z"},
        "maps": [],
        "rounds": list(rounds) or [{"n": 1, "state": "current", "banner": banner(), "items": [item("i-a")]}],
    }


def two_rounds():
    settled = item("i-old", "decided", state="settled_by_mark",
                   settled={"by": "mark", "round": 1, "signal": "accept"})
    return document({"n": 1, "state": "settled", "banner": banner(), "items": [settled]},
                    {"n": 2, "state": "current", "banner": banner("i-old accepted"), "items": [item("i-new")]})


@pytest.fixture
def data_home(tmp_path, monkeypatch):
    home = tmp_path / "local"
    home.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(home))
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("LAVISH_AXI_HOST", raising=False)
    return home


@pytest.fixture
def repo(tmp_path, data_home):
    root = tmp_path / "repo"
    (root / ".afkv2").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    (root / "specs" / "feature" / "pages").mkdir(parents=True)
    return root


def holds(text, *parts):
    return all(part in text for part in parts)


def lacks(text, *parts):
    return not any(part in text for part in parts)


def position(text, part):
    return text.index(part)


ROUND_ONE = 'id="afkv2-r-1"'
ITEM_MARKER = 'data-afkv2-item="{}"'
COLOUR_RULE = "--afkv2-round: {}"


def item_markers(ids):
    return list(map(ITEM_MARKER.format, ids))


def round_colour_rules(colours):
    return list(map(COLOUR_RULE.format, colours))


def run_engine(*args, env=None):
    done = subprocess.run([sys.executable, str(ENGINE), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", env=env, check=False)
    return done.returncode, json.loads(done.stdout)


def save(path, doc):
    path.write_text(json.dumps(doc), "utf-8")
    return path


def call(capsys, *args):
    code = engine.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def in_home(repo, doc):
    return save(repo / "specs" / "feature" / "pages" / "grill-s1.json", doc)


def refused(capsys, tmp_path, doc):
    code, answer = call(capsys, "check", save(tmp_path / "doc.json", doc))
    assert code == 1 and answer["ok"] is False
    return answer["error"]


# --- the command contract


def test_check_answers_one_object_with_exit_0(tmp_path):
    code, answer = run_engine("check", save(tmp_path / "doc.json", document()))
    assert code == 0 and answer["ok"] is True


def test_refusal_is_exit_1_and_names_item_and_field(tmp_path):
    doc = document()
    doc["rounds"][0]["items"][0]["kind"] = "wrong"
    code, answer = run_engine("check", save(tmp_path / "doc.json", doc))
    assert code == 1 and set(answer["error"]) == {"code", "reason"}
    assert "item i-a" in answer["error"]["reason"] and "field kind" in answer["error"]["reason"]


@pytest.mark.parametrize("content", [b"{not json", b"\xff\xfe", b"[1]"])
def test_unreadable_input_is_exit_2(tmp_path, content):
    path = tmp_path / "doc.json"
    path.write_bytes(content)
    code, answer = run_engine("check", path)
    assert code == 2 and answer["error"]["code"] == "unreadable"


def test_a_missing_file_is_exit_2(tmp_path):
    assert run_engine("check", tmp_path / "none.json")[0] == 2


def test_a_bad_verb_is_exit_2_with_one_object(tmp_path):
    code, answer = run_engine("publish", tmp_path / "doc.json")
    assert code == 2 and answer["error"]["code"] == "usage"


# --- schema refusals


@pytest.mark.parametrize("change, name, field", [
    (lambda d: d["rounds"][0]["items"][0].pop("body"), "item i-a", "body"),
    (lambda d: d["rounds"][0]["items"][0].update(state="done"), "item i-a", "state"),
    (lambda d: d["rounds"][0]["items"][0].update(extra=1), "item i-a", "extra"),
    (lambda d: d["rounds"][0]["items"][0]["body"]["props"].pop("text"), "item i-a", "body.props.text"),
    (lambda d: d["rounds"][0].pop("banner"), "round 1", "banner"),
    (lambda d: d["rounds"][0]["banner"].pop("parked"), "round 1", "banner.parked"),
    (lambda d: d["session"].update(skill="other"), "item session", "skill"),
    (lambda d: d["session"].update(started="yesterday"), "item session", "started"),
    (lambda d: d["session"].update(id="a/b"), "item session", "id"),
    (lambda d: d.update(rounds=[]), "item document", "rounds"),
    (lambda d: d.update(extra=1), "item document", "extra"),
])
def test_schema_refusal_names_item_and_field(capsys, tmp_path, change, name, field):
    doc = document()
    change(doc)
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "schema"
    assert f"{name}, field {field}" in error["reason"]


def test_every_problem_is_named_up_to_the_limit(capsys, tmp_path):
    doc = document()
    for number in range(30):
        doc["rounds"][0]["items"].append({"id": f"i-{number}", "kind": "wrong", "body": text("x")})
    reason = refused(capsys, tmp_path, doc)["reason"]
    assert "item i-0," in reason and "item i-19," in reason and "and 10 more" in reason


# --- invariants


def test_exactly_one_round_is_current(capsys, tmp_path):
    doc = two_rounds()
    doc["rounds"][0]["state"] = "current"
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "invariant" and "exactly one round is current" in error["reason"]
    doc["rounds"][0]["state"] = doc["rounds"][1]["state"] = "settled"
    assert "exactly one round is current" in refused(capsys, tmp_path, doc)["reason"]


def test_round_numbers_count_in_order(capsys, tmp_path):
    doc = two_rounds()
    doc["rounds"][1]["n"] = 5
    assert "field rounds" in refused(capsys, tmp_path, doc)["reason"]


def test_ids_are_unique_across_items_and_components(capsys, tmp_path):
    doc = document()
    doc["rounds"][0]["items"].append({"id": "i-b", "kind": "info", "body": text("x", id="i-a")})
    assert "not unique" in refused(capsys, tmp_path, doc)["reason"]


def by_note(**settled):
    note = {"id": "N-1-i-n", "round": 1, "target": "i-n", "text": "Picks CSV.", "deleted": False}
    value = {"by": "note", "round": 1, "signal": "N-1-i-n", "reading": "Picks CSV.", **settled}
    return item("i-n", state="settled_by_note", settled=value, notes=[note])


def test_settled_by_note_passes_with_a_note_id_and_a_reading(capsys, tmp_path):
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [by_note()]})
    assert call(capsys, "check", save(tmp_path / "doc.json", doc))[0] == 0


@pytest.mark.parametrize("settled, field", [
    ({"reading": ""}, "settled.reading"),
    ({"signal": "N-9-other"}, "settled.signal"),
    ({"by": "mark"}, "settled.by"),
])
def test_settled_by_note_needs_a_note_id_and_a_reading(capsys, tmp_path, settled, field):
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [by_note(**settled)]})
    assert f"item i-n, field {field}" in refused(capsys, tmp_path, doc)["reason"]


def test_settled_by_note_refuses_a_deleted_note(capsys, tmp_path):
    point = by_note()
    point["notes"][0]["deleted"] = True
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [point]})
    assert "field settled.signal" in refused(capsys, tmp_path, doc)["reason"]


def test_a_settled_field_needs_a_settled_state(capsys, tmp_path):
    point = item("i-a", settled={"by": "mark", "round": 1, "signal": "accept"})
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [point]})
    assert "item i-a, field settled" in refused(capsys, tmp_path, doc)["reason"]
    point = item("i-a", state="settled_by_mark")
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [point]})
    assert "item i-a, field settled" in refused(capsys, tmp_path, doc)["reason"]


def test_a_note_id_has_the_engine_grammar(capsys, tmp_path):
    bad = {"id": "note-1", "round": 1, "target": "i-a", "text": "x", "deleted": False}
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [item("i-a", notes=[bad])]})
    assert "field notes[0].id" in refused(capsys, tmp_path, doc)["reason"]


def test_a_note_target_and_a_card_node_must_resolve(capsys, tmp_path):
    note = {"id": "N-1-i-a", "round": 1, "target": "nowhere", "text": "x", "deleted": False}
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": [item("i-a", notes=[note], node="n-x")]})
    reason = refused(capsys, tmp_path, doc)["reason"]
    assert "field notes[0].target" in reason and "field node" in reason


def stamped_response(session="s1", round_n=1):
    received, raw = "2026-01-05T10:00:00Z", "[round R-1]\ni-a accept"
    signal = {"target": "i-a", "signal": "accept"}
    signal["stamp"] = invariants.ingest_stamp(session, round_n, received, raw, signal)
    return {"received": received, "raw": raw, "signals": [signal]}


def test_a_response_with_the_ingest_stamp_passes(capsys, tmp_path):
    doc = document()
    doc["rounds"][0]["responses"] = [stamped_response()]
    assert call(capsys, "check", save(tmp_path / "doc.json", doc))[0] == 0


def test_only_ingest_writes_responses_and_signals(capsys, tmp_path):
    doc = document()
    forged = stamped_response()
    forged["signals"][0]["signal"] = "sign"
    doc["rounds"][0]["responses"] = [forged]
    assert "only ingest" in refused(capsys, tmp_path, doc)["reason"]
    doc["rounds"][0]["responses"] = [{"received": forged["received"], "raw": "x", "signals": [{"signal": "sign"}]}]
    assert "stamp" in refused(capsys, tmp_path, doc)["reason"]
    doc["rounds"][0]["responses"] = [{"received": forged["received"], "raw": "x", "signals": []}]
    assert "field responses[0].signals" in refused(capsys, tmp_path, doc)["reason"]


def test_a_settled_round_is_never_rewritten(capsys, repo):
    doc = two_rounds()
    path = in_home(repo, doc)
    assert call(capsys, "render", path)[0] == 0
    assert call(capsys, "check", path)[1]["saved_copy"] == "compared"
    changed = copy.deepcopy(doc)
    changed["rounds"][0]["items"][0]["body"]["props"]["text"] = "rewritten"
    code, answer = call(capsys, "check", save(path, changed))
    assert code == 1 and "round 1" in answer["error"]["reason"] and "never rewritten" in answer["error"]["reason"]
    assert call(capsys, "render", path)[0] == 1
    removed = copy.deepcopy(doc)
    removed["rounds"] = [{**removed["rounds"][1], "n": 1}]
    assert "never rewritten" in call(capsys, "check", save(path, removed))[1]["error"]["reason"]


def test_a_new_settled_round_is_not_a_rewrite(capsys, repo):
    doc = two_rounds()
    path = in_home(repo, doc)
    call(capsys, "render", path)
    doc["rounds"][1]["state"] = "settled"
    doc["rounds"].append({"n": 3, "state": "current", "banner": banner(), "items": [item("i-3")]})
    assert call(capsys, "check", save(path, doc))[0] == 0


def test_ingest_can_save_the_copy_after_a_late_note(capsys, repo):
    doc = two_rounds()
    path = in_home(repo, doc)
    call(capsys, "render", path)
    late = doc["rounds"][0]["items"][0]
    late.update(state="open", settled=None)
    late["notes"] = [{"id": "N-2-i-old", "round": 2, "target": "i-old", "text": "No.", "deleted": False}]
    engine.save_settled_copy(path, doc)
    assert call(capsys, "check", save(path, doc))[0] == 0


def test_check_passes_with_no_data_folder_and_says_so(capsys, tmp_path, monkeypatch):
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    code, answer = call(capsys, "check", save(tmp_path / "doc.json", two_rounds()))
    assert code == 0 and answer["saved_copy"] == "unavailable"


def test_a_broken_saved_copy_is_unreadable_not_a_pass(capsys, repo):
    path = in_home(repo, two_rounds())
    call(capsys, "render", path)
    engine._copy_path(path).write_text("{broken", "utf-8")
    code, answer = call(capsys, "check", path)
    assert code == 2 and answer["error"]["code"] == "unreadable"


def test_a_signoff_card_can_go_back_for_a_sign_mark_after_a_note(capsys, tmp_path):
    note = {"id": "N-1-i-s", "round": 1, "target": "i-s", "text": "Change the wording.", "deleted": False}
    old = item("i-s", "signoff", state="open", notes=[note])
    doc = document({"n": 1, "state": "settled", "banner": banner(), "items": [old]},
                   {"n": 2, "state": "current", "banner": banner(), "items": [item("i-s2", "signoff")]})
    assert call(capsys, "check", save(tmp_path / "doc.json", doc))[0] == 0


# --- schema versions


@pytest.mark.parametrize("value", ["afkv2.page/9", 1, None])
def test_an_unknown_schema_is_refused_with_its_version(capsys, tmp_path, value):
    doc = document()
    doc["schema"] = value
    error = refused(capsys, tmp_path, doc)
    assert error["code"] == "unknown-schema" and repr(value) in error["reason"]


@pytest.mark.parametrize("name", ["v1-grill-final.json", "v1-sdd.json"])
def test_a_v1_document_is_refused_with_version_1(name):
    code, answer = run_engine("check", FIXTURES / name)
    assert code == 1 and "version 1 is unknown" in answer["error"]["reason"]


def test_the_engine_keeps_a_reader_and_a_schema_file_for_every_value():
    assert set(engine.READERS) == set(engine.SCHEMA_FILES) == {SCHEMA}
    assert all(path.is_file() for path in engine.SCHEMA_FILES.values())


def test_a_real_document_passes_and_renders(capsys, repo):
    doc = json.loads((FIXTURES / "v0-sdd-pass.json").read_text("utf-8"))
    path = save(repo / "specs" / "feature" / "pages" / "propose-solution-sdd-pass.json", doc)
    code, answer = call(capsys, "render", path)
    assert code == 0
    html = Path(answer["page"]).read_text("utf-8")
    assert holds(html, *item_markers(i["id"] for r in doc["rounds"] for i in r["items"]))


# --- registry


@pytest.fixture
def scratch_type():
    names = []

    def add(name, schema=None, render=None, **options):
        registry.register_component(name, schema or {"type": "object"},
                                    render or (lambda props, children: "".join(children)), **options)
        names.append(name)

    yield add
    for name in names:
        registry._types.pop(name, None)


def test_a_type_name_maps_to_a_schema_and_a_renderer():
    kind = registry.lookup("chip")
    assert kind.name == "chip" and kind.schema["required"] == ["text", "tone"] and callable(kind.render)
    assert registry.lookup("no-such") is None


def test_an_unknown_type_is_refused_with_its_name(capsys, tmp_path):
    doc = document()
    doc["rounds"][0]["items"][0]["body"] = {"type": "hologram"}
    error = refused(capsys, tmp_path, doc)
    assert "item i-a, field body.type" in error["reason"] and "hologram" in error["reason"]


def test_a_new_component_is_one_registry_entry(capsys, tmp_path, scratch_type):
    scratch_type("badge", {"type": "object", "required": ["label"], "properties": {"label": {"type": "string"}}},
                 lambda props, children: f"<b>{props['label']}</b>" + "".join(children))
    doc = document()
    doc["rounds"][0]["items"][0]["body"] = {"type": "badge", "props": {"label": "new"}}
    assert call(capsys, "check", save(tmp_path / "doc.json", doc))[0] == 0
    assert "<b>new</b>" in page.build(doc)
    doc["rounds"][0]["items"][0]["body"] = {"type": "badge", "props": {}}
    assert "field body.props.label" in refused(capsys, tmp_path, doc)["reason"]


def test_a_type_cannot_be_registered_twice_or_with_an_unknown_keyword(scratch_type):
    with pytest.raises(ValueError):
        registry.register_component("chip", {"type": "object"}, lambda p, c: "")
    with pytest.raises(ValueError):
        registry.register_component("bad", {"oneOf": []}, lambda p, c: "")


COMPONENTS = {
    "text": {"text": "hello"},
    "chip": {"text": "hello", "tone": "new"},
    "table": {"columns": ["A"], "rows": [["hello"]]},
    "freestyle": {"reason": "a drawing"},
}


@pytest.mark.parametrize("name", sorted(COMPONENTS))
def test_every_base_component_takes_style_and_children(name):
    component = {"type": name, "props": COMPONENTS[name], "style": "color: red", "id": "c-1",
                 "children": [{"type": "chip", "props": {"text": "inner child", "tone": "kept"}}]}
    if name == "freestyle":
        component["html"] = "<svg></svg>"
    assert registry.validate(component) == []
    html = registry.render_component(component)
    assert holds(html, 'style="color: red"', "inner child", 'data-afkv2-element="c-1"')


def test_the_style_field_is_open_and_escaped_as_one_attribute():
    html = registry.render_component(text("x", style='font-family: "Segoe UI"'))
    assert 'style="font-family: &quot;Segoe UI&quot;"' in html


def test_freestyle_renders_any_html_and_the_page_marks_it():
    html = registry.render_component({"type": "freestyle", "id": "f-1", "props": {"reason": "a drawing"},
                                      "html": '<svg id="raw"><circle r="1"/></svg>'})
    assert '<svg id="raw"><circle r="1"/></svg>' in html
    assert holds(html, 'data-afkv2-freestyle="1"', "Freestyle: a drawing")


@pytest.mark.parametrize("component, field", [
    ({"type": "freestyle", "props": {}, "html": "<b></b>"}, "props.reason"),
    ({"type": "freestyle", "props": {"reason": "x"}}, "html"),
    ({"type": "text", "props": {"text": "x"}, "html": "<b></b>"}, "html"),
    ({"type": "chip", "props": {"text": "x"}}, "props.tone"),
    ({"type": "chip", "props": {"text": "x", "tone": "loud"}}, "props.tone"),
    ({"type": "table", "props": {"columns": ["A", "B"], "rows": [["x"]]}}, "props.rows[0]"),
    ({"type": "table", "props": {"columns": ["A"], "rows": [[{"type": "nope"}]]}}, "props.rows[0][0].type"),
])
def test_bad_props_name_the_field(capsys, tmp_path, component, field):
    doc = document()
    doc["rounds"][0]["items"][0]["body"] = component
    assert f"item i-a, field body.{field}" in refused(capsys, tmp_path, doc)["reason"]


# --- base components


@pytest.mark.parametrize("tone", ["removed", "kept", "new", "proposed"])
def test_chip_and_text_have_the_four_tones(tone):
    assert holds(registry.render_component({"type": "chip", "props": {"text": "x", "tone": tone}}), f"afkv2-tone--{tone}")
    assert holds(registry.render_component({"type": "text", "props": {"text": "x", "tone": tone}}), f"afkv2-tone--{tone}")


def test_a_chip_renders_in_a_table_cell():
    table = {"type": "table", "props": {"columns": ["A", "B"], "rows": [
        ["plain <text>", {"type": "chip", "id": "c-chip", "props": {"text": "a cell chip", "tone": "new"}}]]}}
    assert registry.validate(table) == []
    html = registry.render_component(table)
    assert "plain &lt;text&gt;" in html
    cell = html[html.index("<td>", html.index("<td>") + 1):]
    assert holds(cell, "afkv2-chip", "a cell chip", 'data-afkv2-element="c-chip"')


def test_components_nest_in_any_other():
    deep = {"type": "table", "props": {"columns": ["A"], "rows": [[
        {"type": "text", "props": {"text": "outer"}, "children": [
            {"type": "table", "props": {"columns": ["B"], "rows": [[
                {"type": "freestyle", "id": "f", "props": {"reason": "r"}, "html": "<i>deep</i>"}]]}}]}]]}}
    assert registry.validate(deep) == []
    assert "<i>deep</i>" in registry.render_component(deep)
    assert [part["type"] for _, part in registry.walk(deep)] == ["table", "text", "table", "freestyle"]


def test_text_is_escaped():
    assert "&lt;script&gt;" in registry.render_component(text("<script>"))


def card_html(point, current=True):
    return registry.render_component({"type": "card", "children": [point["body"]], "props": {
        "item": point, "round": 3, "colour": "red", "current": current}})


@pytest.mark.parametrize("kind, tokens", [
    ("decided", ["accept", "reopen"]),
    ("confirm", ["accept", "write-in"]),
    ("signoff", ["sign", "changes"]),
])
def test_a_card_has_the_controls_of_its_kind(kind, tokens):
    html = card_html(item("i-a", kind))
    for token in tokens:
        assert f'value="{token}"' in html
    assert html.count('type="radio"') == len(tokens)
    assert holds(html, 'data-afkv2-required="1"', 'data-afkv2-input="note"')


def test_an_info_card_has_a_note_and_no_mark():
    html = card_html(item("i-a", "info"))
    assert lacks(html, 'type="radio"') and holds(html, 'data-afkv2-input="note"')
    assert lacks(html, "data-afkv2-required", "afkv2-round-chip")


def test_a_debate_card_offers_each_option_cell_and_a_write_in():
    point = item("i-f", "debate")
    point["body"] = text("Which?", children=[{"type": "table", "props": {
        "columns": ["A: CSV", "B: JSON"],
        "rows": [[text("flat", id="i-f-opt-a"), text("nested", id="i-f-opt-b")]]}}])
    html = card_html(point)
    assert 'value="a"' in html and 'value="b"' in html and 'value="write-in"' in html
    assert "<span>A: CSV</span>" in html and "<span>B: JSON</span>" in html


def test_a_debate_card_with_no_option_cells_still_takes_a_write_in():
    html = card_html(item("i-f", "debate"))
    assert html.count('type="radio"') == 1 and 'value="write-in"' in html


def test_settled_by_note_differs_from_settled_by_mark():
    by_mark = card_html(item("i-m", state="settled_by_mark", settled={"by": "mark", "round": 1, "signal": "accept"}))
    noted = card_html(by_note())
    assert holds(by_mark, "settled by mark", "afkv2-settled--mark")
    assert holds(noted, "settled by note", "afkv2-settled--note", "Picks CSV.")
    assert 'type="radio"' not in by_mark + noted and "<textarea" not in by_mark + noted


def test_a_blocked_card_takes_a_note_and_no_mark():
    html = card_html(item("i-b", state="blocked"))
    assert lacks(html, 'type="radio"') and holds(html, "<textarea", "afkv2-round-chip")
    assert holds(html, 'data-afkv2-state="blocked"')


def test_a_round_banner_holds_its_three_lists():
    html = registry.render_component({"type": "round-banner", "props": {
        "n": 4, "colour": "red", "current": True, "settled": ["a <b>"], "unlocks": [], "parked": ["p"]}})
    assert holds(html, "R-4", "a &lt;b&gt;", "<li>p</li>", "--afkv2-round: red")


# --- the page


def test_page_order_is_banner_slot_maps_cards(scratch_type):
    scratch_type("map")
    doc = two_rounds()
    doc["maps"] = [{"type": "map", "id": "m-1", "props": {
        "nodes": [{"id": "n-1", "state": "open", "round": 1, "label": "x"}]}}]
    html = page.build(doc)
    body = html[position(html, "<body>"):]
    order = ["afkv2-banner", 'id="afkv2-notes-replies"', 'id="afkv2-maps"', 'id="afkv2-answer-form"', 'id="afkv2-r-1"']
    positions = [position(body, mark) for mark in order]
    assert positions == sorted(positions)


def test_the_slot_holds_what_its_registered_component_renders(scratch_type):
    assert holds(page.build(two_rounds()), '<section class="afkv2-notes-replies" id="afkv2-notes-replies"></section>')
    scratch_type("notes-and-replies", render=lambda props, children: f"<p>{props['document']['session']['id']}</p>")
    assert holds(page.build(two_rounds()), 'id="afkv2-notes-replies"><p>s1</p></section>')


def test_each_round_has_its_own_colour():
    doc = document(*[{"n": n, "state": "settled" if n < 12 else "current", "banner": banner(), "items": []}
                     for n in range(1, 13)])
    colours = [page.round_colour(r) for r in doc["rounds"]]
    assert len(set(colours)) == 12
    assert page.round_colour({"n": 1, "colour": "tomato"}) == "tomato"
    assert holds(page.build(doc), *round_colour_rules(colours))


def test_a_round_chip_marks_every_item_that_needs_the_human_in_that_round():
    doc = two_rounds()
    doc["rounds"][1]["items"] += [item("i-info", "info"), item("i-done", state="settled_by_mark",
                                                              settled={"by": "mark", "round": 2, "signal": "accept"})]
    html = page.build(doc)
    def card(item_id):
        start = position(html, f'id="afkv2-i-{item_id}"')
        return html[start:html.find("</article>", start)]

    assert "R-2</span>" in card("i-new")
    for other in ("i-old", "i-info", "i-done"):
        assert lacks(card(other), "afkv2-round-chip")


def test_no_item_is_removed_when_a_round_settles():
    doc = two_rounds()
    html = page.build(doc)
    assert holds(html, 'data-afkv2-item="i-old"', 'data-afkv2-item="i-new"')
    first_round = position(html, ROUND_ONE)
    past = html[first_round:position(html, "<script>")]
    assert lacks(past, "<textarea", 'type="radio"')


def test_past_rounds_come_newest_first():
    doc = two_rounds()
    doc["rounds"][1]["state"] = "settled"
    doc["rounds"].append({"n": 3, "state": "current", "banner": banner(), "items": [item("i-3")]})
    html = page.build(doc)
    assert position(html, 'id="afkv2-r-3"') < position(html, 'id="afkv2-r-2"') < position(html, 'id="afkv2-r-1"')


def test_a_round_with_nothing_to_answer_has_no_send_bar():
    doc = document({"n": 1, "state": "current", "banner": banner(), "items": []})
    html = page.build(doc)
    assert lacks(html, 'id="afkv2-send"', 'id="afkv2-answer-form"')


def test_same_document_same_bytes(repo, capsys):
    path = in_home(repo, two_rounds())
    call(capsys, "render", path)
    first = path.with_suffix(".html").read_bytes()
    os.utime(path.with_suffix(".html"), (1, 1))
    call(capsys, "render", path)
    assert path.with_suffix(".html").read_bytes() == first
    assert path.with_suffix(".html").stat().st_mtime == 1


def test_the_shell_reuses_the_kit_with_new_names():
    html = page.build(two_rounds())
    assert holds(html, 'id="afkv2-send-go"', 'data-lavish-question="round:R-2"')
    assert "window.lavish" in html and "queuePrompt" in html
    assert "backdrop-filter" in html and "display: flow-root" in html


def test_a_browser_draft_is_keyed_by_session_and_round_and_cleared_on_send():
    runtime = (ENGINE_DIR / "shell" / "runtime.js").read_text("utf-8")
    assert holds(runtime, "KEY_PREFIX + bar.getAttribute('data-afkv2-session') + ':' + round")
    assert "location.pathname" not in runtime
    assert runtime.index("sendQueuedPrompts();") < runtime.index("clearDraft();", runtime.index("sendQueuedPrompts();"))
    assert holds(page.build(two_rounds()), 'data-afkv2-session="s1"')


def test_the_rendered_page_has_the_tooltip_layer(repo, capsys):
    (repo / "GLOSSARY.md").write_text("**Widget**: a small part.\n", "utf-8")
    (repo / "specs" / "feature" / "PAGE-TIPS.md").write_text("**Gadget**: a feature term.\n", "utf-8")
    path = in_home(repo, two_rounds())
    assert call(capsys, "render", path)[0] == 0
    html = path.with_suffix(".html").read_text("utf-8")
    assert holds(html, "afkv2-tips-dict", "a small part.", "a feature term.")
    assert html.index(inject.MARK_START) < html.index("</body>")
    assert html.count(inject.MARK_START) == 1
    inject.inject_file(path.with_suffix(".html"))
    assert path.with_suffix(".html").read_text("utf-8").count(inject.MARK_START) == 1


def test_a_closing_script_tag_in_a_tip_does_not_end_the_block():
    assert "</script>" not in inject.tips_block({"x": "</script>"}).split('type="application/json">')[1].split("<\\/script>")[0]


# --- where a document lives


def test_render_writes_the_page_beside_the_document(repo, capsys):
    path = in_home(repo, two_rounds())
    code, answer = call(capsys, "render", path)
    assert code == 0 and answer == {"ok": True, "verb": "render", "page": str(path.with_suffix(".html").resolve())}
    assert path.with_suffix(".html").is_file()
    assert sorted(p.name for p in path.parent.iterdir()) == ["grill-s1.html", "grill-s1.json"]


@pytest.mark.parametrize("relative, code", [
    ("specs/feature/pages/grill-other.json", "bad-location"),
    ("specs/feature/grill-s1.json", "bad-location"),
    ("elsewhere/pages/grill-s1.json", "bad-location"),
])
def test_render_refuses_a_document_outside_its_home(repo, capsys, relative, code):
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    save(path, two_rounds())
    exit_code, answer = call(capsys, "render", path)
    assert exit_code == 1 and answer["error"]["code"] == code and "field id" in answer["error"]["reason"]


def test_render_refuses_a_session_id_used_twice_in_a_feature(repo, capsys):
    save(repo / "specs" / "feature" / "pages" / "propose-solution-s1.json", {})
    path = in_home(repo, two_rounds())
    code, answer = call(capsys, "render", path)
    assert code == 1 and answer["error"]["code"] == "duplicate-session"


def test_render_refuses_with_no_config(capsys, tmp_path, data_home):
    (tmp_path / ".git").mkdir()
    (tmp_path / "pages").mkdir()
    path = save(tmp_path / "pages" / "grill-s1.json", two_rounds())
    code, answer = call(capsys, "render", path)
    assert code == 1 and answer["error"]["code"] == "no-config"


def test_render_with_no_data_folder_is_exit_2(repo, capsys, monkeypatch):
    path = in_home(repo, two_rounds())
    monkeypatch.delenv("LOCALAPPDATA")
    code, answer = call(capsys, "render", path)
    assert code == 2 and answer["error"]["code"] in ("no-data-folder", "no-config")


# --- launcher


@pytest.mark.parametrize("argv", [
    [], ["stop"], ["share", "p.html"], ["setup"], ["update"], ["playbook"], ["reply", "p.html"], ["--help"],
    ["open"], ["open", "p.txt"], ["open", "missing.html"], ["end"], ["end", "p.txt"],
    ["poll"], ["poll", "p.html", "--takeover"], ["poll", "p.html", "--timeout-ms", "soon"],
])
def test_the_launcher_refuses_outside_its_grammar(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "p.html").write_text("<html></html>", "utf-8")
    (tmp_path / "p.txt").write_text("x", "utf-8")
    assert launcher.run(argv)[0] == 64


def test_the_launcher_grammar_holds_open_poll_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "p.html").write_text("<html></html>", "utf-8")
    assert launcher.plan(["open", "p.html"]) == "p.html"
    assert launcher.plan(["open", "p.html", "--no-open"]) == "p.html"
    assert launcher.plan(["open", "p.html", "--reopen"]) == "p.html"
    assert launcher.plan(["poll", "p.html"]) is None
    assert launcher.plan(["poll", "p.html", "--timeout-ms", "1000"]) is None
    assert launcher.plan(["end", "p.html"]) is None


def test_exit_64_when_the_host_variable_is_set(monkeypatch):
    monkeypatch.setenv("LAVISH_AXI_HOST", "0.0.0.0")
    assert launcher.run(["end", "p.html"])[0] == 64


def test_exit_127_when_the_host_is_not_on_the_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "p.html").write_text("<html></html>", "utf-8")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    assert launcher.run(["open", "p.html"])[0] == 127


def fake_install(folder, version="0.1.80", layout="global"):
    package = folder / "node_modules" / "lavish-axi" if layout == "global" else folder / "lavish-axi"
    (package / "dist").mkdir(parents=True)
    (package / "dist" / "cli.mjs").write_text("", "utf-8")
    (package / "package.json").write_text(json.dumps({"version": version, "bin": {"lavish-axi": "dist/cli.mjs"}}), "utf-8")
    shim_folder = folder if layout == "global" else folder / ".bin"
    shim_folder.mkdir(exist_ok=True)
    shim = shim_folder / "lavish-axi.cmd"
    shim.write_text("", "utf-8")
    return shim, package


@pytest.mark.skipif(os.name != "nt", reason="the npm .cmd shim is a Windows layout")
@pytest.mark.parametrize("layout", ["global", "local"])
def test_the_launcher_runs_the_package_script_of_either_layout(tmp_path, monkeypatch, layout):
    shim, package = fake_install(tmp_path, layout=layout)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: str(shim) if name == "lavish-axi" else "node-on-path")
    assert launcher.upstream(["poll", "p.html"]) == ["node-on-path", str(package / "dist" / "cli.mjs"), "poll", "p.html"]


def test_the_launcher_refuses_any_host_version_but_the_pin(tmp_path, monkeypatch):
    shim, _ = fake_install(tmp_path, version="0.1.63")
    (tmp_path / "p.html").write_text("<html></html>", "utf-8")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: str(shim))
    code, out = launcher.run(["end", str(tmp_path / "p.html")])
    assert code == 64 and "0.1.63" in out and "0.1.80" in out


def test_exit_65_when_the_page_cannot_be_injected(tmp_path, monkeypatch):
    shim, _ = fake_install(tmp_path)
    page_file = tmp_path / "p.html"
    page_file.write_bytes(b"\xff\xfe not utf-8")
    monkeypatch.setattr(launcher.shutil, "which", lambda name: str(shim))
    assert launcher.run(["open", str(page_file)])[0] == 65


def test_exit_69_when_the_batch_path_cannot_be_bound(tmp_path, monkeypatch):
    def unbound(command, **streams):
        raise launcher.Unbound("no job")
    monkeypatch.setattr(launcher, "upstream", lambda args: ["x.cmd", *args])
    monkeypatch.setattr(launcher, "start_batch", unbound)
    assert launcher.run(["end", "p.html"])[0] == 69


def fake_host_script(tmp_path, body):
    script = tmp_path / "fake_host.py"
    script.write_text(body, "utf-8")
    return script


def test_the_launcher_answers_the_host_exit_and_exact_stdout(tmp_path, monkeypatch):
    script = fake_host_script(tmp_path, "import sys; sys.stdout.buffer.write('é\\n\"x\"'.encode('utf-8')); sys.exit(3)")
    monkeypatch.setattr(launcher, "upstream", lambda args: [sys.executable, str(script), *args])
    assert launcher.run(["end", "p.html"]) == (3, 'é\n"x"')


def host_fixture(name):
    return (FIXTURES / name).read_text("utf-8")


def test_the_reader_keeps_the_raw_text_of_the_recorded_host_output():
    parsed = launcher.parse_host_output(host_fixture("host-poll-feedback.txt"))
    assert parsed["session"]["status"] == "feedback"
    assert parsed["prompts"][0]["prompt"] == (
        '[round R-1]\ni-a accept | C:\\Users\\x "q" trailing  \n  second\ttab | pipe é 中文 \\\\double\ni-b —')
    assert parsed["prompts"][0]["tag"] == "choice" and parsed["prompts"][0]["selector"] == "form#f"


def test_the_reader_takes_the_expanded_list_shape():
    parsed = launcher.parse_host_output(host_fixture("host-poll-two-prompts.txt"))
    assert [p["prompt"] for p in parsed["prompts"]] == ["first, with a comma", "- second\nline"]
    assert parsed["prompts"][1]["selector"] is None
    assert parsed["session"]["session_ended"] is True


def test_the_reader_takes_open_error_and_the_other_statuses():
    assert launcher.parse_host_output(host_fixture("host-open.txt"))["session"]["url"].startswith("http://127.0.0.1:")
    error = launcher.parse_host_output(host_fixture("host-error-missing.txt"))
    assert error["code"] == "NOT_FOUND" and "No active" in error["error"]
    for name, status in (("ended", "ended"), ("disconnected", "browser_disconnected"), ("waiting", "waiting")):
        assert launcher.parse_host_output(host_fixture(f"host-poll-{name}.txt"))["session"]["status"] == status


# --- show and poll, over a host recorded from the real encoder


@pytest.fixture
def host(monkeypatch):
    """A stand-in for `launcher.run`; `outputs` maps an operation to `(exit, stdout)`."""
    calls, outputs = [], {"open": (0, host_fixture("host-open.txt")), "poll": (0, host_fixture("host-poll-feedback.txt"))}

    def run(argv):
        calls.append(argv)
        return outputs[argv[0]]

    monkeypatch.setattr(launcher, "run", run)
    return calls, outputs


def test_show_renders_opens_and_answers_the_url(repo, capsys, host):
    calls, _ = host
    path = in_home(repo, two_rounds())
    code, answer = call(capsys, "show", path)
    assert code == 0 and answer["ok"] is True and answer["status"] == "opened"
    assert answer["url"].startswith("http://127.0.0.1:") and answer["waiting_record"] is None
    assert calls == [["open", str(path.with_suffix(".html").resolve())]]
    assert path.with_suffix(".html").is_file()


@pytest.mark.parametrize("flag", ["--no-open", "--reopen"])
def test_show_passes_its_one_flag(repo, capsys, host, flag):
    calls, _ = host
    assert call(capsys, "show", in_home(repo, two_rounds()), flag)[0] == 0
    assert calls[0][2:] == [flag]


def test_show_refuses_a_document_that_fails_the_check_and_opens_nothing(repo, capsys, host):
    calls, _ = host
    doc = two_rounds()
    doc["rounds"][1]["state"] = "settled"
    assert call(capsys, "show", in_home(repo, doc))[0] == 1
    assert calls == []


@pytest.mark.parametrize("wrapper_exit", [64, 65, 69, 127])
def test_a_wrapper_exit_leads_to_the_markdown_fallback(repo, capsys, host, wrapper_exit):
    _, outputs = host
    outputs["open"] = outputs["poll"] = (wrapper_exit, "the wrapper said no")
    path = in_home(repo, two_rounds())
    for verb in ("show", "poll"):
        if verb == "poll":
            path.with_suffix(".html").write_text("<html></html>", "utf-8")
        code, answer = call(capsys, verb, path)
        assert code == 1 and answer["error"]["code"] == "markdown-fallback"
        assert f"wrapper exit {wrapper_exit}" in answer["error"]["reason"]


def test_show_reports_a_host_error(repo, capsys, host):
    _, outputs = host
    outputs["open"] = (1, host_fixture("host-error-missing.txt"))
    code, answer = call(capsys, "show", in_home(repo, two_rounds()))
    assert code == 1 and answer["error"]["code"] == "host-error" and "No active" in answer["error"]["reason"]


def test_poll_returns_the_raw_response_verbatim(repo, capsys, host):
    path = in_home(repo, two_rounds())
    path.with_suffix(".html").write_text("<html></html>", "utf-8")
    code, answer = call(capsys, "poll", path)
    assert code == 0 and answer["ok"] is True and answer["status"] == "feedback"
    assert answer["raw"] == launcher.parse_host_output(host_fixture("host-poll-feedback.txt"))["prompts"][0]["prompt"]


def test_poll_joins_several_prompts_with_one_line_break(repo, capsys, host):
    _, outputs = host
    outputs["poll"] = (0, host_fixture("host-poll-two-prompts.txt"))
    path = in_home(repo, two_rounds())
    path.with_suffix(".html").write_text("<html></html>", "utf-8")
    answer = call(capsys, "poll", path)[1]
    assert answer["raw"] == "first, with a comma\n- second\nline"
    assert answer["session_ended"] is True and [p["tag"] for p in answer["prompts"]] == ["note", "choice"]


@pytest.mark.parametrize("output, code_word", [
    ((0, "host-poll-ended.txt"), "page-ended"),
    ((0, "host-poll-disconnected.txt"), "page-browser-disconnected"),
    ((1, "host-error-missing.txt"), "host-error"),
])
def test_poll_with_no_answer_is_refused_and_named(repo, capsys, host, output, code_word):
    _, outputs = host
    outputs["poll"] = (output[0], host_fixture(output[1]))
    path = in_home(repo, two_rounds())
    path.with_suffix(".html").write_text("<html></html>", "utf-8")
    code, answer = call(capsys, "poll", path)
    assert code == 1 and answer["error"]["code"] == code_word


def test_poll_with_no_rendered_page_is_exit_2(repo, capsys, host):
    assert call(capsys, "poll", in_home(repo, two_rounds()))[0] == 2


# --- Codex: the waiting record and the Stop hook


def test_on_codex_show_writes_one_record_per_session(repo, capsys, host, monkeypatch, data_home):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    path = in_home(repo, two_rounds())
    answer = call(capsys, "show", path)[1]
    record = launcher.read_waiting_record(data_home / "afkv2", "thread-1")
    assert answer["waiting_record"] == str(data_home / "afkv2" / "page-waiting-thread-1.json")
    assert record["page"] == str(path.with_suffix(".html").resolve()) and record["document"] == str(path.resolve())
    call(capsys, "show", path)
    assert [p.name for p in (data_home / "afkv2").glob("page-waiting-*")] == ["page-waiting-thread-1.json"]


def test_a_refused_show_writes_no_record(repo, capsys, host, monkeypatch, data_home):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    _, outputs = host
    outputs["open"] = (127, "absent")
    call(capsys, "show", in_home(repo, two_rounds()))
    assert launcher.read_waiting_record(data_home / "afkv2", "thread-1") is None


def test_a_foreground_poll_on_codex_clears_the_record(repo, capsys, host, monkeypatch, data_home):
    monkeypatch.setenv("CODEX_THREAD_ID", "thread-1")
    path = in_home(repo, two_rounds())
    call(capsys, "show", path)
    assert call(capsys, "poll", path)[0] == 0
    assert launcher.read_waiting_record(data_home / "afkv2", "thread-1") is None


def test_an_unsafe_session_name_stays_in_the_data_folder(tmp_path):
    path = launcher.write_waiting_record(tmp_path, "../../evil", "d.json", "p.html")
    assert path.parent == tmp_path and launcher.read_waiting_record(tmp_path, "../../evil")["page"] == "p.html"


def run_stop_hook(stdin, env):
    done = subprocess.run([sys.executable, str(STOP_HOOK)], input=stdin, capture_output=True, text=True,
                          encoding="utf-8", env=env, check=False)
    return done.returncode, done.stdout


def hook_env(data_home, **extra):
    return {**os.environ, "LOCALAPPDATA": str(data_home), **extra}


def test_with_no_record_the_stop_hook_returns_nothing(data_home):
    assert run_stop_hook(json.dumps({"session_id": "t-1", "stop_hook_active": False}), hook_env(data_home)) == (0, "")


@pytest.mark.parametrize("stdin", ["", "not json", "[]", "{}"])
def test_the_stop_hook_ignores_input_it_cannot_read(data_home, stdin):
    assert run_stop_hook(stdin, hook_env(data_home)) == (0, "")


def test_with_a_record_and_a_queued_answer_the_hook_blocks_with_the_raw_text(tmp_path, data_home, monkeypatch):
    folder = data_home / "afkv2"
    launcher.write_waiting_record(folder, "t-1", "d.json", "p.html")
    raw = 'line one\n  "two" \\ é'
    seen = []

    def poll(argv):
        seen.append(argv)
        return "feedback", {"raw": raw}

    monkeypatch.setattr(codex_stop, "wait_for_answer", partial(WAIT_FOR_ANSWER, poll=poll))
    out = json.loads(codex_stop.main(json.dumps({"session_id": "t-1"})))
    assert out == {"decision": "block", "reason": raw}
    assert seen[0][:2] == ["poll", "p.html"] and seen[0][2] == "--timeout-ms" and int(seen[0][3]) <= 60_000
    assert launcher.read_waiting_record(folder, "t-1") is None
    assert codex_stop.main(json.dumps({"session_id": "t-1"})) is None


WAIT_FOR_ANSWER = codex_stop.wait_for_answer


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def scripted_poll(clock, statuses, step=60):
    remaining = list(statuses)
    seen = []

    def poll(argv):
        seen.append(argv)
        clock.now += step
        status = remaining.pop(0) if remaining else "waiting"
        return status, {"raw": "answer" if status == "feedback" else "", "code": None}

    poll.seen = seen
    return poll


def test_the_wait_goes_on_past_waiting_and_a_closed_browser():
    clock = Clock()
    poll = scripted_poll(clock, ["waiting", "browser_disconnected", "error", "waiting", "feedback"])
    assert WAIT_FOR_ANSWER("p.html", poll=poll, sleep=clock.sleep, clock=clock) == ("feedback", "answer")
    assert len(poll.seen) == 5


def test_the_wait_stops_at_3600_seconds():
    clock = Clock()
    poll = scripted_poll(clock, [])
    assert WAIT_FOR_ANSWER("p.html", poll=poll, sleep=clock.sleep, clock=clock) == ("timeout", "")
    assert clock.now == 3600 and codex_stop.WAIT_SECONDS == 3600
    assert int(poll.seen[-1][3]) == 60_000


@pytest.mark.parametrize("status", ["ended", "fallback", "no-session"])
def test_the_wait_ends_when_no_answer_can_come(status):
    clock = Clock()
    poll = scripted_poll(clock, [status])
    assert WAIT_FOR_ANSWER("p.html", poll=poll, sleep=clock.sleep, clock=clock)[0] == status
    assert len(poll.seen) == 1


def test_no_answer_gives_a_warning_that_names_the_fallback_and_no_block(data_home, monkeypatch):
    folder = data_home / "afkv2"
    launcher.write_waiting_record(folder, "t-1", "d.json", "p.html")
    monkeypatch.setattr(codex_stop, "wait_for_answer", lambda page: ("timeout", ""))
    out = json.loads(codex_stop.main(json.dumps({"session_id": "t-1"})))
    assert "decision" not in out and "one chat message" in out["systemMessage"]
    assert launcher.read_waiting_record(folder, "t-1") is None


def test_poll_status_names_a_missing_session(monkeypatch):
    monkeypatch.setattr(launcher, "run", lambda argv: (1, host_fixture("host-error-missing.txt")))
    assert launcher.poll_status(["poll", "p.html"])[0] == "no-session"


def test_the_hook_file_registers_the_codex_stop_hook():
    entry = json.loads((PLUGIN / "hooks" / "hooks.json").read_text("utf-8"))["hooks"]["Stop"][0]["hooks"][0]
    assert "codex_stop.py" in entry["commandWindows"] and entry["timeout"] > 3600
    assert "codex_stop" not in " ".join([entry["command"], *entry["args"]])


def test_the_owner_has_the_stop_hook_live_check():
    steps = (PLUGIN / "tests" / "live" / "CODEX-LIVE-CHECKS.md").read_text("utf-8")
    assert "## Check 3" in steps and "10 minutes" in steps and "one chat message" in steps


# --- live seam test on the pinned host


LIVE = os.environ.get("AFKV2_TEST_LAVISH_DIR")
LIVE_NOTE = 'C:\\Users\\x back\\slash "q" trailing  \n\n  second line\ttab | pipe é 中文 \\\\double'


@pytest.mark.skipif(not LIVE, reason="AFKV2_TEST_LAVISH_DIR is not set")
def test_live_show_send_poll_and_stop_hook_on_the_pinned_host():
    """Shows a rendered fixture on a local 0.1.80, sends from Edge, reads the raw text back.

    AFKV2_TEST_LAVISH_DIR holds lavish-axi@0.1.80 and playwright-core. A playwright-core install brings an
    .exe (PrintDeps.exe): keep the folder out of Temp, or delete the .exe at once.
    """
    folder = Path(LIVE)
    work = Path(tempfile.mkdtemp(dir=os.environ.get("AFKV2_TEST_TMP")))
    repo = work / "repo"
    (repo / ".afkv2").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "specs"}), "utf-8")
    (repo / "specs" / "f" / "pages").mkdir(parents=True)
    env = {**os.environ, "PATH": f"{folder / 'node_modules' / '.bin'}{os.pathsep}{os.environ['PATH']}",
           "LOCALAPPDATA": str(work / "local"), "LAVISH_AXI_PORT": os.environ.get("AFKV2_TEST_LAVISH_PORT", "47392"),
           "LAVISH_AXI_STATE_DIR": str(work / "state"), "LAVISH_AXI_NO_OPEN": "1",
           "LAVISH_AXI_IDLE_TIMEOUT_MS": "60000", "NODE_PATH": str(folder / "node_modules")}
    env.pop("CODEX_THREAD_ID", None)
    (work / "local").mkdir()
    (work / "state").mkdir()
    doc = two_rounds()
    doc["rounds"][1]["items"] = [item("i-new", "decided"), item("i-other", "signoff")]
    path = save(repo / "specs" / "f" / "pages" / "grill-s1.json", doc)
    html = str(path.with_suffix(".html").resolve())

    tab = None

    def send(item_id):
        tab.stdin.write(f"{item_id}\n")
        tab.stdin.flush()
        line = tab.stdout.readline().strip()
        assert line == f"sent {item_id}", line + tab.stderr.read()

    try:
        code, shown = run_engine("show", path, "--no-open", env=env)
        assert code == 0, shown
        assert shown["url"].startswith(f"http://127.0.0.1:{env['LAVISH_AXI_PORT']}/"), shown
        tab = subprocess.Popen(["node", str(FIXTURES / "send_from_edge.mjs"), shown["url"]],
                               env={**env, "AFKV2_NOTE": LIVE_NOTE, "AFKV2_SHOT": str(work / "page.png")},
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        send("i-new")
        code, answer = run_engine("poll", path, env=env)
        assert code == 0, answer
        assert answer["raw"] == f"[round R-2]\ni-new accept | {LIVE_NOTE.strip()}\ni-other \u2014"

        # The next round in the same open tab, on Codex: a waiting record and a queued answer.
        doc["rounds"][1]["state"] = "settled"
        doc["rounds"].append({"n": 3, "state": "current", "banner": banner("round 2"), "items": [item("i-third", "decided")]})
        save(path, doc)
        code, shown = run_engine("show", path, "--no-open", env={**env, "CODEX_THREAD_ID": "thread-live"})
        assert code == 0 and shown["waiting_record"], shown
        send("i-third")
        code, out = run_stop_hook(json.dumps({"session_id": "thread-live", "stop_hook_active": False}), env)
        assert code == 0 and json.loads(out) == {"decision": "block", "reason": f"[round R-3]\ni-third accept | {LIVE_NOTE.strip()}"}
        assert run_stop_hook(json.dumps({"session_id": "thread-live"}), env) == (0, "")
    finally:
        if tab:
            tab.stdin.close()
            tab.wait(timeout=30)
        script = ("import sys; sys.path[:0] = sys.argv[1:3]; import launcher; print(launcher.run(['end', sys.argv[3]]))")
        subprocess.run([sys.executable, "-c", script, str(ENGINE_DIR), str(PLUGIN / "scripts"), html], env=env,
                       capture_output=True, text=True, timeout=60, check=False)
        shot = work / "page.png"
        keep = os.environ.get("AFKV2_TEST_SHOT")
        if keep and shot.is_file():
            shutil.copy(shot, keep)
        time.sleep(1)
        shutil.rmtree(work, ignore_errors=True)

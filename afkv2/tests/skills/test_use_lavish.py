"""The use-lavish skill: the one home of the round commands, the round builder and the shared page helpers."""

import ast
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
HOME = SKILLS / "use-lavish"
MOVED = ("page_round.py", "round_document.py", "grill_common.py", "page_links.py")
ROUND_COMMANDS = {"page_round.py": ("present", "wait", "reply", "ingest", "end"),
                  "round_document.py": ("build", "apply-readings")}
PAGE_SKILLS = ("grill", "propose-solution", "to-subtasks")


def _imports(path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text("utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_moved_scripts_live_only_in_the_use_lavish_home():
    for name in MOVED:
        assert (HOME / "scripts" / name).is_file(), name
        assert not (SKILLS / "grill" / "scripts" / name).exists(), name


def test_the_new_home_holds_the_produced_symbols():
    assert "def present(doc" in (HOME / "scripts" / "page_round.py").read_text("utf-8")
    builder = (HOME / "scripts" / "round_document.py").read_text("utf-8")
    assert "def build_round_document(" in builder
    assert "def apply_readings(doc_path" in builder


def test_the_skill_file_has_frontmatter_and_names_its_commands():
    text = (HOME / "SKILL.md").read_text("utf-8")
    head = re.match(r"---\n(.*?)\n---\n", text, re.S).group(1)
    assert re.search(r"^name: use-lavish$", head, re.M)
    assert re.search(r"^description: .+", head, re.M)
    for script, verbs in ROUND_COMMANDS.items():
        for verb in verbs:
            assert f"scripts/{script} {verb}" in text, (script, verb)


def test_every_importer_finds_the_helpers_in_the_use_lavish_home():
    modules = {Path(name).stem for name in MOVED}
    importers = [path for path in SKILLS.glob("*/scripts/*.py") if _imports(path) & modules]
    assert importers
    for path in importers:
        if path.parent != HOME / "scripts":
            assert '"use-lavish"' in path.read_text("utf-8"), path


def test_the_page_skills_run_every_round_command_from_the_use_lavish_home():
    for skill in PAGE_SKILLS:
        for name in ("SKILL.md", "CODEX-LIVE-CHECK.md"):
            text = (SKILLS / skill / name).read_text("utf-8")
            for script in ROUND_COMMANDS:
                for line in [line for line in text.splitlines() if script in line]:
                    assert f"use-lavish/scripts/{script}" in line, (skill, name, line)
                    assert "grill/scripts" not in line, (skill, name, line)


# ---- the builder writes page format 1 (SDD §14 row "Page format"; ADR-0002 design)

import json  # noqa: E402
import sys  # noqa: E402

for _folder in (HOME / "scripts", SKILLS / "grill" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
    sys.path.insert(0, str(_folder))

import engine  # noqa: E402
import grill_log  # noqa: E402
import round_document as rd  # noqa: E402

SESSION = {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1"}


def a_card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "body": {"type": "text", "id": f"{item_id}-body", "props": {"text": "x"}},
            **extra}


def round_input(*item_ids):
    return {"banner": {"settled": [], "unlocks": [], "parked": []}, "items": [a_card(i) for i in item_ids]}


def engine_answer(capsys, *args):
    code = engine.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def ingest(capsys, path, raw):
    raw_file = path.with_name("raw.txt")
    raw_file.write_text(raw, "utf-8")
    code, answer = engine_answer(capsys, "ingest", path, "--raw-file", raw_file)
    assert code == 0, answer
    return answer


def test_the_builder_writes_format_1(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a"))
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == "afkv2.page/1" and doc["notes"] == []
    assert doc["session"]["step"] == "Requirements grill"
    assert doc["session"]["private"] is False and doc["session"]["takeovers"] == []
    assert engine_answer(capsys, "check", path)[0] == 0


def test_the_next_round_of_a_live_format_0_page_is_written_as_format_1(tmp_path, capsys):
    note = {"id": "N-1-i-a-1", "round": 1, "target": "i-a", "text": "why", "deleted": False}
    settled = {"by": "note", "round": 1, "signal": "N-1-i-a-1", "reading": "Yes."}
    item = {**rd._item(a_card("i-a"), set(), []), "state": "settled_by_note", "settled": settled, "notes": [note]}
    raw, signal = "[round R-1]\ni-a — | why", {"target": "i-a", "item": "i-a", "note": "N-1-i-a-1"}
    signal["stamp"] = engine.invariants.ingest_stamp("s-1", 1, "2026-01-05T10:00:00Z", raw, signal)
    v0 = {"schema": "afkv2.page/0", "session": {**SESSION, "started": "2026-01-05T09:00:00Z"}, "maps": [],
          "rounds": [{"n": 1, "state": "current", "banner": round_input()["banner"], "items": [item],
                      "responses": [{"received": "2026-01-05T10:00:00Z", "raw": raw, "signals": [signal]}]}]}
    path = tmp_path / "pages" / "grill-s-1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(v0), "utf-8")
    assert engine_answer(capsys, "check", path)[0] == 0
    rd.build_round_document(path, SESSION, round_input("i-b"))
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == "afkv2.page/1"
    assert doc["notes"] == [{**note, "item": "i-a"}]
    assert all("notes" not in r and all("notes" not in i for i in r["items"]) for r in doc["rounds"])
    assert engine_answer(capsys, "check", path)[0] == 0


def test_the_round_pass_and_the_readings_read_the_session_list(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a"))
    ingest(capsys, path, "[round R-1]\ni-a note 1\n  why\ni-a note 2\n  and how")
    pending = rd.pending(json.loads(path.read_text("utf-8")))
    assert [n["id"] for n in pending["needs_reading"][0]["notes"]] == ["N-1-i-a-1", "N-1-i-a-2"]
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}]})
    doc = json.loads(path.read_text("utf-8"))
    assert doc["rounds"][0]["items"][0]["state"] == "settled_by_note"
    assert engine_answer(capsys, "check", path)[0] == 0


def test_the_grill_log_rows_from_notes_read_the_session_list(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a"))
    ingest(capsys, path, "[round R-1]\ni-a note 1\n  why\nR-1 note 1\n  a steer")
    rows = [line for row in grill_log._document_rows(json.loads(path.read_text("utf-8"))) for line in row]
    assert '  owner note on i-a (N-1-i-a-1): "why"' in rows
    assert '- Steer: R-1 (N-1-R-1-1): "a steer"' in rows


# ---- answers, change lists, warnings and take-over (SDD §3 rows "build", "apply-readings", "take-over")

import pytest  # noqa: E402

from grill_common import Refusal  # noqa: E402


def a_noted_round(tmp_path, capsys, raw="[round R-1]\ni-a note 1\n  why\ni-a note 2\n  and how\ni-b note 1\n  same"):
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a", "i-b"))
    ingest(capsys, path, raw)
    return path


def read(path):
    return json.loads(path.read_text("utf-8"))


def test_a_reply_is_an_answer_with_an_id_its_notes_and_what_it_changed(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {
        "settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both.", "changed": ["i-b-body"]}],
        "replies": [{"text": "One answer.", "notes": ["N-1-i-a-1", "N-1-i-b-1"]}]})
    rd.apply_readings(path, {"replies": [{"text": "And more.", "notes": ["N-1-i-b-1"], "changed": ["i-a"]}]})
    assert read(path)["rounds"][0]["replies"] == [
        {"id": "A-1-1", "text": "Settled by your note: Both.", "notes": ["N-1-i-a-2"], "changed": ["i-b-body"]},
        {"id": "A-1-2", "text": "One answer.", "notes": ["N-1-i-a-1", "N-1-i-b-1"]},
        {"id": "A-1-3", "text": "And more.", "notes": ["N-1-i-b-1"], "changed": ["i-a"]}]
    assert engine_answer(capsys, "check", path)[0] == 0


def test_a_round_input_reply_is_an_answer_of_the_new_round(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"open": [{"item": "i-a", "reply": "Asked again."}, {"item": "i-b", "reply": "Again."}]})
    built = {**round_input("i-c"), "replies": [{"text": "Covered.", "notes": ["N-1-i-a-1", "N-1-i-a-2"]}]}
    built["items"][0]["carries"] = ["i-a", "i-b"]
    rd.build_round_document(path, SESSION, built)
    doc = read(path)
    assert doc["rounds"][0]["replies"] == [{"id": "A-1-1", "text": "Asked again.", "notes": ["N-1-i-a-1", "N-1-i-a-2"]},
                                           {"id": "A-1-2", "text": "Again.", "notes": ["N-1-i-b-1"]}]
    assert doc["rounds"][1]["replies"] == [{"id": "A-2-1", "text": "Covered.", "notes": ["N-1-i-a-1", "N-1-i-a-2"]}]
    assert engine_answer(capsys, "check", path)[0] == 0


@pytest.mark.parametrize("reply", [{"text": "x", "about": ["i-a"]}, {"text": "x"}, {"text": "x", "notes": []},
                                   {"notes": ["N-1-i-a-1"]}, {"text": "x", "notes": ["N-1-i-a-1"], "id": "A-1-9"}])
def test_a_reply_that_is_not_text_notes_and_changed_is_refused(tmp_path, capsys, reply):
    path = a_noted_round(tmp_path, capsys)
    before = path.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.apply_readings(path, {"replies": [reply]})
    assert refused.value.code == "bad-reply"
    assert path.read_bytes() == before


def test_the_round_input_writes_the_short_title_the_step_and_what_changed(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    answer = rd.build_round_document(path, SESSION, {**round_input("i-a"), "short_title": "Order export",
                                                     "step": "Format questions", "changed": ["i-a-body"]})
    doc = read(path)
    assert (doc["session"]["short_title"], doc["session"]["step"]) == ("Order export", "Format questions")
    assert doc["rounds"][0]["changed"] == ["i-a-body"] and answer["warnings"] == []
    assert engine_answer(capsys, "check", path)[0] == 0


def test_a_short_title_in_a_later_round_is_ignored_with_a_warning(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys, raw="[round R-1]\ni-a accept\ni-b accept")
    answer = rd.build_round_document(path, SESSION, {**round_input("i-c"), "short_title": "Another title",
                                                     "step": "Later step"})
    doc = read(path)
    assert doc["session"].get("short_title") is None and doc["session"]["step"] == "Later step"
    assert [warning["code"] for warning in answer["warnings"]] == ["ignored-title"]
    assert engine_answer(capsys, "check", path)[0] == 0


@pytest.mark.parametrize("field", [{"short_title": "x" * 41}, {"step": ""}, {"changed": "i-a"}])
def test_a_bad_title_step_or_change_list_is_refused(tmp_path, field):
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(tmp_path / "pages" / "grill-s-1.json", SESSION, {**round_input("i-a"), **field})
    assert refused.value.code == "bad-round"
    assert not (tmp_path / "pages" / "grill-s-1.json").exists()


def a_round_2(path, replies=()):
    built = {**round_input("i-c"), "replies": list(replies)}
    built["items"][0]["carries"] = ["i-b"]
    return rd.build_round_document(path, SESSION, built)


def test_a_note_of_the_last_round_with_no_answer_is_warned_and_the_round_still_builds(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}],
                             "open": [{"item": "i-b", "reply": "Asked again."}]})
    answer = a_round_2(path)
    assert answer["round"] == 2 and len(read(path)["rounds"]) == 2
    assert [(w["code"], w["note"]) for w in answer["warnings"]] == [("unanswered-note", "N-1-i-a-1")]


def test_a_note_answered_in_the_new_round_is_not_warned(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}],
                             "open": [{"item": "i-b", "reply": "Asked again."}]})
    assert a_round_2(path, [{"text": "Yes.", "notes": ["N-1-i-a-1"]}])["warnings"] == []


def test_an_answer_about_a_card_on_an_upgraded_page_answers_its_notes():
    doc = {"notes": [{"id": "N-1-i-a", "round": 1, "target": "i-a-body", "item": "i-a", "text": "x", "deleted": False},
                     {"id": "N-1-i-b", "round": 1, "target": "i-b", "item": "i-b", "text": "y", "deleted": True}],
           "rounds": [{"n": 1, "replies": [{"text": "old", "about": ["i-a"]}]}]}
    assert rd.unanswered_note_warnings(doc, 1) == []


@pytest.mark.parametrize("extra", [{"replies": [{"text": "x", "notes": ["N-9-i-z-1"]}]},
                                   {"replies": [{"text": "x", "notes": ["N-1-i-a-1"], "changed": ["i-nothing"]}]},
                                   {"changed": ["i-nothing"]}])
def test_a_build_with_an_id_that_names_nothing_is_refused(tmp_path, capsys, extra):
    path = a_noted_round(tmp_path, capsys, raw="[round R-1]\ni-a note 1\n  why\ni-b accept")
    rd.apply_readings(path, {"open": [{"item": "i-a", "reply": "Again."}]})
    before = path.read_bytes()
    built = {**round_input("i-c"), **extra}
    built["items"][0]["carries"] = ["i-a"]
    with pytest.raises(Refusal) as refused:
        rd.build_round_document(path, SESSION, built)
    assert refused.value.code == "bad-link" and path.read_bytes() == before


@pytest.mark.parametrize("readings", [{"replies": [{"text": "x", "notes": ["N-1-i-z-1"]}]},
                                      {"replies": [{"text": "x", "notes": ["N-1-i-a-1"], "changed": ["nothing"]}]},
                                      {"settle": [{"item": "i-a", "note": "N-1-i-a-1", "reading": "r", "changed": ["nothing"]}]}])
def test_apply_readings_with_an_id_that_names_nothing_is_refused(tmp_path, capsys, readings):
    path = a_noted_round(tmp_path, capsys)
    before = path.read_bytes()
    with pytest.raises(Refusal) as refused:
        rd.apply_readings(path, readings)
    assert refused.value.code == "bad-link" and path.read_bytes() == before


def test_an_answer_may_name_a_card_a_component_and_a_banner(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"replies": [{"text": "x", "notes": ["N-1-i-a-1"], "changed": ["i-a", "i-b-body", "R-1"]}]})
    assert engine_answer(capsys, "check", path)[0] == 0

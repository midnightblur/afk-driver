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
PAGE_SKILLS = ("grill-requirements", "propose-solution", "to-subtasks")


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
        assert not (SKILLS / "grill-requirements" / "scripts" / name).exists(), name


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
                    assert "grill-requirements/scripts" not in line, (skill, name, line)


# ---- the builder writes page format 1 (SDD §14 row "Page format"; ADR-0002 design)

import json  # noqa: E402
import sys  # noqa: E402

for _folder in (HOME / "scripts", SKILLS / "grill-requirements" / "scripts", PLUGIN / "scripts", PLUGIN / "engine"):
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


def test_the_builder_writes_format_2(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a"))
    doc = json.loads(path.read_text("utf-8"))
    assert doc["schema"] == "afkv2.page/2" and doc["notes"] == []
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


def a_noted_round(tmp_path, capsys, raw="[round R-1]\ni-a note 1\n  why\ni-a note 2\n  and how\ni-b note 1\n  same",
                  version_1=False):
    """A new page with cards i-a and i-b, answered with `raw`. `version_1` relabels it as the version 1 page of an
    older session, which warns about a note with no answer instead of refusing the next round."""
    path = tmp_path / "pages" / "grill-s-1.json"
    rd.build_round_document(path, SESSION, round_input("i-a", "i-b"))
    if version_1:
        path.write_text(json.dumps({**json.loads(path.read_text("utf-8")), "schema": "afkv2.page/1"}), "utf-8")
    ingest(capsys, path, raw)
    return path


def read(path):
    return json.loads(path.read_text("utf-8"))


def test_a_reply_is_an_answer_with_an_id_its_notes_and_what_it_changed(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {
        "settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both.", "changed": ["i-b-body"]}],
        "replies": [{"text": "One answer.", "notes": ["N-1-i-a-1"]}]})
    rd.apply_readings(path, {"replies": [{"text": "And more.", "notes": ["N-1-i-b-1"], "changed": ["i-a"]}]})
    assert read(path)["rounds"][0]["replies"] == [
        {"id": "A-1-1", "text": "Settled by your note: Both.", "notes": ["N-1-i-a-2"], "changed": ["i-b-body"]},
        {"id": "A-1-2", "text": "One answer.", "notes": ["N-1-i-a-1"]},
        {"id": "A-1-3", "text": "And more.", "notes": ["N-1-i-b-1"], "changed": ["i-a"]}]
    assert engine_answer(capsys, "check", path)[0] == 0


def test_a_round_input_reply_is_an_answer_of_the_new_round(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"open": [{"item": "i-a", "note": "N-1-i-a-1", "reply": "Asked again."},
                                      {"item": "i-b", "note": "N-1-i-b-1", "reply": "Again."}]})
    built = {**round_input("i-c"), "replies": [{"text": "Covered.", "notes": ["N-1-i-a-2"]}]}
    built["items"][0]["carries"] = ["i-a", "i-b"]
    rd.build_round_document(path, SESSION, built)
    doc = read(path)
    assert doc["rounds"][0]["replies"] == [{"id": "A-1-1", "text": "Asked again.", "notes": ["N-1-i-a-1"]},
                                           {"id": "A-1-2", "text": "Again.", "notes": ["N-1-i-b-1"]}]
    assert doc["rounds"][1]["replies"] == [{"id": "A-2-1", "text": "Covered.", "notes": ["N-1-i-a-2"]}]
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
    path = a_noted_round(tmp_path, capsys, version_1=True)
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}],
                             "open": [{"item": "i-b", "reply": "Asked again."}]})
    answer = a_round_2(path)
    assert answer["round"] == 2 and len(read(path)["rounds"]) == 2
    assert [(w["code"], w["note"]) for w in answer["warnings"]] == [("unanswered-note", "N-1-i-a-1")]


def test_a_note_answered_in_the_new_round_is_not_warned(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}],
                             "open": [{"item": "i-b", "note": "N-1-i-b-1", "reply": "Asked again."}]})
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


def test_build_runs_with_no_ticket(tmp_path, capsys):
    path = tmp_path / "pages" / "grill-s-1.json"
    round_file = tmp_path / "round.json"
    round_file.write_text(json.dumps({**round_input("i-a"), "short_title": "No ticket"}), "utf-8")
    answer = rd.main(["build", "--doc", str(path), "--session", "s-1", "--round-input", str(round_file)])
    assert answer["ok"] and answer["round"] == 1
    session = read(path)["session"]
    assert session["ticket"] is None and session["short_title"] == "No ticket"


import page_round  # noqa: E402


def test_take_over_records_one_takeover_per_round(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys, raw="[round R-1]\ni-a accept\ni-b accept")
    answer = page_round.main(["take-over", "--doc", str(path)])
    takeovers = read(path)["session"]["takeovers"]
    assert len(takeovers) == 1 and takeovers[0]["round"] == 1
    assert answer == {"ok": True, "session": "s-1", "round": 1, "takeovers": takeovers}
    before = path.read_bytes()
    assert page_round.take_over(path)["takeovers"] == takeovers
    assert path.read_bytes() == before
    assert engine_answer(capsys, "check", path)[0] == 0
    rd.build_round_document(path, SESSION, round_input("i-c"))
    assert [entry["round"] for entry in page_round.take_over(path)["takeovers"]] == [1, 2]


@pytest.mark.parametrize("content", [None, "not json", "{}", "[]", '{"schema": "afkv2.page/9"}'])
def test_take_over_of_an_unreadable_document_is_refused(tmp_path, content):
    path = tmp_path / "pages" / "grill-s-1.json"
    if content is not None:
        path.parent.mkdir()
        path.write_text(content, "utf-8")
    with pytest.raises(Refusal) as refused:
        page_round.take_over(path)
    assert refused.value.code == "unreadable"
    assert content is None or path.read_text("utf-8") == content


def test_take_over_of_a_format_0_page_writes_format_1(tmp_path, capsys):
    v0 = {"schema": "afkv2.page/0", "session": {**SESSION, "started": "2026-01-05T09:00:00Z"}, "maps": [],
          "rounds": [{"n": 1, "state": "current", "banner": round_input()["banner"],
                      "items": [rd._item(a_card("i-a"), set(), [])]}]}
    path = tmp_path / "pages" / "grill-s-1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(v0), "utf-8")
    assert engine_answer(capsys, "check", path)[0] == 0
    assert [entry["round"] for entry in page_round.take_over(path)["takeovers"]] == [1]
    assert read(path)["schema"] == "afkv2.page/1"
    assert engine_answer(capsys, "check", path)[0] == 0


def test_an_older_about_answer_does_not_answer_a_later_note():
    doc = {"notes": [{"id": "N-3-i-a-1", "round": 3, "target": "i-a", "item": "i-a", "text": "x", "deleted": False}],
           "rounds": [{"n": 1, "replies": [{"text": "old", "about": ["i-a"]}]}, {"n": 2}, {"n": 3}]}
    assert [w["note"] for w in rd.unanswered_note_warnings(doc, 3)] == ["N-3-i-a-1"]


def test_an_open_entry_keeps_what_it_changed(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys)
    rd.apply_readings(path, {"open": [{"item": "i-a", "reply": "Again.", "changed": ["i-a-body"]}]})
    assert read(path)["rounds"][0]["replies"][0]["changed"] == ["i-a-body"]
    with pytest.raises(Refusal) as refused:
        rd.apply_readings(path, {"open": [{"item": "i-b", "reply": "Again.", "changed": ["nothing"]}]})
    assert refused.value.code == "bad-link"


def test_only_the_notes_of_the_last_round_are_warned(tmp_path, capsys):
    path = a_noted_round(tmp_path, capsys, version_1=True)
    rd.apply_readings(path, {"settle": [{"item": "i-a", "note": "N-1-i-a-2", "reading": "Both."}],
                             "open": [{"item": "i-b", "reply": "Asked again."}]})
    assert [w["note"] for w in a_round_2(path)["warnings"]] == ["N-1-i-a-1"]
    ingest(capsys, path, "[round R-2]\ni-c accept\nR-2 note 1\n  a steer")
    warned = rd.build_round_document(path, SESSION, round_input("i-d"))["warnings"]
    assert [w["note"] for w in warned] == ["N-2-R-2-1"]


# ---- the skill text: page rules, answer rules, forms by kind, page or chat (PRD Catalog; SDD §8 row "use-lavish
# skill: instructions"). The quality of the rules is proved by a dogfood run; these tests pin where they live.

SKILL_MD = HOME / "SKILL.md"
ROUND_PASS_MD = HOME / "ROUND-PASS.md"
RETIRED_KINDS = (30, 31, 32, 43)
STEP_LINE = re.compile(r"^ *```sh step=([\w-]+)\n *(.*?)\n *```", re.S | re.M)


def _section(text, heading):
    """The text under `heading` up to the next heading of the same or a higher level."""
    level = heading.split(" ", 1)[0]
    start = text.index(heading + "\n")
    rest = text[start + len(heading) + 1:]
    stop = re.search(rf"^#{{1,{len(level)}}} ", rest, re.M)
    return rest[:stop.start()] if stop else rest


def _table_ids(text, prefix):
    return re.findall(rf"^\| ({prefix}-\d\d) \|", text, re.M)


def test_the_skill_holds_the_four_tables_with_every_id():
    text = SKILL_MD.read_text("utf-8")
    assert _table_ids(_section(text, "### Page rules"), "PR") == [f"PR-{k:02}" for k in range(1, 16)]
    assert _table_ids(_section(text, "### Answer rules"), "AR") == [f"AR-{k:02}" for k in range(1, 11)]
    forms = [f"K-{k:02}" for k in range(1, 54) if k not in RETIRED_KINDS]
    assert _table_ids(_section(text, "### Forms by kind"), "K") == forms
    assert _table_ids(_section(text, "### Refinements"), "RF") == [f"RF-{k:02}" for k in range(1, 10)]


def test_table_k_holds_no_retired_kind():
    """PRD AC-007: for goals, open questions, quality requirements and guarantees the agent picks a form."""
    text = SKILL_MD.read_text("utf-8")
    for k in RETIRED_KINDS:
        assert f"K-{k}" not in text
    assert "retired" not in text


def test_an_answer_holds_no_copy_of_the_note():
    """PRD AC-017, AR-09; ADR-0004 requirements: one note, one row."""
    rules = _section(SKILL_MD.read_text("utf-8"), "### Answer rules")
    assert "| AR-09 | Never repeat the human's note in the reply, steers included" in rules
    assert "| AR-10 | Each note gets its own row." in rules


def test_another_form_than_table_k_states_why_in_one_line():
    forms = _section(SKILL_MD.read_text("utf-8"), "### Forms by kind")
    assert "state on the page in one line why" in forms


def test_page_or_chat_and_the_hands_off_rule():
    """PRD AC-008, AC-009."""
    rule = _section(SKILL_MD.read_text("utf-8"), "## Page or chat")
    assert "Offer a page for options side by side, a picture, or 3 or more questions." in rule
    assert "Ask a one-line question in chat." in rule
    assert "hands-off subagent" in rule and "open no page, and park the question" in rule


def test_the_skill_lists_every_page_command():
    """The 0006 IOU: start, track and present --scan have their caller here; take-over too."""
    commands = _section(SKILL_MD.read_text("utf-8"), "## The commands")
    for command in ("scripts/page_home.py start --topic", "scripts/page_home.py track --doc",
                    "scripts/page_round.py present --doc D [--scan F]... [--no-show]",
                    "scripts/page_round.py take-over --doc"):
        assert command in commands, command


def test_an_ad_hoc_page_needs_a_topic_and_starts_by_the_home_rule():
    """PRD AC-001, AC-002."""
    steps = _section(SKILL_MD.read_text("utf-8"), "## An ad-hoc page")
    assert "ask in chat what the page is about, and open no page" in steps
    assert "page_home.py start" in steps and "--private" in steps


def test_the_notices_reach_chat_and_track_moves_the_page():
    """PRD AC-047, AC-048, AC-049, AC-053."""
    text = SKILL_MD.read_text("utf-8")
    shown = _section(text, "## After each show")
    for word in ("git_state", "secrets", "secrets_more", "scan_cut", "no known shape"):
        assert word in shown, word
    track = _section(text, "## Track a page")
    for word in ("page_home.py track", "needs-ticket", "private", "commit"):
        assert word in track, word


def test_the_diagram_counts_reach_chat_when_a_diagram_shows_as_text():
    """Ruling D-52: present answers `diagrams`; this line is its reader."""
    shown = _section(SKILL_MD.read_text("utf-8"), "## After each show")
    line = next((row for row in shown.splitlines() if "`diagrams`" in row), "")
    for word in ("as_text", "rendered", "cached", "reason"):
        assert word in line, word


def test_a_resuming_session_takes_the_page_over():
    """PRD AC-054; SDD §7 "Take over a page"; SDD §14 row "Log rows of a takeover"."""
    steps = _section(SKILL_MD.read_text("utf-8"), "## Take over a page")
    assert "page_round.py take-over" in steps
    assert "- Takeover: R<n> · <at>" in steps
    assert "every note that has no reply" in steps


# The round pass moved here from the visualize guide (SDD §14 row "visualize guide"): a changed sentence must fail.
ROUND_PASS = """
When the human sends a round, the engine settles a point with one `accept`,
`sign` or option mark. It moves a point to `needs_reading` on `reopen`,
`changes`, a write-in, a note, a mark plus a note, or 2 marks. On a card that is
already settled, a signal that changes the answer sets `state` to `open` and
removes `settled`, and a note stays on that card, also in a settled round. Its
signal has `reopened: true`. Before you mark the round `settled`, go through the
cards of the current round. Never change a card in a settled round: only the
engine writes there. A steer lives on the round, and its signal has `steer: true`
and no `item`: leave it out when you read the signals, because it settles nothing.

- `needs_reading` with a clear note and no signal that disagrees with it: set
  `state` to `settled_by_note` and write `settled`, for example `{"by": "note", "round": 2, "signal": "N-2-i-format", "reading": "Picks CSV."}`.
  The `signal` is the note id. A note that leaves the answer open is not a clear
  note. A `signoff` card settles only by a `sign` mark: a note on it is never a clear
  note, even when it keeps the wording, and `apply-readings` refuses that reading. The
  new card asks the human to sign. A note on an `info` card is not a
  clear note: it answers nothing, so it gets a reply only. A `reopen` or `changes`
  mark always disagrees.
- `needs_reading` in any other case: set `state` to `open`. A write-in has no note
  id, so it cannot settle by note: the new card for that point is a `confirm` card
  that states the write-in as your reading.
- `blocked` with the point it waits on now settled: set `state` to `open`.

Then mark the round `settled` and append the next round. Make one new card for
each point that returns:

- a `decided`, `confirm`, `debate` or `signoff` card of the round you settled that
  is still `open` or `blocked`;
- a `decided`, `confirm`, `debate` or `signoff` card of an earlier round that the
  human noted or reopened in this send.

The new card has a new id. Its `carries` lists each old card id; each id must be
a card of an earlier round. Its body shows the signals that returned the point,
for example both the mark and the note. A carried
`blocked` card names the current card id of the point it waits on. An `info` card
stays in its round. The old card stays as it is.
"""
SETTLED_FIELDS = {"by", "round", "signal", "reading"}


def test_the_round_pass_lives_here_word_for_word():
    found = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the cards")
    assert found.split() == ROUND_PASS.split()


def test_the_settled_example_has_the_schema_shape():
    found = re.findall(r"`(\{\"by\": .*?\})`", ROUND_PASS_MD.read_text("utf-8"))
    assert found, "ROUND-PASS.md has no settled example"
    for raw in found:
        settled = json.loads(raw)
        assert set(settled) == SETTLED_FIELDS and settled["by"] == "note"
        assert settled["signal"].startswith(f"N-{settled['round']}-")


def test_the_note_reading_answers_by_the_rules_and_repeats_no_steer():
    """SDD §14 row "visualize guide": the text that groups notes or repeats a steer goes."""
    notes = _section(ROUND_PASS_MD.read_text("utf-8"), "## Read the notes")
    assert "answer rules" in notes and "Read every note" in notes
    for gone in ("word for word", "group of notes", "per group"):
        assert gone not in notes, gone


def test_each_page_skill_points_here_and_scans_its_files():
    """PRD AC-003, AC-004; the 0006 IOU: each page skill passes --scan where it presents a round."""
    for skill in PAGE_SKILLS:
        text = (SKILLS / skill / "SKILL.md").read_text("utf-8")
        assert "../use-lavish/SKILL.md" in text and "../use-lavish/ROUND-PASS.md" in text, skill
        assert "visualize/components/card.md" not in text and "notes-and-replies" not in text, skill
        assert "answer rules of `/afkv2:use-lavish`" in text and '"Take over a page"' in text, skill
        scan = '--scan "<spec dir>/INDEX.md"' if skill == "to-subtasks" else '--scan "<log>"'
        assert dict(STEP_LINE.findall(text))["present"].endswith(scan), skill
    for other in (SKILLS / "grill-requirements" / "ROUNDS.md", SKILLS / "propose-solution" / "DRAFT.md"):
        text = other.read_text("utf-8")
        assert "visualize/components/card.md" not in text and "use-lavish/ROUND-PASS.md" in text, other.name


def test_the_grill_repeats_no_steer_in_an_answer():
    text = (SKILLS / "grill-requirements" / "SKILL.md").read_text("utf-8")
    assert "a steer word for word" not in text


def test_the_ad_hoc_wait_answers_side_questions_and_present_refusals_have_a_path():
    """Review r1 (correctness): a send of side questions only has no raw response; a refused present has a path."""
    steps = _section(SKILL_MD.read_text("utf-8"), "## An ad-hoc page")
    for words in ("`btw`", "scripts/page_round.py reply", "`raw_file` is null", "--replace", "round-shown",
                  "as Markdown in chat"):
        assert words in steps, words


def test_a_private_page_is_never_tracked_and_ends_only_after_track_passed():
    """Review r1 (correctness): track refuses a private page for good, so the page stays shown."""
    track = _section(SKILL_MD.read_text("utf-8"), "## Track a page")
    assert "A private page cannot be tracked" in track
    assert track.index("A private page cannot be tracked") < track.index("Run `end`") < track.index("page_home.py track")


def test_one_term_for_the_json_a_command_prints():
    """Review r1 (rules): 'answer' is the reply to a note; a command prints its result; the human sends a round."""
    text = SKILL_MD.read_text("utf-8")
    head = text[:text.index("## The rules")]
    assert "Every result is one JSON object" in head
    for gone in ("Every answer is one JSON object", "answers `doc`", "answers ok", "the answer holds"):
        assert gone not in head, gone

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

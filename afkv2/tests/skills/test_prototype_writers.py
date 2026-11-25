"""The sole writer of PROTOTYPE.md and the INDEX Prototype row, and the owner checklist (ticket 207).

VR-030 (PRD AC-030): only skills/prototype writes PROTOTYPE.md and the INDEX.md Prototype row; the readers only read.
VR-031: afkv2/tests/live/PROTOTYPE-LIVE-CHECKS.md holds 1 real-session check per moved plan row.
Each search also runs on a planted violation in a temp folder, so a test proves that it can fail.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
OWNER = "skills/prototype/"
FILE_NAME = "PROTOTYPE.md"
ROW = "Prototype"
SKIPPED = {"__pycache__", "tests"}
WRITE_METHODS = {"write_text", "write_bytes", "unlink", "rename", "replace", "touch"}
WRITE_FUNCTIONS = {"write_text", "write_bytes", "set_row"}
COPY_FUNCTIONS = {"copy", "copy2", "copyfile", "move"}
PROSE_WRITE = re.compile(r"\b(write|writes|writing|set|sets|update|updates|edit|edits|change|changes)\b", re.IGNORECASE)
CHECKLIST = PLUGIN / "tests" / "live" / "PROTOTYPE-LIVE-CHECKS.md"
MOVED = ["VR-001", "VR-002", "VR-003", "VR-018", "VR-004", "VR-005", "VR-006", "VR-016", "VR-022", "VR-025", "VR-026"]
HEADING = "## Owner live checks — the real-session checks the owner runs before Ready"


def _sources(root, suffix):
    for path in sorted(root.rglob(f"*{suffix}")):
        relative = path.relative_to(root)
        if not SKIPPED.intersection(relative.parts):
            yield path, relative.as_posix()


def _constants(tree):
    """{name: str value} of each module-level `NAME = "text"`."""
    found = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            found.update({target.id: node.value.value for target in node.targets if isinstance(target, ast.Name)})
    return found


def _called(call):
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", None)


def row_writers(root):
    """{artifact: [file]} of each `set_row(index, artifact, ...)` call; an artifact that is no string constant is `?`."""
    writers = {}
    for path, name in _sources(root, ".py"):
        tree = ast.parse(path.read_text("utf-8"))
        constants = _constants(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called(node) == "set_row" and len(node.args) > 1:
                arg = node.args[1]
                artifact = (arg.value if isinstance(arg, ast.Constant) else constants.get(getattr(arg, "id", None), "?"))
                writers.setdefault(artifact, []).append(name)
    return writers


def _tainted(node, names):
    return any((isinstance(sub, ast.Name) and sub.id in names) or (isinstance(sub, ast.Constant) and sub.value == FILE_NAME)
               for sub in ast.walk(node))


def _taint(scope, names):
    """`names` plus each name an assignment in `scope` binds to a value built from one of them, to a fixed point."""
    names = set(names)
    while True:
        before = len(names)
        for node in ast.walk(scope):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                pairs = (zip(target.elts, node.value.elts) if isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple)
                         and len(target.elts) == len(node.value.elts) else [(target, node.value)])
                names.update(t.id for t, v in pairs if isinstance(t, ast.Name) and _tainted(v, names))
        if len(names) == before:
            return names


def _writes(call, names):
    called = _called(call)
    if isinstance(call.func, ast.Attribute) and called in WRITE_METHODS and _tainted(call.func.value, names):
        return True
    if called in WRITE_FUNCTIONS and call.args and _tainted(call.args[0], names):
        return True
    if called in COPY_FUNCTIONS and len(call.args) > 1 and _tainted(call.args[1], names):
        return True
    if called == "open" and call.args and _tainted(call.args[0], names):
        modes = [arg for arg in call.args[1:2] if isinstance(arg, ast.Constant)]
        modes += [kw.value for kw in call.keywords if kw.arg == "mode" and isinstance(kw.value, ast.Constant)]
        return any(set(str(mode.value)) & set("wax+") for mode in modes)
    return False


def prototype_md_writes(root):
    """`file:line` of each call outside skills/prototype that writes a path built from `PROTOTYPE.md`."""
    hits = []
    for path, name in _sources(root, ".py"):
        if name.startswith(OWNER):
            continue
        tree = ast.parse(path.read_text("utf-8"))
        seeds = {key for key, value in _constants(tree).items() if value == FILE_NAME}
        for scope in [tree, *(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))]:
            names = _taint(scope, seeds)
            hits += [f"{name}:{node.lineno}" for node in ast.walk(scope)
                     if isinstance(node, ast.Call) and _writes(node, names)]
    return sorted(set(hits))


def prose_writers(root):
    """`file:line` of each prose line outside skills/prototype that names PROTOTYPE.md or the Prototype row with a
    write verb."""
    hits = []
    for path, name in _sources(root, ".md"):
        if name.startswith(OWNER):
            continue
        for number, line in enumerate(path.read_text("utf-8").splitlines(), start=1):
            if (FILE_NAME in line or f"{ROW} row" in line) and PROSE_WRITE.search(line):
                hits.append(f"{name}:{number}")
    return hits


def _plant(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# --- VR-030 (PRD AC-030): only skills/prototype writes PROTOTYPE.md and the INDEX Prototype row

def test_only_prototype_files_sets_the_index_prototype_row():
    writers = row_writers(PLUGIN / "skills")
    assert writers.get(ROW) == ["prototype/scripts/prototype_files.py"]
    assert "?" not in writers


def test_no_script_outside_the_prototype_skill_writes_prototype_md():
    assert prototype_md_writes(PLUGIN) == []


def test_no_skill_text_outside_the_prototype_skill_writes_prototype_md_or_its_row():
    assert prose_writers(PLUGIN) == []
    owners = (PLUGIN / "skills" / "to-prd" / "INDEX-FORMAT.md").read_text("utf-8")
    assert "| `Prototype` | `/afkv2:prototype` |" in owners
    skill = (PLUGIN / "skills" / "prototype" / "SKILL.md").read_text("utf-8")
    assert "Only this skill writes `PROTOTYPE.md` and the `INDEX.md` Prototype row." in skill


def test_each_writer_search_finds_a_planted_writer(tmp_path):
    _plant(tmp_path, "skills/other/scripts/rows.py",
           'ROW = "Prototype"\n\ndef go(index, name):\n    set_row(index, ROW, "PROTOTYPE.md", "x")\n    set_row(index, name, "a", "b")\n')
    _plant(tmp_path, "skills/other/scripts/files.py",
           'import shutil\nNAME = "PROTOTYPE.md"\n\ndef go(spec, other):\n    sdd, proto = spec / "SDD.md", spec / NAME\n'
           '    target = proto\n    target.write_text("x")\n    open(proto, "a")\n    open(proto).read()\n'
           '    shutil.copy(other, proto)\n    sdd.write_text("y")\n')
    _plant(tmp_path, "skills/prototype/scripts/owner.py", 'def go(spec):\n    (spec / "PROTOTYPE.md").write_text("x")\n')
    _plant(tmp_path, "skills/other/tests/test_x.py", 'def go(spec):\n    (spec / "PROTOTYPE.md").write_text("x")\n')
    _plant(tmp_path, "skills/other/SKILL.md", "Read `PROTOTYPE.md`.\nThen update `PROTOTYPE.md`.\nSet the INDEX Prototype row.\n")
    assert row_writers(tmp_path / "skills") == {"Prototype": ["other/scripts/rows.py"], "?": ["other/scripts/rows.py"]}
    assert prototype_md_writes(tmp_path) == ["skills/other/scripts/files.py:10", "skills/other/scripts/files.py:7",
                                             "skills/other/scripts/files.py:8"]
    assert prose_writers(tmp_path) == ["skills/other/SKILL.md:2", "skills/other/SKILL.md:3"]


# --- VR-031: the owner checklist holds 1 real-session check per moved plan row

def checks(text):
    """{VR id: {field: value}} of each `### VR-NNN` section under the owner heading."""
    body = text.split(HEADING, 1)[1].split("\n## ", 1)[0]
    found = {}
    for section in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
        key = section.split(" ", 1)[0]
        assert key not in found, f"{key} has 2 checks"
        found[key] = dict(re.findall(r"^- (Session|Data|Given|When|Then): (\S.*)$", section, flags=re.MULTILINE))
    return found


def test_the_owner_checklist_holds_1_real_session_check_per_moved_row():
    text = CHECKLIST.read_text("utf-8")
    found = checks(text)
    assert list(found) == MOVED
    for key, fields in found.items():
        assert set(fields) == {"Session", "Data", "Given", "When", "Then"}, key
        assert re.match(r"a real (Claude|Codex) session", fields["Session"]), key
    assert (found["VR-016"]["Session"].startswith("a real Codex session")
            and all(found[key]["Session"].startswith("a real Claude session") for key in MOVED if key != "VR-016"))
    results = re.findall(r"^\| (VR-\d{3}) \|", text.split("## Results", 1)[1], flags=re.MULTILINE)
    assert results == MOVED


def test_the_checklist_reader_finds_a_missing_field():
    text = f"{HEADING}\n\n### VR-001 — x\n\n- Session: a real Claude session\n- Given: g\n- When: w\n\n## Results\n"
    assert checks(text) == {"VR-001": {"Session": "a real Claude session", "Given": "g", "When": "w"}}

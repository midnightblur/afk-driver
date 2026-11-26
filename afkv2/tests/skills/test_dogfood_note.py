"""The milestone note of the dogfood skill: the parser, its 10 rule codes, and its agreement with NOTE-FORMAT.md."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
SKILL = AFKV2 / "skills" / "dogfood"
sys.path.insert(0, str(SKILL / "scripts"))

HEADER = "afkv2-note v1"


@pytest.fixture
def note_module():
    return importlib.import_module("dogfood_note")


@pytest.fixture
def worktree(tmp_path):
    root = tmp_path / "wt"
    for name in ("skills/lane/SKILL.md", "skills/lane/scripts/lane.py", "core/CORE.md", "hooks/hooks.json"):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("x\n", encoding="utf-8")
    return root


def milestone(wt, rows, best_effort=(), use=("Run the lane skill once.",), redo="none"):
    lines = [HEADER, "kind: milestone", "ask: Add a link to the report", "purpose: try the new lane", "changed:"]
    lines += [f"- {wt / path} | {kind} | {action} | {what}" for path, kind, action, what in rows]
    if use:
        lines += [f"use: {use[0]}", *(f"  {line}" for line in use[1:])]
    lines += [f"best-effort: {wt / path} - {what}" for path, what in best_effort]
    if redo is not None:
        lines.append(f"redo: {redo}")
    return "\n".join(lines) + "\n"


def wrap(rows=(("https://forge.example/pr/7", "feat/x", "ask 1, ask 2"),)):
    lines = [HEADER, "kind: wrap", "ask: Add a link to the report", "changes:"]
    lines += [f"- {url} | {branch} | {asks}" for url, branch, asks in rows]
    lines.append("open-asks: none")
    return "\n".join(lines) + "\n"


VALID_ROWS = {
    "CK-1": ("skills/lane/SKILL.md", "CK-1", "changed", "the lane asks once"),
    "CK-2": ("skills/lane/scripts/lane.py", "CK-2", "added", "the lane script"),
    "CK-3": ("core/CORE.md", "CK-3", "changed", "one more core rule"),
    "CK-4": ("hooks/hooks.json", "CK-4", "changed", "one more hook"),
}


@pytest.mark.parametrize("kind", sorted(VALID_ROWS))
def test_valid_milestone_parses_clean(note_module, worktree, kind):
    row = VALID_ROWS[kind]
    best = [(row[0], "the hook may not run this session")] if kind == "CK-4" else []
    text = milestone(worktree, [row], best_effort=best, use=("Run the lane skill once.", "Then read its answer."))
    note = note_module.parse(text)
    assert note_module.check(note, [str(worktree)]) == []
    assert note["header"] == HEADER
    assert (note["kind"], note["ask"], note["purpose"]) == ("milestone", "Add a link to the report", "try the new lane")
    assert note["changed"] == [{"path": str(worktree / row[0]), "kind": kind, "action": row[2], "what": row[3], "line": 6}]
    assert note["use"] == "Run the lane skill once.\nThen read its answer."
    assert note["redo"] == "none"
    expected = [{"path": str(worktree / row[0]), "what": "the hook may not run this session", "line": 9}] if best else []
    assert note["best_effort"] == expected


def test_valid_wrap_parses_clean(note_module, worktree):
    note = note_module.parse(wrap())
    assert note_module.check(note, [str(worktree)]) == []
    assert note["kind"] == "wrap"
    assert note["changes"] == [{"url": "https://forge.example/pr/7", "branch": "feat/x", "asks": "ask 1, ask 2", "line": 5}]
    assert note["open_asks"] == "none"


CK1 = VALID_ROWS["CK-1"]
CK4 = VALID_ROWS["CK-4"]


def invalid_notes(wt, outside):
    """{rule code: (note text, line of the failure)}: each note breaks only its own rule."""
    good = milestone(wt, [CK1])
    return {
        "N-HEADER": ("dogfood-note v1\n" + good.partition("\n")[2], 1),
        "N-KIND": (good.replace("kind: milestone", "kind: release"), 2),
        "N-NO-PATH": (milestone(wt, []), 5),
        "N-PATH-OUTSIDE": (good.replace(str(wt / CK1[0]), str(outside / "SKILL.md")), 6),
        "N-PATH-MISSING": (milestone(wt, [("skills/lane/GONE.md", "CK-1", "added", "a new page")]), 6),
        "N-CK": (milestone(wt, [(CK1[0], "CK-5", "changed", "the lane asks once")]), 6),
        "N-NO-USE": (milestone(wt, [CK1], use=()), 2),
        "N-NO-BEST-EFFORT": (milestone(wt, [CK1, CK4], best_effort=[(CK1[0], "not the hook")]), 7),
        "N-NO-REDO": (milestone(wt, [CK1], redo=None), 2),
        "N-NO-CHANGES": (wrap(rows=()), 4),
    }


@pytest.mark.parametrize("code", ["N-HEADER", "N-KIND", "N-NO-PATH", "N-PATH-OUTSIDE", "N-PATH-MISSING", "N-CK",
                                  "N-NO-USE", "N-NO-BEST-EFFORT", "N-NO-REDO", "N-NO-CHANGES"])
def test_invalid_note_gives_its_own_code(note_module, worktree, tmp_path, code):
    outside = tmp_path / "other"
    outside.mkdir()
    (outside / "SKILL.md").write_text("x\n", encoding="utf-8")
    text, line = invalid_notes(worktree, outside)[code]
    failures = note_module.check(note_module.parse(text), [str(worktree)])
    assert [failure["code"] for failure in failures] == [code]
    assert failures[0]["where"] == f"line {line}"
    assert failures[0]["reason"]


def test_invalid_notes_cover_every_code(note_module, worktree, tmp_path):
    assert set(invalid_notes(worktree, tmp_path)) == set(note_module.CODES)


def test_removed_path_need_not_exist(note_module, worktree):
    text = milestone(worktree, [("skills/lane/OLD.md", "CK-1", "removed", "the old page")])
    assert note_module.check(note_module.parse(text), [str(worktree)]) == []


def test_path_that_climbs_out_is_outside(note_module, worktree):
    text = milestone(worktree, [("../wt-escape/SKILL.md", "CK-1", "removed", "a page")])
    assert [f["code"] for f in note_module.check(note_module.parse(text), [str(worktree)])] == ["N-PATH-OUTSIDE"]


def test_redo_none_passes(note_module, worktree):
    note = note_module.parse(milestone(worktree, [CK1], redo="none"))
    assert note["redo"] == "none"
    assert note_module.check(note, [str(worktree)]) == []


FORMAT = SKILL / "NOTE-FORMAT.md"
EXAMPLE = "```note"


def format_examples():
    """Each fenced `note` block of NOTE-FORMAT.md, as text."""
    blocks, current = [], None
    for line in FORMAT.read_text(encoding="utf-8").splitlines():
        if current is None and line.strip() == EXAMPLE:
            current = []
        elif current is not None and line.strip() == "```":
            blocks.append("\n".join(current) + "\n")
            current = None
        elif current is not None:
            current.append(line)
    return blocks


def test_format_examples_parse_clean(note_module, tmp_path):
    examples = format_examples()
    assert {note_module.parse(text)["kind"] for text in examples} == {"milestone", "wrap"}
    root = tmp_path / "wt"
    for text in examples:
        text = text.replace("<worktree>", root.as_posix())
        note = note_module.parse(text)
        for row in note["changed"]:
            Path(row["path"]).parent.mkdir(parents=True, exist_ok=True)
            Path(row["path"]).write_text("x\n", encoding="utf-8")
        assert note_module.check(note, [str(root)]) == []


def test_format_codes_equal_module_codes(note_module):
    text = FORMAT.read_text(encoding="utf-8")
    section = text.partition("## The rule codes")[2].partition("\n## ")[0]
    table = {line.split("|")[1].strip() for line in section.splitlines() if line.startswith("| N-")}
    assert table == set(note_module.CODES)


def test_module_imports_only_the_standard_library():
    import ast

    tree = ast.parse((SKILL / "scripts" / "dogfood_note.py").read_text(encoding="utf-8"))
    names = {alias.name.partition(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module.partition(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.level]
    assert names <= set(sys.stdlib_module_names) | {"__future__"}


def codes(note_module, text, worktrees):
    return [(f["code"], f["where"]) for f in note_module.check(note_module.parse(text), worktrees)]


def test_row_after_a_scalar_joins_the_rows(note_module, worktree):
    text = milestone(worktree, [CK1]).replace("redo: none", f"- {worktree / CK4[0]} | CK-4 | changed | a hook\nredo: none")
    assert codes(note_module, text, [str(worktree)]) == [("N-NO-BEST-EFFORT", "line 8")]


def test_repeated_scalar_keeps_its_first_value(note_module, worktree):
    text = milestone(worktree, [CK1]).replace("redo: none", "use: other\n  more\nredo: none")
    best = milestone(worktree, [CK4], best_effort=[(CK4[0], "one"), (CK4[0], "two")])
    assert note_module.parse(text)["use"] == "Run the lane skill once."
    assert [entry["what"] for entry in note_module.parse(best)["best_effort"]] == ["one", "two"]


def test_failures_come_in_line_order(note_module, worktree):
    rows = [CK4, (CK1[0], "CK-5", "changed", "x")]
    text = milestone(worktree, rows, use=(), redo=None)
    assert codes(note_module, text, [str(worktree)]) == [
        ("N-NO-USE", "line 2"), ("N-NO-REDO", "line 2"), ("N-NO-BEST-EFFORT", "line 6"), ("N-CK", "line 7")]


def test_relative_path_and_worktree_root_are_outside(note_module, worktree, monkeypatch):
    monkeypatch.chdir(worktree)
    text = milestone(worktree, [CK1])
    for path in ("skills/lane/SKILL.md", str(worktree)):
        assert codes(note_module, text.replace(str(worktree / CK1[0]), path), [str(worktree)]) == [("N-PATH-OUTSIDE", "line 6")]


def test_best_effort_path_must_be_inside(note_module, worktree, tmp_path):
    text = milestone(worktree, [CK1]).replace("redo: none", f"best-effort: {tmp_path / 'elsewhere.json'} - may not apply\nredo: none")
    assert codes(note_module, text, [str(worktree)]) == [("N-PATH-OUTSIDE", "line 8")]


def test_best_effort_needs_a_reason(note_module, worktree):
    text = milestone(worktree, [CK4]).replace("redo: none", f"best-effort: {worktree / CK4[0]}\nredo: none")
    assert codes(note_module, text, [str(worktree)]) == [("N-NO-BEST-EFFORT", "line 6")]


def test_worktrees_as_1_string_and_bad_roots(note_module, worktree, monkeypatch):
    monkeypatch.chdir(worktree)
    text = milestone(worktree, [CK1])
    assert codes(note_module, text, str(worktree)) == []
    assert codes(note_module, text, ["", "."]) == [("N-PATH-OUTSIDE", "line 6")]


def test_header_allows_a_bom_but_no_padding(note_module, worktree):
    text = milestone(worktree, [CK1])
    assert codes(note_module, "\ufeff" + text, [str(worktree)]) == []
    assert codes(note_module, " " + text, [str(worktree)]) == [("N-HEADER", "line 1")]

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

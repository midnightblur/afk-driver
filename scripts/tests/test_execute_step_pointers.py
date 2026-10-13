"""Pointers to `/afk:execute` steps name the step that still holds the content."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "afk" / "execute" / "SKILL.md"
STEP = re.compile(r"^(\d+(?:\.\d+)?)\. \*\*(.+?)\*\*", re.MULTILINE)
# `execute` followed by a slash-separated step list, as registry rows cite several steps at once.
STEP_LIST = re.compile(r"execute[^|\n]{0,40}?Steps ((?:\d+(?:\.\d+)?/)+\d+(?:\.\d+)?)")


def _steps() -> dict[str, str]:
    text = SKILL.read_text(encoding="utf-8")
    heads = list(STEP.finditer(text))
    return {m.group(1): text[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            for i, m in enumerate(heads)}


def _cited(path: str, marker: str) -> list[str]:
    row = next(line for line in (ROOT / path).read_text(encoding="utf-8").splitlines() if marker in line)
    return STEP_LIST.search(row).group(1).split("/")


def test_step_11_is_the_advisory_wiring_scan():
    step = _steps()["11"]
    assert step.startswith("11. **Wiring scan (advisory).**")
    assert "hooks/wiring-gate.sh" in step


@pytest.mark.parametrize("path, marker, needle", [
    ("FRESHNESS.md", "| `DECISIONS.md` |", "DECISIONS.md"),
    ("FRESHNESS.md", "| `RATIONALE.md` +", "rationale"),
], ids=["decisions-row", "rationale-row"])
def test_a_registry_row_cites_the_steps_that_hold_its_contract(path, marker, needle):
    steps = _steps()
    for number in _cited(path, marker):
        assert needle in steps[number], f"{path} cites execute Step {number}, which no longer names {needle}"


def test_no_markdown_cites_an_execute_step_that_does_not_exist():
    steps = _steps()
    stale = []
    for path in ROOT.rglob("*.md"):
        if any(part.startswith(".") or part == "node_modules" for part in path.relative_to(ROOT).parts):
            continue
        for match in STEP_LIST.finditer(path.read_text(encoding="utf-8", errors="replace")):
            stale += [f"{path.relative_to(ROOT)}: Step {n}" for n in match.group(1).split("/") if n not in steps]
    assert not stale, stale

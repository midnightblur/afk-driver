"""The shared fix procedure: its pointers, its results, and the miss-class pair it records into."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "skills" / "afk" / "fix"
PROCEDURE = FIX / "IN-PLACE-FIX.md"
LEDGER_FORMAT = ROOT / "skills" / "afk" / "lessons" / "LEDGER-FORMAT.md"
APPEND = ROOT / "hooks" / "lesson-append.sh"
RESULTS = {"fixed", "fail", "blocked", "design_conflict", "needs_decision", "adversary_fail", "flaky"}
CALLERS = ("/afk:execute", "/afk:preflight", "/afk:autopilot", "/afk:smoke-test", "/afk:bug", "/afk:fix")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return text[start:end if end != -1 else len(text)]


def _escape_classes() -> set[str]:
    table = _section((FIX / "ESCAPE-ANALYSIS.md").read_text(encoding="utf-8"), "| Miss class |")
    return set(re.findall(r"^\s*\| `([^`]+)` \|", table, re.MULTILINE))


def _mapped_classes() -> set[str]:
    table = _section(LEDGER_FORMAT.read_text(encoding="utf-8"), "## Miss-class mapping")
    rows = [line.split("|")[1] for line in table.splitlines() if line.startswith("| `")]
    return {name for row in rows for name in re.findall(r"`([^`]+)`", row)}


def test_the_miss_class_set_and_its_lesson_mapping_agree():
    assert _escape_classes() and _escape_classes() == _mapped_classes()


def test_workflow_feedback_traces_every_miss_class():
    text = (FIX / "WORKFLOW-FEEDBACK.md").read_text(encoding="utf-8")
    assert all(f"`{name}`" in text for name in _escape_classes())


@pytest.mark.parametrize("path", [
    "skills/afk/fix/SKILL.md",
    "skills/afk/fix/ESCAPE-ANALYSIS.md",
    "skills/afk/fix/WORKFLOW-FEEDBACK.md",
    "skills/afk/lessons/LEDGER-FORMAT.md",
    "skills/afk/grill-requirements/ROUND.md",
    "AGENTS.md",
])
def test_each_pointer_names_the_procedure_file(path):
    assert "IN-PLACE-FIX.md" in (ROOT / path).read_text(encoding="utf-8")


def test_no_pointer_names_a_fix_phase_the_procedure_now_holds():
    stale = re.compile(r"fix/SKILL\.md`?\s+Phase [0-9]")
    hits = [str(p.relative_to(ROOT)) for p in (ROOT / "skills").rglob("*.md")
            if stale.search(p.read_text(encoding="utf-8"))]
    assert hits == []


def test_the_procedure_re_runs_a_failure_once_before_any_diagnosis():
    text = PROCEDURE.read_text(encoding="utf-8")
    steps = re.findall(r"^### (\d+)\. (.+)$", text, re.MULTILINE)
    assert steps[0] == ("1", "Re-run once")
    assert "This step re-runs once. The caller's loop decides any further retry." in text


def test_the_procedure_returns_exactly_the_seven_results():
    table = _section(PROCEDURE.read_text(encoding="utf-8"), "## In-place fix results")
    assert set(re.findall(r"^\| `([a-z_]+)` \|", table, re.MULTILINE)) == RESULTS


def test_the_procedure_names_none_of_its_callers():
    text = PROCEDURE.read_text(encoding="utf-8")
    assert [name for name in CALLERS if name in text] == []


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_fix", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


@pytest.mark.parametrize("miss", sorted(_escape_classes()))
def test_a_lesson_carries_each_miss_class_and_the_finding_id(miss, tmp_path, monkeypatch):
    bash = _bash()
    if bash is None:
        pytest.skip("no POSIX shell on this machine")
    ledger = tmp_path / "LEDGER.jsonl"
    monkeypatch.setenv("LESSON_LEDGER_FILE", str(ledger))
    monkeypatch.delenv("LESSON_LEDGER_DISABLE", raising=False)
    result = subprocess.run([str(bash), str(APPEND), "opened", "--class", "missing-instruction",
                             "--miss", miss, "--target", "t", "--summary", "s", "--draft", "d",
                             "--source", "0001-slice", "--writer", "fix"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    event = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert (event["miss"], event["source"], event["writer"]) == (miss, "0001-slice", "fix")

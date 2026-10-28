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


STALE_TRACE = {"`PRD.md`": "PRD asserted the wrong behavior | requirements",
               "`SDD.md`": "A frozen SDD decision was wrong or infeasible | architecture",
               "`VERIFICATION-PLAN.md`": "No verification scenario would catch the bug | verification design",
               "`plan/NNNN-slug.md`": "An in-flight subtask contract shifted | slicing"}


def test_workflow_feedback_traces_every_stale_artifact():
    step7 = _section(PROCEDURE.read_text(encoding="utf-8"), "### 7. Find stale artifacts").split("\n### ")[0]
    rows = [line.split("|")[2] for line in step7.splitlines() if line.startswith("| ") and "---" not in line][1:]
    artifacts = {re.match(r"\s*(`[^`]+`)", cell).group(1) for cell in rows}
    trace = _section((FIX / "WORKFLOW-FEEDBACK.md").read_text(encoding="utf-8"), "| Miss class / stale artifact |")
    assert artifacts == set(STALE_TRACE)
    assert all(f"| {STALE_TRACE[name]} |" in trace for name in artifacts)


POINTERS = [
    "skills/afk/fix/SKILL.md",
    "skills/afk/fix/ESCAPE-ANALYSIS.md",
    "skills/afk/fix/WORKFLOW-FEEDBACK.md",
    "skills/afk/lessons/LEDGER-FORMAT.md",
    "skills/afk/grill-requirements/ROUND.md",
    "AGENTS.md",
]
# A cited procedure step: "IN-PLACE-FIX.md ... step N", "procedure step(s) N and M",
# "steps N to M of the shared fix procedure"; every cited number must be a procedure step.
CITED_STEP = re.compile(
    r"(?:IN-PLACE-FIX\.md\S*|procedure)\s+steps?\s+(\d+)(?:\s*(?:,|and|or|to)\s*(\d+))?"
    r"|steps?\s+(\d+)\s+to\s+(\d+)\s+of\s+the\s+shared\s+fix\s+procedure", re.IGNORECASE)
FIX_PHASE = re.compile(r"(?:fix/SKILL\.md|/afk:fix|fix skill)['`)\]]*'?s?\s+Phases?\s+[0-9]", re.IGNORECASE)


STEPS = [("1", "Re-run once"), ("2", "Record the failing path"), ("3", "Fix test-first"),
         ("4", "Broaden coverage"), ("5", "Run every tier"), ("6", "Escape analysis"),
         ("7", "Find stale artifacts"), ("8", "Workflow lesson"), ("9", "Return")]


def _procedure_steps() -> set[str]:
    return set(re.findall(r"^### (\d+)\. ", PROCEDURE.read_text(encoding="utf-8"), re.MULTILINE))


def test_the_procedure_steps_keep_the_numbers_their_pointers_cite():
    # A renumbered step leaves every pointer citing a real but wrong step; pinning the order catches it.
    assert re.findall(r"^### (\d+)\. (.+)$", PROCEDURE.read_text(encoding="utf-8"), re.MULTILINE) == STEPS


@pytest.mark.parametrize("path", POINTERS)
def test_each_pointer_names_the_procedure_file(path):
    assert "IN-PLACE-FIX.md" in (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("path", POINTERS)
def test_each_cited_procedure_step_exists(path):
    cited = {n for groups in CITED_STEP.findall((ROOT / path).read_text(encoding="utf-8")) for n in groups if n}
    assert cited and cited <= _procedure_steps()


def test_no_file_points_at_a_fix_phase_the_procedure_now_holds():
    files = [*ROOT.glob("*.md"), *(ROOT / "skills").rglob("*.md")]
    own = ROOT / "skills" / "afk" / "fix" / "SKILL.md"
    hits = [str(f.relative_to(ROOT)) for f in files if f != own and FIX_PHASE.search(f.read_text(encoding="utf-8"))]
    assert hits == []


def test_the_procedure_files_name_no_fix_phase():
    for name in ("IN-PLACE-FIX.md", "ESCAPE-ANALYSIS.md", "WORKFLOW-FEEDBACK.md"):
        assert not re.search(r"\bPhase [0-9]", (FIX / name).read_text(encoding="utf-8")), name


def test_the_procedure_re_runs_a_failure_once_before_any_diagnosis():
    text = PROCEDURE.read_text(encoding="utf-8")
    first = re.search(r"^### (\d+)\. (.+)$", text, re.MULTILINE)
    assert first.groups() == ("1", "Re-run once")
    step1 = _section(text, "### 1. Re-run once").split("\n### ")[0]
    passes = re.search(r"^- The re-run passes.*?(?=^- |\Z)", step1, re.MULTILINE | re.DOTALL).group(0)
    fails = re.search(r"^- The re-run fails.*?(?=^- |\Z)", step1, re.MULTILINE | re.DOTALL).group(0)
    assert all(part in passes for part in ("`flaky`", "`disabled/flaky`", "step 8", "Change no code"))
    assert "step 2" in fails and "flaky" not in fails
    assert "re-runs once" in step1


def test_the_procedure_returns_exactly_the_seven_results():
    text = PROCEDURE.read_text(encoding="utf-8")
    table = _section(text, "## In-place fix results")
    assert set(re.findall(r"^\| `([a-z_]+)` \|", table, re.MULTILINE)) == RESULTS
    returned = set(re.findall(r"return\s+`([a-z_]+)`", text[:text.index("## Record")]))
    assert returned and returned <= RESULTS


def test_the_procedure_names_none_of_its_callers():
    text = PROCEDURE.read_text(encoding="utf-8")
    assert [name for name in CALLERS if name in text] == []
    assert re.findall(r"\b(?:execute|preflight|autopilot|smoke-test)\b", text, re.IGNORECASE) == []


def _mapping() -> dict[str, str]:
    table = _section(LEDGER_FORMAT.read_text(encoding="utf-8"), "## Miss-class mapping")
    out = {}
    for line in table.splitlines():
        if line.startswith("| `"):
            cells = line.split("|")
            lesson = re.search(r"`([^`]+)`", cells[2]).group(1)
            out.update({miss: lesson for miss in re.findall(r"`([^`]+)`", cells[1])})
    return out


def _bash():
    spec = importlib.util.spec_from_file_location("afk_run_hook_for_fix", ROOT / "hooks" / "run-hook.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.find_bash()


@pytest.mark.parametrize("miss", sorted(_escape_classes()))
def test_lesson_append_accepts_the_mapped_class_for_each_miss_class(miss, tmp_path, monkeypatch):
    bash = _bash()
    if bash is None:
        pytest.skip("no POSIX shell on this machine")
    ledger = tmp_path / "LEDGER.jsonl"
    monkeypatch.setenv("LESSON_LEDGER_FILE", str(ledger))
    monkeypatch.delenv("LESSON_LEDGER_DISABLE", raising=False)
    result = subprocess.run([str(bash), str(APPEND), "opened", "--class", _mapping()[miss], "--miss", miss,
                             "--target", "t", "--summary", "s", "--draft", "d", "--source", "r-001",
                             "--writer", "fix"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    event = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert (event["class"], event["miss"]) == (_mapping()[miss], miss)


def test_workflow_feedback_appends_with_flags_lesson_append_takes():
    text = (FIX / "WORKFLOW-FEEDBACK.md").read_text(encoding="utf-8")
    block = text[text.index("lesson-append.sh opened"):text.index("```", text.index("lesson-append.sh opened"))]
    taken = set(re.findall(r"^\s+(--[a-z]+)\)", APPEND.read_text(encoding="utf-8"), re.MULTILINE))
    used = set(re.findall(r"(--[a-z]+)\b", block))
    assert {"--class", "--miss", "--source"} <= used <= taken

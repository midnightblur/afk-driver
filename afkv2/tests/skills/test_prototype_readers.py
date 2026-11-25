"""The 2 readers of PROTOTYPE.md: propose-solution and propose-verification (SDD §14; ADR-0004 design; ticket 207
VR-023, VR-024, VR-025, VR-026).

Each start test builds its own scratch git repository and runs the script by its path, through its command line, as
SKILL.md states it. PROTOTYPE.md is an optional input: a spec folder without it runs as today, with no refusal. Each
failure message names the input, the expected value and the actual value.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
DESIGN_FILES = SKILLS / "propose-solution" / "scripts" / "design_files.py"
VERIFICATION_FILES = SKILLS / "propose-verification" / "scripts" / "verification_files.py"
SPEC_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "propose_solution" / "spec"
TICKET = "PROJ-1"
PROTOTYPE = "# Prototype — sample\n\n> Frontend: web\n> Fidelity: source-only\n> Date: 2026-11-25\n"


def _git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, (f"input: git {' '.join(args)}\nexpected: exit 0\nactual: exit {done.returncode}\n"
                                  f"{done.stderr}")


def _repo(tmp_path):
    """A scratch git repository: config with spec_folder docs, and docs/PROJ-1 with PRD.md, SDD.md, a GRILL-LOG.md whose
    exit gate passed and its page document. No PROTOTYPE.md."""
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / ".afkv2").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "docs", "tracker": {"kind": "jira"}}),
                                                 "utf-8")
    shutil.copytree(SPEC_FIXTURE, root / "docs" / TICKET)
    (root / "docs" / TICKET / "SDD.md").write_text("# SDD\n", "utf-8")
    return root


def _start(script, root, state):
    """Run `<script> start --ticket PROJ-1` in `root`; return its input line, exit code and JSON answer."""
    command = [sys.executable, str(script), "start", "--ticket", TICKET]
    done = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8",
                          stdin=subprocess.DEVNULL, timeout=120)
    given = f"{script.name} start --ticket {TICKET}, with {state}"
    try:
        answer = json.loads(done.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f"input: {given}\nexpected: 1 JSON answer\nactual: exit {done.returncode}\n"
                             f"stdout: {done.stdout!r}\nstderr: {done.stderr!r}") from None
    return given, done.returncode, answer


def _expect(given, field, actual, expected, answer):
    assert actual == expected, (f"input: {given}\nfield: {field}\nexpected: {expected!r}\nactual: {actual!r}\n"
                                f"answer: {json.dumps(answer)}")


def _relative(root, path):
    """The answer path, relative to the repository, or the answer path itself when it lies outside."""
    resolved, base = Path(path).resolve(), root.resolve()
    return resolved.relative_to(base).as_posix() if resolved.is_relative_to(base) else path


def _check_start(script, root, state, exists):
    given, code, answer = _start(script, root, state)
    _expect(given, "exit code", code, 0, answer)
    _expect(given, "ok", answer.get("ok"), True, answer)
    _expect(given, "prototype_exists", answer.get("prototype_exists"), exists, answer)
    _expect(given, "prototype", _relative(root, answer.get("prototype", "")), "docs/PROJ-1/PROTOTYPE.md",
            answer)
    return given, answer


# --- VR-023 (PRD AC-027, AC-029): design_files.py start answers prototype and prototype_exists

def test_design_start_with_the_prototype_answers_true_and_the_path(tmp_path):
    root = _repo(tmp_path)
    (root / "docs" / TICKET / "PROTOTYPE.md").write_text(PROTOTYPE, "utf-8")
    _check_start(DESIGN_FILES, root, "docs/PROJ-1/PROTOTYPE.md present", True)


def test_design_start_without_the_prototype_answers_false_and_no_refusal(tmp_path):
    root = _repo(tmp_path)
    _check_start(DESIGN_FILES, root, "no docs/PROJ-1/PROTOTYPE.md", False)


# --- VR-024 (PRD AC-028, AC-029): verification_files.py start answers prototype and prototype_exists

def test_verification_start_with_the_prototype_answers_true_and_the_path(tmp_path):
    root = _repo(tmp_path)
    (root / "docs" / TICKET / "PROTOTYPE.md").write_text(PROTOTYPE, "utf-8")
    given, answer = _check_start(VERIFICATION_FILES, root, "docs/PROJ-1/PROTOTYPE.md present", True)
    _expect(given, "PROTOTYPE.md named in missing", "PROTOTYPE.md" in json.dumps(answer.get("missing", [])), False,
            answer)


def test_verification_start_without_the_prototype_answers_false_and_no_refusal(tmp_path):
    root = _repo(tmp_path)
    given, answer = _check_start(VERIFICATION_FILES, root, "no docs/PROJ-1/PROTOTYPE.md", False)
    _expect(given, "PROTOTYPE.md named in missing", "PROTOTYPE.md" in json.dumps(answer.get("missing", [])), False,
            answer)


# --- VR-025, VR-026 (PRD AC-027, AC-028): each SKILL.md reads PROTOTYPE.md in its read step and its proposer brief

def _flat(text):
    return " ".join(text.split())


def _guide(skill):
    return (SKILLS / skill / "SKILL.md").read_text("utf-8")


def _step(text, number):
    """The text of numbered step `number`, up to the next numbered step, on 1 line."""
    start = text.index(f"\n{number}. **")
    end = text.find(f"\n{number + 1}. **", start)
    return _flat(text[start:end if end > 0 else None])


def _row(text, label):
    return _flat(next(line for line in text.splitlines() if line.lstrip().startswith(f"| {label}")))


def _optional_input(text):
    row = _row(text, "`PROTOTYPE.md`")
    assert "/afkv2:prototype" in row and "stop" not in row, row
    start = _step(text, 1)
    assert "`prototype`" in start and "`prototype_exists`" in start
    assert "`prototype`" in _row(text, "R-1 Same inputs")


def test_propose_solution_guide_reads_the_prototype_and_cites_each_ui_decision():
    text = _guide("propose-solution")
    _optional_input(text)
    read = _step(text, 2)
    assert "`prototype_exists` true: read `prototype`" in read
    assert "each UI decision of it that changes the design in the existing SDD section it changes" in read
    assert "no new section" in read


def test_propose_verification_guide_reads_the_prototype_and_derives_rows_from_its_coverage():
    text = _guide("propose-verification")
    _optional_input(text)
    read = _step(text, 2)
    assert "`prototype_exists` true: read `prototype`" in read
    assert "`ui-e2e` and `acceptance` rows from each `reachable` row of its Coverage table" in read
    assert "`story` and `criteria`" in read and "no new column" in read

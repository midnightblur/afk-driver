"""The 2 readers of PROTOTYPE.md: propose-solution and propose-verification (SDD §14; ADR-0004 design; ticket 207
VR-023, VR-024, VR-025, VR-026).

Each start test builds its own scratch git repository with its own spec files, and runs the script by its path with
`start --ticket PROJ-1`. PROTOTYPE.md is an optional input: a spec folder without it runs as today, with no refusal.
Each failure names the input, the expected value and the actual value.

The guide tests are static rows: a static row proves the rule is written in the file that owns it (the plan lowered
these rows to static). Each finds the step or table row that owns the rule and compares on normalized text (lowercase,
whitespace collapsed, backticks and quotes removed).
"""

import json
import re
import subprocess
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]
SKILLS = PLUGIN / "skills"
DESIGN_FILES = SKILLS / "propose-solution" / "scripts" / "design_files.py"
VERIFICATION_FILES = SKILLS / "propose-verification" / "scripts" / "verification_files.py"
TICKET = "PROJ-1"
PROTOTYPE = "# Prototype — sample\n\n> Frontend: web\n> Fidelity: source-only\n> Date: 2026-11-25\n"


def _git(root, *args):
    done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, (f"input: git {' '.join(args)}\nexpected: exit 0\nactual: exit {done.returncode}\n"
                                  f"{done.stderr}")


PRD = "# PRD — sample\n\n## Acceptance Criteria\n\n- [ ] AC-001 The list page shows orders.\n"
GRILL_LOG = "# Grill log — PROJ-1\n\n## Requirements grill\n\n- Settled: exit gate passed 2026-11-25 · session s-1\n"
GRILL_PAGE = {"schema": "afkv2.page/0", "maps": [], "rounds": [],
              "session": {"id": "s-1", "skill": "grill", "feature": "PROJ-1", "ticket": "PROJ-1",
                          "started": "2026-11-25T09:00:00Z"}}


def _repo(tmp_path, sdd=True):
    """A scratch git repository: config with spec_folder docs, and docs/PROJ-1 with PRD.md, SDD.md (unless `sdd` is
    false), a GRILL-LOG.md whose exit gate passed for session s-1 and its grill page document. No PROTOTYPE.md."""
    root = tmp_path / "repo"
    spec = root / "docs" / TICKET
    (spec / "pages").mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    (root / ".afkv2").mkdir()
    (root / ".afkv2" / "config.json").write_text(json.dumps({"spec_folder": "docs", "tracker": {"kind": "jira"}}),
                                                 "utf-8")
    (spec / "PRD.md").write_text(PRD, "utf-8")
    if sdd:
        (spec / "SDD.md").write_text("# SDD\n", "utf-8")
    (spec / "GRILL-LOG.md").write_text(GRILL_LOG, "utf-8")
    (spec / "pages" / "grill-s-1.json").write_text(json.dumps(GRILL_PAGE), "utf-8")
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
    _check_start(VERIFICATION_FILES, root, "docs/PROJ-1/PROTOTYPE.md present", True)


def test_verification_start_without_the_prototype_answers_false_and_no_refusal(tmp_path):
    root = _repo(tmp_path)
    _check_start(VERIFICATION_FILES, root, "no docs/PROJ-1/PROTOTYPE.md", False)


def test_verification_start_never_names_a_missing_prototype_in_missing(tmp_path):
    root = _repo(tmp_path, sdd=False)
    given, code, answer = _start(VERIFICATION_FILES, root, "no docs/PROJ-1/SDD.md and no docs/PROJ-1/PROTOTYPE.md")
    _expect(given, "exit code", code, 1, answer)
    _expect(given, "error.code", answer.get("error", {}).get("code"), "missing-input", answer)
    _expect(given, "error.missing", _relative(root, answer.get("error", {}).get("missing", "")), "docs/PROJ-1/SDD.md",
            answer)


# --- VR-025, VR-026 (PRD AC-027, AC-028): each SKILL.md reads PROTOTYPE.md in its read step and its proposer brief

QUOTES = str.maketrans("", "", "`\"'\u2018\u2019\u201c\u201d")


def _norm(text):
    """Lowercase, quotes and backticks removed, whitespace collapsed to 1 space."""
    return " ".join(text.translate(QUOTES).lower().split())


def _guide(skill):
    path = SKILLS / skill / "SKILL.md"
    assert path.is_file(), f"input: {path}\nexpected: the file exists\nactual: no file"
    return path.read_text("utf-8")


def _step(skill, text, number):
    """The normalized text of numbered step `number`, up to the next numbered step."""
    steps = re.findall(r"^(\d+)\. \*\*", text, re.M)
    start = text.find(f"\n{number}. **")
    assert start >= 0, f"file: {skill}/SKILL.md\nexpected: step {number}\nactual steps: {steps}"
    end = text.find(f"\n{number + 1}. **", start)
    return _norm(text[start:end if end > 0 else None])


def _row(skill, text, label):
    """The normalized table row whose first cell starts with `label`."""
    rows = [line for line in text.splitlines() if line.lstrip().startswith("|")]
    found = next((line for line in rows if _norm(line.lstrip()[1:]).startswith(_norm(label))), None)
    firsts = [line.strip().split("|")[1].strip() for line in rows if line.strip().count("|") > 1]
    assert found is not None, f"file: {skill}/SKILL.md\nexpected: table row {label!r}\nactual first cells: {firsts}"
    return _norm(found)


def _holds(skill, where, text, phrase, present=True):
    """Assert that `text` (the normalized step or row `where`) holds `phrase`, or lacks it when `present` is false."""
    expected = f"{'holds' if present else 'lacks'} {phrase!r}"
    assert (_norm(phrase) in text) is present, (f"file: {skill}/SKILL.md\nsection: {where}\nexpected: {expected}\n"
                                                f"actual: {text[:600]!r}")


def _optional_input(skill, text):
    row = _row(skill, text, "`PROTOTYPE.md`")
    _holds(skill, "input row `PROTOTYPE.md`", row, "/afkv2:prototype")
    _holds(skill, "input row `PROTOTYPE.md`", row, "stop", present=False)
    start = _step(skill, text, 1)
    _holds(skill, "step 1", start, "`prototype`")
    _holds(skill, "step 1", start, "`prototype_exists`")
    _holds(skill, "row R-1 Same inputs", _row(skill, text, "R-1 Same inputs"), "`prototype`")


def test_propose_solution_guide_reads_the_prototype_and_cites_each_ui_decision():
    skill = "propose-solution"
    text = _guide(skill)
    _optional_input(skill, text)
    read = _step(skill, text, 2)
    _holds(skill, "step 2", read, "`prototype_exists` true: read `prototype`")
    _holds(skill, "step 2", read,
           "each UI decision of it that changes the design in the existing SDD section it changes")
    _holds(skill, "step 2", read, "no new section")


def test_propose_verification_guide_reads_the_prototype_and_derives_rows_from_its_coverage():
    skill = "propose-verification"
    text = _guide(skill)
    _optional_input(skill, text)
    read = _step(skill, text, 2)
    _holds(skill, "step 2", read, "`prototype_exists` true: read `prototype`")
    _holds(skill, "step 2", read, "`ui-e2e` and `acceptance` rows from each `reachable` row of its Coverage table")
    _holds(skill, "step 2", read, "`story` and `criteria`")
    _holds(skill, "step 2", read, "no new column")

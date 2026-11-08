"""The design files of propose-solution: take-over, note sync, the gate lists and refusals, the ADR Driven by section
(SDD §3 rows S-3, S-4, S-5; §6 I-6, I-8; ADR-0004 and ADR-0007 design; PRD AC-011, AC-031, AC-032, AC-034, AC-035)."""

import json
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN / "skills" / "propose-solution" / "scripts"))

import design_files  # noqa: E402
from grill_common import Refusal  # noqa: E402

LOG_HEAD = "# Grill log — PROJ-1\n\n## Requirements grill\n- Policy: x\n\n## Solution design\n- Premise: a → pending\n"
LOG_TAIL = "\n## Other\nkept\n"


def note(note_id, text, round_n=1, target="c-1", deleted=False):
    return {"id": note_id, "round": round_n, "target": target, "item": target, "text": text, "deleted": deleted}


@pytest.fixture
def files(tmp_path):
    log, doc = tmp_path / "GRILL-LOG.md", tmp_path / "pages" / "propose-solution-s-1.json"
    log.write_text(LOG_HEAD + LOG_TAIL, "utf-8")
    doc.parent.mkdir()
    return log, doc


def write_doc(doc, notes):
    doc.write_text(json.dumps({"session": {"id": "s-1"}, "rounds": [], "notes": notes}), "utf-8")


def test_sync_copies_each_new_note_word_for_word_and_skips_a_note_already_there(files):
    log, doc = files
    words = 'Keep the "old" table,\nand drop the cache.'
    write_doc(doc, [note("N-1-c-1-1", words), note("N-1-c-1-2", "gone", deleted=True)])
    assert design_files.sync_notes(doc, log) == {"ok": True, "notes": 1, "rows": 1}
    text = log.read_text("utf-8")
    row = f"- Note: N-1-c-1-1 · R1 · on c-1: {json.dumps(words, ensure_ascii=False)}"
    assert row in text and json.loads(row.split(": ", 2)[2]) == words
    head = LOG_HEAD.split("- Premise")[0]
    assert text.startswith(head) and f"- Premise: a → pending\n{row}\n" in text
    assert text.endswith(LOG_TAIL) and "gone" not in text
    write_doc(doc, [note("N-1-c-1-1", "edited later"), note("N-2-c-2-1", "Second.", 2, "c-2")])
    assert design_files.sync_notes(doc, log) == {"ok": True, "notes": 1, "rows": 2}
    text = log.read_text("utf-8")
    assert row in text and "edited later" not in text and '- Note: N-2-c-2-1 · R2 · on c-2: "Second."' in text


def test_sync_is_a_verb_and_refuses_a_missing_file(files):
    log, doc = files
    write_doc(doc, [])
    assert design_files.main(["sync", "--doc", str(doc), "--log", str(log)])["notes"] == 0
    with pytest.raises(Refusal) as refused:
        design_files.main(["sync", "--doc", str(doc.with_name("none.json")), "--log", str(log)])
    assert refused.value.code == "missing-input"


# Take-over, the gate lists and refusals: through the stated commands of SKILL.md.

from test_propose_solution import World, aspect_card, gate_failures, round_of  # noqa: E402


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def passed_design(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    return started, gate_failures(world, started, expect=0)


def test_start_takes_over_the_session_whose_gate_passed(world):
    started, _ = passed_design(world)
    log = world.spec / "GRILL-LOG.md"
    again = world.run("start", ticket_key="PROJ-1")
    assert again["takeover"] == started["session"] and again["resume"] is False
    assert (again["session"], again["doc"]) == (started["session"], started["doc"])
    rows = log.read_text("utf-8").split("## Solution design", 1)[1].splitlines()
    assert rows.count(f"- Last pass: R2 · session {started['session']}") == 1


def solution_rows(world):
    return (world.spec / "GRILL-LOG.md").read_text("utf-8").split("## Solution design", 1)[1].splitlines()


def test_start_writes_the_last_pass_row_when_it_takes_over_a_log_from_before_that_row(world):
    started, _ = passed_design(world)
    log = world.spec / "GRILL-LOG.md"
    log.write_text("\n".join(line for line in log.read_text("utf-8").splitlines()
                             if not line.startswith("- Last pass:")) + "\n", "utf-8")
    assert not any(row.startswith("- Last pass:") for row in solution_rows(world))
    again = world.run("start", ticket_key="PROJ-1")
    assert again["takeover"] == started["session"]
    assert [row for row in solution_rows(world) if row.startswith("- Last pass:")] == [
        f"- Last pass: R2 · session {started['session']}"]


def test_start_resumes_a_taken_over_session_once_a_later_round_exists(world):
    started, _ = passed_design(world)
    assert world.run("start", ticket_key="PROJ-1")["takeover"] == started["session"]
    world.build(started, round_of(aspect_card("entities", "a-entities-2", carries=["a-entities"])))
    again = world.run("start", ticket_key="PROJ-1")
    assert again["resume"] is True and again["takeover"] is None and again["session"] == started["session"]


def test_a_pass_answers_stale_with_the_plan_of_the_run_branch(world, monkeypatch):
    from test_pass_history import git
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(world.root))
    started = walked(world)
    git(world.repo, "init", "-q", "-b", "feat-x")
    git(world.repo, "commit", "-q", "--allow-empty", "-m", "base")
    git(world.repo, "checkout", "-q", "--orphan", "feat-x-run")
    (world.repo / "plan").mkdir()
    (world.repo / "plan" / "PLAN.md").write_text("# Plan\n", "utf-8")
    git(world.repo, "add", "plan/PLAN.md")
    git(world.repo, "commit", "-q", "-m", "plan")
    git(world.repo, "checkout", "-q", "-f", "feat-x")
    assert gate_failures(world, started, expect=0)["stale"] == ["feat-x-run:plan/PLAN.md"]


def test_start_names_no_takeover_for_a_new_or_open_session(world):
    first = world.run("start", ticket_key="PROJ-1")
    assert first["takeover"] is None
    world.build(first, round_of(aspect_card("entities")))
    assert world.run("start", ticket_key="PROJ-1")["takeover"] is None


def test_a_pass_answers_stale_and_changed_each_empty_when_nothing_applies(world):
    started, passed = passed_design(world)
    assert passed["stale"] == [] and passed["changed"] == []


def test_a_pass_after_a_takeover_lists_the_points_changed_since_the_last_pass(world):
    started, _ = passed_design(world)
    world.run("start", ticket_key="PROJ-1")
    world.build(started, round_of(aspect_card("entities", "a-entities-2", carries=["a-entities"])))
    world.accept_all(started)
    passed = gate_failures(world, started, expect=0)
    assert passed["changed"] == [{"id": "a-entities", "kind": "card", "text": "The reading on entities."}]
    rows = (world.spec / "GRILL-LOG.md").read_text("utf-8").split("## Solution design", 1)[1].splitlines()
    assert [row for row in rows if row.startswith("- Last pass:")] == [f"- Last pass: R3 · session {started['session']}"]


def walked(world):
    started = world.run("start", ticket_key="PROJ-1")
    world.walk_to_write(started)
    world.write_design()
    return started


def write_page(world, started, doc):
    (world.repo / started["doc"]).write_text(json.dumps(doc), "utf-8")


def test_the_gate_refuses_each_open_question_for_others(world):
    started = walked(world)
    doc = world.doc(started)
    doc["questions"] = [{"id": "q-1", "question": "Which store?", "who": ["ops"], "state": "open"},
                        {"id": "q-2", "question": "Which font?", "who": ["design"], "state": "answered"}]
    write_page(world, started, doc)
    failures = gate_failures(world, started)
    assert "question-open: q-1: Which store? (who: ops)" in failures
    assert not any("q-2" in failure for failure in failures)


@pytest.mark.parametrize("missing", ["sec-system", "sec-patterns", "sec-performance"])
def test_the_gate_refuses_a_missing_required_section(world, missing):
    started = walked(world)
    doc = world.doc(started)
    doc["sections"] = [entry for entry in doc["sections"] if entry["id"] != missing]
    write_page(world, started, doc)
    failures = gate_failures(world, started)
    assert [failure for failure in failures if failure.startswith("section-missing")] == [f"section-missing: {missing}"]


def test_a_removed_section_counts_as_missing(world):
    started = walked(world)
    doc = world.doc(started)
    next(entry for entry in doc["sections"] if entry["id"] == "sec-performance")["state"] = "removed"
    write_page(world, started, doc)
    assert "section-missing: sec-performance" in gate_failures(world, started)


def test_the_gate_refuses_while_the_proposers_state_file_records_an_open_pane(world):
    started = walked(world)
    state = (world.repo / started["doc"]).with_suffix(".proposers.json")
    state.write_text(json.dumps({"version": 1, "count": 2, "cleaned": False, "proposers": [
        {"tool": "claude", "pane": "p-1", "worktree": None}, {"tool": "codex", "pane": None, "worktree": "w-2"}]}), "utf-8")
    failures = gate_failures(world, started)
    assert "pane-open: p-1" in failures and "pane-open: w-2" in failures
    state.write_text(json.dumps({"version": 1, "count": 2, "cleaned": True, "proposers": [
        {"tool": "claude", "pane": None, "worktree": None}, {"tool": "codex", "pane": None, "worktree": None}]}), "utf-8")
    assert gate_failures(world, started, expect=0)["ok"] is True


def test_a_design_adr_without_driven_by_fails_the_gate(world):
    started = walked(world)
    adr = next((world.spec / "adr" / "design").glob("*.md"))
    text = adr.read_text("utf-8")
    assert "## Driven by\n" in text
    adr.write_text(text.replace("## Driven by\n", "## Drivers\n"), "utf-8")
    assert f"{adr.name}: no section `## Driven by`" in gate_failures(world, started)


def test_the_adr_format_shows_the_driven_by_section():
    template = (PLUGIN / "skills" / "propose-solution" / "ADR-FORMAT.md").read_text("utf-8")
    sections = [line for line in template.split("```markdown", 1)[1].split("\n```", 1)[0].splitlines()
                if line.startswith("## ")]
    assert sections[:3] == ["## Context", "## Driven by", "## Decision"]

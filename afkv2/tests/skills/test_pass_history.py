"""The shared pass history of the grill gate and the design gate (ADR-0007 design; SDD §14 rows "grill log helpers",
"design gate"; PRD AC-031, AC-032, AC-035)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[2]
for _folder in (PLUGIN / "skills" / "use-lavish" / "scripts", PLUGIN / "skills" / "grill-requirements" / "scripts"):
    sys.path.insert(0, str(_folder))

import grill_log  # noqa: E402
import pass_history  # noqa: E402


def card(item_id, **extra):
    return {"id": item_id, "kind": "confirm", "state": "settled_by_mark",
            "body": {"type": "text", "id": f"{item_id}-body", "props": {"text": f"Point {item_id}"}}, **extra}


def doc_of(*rounds, **lists):
    return {"session": {"id": "s-1"}, "rounds": [{"n": n, "state": "current" if n == len(rounds) else "closed",
                                                   "items": list(items)} for n, items in enumerate(rounds, 1)], **lists}


def test_a_last_pass_row_names_the_current_round_and_reads_back_for_its_session_only():
    doc = doc_of([card("i-a")], [card("i-b")])
    row = pass_history.last_pass_row(doc)
    assert row == "- Last pass: R2 · session s-1"
    assert pass_history.last_pass(row, "s-1") == 2
    assert pass_history.last_pass(row, "s-2") is None
    assert pass_history.last_pass("- Settled: x · card i-a", "s-1") is None


def test_changed_is_empty_with_no_pass_and_lists_carried_cards_and_entries_changed_on_both_sides():
    later = card("i-b", carries=["i-a"])
    sections = [{"id": "s-one", "title": "One", "changes": [{"round": 1}, {"round": 2}]},
                {"id": "s-new", "title": "New", "changes": [{"round": 2}]}]
    doc = doc_of([card("i-a"), card("i-x")], [later], sections=sections)
    assert pass_history.changed(doc, None) == []
    assert pass_history.changed(doc, 1) == [{"id": "i-a", "kind": "card", "text": "Point i-a"},
                                             {"id": "s-one", "kind": "section", "text": "One"}]
    assert pass_history.changed(doc, 2) == []


def test_open_questions_lists_only_the_open_questions_for_others():
    questions = [{"id": "q-1", "question": "Which store?", "who": ["ops"], "state": "open"},
                 {"id": "q-2", "question": "Which font?", "who": ["design"], "state": "answered"}]
    assert pass_history.open_questions(doc_of([card("i-a")], questions=questions)) == [questions[0]]
    assert pass_history.open_questions(doc_of([card("i-a")])) == []
    assert pass_history.question_line(questions[0]) == "q-1: Which store? (who: ops)"


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"})


@pytest.fixture
def spec(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    spec_dir = tmp_path / "repo" / "specs" / "PROJ-1"
    spec_dir.mkdir(parents=True)
    return spec_dir


def test_stale_lists_the_named_writers_files_and_nothing_when_none_exists(spec):
    assert pass_history.stale(spec, ()) == []
    assert pass_history.stale(spec, (("SDD.md", "adr/design"),)) == []
    (spec / "SDD.md").write_text("# x\n", "utf-8")
    (spec / "adr" / "design").mkdir(parents=True)
    (spec / "adr" / "design" / "0001-b.md").write_text("# x\n", "utf-8")
    (spec / "PRD.md").write_text("# x\n", "utf-8")
    assert pass_history.stale(spec, (("SDD.md", "adr/design"),)) == [f"{spec.as_posix()}/SDD.md",
                                                                     f"{spec.as_posix()}/adr/design/0001-b.md"]


def test_stale_names_the_plan_of_the_run_branch(spec):
    repo = spec.parent.parent
    git(repo, "init", "-q", "-b", "feat-x")
    git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    git(repo, "checkout", "-q", "--orphan", "feat-x-run")
    (repo / "plan").mkdir()
    (repo / "plan" / "PLAN.md").write_text("# Plan\n", "utf-8")
    git(repo, "add", "plan/PLAN.md")
    git(repo, "commit", "-q", "-m", "plan")
    git(repo, "checkout", "-q", "-f", "feat-x")
    assert pass_history.stale(spec, ()) == ["feat-x-run:plan/PLAN.md"]


def test_the_run_suffix_is_the_one_of_the_plan_check():
    sys.path.insert(0, str(PLUGIN / "skills" / "to-subtasks" / "scripts"))
    import check_plan
    assert pass_history.RUN_SUFFIX == check_plan.RUN_SUFFIX


def test_the_grill_log_calls_the_shared_helpers_and_keeps_no_private_copy():
    for private in ("_run_plan", "_last_pass", "_last_pass_row", "_first_text", "ENTRY_TEXT", "LAST_PASS_ROW", "_NoAnswer"):
        assert not hasattr(grill_log, private), private
    source = (PLUGIN / "skills" / "grill-requirements" / "scripts" / "grill_log.py").read_text("utf-8")
    assert "pass_history.changed(" in source and "pass_history.stale(" in source
    assert "pass_history.is_open(" in source
    assert grill_log.RUN_SUFFIX is pass_history.RUN_SUFFIX and grill_log.GIT_LIMIT_S == pass_history.GIT_LIMIT_S


def test_resume_or_take_over_resumes_an_open_session_and_takes_over_a_passed_one(tmp_path):
    page = tmp_path / "page.json"
    page.write_text(__import__("json").dumps(doc_of([card("i-a")], [card("i-b")])), "utf-8")
    rows = ["- Last pass: R2 · session s-1"]
    assert pass_history.resume_or_take_over(None, False, page, []) == (None, None)
    assert pass_history.resume_or_take_over("s-1", False, page, []) == ("s-1", None)
    assert pass_history.resume_or_take_over("s-1", True, page, rows) == (None, "s-1")
    assert pass_history.resume_or_take_over("s-1", True, page, []) == (None, "s-1")


def test_resume_or_take_over_resumes_a_passed_session_with_a_later_round(tmp_path):
    page = tmp_path / "page.json"
    page.write_text(__import__("json").dumps(doc_of([card("i-a")], [card("i-b")], [card("i-c")])), "utf-8")
    assert pass_history.resume_or_take_over("s-1", True, page, ["- Last pass: R2 · session s-1"]) == ("s-1", None)


def test_missing_last_pass_row_is_the_current_round_only_when_no_row_holds_the_session():
    doc = doc_of([card("i-a")], [card("i-b")])
    assert pass_history.missing_last_pass_row(doc, ["- Policy: x"]) == "- Last pass: R2 · session s-1"
    assert pass_history.missing_last_pass_row(doc, ["- Last pass: R1 · session s-1"]) is None
    assert pass_history.missing_last_pass_row(doc, ["- Last pass: R1 · session s-9"]) == "- Last pass: R2 · session s-1"

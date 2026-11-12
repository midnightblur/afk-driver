"""One subtask of a run: the fresh subagent, the test-first order, its own commits, and the plan calls."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(AFKV2 / "tests" / "autopilot"))
sys.path.insert(0, str(AFKV2 / "skills" / "autopilot" / "scripts"))
sys.path.insert(0, str(AFKV2 / "skills" / "execute" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import plan_contract  # noqa: E402
import plan_fixture  # noqa: E402
import tdd_log  # noqa: E402
import walk  # noqa: E402
from plan_fixture import contract_text, git  # noqa: E402
from tracker import envelope  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

REVIEW = AFKV2 / "skills" / "code-review" / "scripts" / "review_rounds.py"
FAIL = f'"{sys.executable}" -c "import sys; sys.exit(1)"'
PASS = f'"{sys.executable}" -c "import sys; sys.exit(0)"'


def call(verb, **payload):
    """One verb, as the command answers it."""
    try:
        return walk.VERBS[verb](payload)
    except Refusal as refusal:
        return envelope.fail(refusal.code, refusal.reason, **refusal.extra)


def log(verb, **payload):
    try:
        return tdd_log.VERBS[verb](payload)
    except Refusal as refusal:
        return envelope.fail(refusal.code, refusal.reason, **refusal.extra)


def code_of(answer):
    assert not answer["ok"], answer
    return answer["error"]["code"]


@pytest.fixture
def run(tmp_path, monkeypatch):
    """A plan of 3: 0001-a, then 0002-b that waits on it, then 0003-c that waits on 0002-b; 0004-d waits on nothing."""
    built = plan_fixture.build(tmp_path, {
        "0001-a": contract_text("0001-a"),
        "0002-b": contract_text("0002-b", blocked=["0001-a"]),
        "0003-c": contract_text("0003-c", blocked=["0002-b"]),
        "0004-d": contract_text("0004-d"),
    })
    monkeypatch.chdir(built.work)
    monkeypatch.setattr(walk, "ci_state", lambda change: "watching")
    return built


def finished_review(built, subtask):
    """A real review run with no findings: `begin`, `record`, `finish`. No forge call happens."""
    for verb, payload in (("begin", {"change": "7", "concerns": [{"name": "logic", "why": "the diff has code"}]}),
                          ("record", {"findings": []}), ("finish", {})):
        done = subprocess.run([sys.executable, str(REVIEW), verb], capture_output=True, timeout=60,
                              input=json.dumps({"plan": str(built.plan), "subtask": subtask, **payload}).encode("utf-8"))
        assert done.returncode == 0, done.stdout


def build_subtask(built, subtask):
    """The full work of one subtask, up to the step before `done`."""
    name = subtask[5:]
    script = f"import os, sys; sys.exit(0 if os.path.exists('src/{subtask}.py') else 1)"
    passes_once_built = f'"{sys.executable}" -c "{script}"'
    assert log("red", plan=str(built.plan), subtask=subtask, behavior=name, command=passes_once_built)["ok"]
    assert code_of(log("green", plan=str(built.plan), subtask=subtask, behavior=name)) == "not-green"
    built.commit_code(f"src/{subtask}.py", f"def build_{name}():\n    return 1\n", f"[{subtask}] {name}")
    assert log("green", plan=str(built.plan), subtask=subtask, behavior=name)["ok"]
    built.push()
    finished_review(built, subtask)


def plan_call(built, subtask="0002-b", **fields):
    payload = {"plan": str(built.plan), "subtask": subtask, "kinds": ["scope"], "question": "a file sits outside the Scope",
               "options": "A add it vs B stop", "ruling": "A", "evidence": "the file serves the same goal",
               "reversible": True, "inside_goal": True, "reverse": "revert the commit"}
    payload.update(fields)
    return call("rule", **payload)


def ledger_of(built):
    return (built.plan / "DECISIONS.md").read_text(encoding="utf-8")


def journal_of(built):
    return (built.plan / "JOURNAL.md").read_text(encoding="utf-8")


# --- fresh subagent ---------------------------------------------------------------------------------------------------


def test_the_brief_says_that_no_human_reads_a_page(run):
    """SDD §14 row "Hands-off brief": a hands-off executor opens no page and parks a question for the human."""
    brief = call("start", plan=str(run.plan), subtask="0001-a")["brief"].splitlines()
    lines = [line for line in brief if "No human reads a page" in line]
    assert lines == ["No human reads a page in this run: open no page, and park a question for the human."]


def test_each_subtask_gets_a_brief_of_its_own_with_nothing_of_an_earlier_subtask(run):
    first = call("start", plan=str(run.plan), subtask="0001-a")
    assert first["ok"] and first["base"] == git(run.work, "rev-parse", "HEAD")
    build_subtask(run, "0001-a")
    assert call("set-change", plan=str(run.plan), change="7")["ok"]
    assert call("done", plan=str(run.plan), subtask="0001-a")["ok"]
    second = call("start", plan=str(run.plan), subtask="0002-b")
    assert second["ok"]
    assert "0002-b" in second["brief"] and "0001-a" not in second["brief"]
    assert second["base"] == git(run.work, "rev-parse", "HEAD") != first["base"]
    assert second["brief"].splitlines()[0] == "Run /afkv2:execute for one subtask. This prompt is all you get from the run."
    assert second["change"] == "7" and "change: 7" in second["brief"]


def test_only_one_subtask_runs_at_a_time(run):
    assert call("start", plan=str(run.plan), subtask="0001-a")["ok"]
    assert code_of(call("start", plan=str(run.plan), subtask="0004-d")) == "subtask-in-flight"
    answer = call("next", plan=str(run.plan))
    assert answer["subtask"] == "0001-a" and answer["resume"] is True


def test_a_second_start_resumes_with_the_same_base_and_counts_the_attempt(run):
    first = call("start", plan=str(run.plan), subtask="0001-a")
    run.commit_code("src/early.py", "x = 1\n", "[0001-a] early")
    second = call("start", plan=str(run.plan), subtask="0001-a")
    assert second["base"] == first["base"]
    assert (first["attempt"], second["attempt"]) == (1, 2)
    assert second["resume"] is True and "git log" in second["brief"]


def test_a_subtask_does_not_start_before_its_blocker_is_done(run):
    assert code_of(call("start", plan=str(run.plan), subtask="0002-b")) == "blocked-by"


def test_next_takes_the_first_row_whose_blockers_are_done(run):
    assert call("next", plan=str(run.plan))["subtask"] == "0001-a"
    assert call("park", plan=str(run.plan), subtask="0001-a", reason="one-way door", fork="f", options="o", recommendation="r")["ok"]
    assert call("next", plan=str(run.plan))["subtask"] == "0004-d"


# --- test-first order -------------------------------------------------------------------------------------------------


def test_red_refuses_a_test_that_passes(run):
    assert code_of(log("red", plan=str(run.plan), subtask="0001-a", behavior="b", command=PASS)) == "not-red"


def test_red_refuses_when_code_changed_first_and_allows_a_new_test_file(run):
    (run.work / "src").mkdir()
    (run.work / "tests").mkdir()
    (run.work / "tests" / "test_a.py").write_text("x", encoding="utf-8")
    assert log("red", plan=str(run.plan), subtask="0001-a", behavior="b", command=FAIL)["ok"]
    (run.work / "src" / "a.py").write_text("x", encoding="utf-8")
    answer = log("red", plan=str(run.plan), subtask="0001-a", behavior="c", command=FAIL)
    assert code_of(answer) == "code-before-red" and answer["error"]["files"] == ["src/a.py"]


def test_green_needs_a_red_and_a_passing_test(run):
    assert code_of(log("green", plan=str(run.plan), subtask="0001-a", behavior="b")) == "no-red"
    assert log("red", plan=str(run.plan), subtask="0001-a", behavior="b", command=FAIL)["ok"]
    assert code_of(log("green", plan=str(run.plan), subtask="0001-a", behavior="b")) == "not-green"


@pytest.mark.parametrize("name, expected", [
    ("tests/test_a.py", True), ("src/a_test.go", True), ("src/a.test.ts", True), ("src/FooTest.java", True),
    ("afkv2/tests/autopilot/fakes/f.py", True), ("src/a.py", False), ("src/latest.py", False), ("README.md", False)])
def test_what_counts_as_a_test_file(name, expected):
    assert tdd_log.is_test_file(name) is expected


def test_verdict_names_each_break_of_the_order(run):
    base = git(run.work, "rev-parse", "HEAD")
    assert [item["code"] for item in tdd_log.verdict(run.plan, "0001-a", base)] == ["no-tdd-record"]
    run.commit_code("src/first.py", "x = 1\n", "[0001-a] code first")
    assert log("red", plan=str(run.plan), subtask="0001-a", behavior="b", command=FAIL)["ok"]
    assert [item["code"] for item in tdd_log.verdict(run.plan, "0001-a", base)] == ["red-open", "code-before-red"]


@pytest.fixture
def rows_run(tmp_path, monkeypatch):
    """A `> Rules: 2` plan of 1 subtask with a Plan row column."""
    built = plan_fixture.build(tmp_path, {"0001-a": rows_contract("0001-a")}, header_extra="> Rules: 2")
    monkeypatch.chdir(built.work)
    monkeypatch.setattr(walk, "ci_state", lambda change: "watching")
    return built


OLD_HEADER = "| Tier | Check (command or method) | Proves |\n|------|---------------------------|--------|"
ROW_HEADER = "| Tier | Plan row | Check (command or method) | Proves |\n|------|----------|---------------------------|--------|"
PLAN_ROWS = ("| static | — | `git --version` | it builds |\n| unit | VR-001 | `git status --short` | the first rule |\n"
             "| unit | VR-002, VR-003 | `git status --short` | the second rule |\n| api | VR-004 | `git --version` | the answer |")


def rows_contract(subtask, rows=PLAN_ROWS):
    return contract_text(subtask, rows=rows).replace(OLD_HEADER, ROW_HEADER)


def record_of(built, subtask="0001-a"):
    return json.loads((built.plan / "review" / f"{subtask}.tdd.json").read_text(encoding="utf-8"))


def test_red_and_no_test_record_the_plan_row_the_test_and_the_level(rows_run):
    """SDD §3 row "S-4"; SDD §4: `cycles[].row`, `test`, `level`, and `no_test[].row`."""
    plan = str(rows_run.plan)
    assert log("red", plan=plan, subtask="0001-a", behavior="b", command=FAIL, row="VR-001", test="tests/test_a.py::test_b")["ok"]
    assert log("red", plan=plan, subtask="0001-a", behavior="h", command=FAIL, row="VR-004", test="tests/test_h.py::test_h", level="high")["ok"]
    assert log("no-test", plan=plan, subtask="0001-a", why="prose only", row="VR-002")["ok"]
    record = record_of(rows_run)
    assert [(item["row"], item["test"], item["level"]) for item in record["cycles"]] == [
        ("VR-001", "tests/test_a.py::test_b", "low"), ("VR-004", "tests/test_h.py::test_h", "high")]
    assert record["no_test"][0]["row"] == "VR-002" and record["no_test"][0]["why"] == "prose only"


def test_a_rules_2_plan_refuses_a_red_or_a_no_test_with_no_row(rows_run):
    plan = str(rows_run.plan)
    assert code_of(log("red", plan=plan, subtask="0001-a", behavior="b", command=FAIL)) == "bad-payload"
    assert code_of(log("no-test", plan=plan, subtask="0001-a", why="prose only")) == "bad-payload"
    assert code_of(log("red", plan=plan, subtask="0001-a", behavior="b", command=FAIL, row="VR-001", level="middle")) == "bad-payload"
    assert not (rows_run.plan / "review" / "0001-a.tdd.json").exists()


def test_an_old_call_with_no_row_still_works_on_a_plan_with_no_rules_line(run):
    assert log("red", plan=str(run.plan), subtask="0001-a", behavior="b", command=FAIL)["ok"]
    assert log("no-test", plan=str(run.plan), subtask="0001-a", why="prose only")["ok"]
    assert record_of(run)["cycles"][0]["row"] is None


def verdict_codes(built, base, subtask="0001-a"):
    return [item["code"] for item in tdd_log.verdict(built.plan, subtask, base)]


def test_a_no_test_entry_covers_only_its_row_and_not_code_written_before_the_first_red(rows_run):
    """PRD §AC-020; SDD §6 row "I-6": 1 no-test entry no longer turns off the code-before-red check."""
    base = git(rows_run.work, "rev-parse", "HEAD")
    rows_run.commit_code("src/first.py", "x = 1\n", "[0001-a] code first")
    assert log("red", plan=str(rows_run.plan), subtask="0001-a", behavior="b", command=FAIL, row="VR-001")["ok"]
    assert log("no-test", plan=str(rows_run.plan), subtask="0001-a", why="prose only", row="VR-002")["ok"]
    failures = tdd_log.verdict(rows_run.plan, "0001-a", base)
    early = [item for item in failures if item["code"] == "code-before-red"]
    assert len(early) == 1 and "VC-1" in early[0]["reason"] and "src/first.py" in early[0]["reason"]


def test_work_after_its_no_test_entry_is_covered(rows_run):
    base = git(rows_run.work, "rev-parse", "HEAD")
    assert log("no-test", plan=str(rows_run.plan), subtask="0001-a", why="prose only", row="VR-002")["ok"]
    rows_run.commit_code("docs/note.md", "text\n", "[0001-a] note")
    assert log("red", plan=str(rows_run.plan), subtask="0001-a", behavior="b", command=FAIL, row="VR-001")["ok"]
    assert "code-before-red" not in verdict_codes(rows_run, base)


def test_an_old_record_reads_as_before(run):
    """SDD §4: old records read null, null, low; an old no-test entry keeps the check off."""
    base = git(run.work, "rev-parse", "HEAD")
    head = run.commit_code("src/first.py", "x = 1\n", "[0001-a] code first")
    old = {"cycles": [{"behavior": "b", "green": {"head": head, "exit": 0}, "command": FAIL, "red": {"head": head, "exit": 1}}],
           "no_test": [{"why": "prose only"}]}
    (run.plan / "review").mkdir()
    (run.plan / "review" / "0001-a.tdd.json").write_text(json.dumps(old), encoding="utf-8")
    assert tdd_log.verdict(run.plan, "0001-a", base) == []


def test_a_high_level_cycle_needs_no_green_in_its_subtask(rows_run):
    """SDD §4: its green comes at the end gate."""
    base = git(rows_run.work, "rev-parse", "HEAD")
    assert log("red", plan=str(rows_run.plan), subtask="0001-a", behavior="h", command=FAIL, row="VR-004", level="high")["ok"]
    assert verdict_codes(rows_run, base) == []
    assert log("red", plan=str(rows_run.plan), subtask="0001-a", behavior="b", command=FAIL, row="VR-001")["ok"]
    assert verdict_codes(rows_run, base) == ["red-open"]


def test_a_subtask_with_no_behavior_says_why(run):
    base = git(run.work, "rev-parse", "HEAD")
    run.commit_code("docs/note.md", "text\n", "[0001-a] note")
    assert log("no-test", plan=str(run.plan), subtask="0001-a", why="prose only")["ok"]
    assert tdd_log.verdict(run.plan, "0001-a", base) == []


# --- own commits and the finish of a subtask --------------------------------------------------------------------------


def done_codes(answer):
    assert not answer["ok"], answer
    assert answer["error"]["code"] == "not-finished"
    return {item["code"] for item in answer["error"]["failures"]}


def test_done_needs_own_commits_and_lists_every_gap(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    codes = done_codes(call("done", plan=str(run.plan), subtask="0001-a"))
    assert {"no-own-commits", "no-tdd-record", "no-change", "no-review", "produces-missing"} <= codes
    assert run.status_of("0001-a") == "developing"


def test_a_commit_with_no_subtask_prefix_is_not_an_own_commit(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    run.commit_code("src/0001-a.py", "def a():\n    pass\n", "no prefix")
    assert "no-own-commits" in done_codes(call("done", plan=str(run.plan), subtask="0001-a"))


def test_done_refuses_an_unpushed_head_and_a_change_with_no_ci_watch(run, monkeypatch):
    call("start", plan=str(run.plan), subtask="0001-a")
    build_subtask(run, "0001-a")
    call("set-change", plan=str(run.plan), change="7")
    run.commit_code("src/later.py", "x = 1\n", "[0001-a] later")
    monkeypatch.setattr(walk, "ci_state", lambda change: "none")
    assert {"not-pushed", "no-ci-watch"} <= done_codes(call("done", plan=str(run.plan), subtask="0001-a"))


def test_a_blocking_finding_refuses_done_and_routes_to_a_park(run, monkeypatch):
    call("start", plan=str(run.plan), subtask="0001-a")
    build_subtask(run, "0001-a")
    call("set-change", plan=str(run.plan), change="7")
    monkeypatch.setattr(walk, "review_report", lambda plan, subtask: envelope.ok(left={"blocking": [{"id": "f1"}], "posted": [], "not_posted": []}, stopped_by="cap"))
    assert "review-blocking" in done_codes(call("done", plan=str(run.plan), subtask="0001-a"))


@pytest.mark.parametrize("delta, code", [({"owed": [{"id": "f1"}], "confirmed": [], "parked": []}, "delta-owed"),
                                         ({"owed": [], "confirmed": [], "parked": [{"id": "f1"}]}, "delta-parked")])
def test_an_open_delta_check_refuses_done(run, monkeypatch, delta, code):
    call("start", plan=str(run.plan), subtask="0001-a")
    build_subtask(run, "0001-a")
    call("set-change", plan=str(run.plan), change="7")
    monkeypatch.setattr(walk, "review_report", lambda plan, subtask: envelope.ok(left={"blocking": [], "posted": [], "not_posted": []}, stopped_by="cap", delta=delta))
    assert code in done_codes(call("done", plan=str(run.plan), subtask="0001-a"))


def test_done_sets_the_row_and_commits_only_on_the_run_branch(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    build_subtask(run, "0001-a")
    call("set-change", plan=str(run.plan), change="7")
    feature_before = git(run.work, "rev-parse", "HEAD")
    answer = call("done", plan=str(run.plan), subtask="0001-a")
    assert answer["ok"], answer
    assert answer["commits"] == [git(run.work, "rev-parse", "HEAD")]
    assert run.status_of("0001-a") == "done"
    assert git(run.work, "rev-parse", "HEAD") == feature_before
    assert git(run.run, "status", "--porcelain") == ""
    assert "0001-a" in git(run.run, "log", "-1", "--format=%s")


def test_the_run_has_one_change(run):
    assert call("set-change", plan=str(run.plan), change="7")["ok"]
    assert call("set-change", plan=str(run.plan), change="7")["ok"]
    assert code_of(call("set-change", plan=str(run.plan), change="8")) == "change-differs"


def test_a_missing_consumed_anchor_refuses_the_start(tmp_path, monkeypatch):
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", consumes=["0000-z src/none.py#def none( — a thing"])})
    monkeypatch.chdir(built.work)
    answer = call("start", plan=str(built.plan), subtask="0001-a")
    assert code_of(answer) == "contract-mismatch" and answer["error"]["producer"] == "0000-z"
    assert built.status_of("0001-a") == "pending"


def test_a_gate_that_cannot_run_refuses_the_start_of_that_subtask(tmp_path, monkeypatch):
    rows = "| e2e | `git --version` | the browser run |"
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", rows=rows)})
    monkeypatch.chdir(built.work)
    assert code_of(call("start", plan=str(built.plan), subtask="0001-a")) == "gate-cannot-run"
    assert built.status_of("0001-a") == "pending"


def test_a_rules_2_plan_refuses_a_live_row_marked_not_applicable_at_the_subtask_start(tmp_path, monkeypatch):
    """D-29; SDD §3 row "S-3": the start of a subtask asks the rules switch, as the run's start gate does."""
    rows = "| unit | `git status --short` | the tests run |\n| e2e | not applicable: no screen | the browser run |"
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", rows=rows)}, header_extra="> Rules: 2")
    monkeypatch.chdir(built.work)
    answer = call("start", plan=str(built.plan), subtask="0001-a")
    assert code_of(answer) == "gate-cannot-run"
    assert [item["code"] for item in answer["error"]["failures"]] == ["live-not-applicable"]
    assert built.status_of("0001-a") == "pending"


def test_a_rules_1_plan_still_skips_a_live_row_marked_not_applicable(tmp_path, monkeypatch):
    rows = "| unit | `git status --short` | the tests run |\n| e2e | not applicable: no screen | the browser run |"
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", rows=rows)})
    monkeypatch.chdir(built.work)
    assert call("start", plan=str(built.plan), subtask="0001-a")["ok"]


def test_app_config_proves_the_live_build_once_per_run_and_not_at_each_subtask_start(tmp_path, monkeypatch):
    """D-29; SDD: the live check runs once per run. Each start is a process of its own, so the proof lives in run.json."""
    rows = "| unit | `git status --short` | the tests run |\n| e2e | `git --version` | the browser run |"
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", rows=rows), "0002-b": contract_text("0002-b", rows=rows)},
                               header_extra="> App: config")
    monkeypatch.chdir(built.work)
    proofs = []
    monkeypatch.setattr(walk.start_gate, "live_check", lambda code: proofs.append(code) or envelope.ok(address="http://127.0.0.1:1"))
    assert call("start", plan=str(built.plan), subtask="0001-a")["ok"]
    assert call("park", plan=str(built.plan), subtask="0001-a", reason="r", fork="f", options="o", recommendation="r")["ok"]
    assert call("start", plan=str(built.plan), subtask="0002-b")["ok"]
    assert len(proofs) == 1
    assert git(built.run, "status", "--porcelain") == ""


def test_a_failed_live_proof_is_not_kept_so_the_next_start_proves_again(tmp_path, monkeypatch):
    rows = "| e2e | `git --version` | the browser run |"
    built = plan_fixture.build(tmp_path, {"0001-a": contract_text("0001-a", rows=rows)}, header_extra="> App: config")
    monkeypatch.chdir(built.work)
    answers = [envelope.fail("live-no-answer", "no answer"), envelope.ok(address="http://127.0.0.1:1")]
    monkeypatch.setattr(walk.start_gate, "live_check", lambda code: answers.pop(0))
    answer = call("start", plan=str(built.plan), subtask="0001-a")
    assert code_of(answer) == "gate-cannot-run" and answer["error"]["failures"][0]["code"] == "app-unreachable"
    assert call("start", plan=str(built.plan), subtask="0001-a")["ok"]
    assert answers == []


# --- two-way doors ----------------------------------------------------------------------------------------------------


def test_a_two_way_door_is_recorded_and_committed_on_the_run_branch(run):
    answer = call("decide", plan=str(run.plan), subtask="0001-a", fork="which name", options="A vs B", chosen="A", evidence="the contract says so", reverse="rename it")
    assert answer["ok"] and answer["id"] == "D-1"
    ledger = ledger_of(run)
    assert "## D-1 — which name" in ledger and "- Chosen: A — the contract says so" in ledger and "- To reverse: rename it" in ledger
    assert "decision(D-1)" in journal_of(run)
    assert git(run.run, "status", "--porcelain") == ""
    second = call("decide", plan=str(run.plan), subtask="0001-a", fork="next", options="A vs B", chosen="B", evidence="e", reverse="r")
    assert second["id"] == "D-2"


# --- plan calls: the orchestrator rules, the human gets the rest ------------------------------------------------------


def test_an_executor_stop_on_a_scope_call_is_ruled_and_recorded(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    answer = plan_call(run, subtask="0001-a")
    assert answer["ok"] and answer["ruled"] is True and answer["id"] == "D-1"
    ledger = ledger_of(run)
    assert "## D-1 — plan call: a file sits outside the Scope" in ledger
    assert "decided by autopilot" in ledger and "- Chosen: A — the file serves the same goal" in ledger
    assert "decision(D-1)" in journal_of(run)
    assert run.status_of("0001-a") == "developing"
    assert git(run.run, "status", "--porcelain") == ""


def test_the_ruling_reaches_the_executor_in_its_next_brief(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    plan_call(run, subtask="0001-a")
    again = call("start", plan=str(run.plan), subtask="0001-a")
    assert again["rulings"] == [{"id": "D-1", "ruling": "A", "question": "a file sits outside the Scope"}]
    assert "D-1" in again["brief"] and "a file sits outside the Scope" in again["brief"]
    assert again["attempt"] == 1


def test_the_human_gets_each_ruling_after_the_run(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    plan_call(run, subtask="0001-a")
    report = call("end", plan=str(run.plan))
    assert [item["id"] for item in report["rulings"]] == ["D-1"]
    assert report["rulings"][0]["question"] == "a file sits outside the Scope"


@pytest.mark.parametrize("fields, word", [
    ({"kinds": ["acceptance"]}, "acceptance"),
    ({"kinds": ["scope", "acceptance"]}, "acceptance"),
    ({"kinds": ["one-way"]}, "one-way"),
    ({"kinds": ["cost"]}, "cost"),
    ({"reversible": False}, "not reversible"),
    ({"inside_goal": False}, "outside the approved goal"),
])
def test_a_call_that_is_not_the_orchestrators_still_parks_with_its_dependents(run, fields, word):
    call("start", plan=str(run.plan), subtask="0001-a")
    answer = plan_call(run, subtask="0001-a", **fields)
    assert answer["ok"] and answer["ruled"] is False
    assert answer["parked"] == "0001-a" and answer["inherited"] == ["0002-b", "0003-c"]
    assert run.status_of("0001-a").startswith("blocked(") and word in run.status_of("0001-a")
    assert run.status_of("0002-b") == "blocked(waits on 0001-a)"
    assert "- Parked: 0001-a; dependents: 0002-b, 0003-c" in ledger_of(run)
    assert call("start", plan=str(run.plan), subtask="0001-a")["error"]["code"] == "parked"


def test_a_ruling_on_an_unknown_kind_refuses(run):
    assert code_of(plan_call(run, kinds=["taste"])) == "bad-payload"
    assert code_of(plan_call(run, kinds=[])) == "bad-payload"
    assert code_of(plan_call(run, kinds="scope")) == "bad-payload"


def test_a_ruled_call_needs_booleans_and_a_ruling(run):
    assert code_of(plan_call(run, reversible="yes")) == "bad-payload"
    assert code_of(plan_call(run, ruling=None)) == "bad-payload"
    assert code_of(plan_call(run, evidence=None)) == "bad-payload"


def test_an_order_ruling_moves_the_walk(run):
    answer = plan_call(run, subtask="0001-a", kinds=["subtask-order"], first="0004-d", then="0001-a")
    assert answer["ruled"] is True
    assert call("next", plan=str(run.plan))["subtask"] == "0004-d"
    assert code_of(call("start", plan=str(run.plan), subtask="0001-a")) == "blocked-by"


def test_an_order_ruling_on_the_running_subtask_sends_it_back_until_the_other_is_done(run):
    first = call("start", plan=str(run.plan), subtask="0001-a")
    assert plan_call(run, subtask="0001-a", kinds=["subtask-order"], first="0004-d", then="0001-a")["ruled"] is True
    assert run.status_of("0001-a") == "pending"
    assert call("next", plan=str(run.plan))["subtask"] == "0004-d"
    assert call("start", plan=str(run.plan), subtask="0004-d")["ok"]
    plan_contract.write_status(run.plan, "0004-d", "done")
    again = call("start", plan=str(run.plan), subtask="0001-a")
    assert again["base"] == first["base"] and again["resume"] is True


def test_an_order_ruling_against_the_graph_parks(run):
    answer = plan_call(run, subtask="0002-b", kinds=["subtask-order"], first="0003-c", then="0001-a")
    assert answer["ruled"] is False and "graph" in run.status_of("0002-b")


def test_an_order_ruling_of_a_subtask_on_itself_refuses(run):
    answer = plan_call(run, subtask="0001-a", kinds=["subtask-order"], first="0001-a", then="0001-a")
    assert code_of(answer) == "bad-payload"
    assert call("next", plan=str(run.plan))["subtask"] == "0001-a"


def test_an_order_ruling_needs_its_two_subtasks(run):
    assert code_of(plan_call(run, subtask="0001-a", kinds=["subtask-order"])) == "bad-payload"
    assert code_of(plan_call(run, subtask="0001-a", kinds=["subtask-order"], first="0004-d", then="9999-x")) == "bad-payload"


def test_a_file_owner_ruling_reaches_the_subtask_that_now_owns_the_file(run):
    answer = plan_call(run, subtask="0001-a", kinds=["file-owner"], applies_to=["0004-d"], question="who owns src/x.py")
    assert answer["ruled"] is True
    brief = call("start", plan=str(run.plan), subtask="0004-d")["brief"]
    assert "who owns src/x.py" in brief


def test_after_three_rulings_on_a_subtask_the_next_call_parks(run):
    call("start", plan=str(run.plan), subtask="0001-a")
    for _ in range(walk.RULING_CAP):
        assert plan_call(run, subtask="0001-a")["ruled"] is True
    answer = plan_call(run, subtask="0001-a")
    assert answer["ruled"] is False and "rulings" in run.status_of("0001-a")


def test_the_execute_skill_stops_on_a_plan_call_and_only_autopilot_rules():
    execute = (AFKV2 / "skills" / "execute" / "SKILL.md").read_text(encoding="utf-8")
    autopilot = (AFKV2 / "skills" / "autopilot" / "SKILL.md").read_text(encoding="utf-8")
    assert "`rule`" in autopilot and "`rule`" not in execute
    assert "never changes its own Scope" in execute
    assert "RESULT: stopped" in execute and "RESULT: stopped" in autopilot
    assert "fresh subagent" in autopilot
    for kind in walk.RULED_KINDS + walk.PARK_KINDS:
        assert f"`{kind}`" in autopilot and f"`{kind}`" in execute


def frontmatter(text):
    return dict(line.split(": ", 1) for line in text.split("---")[1].strip().splitlines())


def test_the_execute_skill_has_its_frontmatter_and_calls_its_verbs_and_the_skills_it_needs():
    text = (AFKV2 / "skills" / "execute" / "SKILL.md").read_text(encoding="utf-8")
    fields = frontmatter(text)
    assert fields["name"] == "execute" and fields["description"]
    for verb in tdd_log.VERBS:
        assert f"`{verb}`" in text
    for verb in ("status", "decide", "park", "set-change", "done"):
        assert f"`{verb}`" in text
    needed = ("/afkv2:code-review", "/afkv2:create-change-request", "`start`")
    for name in needed:
        assert name in text
    assert (AFKV2 / "skills" / "autopilot" / "DOORS.md").is_file() and "../autopilot/DOORS.md" in text
    source = (AFKV2 / "skills" / "execute" / "scripts" / "tdd_log.py").read_text(encoding="utf-8")
    for code in re.findall(r'Refusal\("([a-z-]+)"', source):
        if code != "bad-payload":
            assert f"`{code}`" in text


def test_the_command_answers_one_object_and_the_exit_code(run, capsys, monkeypatch):
    assert walk.main(["nothing"]) == 2
    capsys.readouterr()
    assert walk.main(["next", json.dumps({"plan": str(run.plan)})]) == 0
    assert json.loads(capsys.readouterr().out)["subtask"] == "0001-a"
    assert tdd_log.main(["nothing"]) == 2

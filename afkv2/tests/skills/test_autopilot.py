"""The start gate of a run, the frozen contract sections, and the park rule."""

from __future__ import annotations

import http.server
import json
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
REPOSITORY = AFKV2.parent
sys.path.insert(0, str(AFKV2 / "tests" / "autopilot"))
sys.path.insert(0, str(AFKV2 / "skills" / "autopilot" / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import plan_contract  # noqa: E402
import plan_fixture  # noqa: E402
import start_gate  # noqa: E402
import walk  # noqa: E402
from autopilot_v1_facts import V1_HEADER_MARK  # noqa: E402
from plan_fixture import contract_text, git  # noqa: E402

FAKE = AFKV2 / "tests" / "autopilot" / "fakes" / "fake_check_plan.py"


@pytest.fixture(autouse=True)
def recorded_inputs(monkeypatch):
    """The plan check is the recorded fake, and the forge says yes, unless a test says other."""
    monkeypatch.setattr(start_gate, "CHECK_PLAN", FAKE)
    monkeypatch.setattr(start_gate, "forge_answer", lambda code: {"ok": True, "authenticated": True, "user": "t"})


def plan_of(tmp_path, monkeypatch, contracts=None, **options):
    built = plan_fixture.build(tmp_path, contracts or {"0001-a": contract_text("0001-a")}, **options)
    monkeypatch.chdir(built.work)
    return built


def failures_of(answer):
    assert answer["ok"] is False, answer
    assert answer["error"]["code"] == "start-refused"
    return answer["error"]["failures"]


def codes_of(answer):
    return [item["code"] for item in failures_of(answer)]


# --- plan check and approval ------------------------------------------------------------------------------------------


def test_a_clean_plan_with_the_approval_starts(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    answer = start_gate.check_start(built.plan)
    assert answer["ok"], answer
    assert answer["run_branch"] == plan_fixture.RUN and answer["subtasks"] == ["0001-a"]


def test_a_failed_check_lists_every_failure_and_the_gate_writes_nothing(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CHECK_PLAN_ANSWER", "fail")
    head = git(built.run, "rev-parse", "HEAD")
    answer = start_gate.check_start(built.plan)
    assert codes_of(answer) == ["A-UNKNOWN-PRODUCER", "B-GENERIC-ANCHOR"]
    assert failures_of(answer)[0]["where"] == "0002-b.md"
    assert git(built.run, "rev-parse", "HEAD") == head and git(built.run, "status", "--porcelain") == ""


def test_no_approval_line_refuses_with_every_other_failure_beside_it(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, approval="")
    monkeypatch.setenv("FAKE_CHECK_PLAN_ANSWER", "fail")
    codes = codes_of(start_gate.check_start(built.plan))
    assert codes.count("no-approval") == 2  # the check's own failure and the gate's
    assert {"A-UNKNOWN-PRODUCER", "B-GENERIC-ANCHOR"} <= set(codes)


@pytest.mark.parametrize("approval, code", [
    ("> Division: approved 2026-13-45", "bad-approval"),
    ("> Division: pending", "no-approval"),
    ("Division: approved 2026-10-30", "no-approval"),
])
def test_only_the_exact_approval_line_counts(tmp_path, monkeypatch, approval, code):
    built = plan_of(tmp_path, monkeypatch, approval=approval)
    assert code in codes_of(start_gate.check_start(built.plan))


def test_an_approval_line_below_the_header_does_not_count(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, approval="")
    path = built.plan / "PLAN.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n> Division: approved 2026-10-30\n", encoding="utf-8")
    git(built.run, "commit", "-qam", "line below")
    assert "no-approval" in codes_of(start_gate.check_start(built.plan))


def test_exit_2_of_the_check_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CHECK_PLAN_ANSWER", "unreadable")
    assert codes_of(start_gate.check_start(built.plan)) == ["plan-check-unreadable"]


def test_an_answer_that_is_no_json_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CHECK_PLAN_ANSWER", "not-json")
    assert codes_of(start_gate.check_start(built.plan)) == ["plan-check-unreadable"]


def test_no_check_script_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.setattr(start_gate, "CHECK_PLAN", tmp_path / "absent.py")
    assert codes_of(start_gate.check_start(built.plan)) == ["plan-check-missing"]


def test_exit_0_with_a_failure_listed_still_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    script = tmp_path / "odd_check.py"
    script.write_text('print(\'{"ok": true, "failures": ["a gap"]}\')\n', encoding="utf-8")
    monkeypatch.setattr(start_gate, "CHECK_PLAN", script)
    assert codes_of(start_gate.check_start(built.plan)) == ["plan-check"]


def test_the_real_command_answers_one_object_and_exit_1(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, approval="")
    done = subprocess.run([sys.executable, str(AFKV2 / "skills" / "autopilot" / "scripts" / "start_gate.py"), "check"],
                          input=json.dumps({"plan": str(built.plan)}).encode("utf-8"), capture_output=True, timeout=120)
    assert done.returncode == 1
    assert json.loads(done.stdout)["error"]["code"] == "start-refused"


# --- v1 plans ---------------------------------------------------------------------------------------------------------


def assert_v1_refusal(answer):
    assert codes_of(answer) == ["v1-plan"]
    options = answer["error"]["options"]
    assert options == failures_of(answer)[0]["options"]
    assert options == ["finish on v1", "slice again with `/afkv2:to-subtasks`"]


def test_a_plan_header_with_a_v1_skill_name_is_a_v1_plan(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, header_extra=f"> Branch (for {V1_HEADER_MARK}execute): feat/x")
    assert_v1_refusal(start_gate.check_start(built.plan))


def test_a_materialized_seam_is_a_v1_plan(tmp_path, monkeypatch):
    produces = ["src/a.py#def a( — the code [materialized]"]
    built = plan_of(tmp_path, monkeypatch, {"0001-a": contract_text("0001-a", produces=produces)})
    assert_v1_refusal(start_gate.check_start(built.plan))


def test_a_plan_folder_on_the_feature_branch_is_a_v1_plan(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    folder = built.work / "docs" / "plan"
    folder.mkdir(parents=True)
    (folder / "PLAN.md").write_text(plan_fixture.plan_text(["0001-a"]), encoding="utf-8")
    assert_v1_refusal(start_gate.check_start(folder))


def test_a_plan_folder_outside_git_is_a_v1_plan(tmp_path, monkeypatch):
    (tmp_path / "PLAN.md").write_text(plan_fixture.plan_text(["0001-a"]), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert_v1_refusal(start_gate.check_start(tmp_path))


def test_a_v2_skill_name_is_no_v1_sign(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, header_extra="> Next: /afkv2:autopilot")
    assert start_gate.check_start(built.plan)["ok"]


def test_a_folder_with_no_plan_refuses(tmp_path):
    assert codes_of(start_gate.check_start(tmp_path)) == ["no-plan"]


# --- the frozen contract sections -------------------------------------------------------------------------------------


def test_this_slices_own_contract_parses_as_a_frozen_contract():
    path = next(REPOSITORY.glob("docs/*/afkv2/plan-s3/0015-autopilot-execute.md"), None)
    if path is None:
        pytest.skip("the plan folder of this build has left the tree")
    contract = plan_contract.read_contract(path.parent, path.stem)
    assert plan_contract.contract_failures(contract) == []
    assert contract.blocked_by == ["0012-forge-tracker-port", "0013-code-review-skill", "0014-change-request-ci-watch"]
    assert contract.produces[2] == ("afkv2/skills/autopilot/scripts/start_gate.py", "def check_start(")
    assert contract.consumes[0] == ("0012-forge-tracker-port", "afkv2/ports/forge/forge_cli.py", "def forge_main(")
    assert [row.tier for row in contract.rows] == ["static", "unit", "unit", "integration"]


def test_a_contract_with_a_missing_or_an_unknown_section_refuses(tmp_path, monkeypatch):
    text = contract_text("0001-a").replace("## Goal\n", "## Aim\n")
    built = plan_of(tmp_path, monkeypatch, {"0001-a": text})
    reasons = [item["reason"] for item in failures_of(start_gate.check_start(built.plan))]
    assert "no section `## Goal`" in reasons and "section `## Aim` is not in the frozen contract" in reasons


def test_a_heading_in_a_code_fence_is_no_section():
    sections = plan_contract.sections_of("## Goal\nbuild\n```\n## Fake\n```\n## Scope\n- a\n")
    assert list(sections) == ["Goal", "Scope"]
    assert "## Fake" in sections["Goal"]


def test_a_pipe_in_a_code_span_stays_in_its_cell():
    assert plan_contract.split_cells("| unit | `a | b` and c | proof |") == ["unit", "`a | b` and c", "proof"]


def test_a_tracker_row_with_no_contract_and_a_blocker_with_no_row_refuse(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, {"0001-a": contract_text("0001-a", blocked=["0009-z"]), "0002-b": contract_text("0002-b")})
    (built.plan / "0002-b.md").unlink()
    git(built.run, "commit", "-qam", "drop")
    assert {"no-contract", "unknown-blocker"} <= set(codes_of(start_gate.check_start(built.plan)))


def test_a_cycle_in_blocked_by_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, {"0001-a": contract_text("0001-a", blocked=["0002-b"]), "0002-b": contract_text("0002-b", blocked=["0001-a"])})
    assert "blocked-by-cycle" in codes_of(start_gate.check_start(built.plan))


# --- a gate the repository cannot run (SDD section 7) ------------------------------------------------------------------


def gate_rows(tmp_path, monkeypatch, rows, **options):
    built = plan_of(tmp_path, monkeypatch, {"0001-a": contract_text("0001-a", rows=rows)})
    return start_gate.check_start(built.plan, **options)


def test_a_live_tier_with_no_app_refuses_before_any_work(tmp_path, monkeypatch):
    answer = gate_rows(tmp_path, monkeypatch, "| e2e | `git --version` | the browser run |")
    assert codes_of(answer) == ["gate-cannot-run"]
    assert "not applicable:" in failures_of(answer)[0]["next"]
    assert failures_of(answer)[0]["where"] == "0001-a tier e2e"


def test_a_row_the_plan_names_not_applicable_needs_nothing(tmp_path, monkeypatch):
    rows = "| e2e | not applicable: the repository has no app | nothing |\n| unit | not applicable: `nosuchtool --x` is gone | nothing |"
    assert gate_rows(tmp_path, monkeypatch, rows)["ok"]


@pytest.mark.parametrize("check", ["not applicable", "not applicable:", "not applicable:   ", "Not Applicable: why", "not applicable - why"])
def test_a_not_applicable_cell_in_another_form_refuses(tmp_path, monkeypatch, check):
    answer = gate_rows(tmp_path, monkeypatch, f"| e2e | {check} | nothing |")
    assert codes_of(answer) == ["bad-not-applicable"]


def test_a_command_not_on_the_path_refuses(tmp_path, monkeypatch):
    answer = gate_rows(tmp_path, monkeypatch, "| unit | `nosuchtool-xyz --run` then read | tests |")
    assert codes_of(answer) == ["gate-cannot-run"]
    assert "nosuchtool-xyz" in failures_of(answer)[0]["reason"]


def test_words_in_code_spans_that_are_no_command_pass(tmp_path, monkeypatch):
    rows = "| static | every file has `name` and `afkv2/x/**/SKILL.md`; `> Division: approved <date>`; `git --version` | parse |"
    assert gate_rows(tmp_path, monkeypatch, rows)["ok"]


def test_a_finished_subtask_is_not_checked_again(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch, {"0001-a": contract_text("0001-a", rows="| e2e | `git --version` | run |")})
    plan_contract.write_status(built.plan, "0001-a", "done")
    git(built.run, "commit", "-qam", "done")
    assert start_gate.check_start(built.plan)["ok"]


@pytest.fixture
def local_app():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/no-such-path"
    server.shutdown()
    server.server_close()


def test_a_live_tier_passes_when_the_app_answers_even_with_an_error_status(tmp_path, monkeypatch, local_app):
    assert gate_rows(tmp_path, monkeypatch, "| api | `git --version` | the api |", app=local_app)["ok"]


@pytest.mark.parametrize("app", ["http://127.0.0.1:9/", "file:///etc/passwd", "not a url"])
def test_a_live_tier_refuses_an_app_that_does_not_answer(tmp_path, monkeypatch, app):
    answer = gate_rows(tmp_path, monkeypatch, "| api | `git --version` | the api |", app=app)
    assert codes_of(answer) == ["app-unreachable"]


# --- the worktree and the forge ---------------------------------------------------------------------------------------


def test_a_dirty_worktree_and_a_wrong_branch_refuse(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    (built.work / "loose.txt").write_text("x", encoding="utf-8")
    git(built.work, "checkout", "-qb", "feat/other")
    assert codes_of(start_gate.check_start(built.plan)) == ["wrong-branch", "dirty-worktree"]


def test_a_forge_that_is_not_ready_refuses(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.setattr(start_gate, "forge_answer", lambda code: {"ok": True, "authenticated": False, "reason": "not signed in"})
    assert codes_of(start_gate.check_start(built.plan)) == ["forge-not-ready"]


def test_the_real_forge_command_refuses_a_remote_on_no_forge_host(tmp_path, monkeypatch):
    built = plan_of(tmp_path, monkeypatch)
    monkeypatch.undo()
    monkeypatch.chdir(built.work)
    answer = start_gate.forge_failures(built.work)
    assert [item["code"] for item in answer] == ["forge-not-ready"]


# --- the park rule ----------------------------------------------------------------------------------------------------


@pytest.fixture
def diamond(tmp_path, monkeypatch):
    """0002 and 0003 wait on 0001; 0004 waits on 0002 and 0003; 0005 waits on nothing."""
    return plan_of(tmp_path, monkeypatch, {
        "0001-a": contract_text("0001-a"),
        "0002-b": contract_text("0002-b", blocked=["0001-a"]),
        "0003-c": contract_text("0003-c", blocked=["0001-a"]),
        "0004-d": contract_text("0004-d", blocked=["0002-b", "0003-c"]),
        "0005-e": contract_text("0005-e"),
    })


def test_a_park_blocks_every_dependent_and_only_those(diamond):
    answer = walk.VERBS["park"]({"plan": str(diamond.plan), "subtask": "0001-a", "reason": "one-way door", "fork": "the schema", "options": "A vs B", "recommendation": "A"})
    assert answer["inherited"] == ["0002-b", "0003-c", "0004-d"]
    assert diamond.status_of("0001-a") == "blocked(one-way door)"
    assert diamond.status_of("0004-d") == "blocked(waits on 0001-a)"
    assert diamond.status_of("0005-e") == "pending"
    assert walk.VERBS["next"]({"plan": str(diamond.plan)})["subtask"] == "0005-e"


def test_a_park_is_recorded_for_retro_in_the_ledger_and_the_journal(diamond):
    walk.VERBS["park"]({"plan": str(diamond.plan), "subtask": "0002-b", "reason": "one-way door", "fork": "the schema", "options": "A vs B", "recommendation": "A"})
    ledger = (diamond.plan / "DECISIONS.md").read_text(encoding="utf-8")
    assert "## D-1 — parked: the schema" in ledger
    assert "- Parked: 0002-b; dependents: 0004-d" in ledger and "- Recommendation: A" in ledger
    journal = (diamond.plan / "JOURNAL.md").read_text(encoding="utf-8")
    assert "| 0002-b | parked(one-way door) — " in journal
    assert "| 0004-d | park-inherited(waiting on 0002-b) — " in journal
    assert git(diamond.run, "status", "--porcelain") == ""


def test_a_second_park_keeps_the_first_reason_on_a_shared_dependent(diamond):
    payload = {"plan": str(diamond.plan), "reason": "one-way door", "fork": "f", "options": "o", "recommendation": "r"}
    walk.VERBS["park"]({**payload, "subtask": "0002-b"})
    answer = walk.VERBS["park"]({**payload, "subtask": "0003-c"})
    assert answer["inherited"] == ["0004-d"] and answer["newly_blocked"] == []
    assert diamond.status_of("0004-d") == "blocked(waits on 0002-b)"


def test_the_end_reports_what_is_done_and_parked(diamond):
    walk.VERBS["park"]({"plan": str(diamond.plan), "subtask": "0001-a", "reason": "r", "fork": "f", "options": "o", "recommendation": "x"})
    report = walk.VERBS["end"]({"plan": str(diamond.plan)})
    assert report["ship"] is False and report["done"] == [] and report["waiting"] == ["0005-e"]
    assert len(report["parked"]) == 4
    assert "run end (0/5 done, 4 parked)" in (diamond.plan / "JOURNAL.md").read_text(encoding="utf-8")


def test_a_status_in_a_pipe_character_stays_one_cell(diamond):
    plan_contract.write_status(diamond.plan, "0001-a", "blocked(a | b\nc)")
    assert diamond.status_of("0001-a") == "blocked(a / b c)"
    assert "> Last updated: 2020-01-01" not in (diamond.plan / "PLAN.md").read_text(encoding="utf-8")


def test_no_write_lands_outside_a_run_branch(diamond):
    folder = diamond.work / "plan"
    folder.mkdir()
    (folder / "PLAN.md").write_text("x", encoding="utf-8")
    with pytest.raises(start_gate.Refusal) as caught:
        walk.VERBS["park"]({"plan": str(folder), "subtask": "0001-a", "reason": "r", "fork": "f", "options": "o", "recommendation": "x"})
    assert caught.value.code == "not-run-branch"


def test_locate_finds_the_worktree_of_the_run_branch_and_adds_one_when_needed(diamond):
    found = walk.VERBS["locate"]({})
    assert Path(found["worktree"]).resolve() == diamond.run.resolve() and found["created"] is False
    git(diamond.work, "worktree", "remove", "--force", str(diamond.run))
    added = walk.VERBS["locate"]({})
    assert added["created"] is True and added["run_branch"] == plan_fixture.RUN
    assert (Path(added["plan"]) / "PLAN.md").is_file()
    assert git(Path(added["worktree"]), "rev-parse", "--abbrev-ref", "HEAD") == plan_fixture.RUN


def test_locate_with_no_run_branch_names_the_options(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-q", "-b", "feat/y")
    git(work, "config", "user.name", "t")
    git(work, "config", "user.email", "t@t.test")
    git(work, "commit", "-q", "--allow-empty", "-m", "start")
    monkeypatch.chdir(work)
    with pytest.raises(start_gate.Refusal) as caught:
        walk.VERBS["locate"]({})
    assert caught.value.code == "no-run-branch" and caught.value.extra["options"] == start_gate.V1_OPTIONS


# --- the skill --------------------------------------------------------------------------------------------------------


def test_the_autopilot_skill_has_its_frontmatter_and_names_every_verb_and_input():
    text = (AFKV2 / "skills" / "autopilot" / "SKILL.md").read_text(encoding="utf-8")
    fields = dict(line.split(": ", 1) for line in text.split("---")[1].strip().splitlines())
    assert fields["name"] == "autopilot" and fields["description"]
    for verb in ("check", "locate", "next", "start", "park", "rule", "end"):
        assert f"`{verb}`" in text
    needed = ("/afkv2:execute", "/afkv2:create-change-request", "ci_watch.py", "Ship", "/afkv2:to-subtasks", "DOORS.md")
    for name in needed:
        assert name in text
    assert (AFKV2 / "skills" / "autopilot" / "DOORS.md").is_file()
    source = (AFKV2 / "skills" / "autopilot" / "scripts" / "walk.py").read_text(encoding="utf-8")
    for code in re.findall(r'Refusal\("([a-z-]+)"', source):
        assert f"`{code}`" in text

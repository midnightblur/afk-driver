"""The end gate: each high-level row runs once (a fail once more), the judge, the gate record, back, the cap."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

AFKV2 = Path(__file__).resolve().parents[1].parent
sys.path.insert(0, str(AFKV2 / "tests" / "autopilot"))
sys.path.insert(0, str(AFKV2 / "skills" / "autopilot" / "scripts"))
sys.path.insert(0, str(AFKV2 / "scripts"))
sys.path.insert(0, str(AFKV2 / "ports"))

import afkv2_config  # noqa: E402
import end_gate  # noqa: E402
import gate_record  # noqa: E402
import plan_contract  # noqa: E402
import plan_fixture  # noqa: E402
import walk  # noqa: E402
from plan_fixture import git  # noqa: E402
from tracker.envelope import Refusal  # noqa: E402

PY = f'"{sys.executable}"'
OLD_HEADER = "| Tier | Check (command or method) | Proves |\n|------|---------------------------|--------|"
NEW_HEADER = "| Tier | Plan row | Check (command or method) | Proves |\n|------|----------|---------------------------|--------|"
SCRIPTS = {
    "pass.py": "import os, pathlib\npathlib.Path(os.environ['AFKV2_EVIDENCE'], 'answer.json').write_text('{\"status\": 200}')\n",
    "fail.py": "import sys\nprint('expected 200, got 500')\nsys.exit(1)\n",
    "flaky.py": ("import pathlib, sys\ncount = pathlib.Path(__file__).with_suffix('.count')\n"
                 "n = int(count.read_text()) if count.exists() else 0\ncount.write_text(str(n + 1))\nsys.exit(1 if n % 2 == 0 else 0)\n"),
    "fetch.py": "import sys, urllib.request\nurllib.request.urlopen(sys.argv[1], timeout=5).close()\n",
}
VERDICT = {"provider": "codex", "model": "m", "effort": "medium", "seen": ["The answer file shows status 200."],
           "compare": ["It matches the row."], "checks": [{"check": "VC-4", "result": "pass", "why": "it asserts the body"}],
           "result": "pass"}


def contract(subtask, rows, blocked=()):
    return plan_fixture.contract_text(subtask, blocked=blocked, rows=rows).replace(OLD_HEADER, NEW_HEADER)


def verification_text(rows):
    lines = ["# Verification plan — T-1", "", "> Parent PRD: PRD.md", "> App: config", "", "## Plan rows", "",
             "| Id | Criteria | Story | Given | When | Then | Level | Tier | Data | Environment | Status |",
             "|----|----------|-------|-------|------|------|-------|------|------|-------------|--------|"]
    for row, spec in rows.items():
        tier = "high" if spec["level"] in ("api", "ui-e2e", "acceptance") else "low"
        lines.append(f"| {row} | AC-001 | journey {row} | a user | they act | they see {row} | {spec['level']} | {tier} | — | — | "
                     f"{spec.get('status', 'active')} |")
    return "\n".join(lines) + "\n"


class Gate:
    def __init__(self, built, rows):
        self.built, self.rows, self.plan = built, rows, built.plan

    def run(self, judge=None, **options):
        return end_gate.run_gate(self.plan, session="claude", judge=judge or FakeJudge(), **options)

    def record(self):
        return gate_record.read(end_gate.record_path(self.plan))

    def new_head(self, name="src/change.py"):
        return self.built.commit_code(name, f"# {name} {git(self.built.work, 'rev-parse', 'HEAD')}\n", "a change")

    def set_status(self, subtask, status):
        plan_contract.write_status(self.plan, subtask, status)
        git(self.built.run, "commit", "-qam", f"{subtask} {status}")


class FakeJudge:
    def __init__(self, results=None, error=None):
        self.results, self.error, self.calls = results or {}, error, []

    def __call__(self, folder, session):
        folder = Path(folder)
        ids = [row["id"] for row in json.loads((folder / "rows.json").read_text(encoding="utf-8"))]
        self.calls.append({"ids": ids, "tests": sorted(p.relative_to(folder / "tests").as_posix() for p in (folder / "tests").rglob("*") if p.is_file()),
                           "evidence": sorted(p.name for p in (folder / "evidence").rglob("*") if p.is_file())})
        if self.error:
            raise afkv2_config.Refusal(*self.error)
        verdicts = {}
        for row in ids:
            verdict = dict(VERDICT)
            if self.results.get(row) == "fail":
                verdict = {**verdict, "result": "fail",
                           "checks": [{"check": "VC-6", "result": "fail", "why": "the expected value is computed"}]}
            verdicts[row] = verdict
        return {"ok": True, "provider": "codex", "model": "m", "effort": "medium", "verdicts": verdicts}


def make_gate(tmp_path, monkeypatch, rows, app="none", live=None, rules=2, status="done", extra_files=None):
    """`rows`: VR id -> {owner, level, check}; each owner gets a contract naming its rows in the Plan row column."""
    owners = {}
    for row, spec in rows.items():
        owners.setdefault(spec["owner"], []).append(f"| {spec.get('tier', 'api')} | {row} | {spec['check']} | it works |")
    contracts = {owner: contract(owner, "| static | — | `git --version` | it builds |\n" + "\n".join(lines))
                 for owner, lines in sorted(owners.items())}
    header = (f"> Rules: {rules}\n" if rules == 2 else "") + f"> App: {app}"
    built = plan_fixture.build(tmp_path, contracts, header_extra=header)
    config = {"spec_folder": "docs", **({"live": live} if live else {})}
    files = {".afkv2/config.json": json.dumps(config), "docs/VERIFICATION.md": verification_text(rows),
             **{f"checks/{name}": text for name, text in SCRIPTS.items()}, **(extra_files or {})}
    for name, text in files.items():
        path = built.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    git(built.work, "add", "-A")
    git(built.work, "commit", "-qm", "gate fixture")
    for owner in contracts:
        plan_contract.write_status(built.plan, owner, status)
    git(built.run, "commit", "-qam", "statuses")
    monkeypatch.chdir(built.work)
    return Gate(built, rows)


def check(script, *args):
    return f"`{PY} checks/{script}{''.join(' ' + item for item in args)}`"


THREE_ROWS = {
    "VR-001": {"owner": "0001-a", "level": "api", "check": check("pass.py")},
    "VR-002": {"owner": "0002-b", "level": "api", "check": check("fail.py")},
    "VR-003": {"owner": "0003-c", "level": "acceptance", "check": check("flaky.py")},
}
PASSING = {
    "VR-001": {"owner": "0001-a", "level": "api", "check": check("pass.py")},
    "VR-002": {"owner": "0002-b", "level": "acceptance", "check": check("pass.py")},
}


def results(record):
    return {row["row"]: row["result"] for row in record["rows"]}


# --- the rows -------------------------------------------------------------------------------------------------------


def test_each_row_runs_once_and_a_fail_once_more_and_fail_then_pass_is_flaky(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    judge = FakeJudge()
    answer = gate.run(judge)
    record = gate.record()
    assert results(record) == {"VR-001": "pass", "VR-002": "fail", "VR-003": "flaky"}
    assert {row["row"]: len(row["runs"]) for row in record["rows"]} == {"VR-001": 1, "VR-002": 2, "VR-003": 2}
    assert record["head"] == git(gate.built.work, "rev-parse", "HEAD") and record["failed_runs"] == 1
    assert answer["result"] == "failed" and answer["ran"] is True and judge.calls == []
    failed = {item["row"]: item for item in answer["failed"]}
    assert set(failed) == {"VR-002", "VR-003"}
    assert failed["VR-002"]["subtasks"] == ["0002-b"] and failed["VR-002"]["journey"] == "journey VR-002"
    assert "flaky" in failed["VR-003"]["why"]


def test_a_passed_row_keeps_its_log_and_evidence_hashed_in_the_record(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    gate.run()
    run = gate.record()["rows"][0]["runs"][0]
    assert run["exit"] == 0 and run["log"]["sha256"] and run["evidence"][0]["path"].endswith("answer.json")
    assert (end_gate.record_path(gate.plan).parent / run["evidence"][0]["path"]).is_file()


def test_the_gate_record_is_committed_on_the_run_branch(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    gate.run()
    assert git(gate.built.run, "status", "--porcelain") == ""
    assert "plan/gate/record.json" in git(gate.built.run, "ls-files")
    assert "end gate" in (gate.plan / "JOURNAL.md").read_text(encoding="utf-8")


def test_an_old_plan_has_no_end_gate(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING, rules=1)
    answer = gate.run()
    assert answer["result"] == "none" and not end_gate.record_path(gate.plan).exists()
    assert end_gate.ship_blocker(gate.plan) is None


def test_the_gate_waits_until_every_subtask_is_done(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    gate.set_status("0002-b", "pending")
    with pytest.raises(Refusal) as caught:
        gate.run()
    assert caught.value.code == "not-finished"
    assert [item["subtask"] for item in caught.value.extra["failures"]] == ["0002-b"]


def test_a_second_run_at_the_same_head_and_verification_runs_nothing(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    judge = FakeJudge()
    gate.run(judge)
    before = end_gate.record_path(gate.plan).read_bytes()
    again = gate.run(judge)
    assert again["ran"] is False and again["result"] == "passed"
    assert len(judge.calls) == 1 and end_gate.record_path(gate.plan).read_bytes() == before


# --- the judge ------------------------------------------------------------------------------------------------------


def test_the_judge_runs_once_when_every_row_passed_and_its_verdict_lands_in_the_record(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    tdd = gate.plan / "review" / "0001-a.tdd.json"
    tdd.parent.mkdir(exist_ok=True)
    tdd.write_text(json.dumps({"cycles": [{"behavior": "b", "row": "VR-001", "test": "checks/pass.py::run", "green": None}],
                               "no_test": []}), encoding="utf-8")
    judge = FakeJudge()
    answer = gate.run(judge)
    assert answer["result"] == "passed" and len(judge.calls) == 1
    assert judge.calls[0]["ids"] == ["VR-001", "VR-002"] and judge.calls[0]["tests"] == ["checks/pass.py"]
    assert "answer.json" in judge.calls[0]["evidence"]
    assert all(row["verdict"]["seen"] for row in gate.record()["rows"])
    assert answer["verdicts"]["VR-001"]["seen"] == VERDICT["seen"]
    assert answer["judge"] == {"provider": "codex", "model": "m", "effort": "medium"}


def test_a_judge_fail_sends_the_row_back_with_the_failed_check_and_counts_as_a_failed_run(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    answer = gate.run(FakeJudge({"VR-002": "fail"}))
    assert answer["result"] == "failed" and answer["failed_runs"] == 1
    failed = answer["failed"]
    assert [item["row"] for item in failed] == ["VR-002"] and "VC-6" in failed[0]["why"]
    assert end_gate.ship_blocker(gate.plan)


def test_a_judge_that_cannot_answer_leaves_the_rows_waiting_for_ship(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    answer = gate.run(FakeJudge(error=("judge-timeout", "no answer in 300 s")))
    assert answer["result"] == "waiting" and "judge-timeout" in answer["waiting"][0]["why"]
    assert end_gate.ship_blocker(gate.plan) is None


# --- back and the cap -----------------------------------------------------------------------------------------------


def test_back_reopens_only_the_subtasks_behind_the_failed_rows_and_the_next_run_runs_every_row(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    first = gate.run()
    answer = end_gate.send_back(gate.plan, [item["row"] for item in first["failed"]])
    assert answer["reopened"] == ["0002-b", "0003-c"]
    assert [gate.built.status_of(item) for item in ("0001-a", "0002-b", "0003-c")] == ["done", "pending", "pending"]
    state = json.loads((gate.plan / "run.json").read_text(encoding="utf-8"))
    record = state["subtasks"]["0002-b"]
    assert "base" not in record and record["attempts"] == 0
    brief = walk._brief(gate.plan, "0002-b", {**record, "base": "b" * 40}, None, [], False)
    assert "VR-002" in brief and "end gate" in brief
    assert git(gate.built.run, "status", "--porcelain") == ""
    gate.new_head()
    gate.set_status("0002-b", "done")
    gate.set_status("0003-c", "done")
    second = gate.run()
    assert second["ran"] is True and {row["row"] for row in gate.record()["rows"] if row["runs"]} == set(THREE_ROWS)
    assert gate.record()["failed_runs"] == 2


def test_back_refuses_a_row_that_did_not_fail(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    gate.run()
    with pytest.raises(Refusal) as caught:
        end_gate.send_back(gate.plan, ["VR-001"])
    assert caught.value.code == "bad-payload"


def test_the_fourth_gate_run_after_three_failed_ones_refuses(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    for number in range(3):
        gate.run()
        gate.new_head(f"src/change{number}.py")
    with pytest.raises(Refusal) as caught:
        gate.run()
    assert caught.value.code == "gate-cap-reached"
    assert gate.record()["failed_runs"] == 3


# --- surfaces it cannot reach ---------------------------------------------------------------------------------------


def test_a_browser_row_with_no_driver_proof_waits_and_no_subtask_stops(tmp_path, monkeypatch):
    rows = {"VR-001": {"owner": "0001-a", "level": "api", "check": check("pass.py")},
            "VR-002": {"owner": "0002-b", "level": "ui-e2e", "tier": "e2e", "check": check("pass.py")}}
    gate = make_gate(tmp_path, monkeypatch, rows)
    answer = gate.run()
    assert answer["result"] == "waiting" and results(gate.record()) == {"VR-001": "pass", "VR-002": "waiting"}
    waiting = {item["row"]: item["why"] for item in answer["waiting"]}
    assert "browser driver" in waiting["VR-002"] and "judge" in waiting["VR-001"]
    assert [gate.built.status_of(item) for item in ("0001-a", "0002-b")] == ["done", "done"]
    assert end_gate.ship_blocker(gate.plan) is None


def test_a_browser_row_runs_after_a_green_driver_proof(tmp_path, monkeypatch):
    rows = {"VR-001": {"owner": "0001-a", "level": "ui-e2e", "tier": "e2e", "check": check("pass.py")}}
    gate = make_gate(tmp_path, monkeypatch, rows)
    record = afkv2_config.data_folder() / "install.txt"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("python x\nbrowser_driver 1.10.1 2026-11-11T00:00:00\n", encoding="utf-8")
    assert gate.run()["result"] == "passed"


def test_an_app_that_does_not_answer_makes_every_row_wait(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING, app=f"http://127.0.0.1:{free_port()}")
    answer = gate.run()
    assert answer["result"] == "waiting" and set(results(gate.record()).values()) == {"waiting"}


def test_a_live_block_whose_credentials_are_not_set_makes_every_row_wait(tmp_path, monkeypatch):
    monkeypatch.delenv("AFKV2_TEST_TOKEN", raising=False)
    live = {"start": "exit 1", "address": f"http://127.0.0.1:{free_port()}", "needs": ["AFKV2_TEST_TOKEN"]}
    gate = make_gate(tmp_path, monkeypatch, PASSING, app="config", live=live)
    answer = gate.run()
    assert answer["result"] == "waiting" and "AFKV2_TEST_TOKEN" in answer["waiting"][0]["why"]


def test_a_row_with_only_a_method_waits(tmp_path, monkeypatch):
    rows = {"VR-001": {"owner": "0001-a", "level": "api", "check": "method: a human clicks through"}}
    gate = make_gate(tmp_path, monkeypatch, rows)
    assert gate.run()["result"] == "waiting"


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def answers(address):
    try:
        import urllib.request
        urllib.request.urlopen(address, timeout=2).close()
        return True
    except OSError:
        return False


def test_the_gate_starts_the_live_build_when_it_is_not_up_and_stops_it_after(tmp_path, monkeypatch):
    port = free_port()
    address = f"http://127.0.0.1:{port}/"
    live = {"start": f"{PY} -m http.server {port} --bind 127.0.0.1", "address": address, "ready_seconds": 30}
    rows = {"VR-001": {"owner": "0001-a", "level": "api", "check": check("fetch.py", address)},
            "VR-002": {"owner": "0002-b", "level": "api", "check": check("flaky.py")},
            "VR-003": {"owner": "0003-c", "level": "api", "check": check("fail.py")}}
    gate = make_gate(tmp_path, monkeypatch, rows, app="config", live=live)
    answer = gate.run()
    assert results(gate.record()) == {"VR-001": "pass", "VR-002": "flaky", "VR-003": "fail"}
    assert answer["result"] == "failed" and not answers(address)


# --- ship -----------------------------------------------------------------------------------------------------------


def test_ship_needs_a_gate_record_that_passed_or_waits(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    assert "end gate" in end_gate.ship_blocker(gate.plan)
    gate.run()
    assert "VR-002" in end_gate.ship_blocker(gate.plan)
    state = walk._load(gate.plan)
    statuses = walk._statuses(gate.plan)
    state["archived"] = walk._journal_digest(gate.plan)
    assert walk._ships(gate.plan, state, walk._tally(statuses), statuses) is False


def test_a_passed_gate_lets_the_run_ship(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    gate.run()
    state = walk._load(gate.plan)
    statuses = walk._statuses(gate.plan)
    state["archived"] = walk._journal_digest(gate.plan)
    assert end_gate.ship_blocker(gate.plan) is None
    assert walk._ships(gate.plan, state, walk._tally(statuses), statuses) is True


# --- the command and the skill --------------------------------------------------------------------------------------


def test_the_real_command_answers_one_object(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING, rules=1)
    done = subprocess.run([sys.executable, str(AFKV2 / "skills" / "autopilot" / "scripts" / "end_gate.py"), "run"],
                          input=json.dumps({"plan": str(gate.plan), "session": "claude"}).encode("utf-8"),
                          capture_output=True, timeout=120, cwd=gate.built.work)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout)["result"] == "none"


def test_the_autopilot_skill_names_the_end_gate_verbs_and_codes():
    text = (AFKV2 / "skills" / "autopilot" / "SKILL.md").read_text(encoding="utf-8")
    assert "end_gate.py" in text
    for verb in ("run", "back"):
        assert f"`{verb}`" in text
    source = (AFKV2 / "skills" / "autopilot" / "scripts" / "end_gate.py").read_text(encoding="utf-8")
    for code in re.findall(r'Refusal\("([a-z-]+)"', source):
        assert f"`{code}`" in text


# --- review round 1 -------------------------------------------------------------------------------------------------

HANG = ("import subprocess, sys, pathlib\n"
        "marker = pathlib.Path(sys.argv[1])\n"
        "code = 'import time, pathlib; time.sleep(4); pathlib.Path(r\"' + str(marker) + '\").write_text(\"alive\")'\n"
        "subprocess.Popen([sys.executable, '-c', code]).wait()\n")


def test_a_row_past_its_time_limit_stops_with_its_whole_process_tree(tmp_path, monkeypatch):
    marker = tmp_path / "child-alive.txt"
    rows = {"VR-001": {"owner": "0001-a", "level": "api", "check": check("hang.py", str(marker))}}
    gate = make_gate(tmp_path, monkeypatch, rows, extra_files={"checks/hang.py": HANG})
    monkeypatch.setattr(end_gate, "TEST_LIMIT", 1)
    gate.run()
    assert results(gate.record()) == {"VR-001": "fail"}
    import time
    time.sleep(6)
    assert not marker.exists()


def test_back_moves_the_old_review_and_test_first_records_aside(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    review = gate.plan / "review"
    review.mkdir(exist_ok=True)
    (review / "0002-b.rounds.json").write_text('{"stopped_by": "clean"}', encoding="utf-8")
    (review / "0002-b.tdd.json").write_text('{"cycles": [], "no_test": []}', encoding="utf-8")
    git(gate.built.run, "add", "-A")
    git(gate.built.run, "commit", "-qm", "records")
    gate.run()
    end_gate.send_back(gate.plan, ["VR-002"])
    assert not (review / "0002-b.rounds.json").exists() and not (review / "0002-b.tdd.json").exists()
    assert (review / "0002-b.rounds.back-1.json").is_file() and (review / "0002-b.tdd.back-1.json").is_file()
    assert git(gate.built.run, "status", "--porcelain") == ""


def test_judge_failed_runs_count_toward_the_cap_and_the_third_failed_run_says_so(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, PASSING)
    for number in range(3):
        answer = gate.run(FakeJudge({"VR-002": "fail"}))
        gate.new_head(f"src/judge{number}.py")
    assert answer["cap_reached"] is True and answer["failed_runs"] == 3
    with pytest.raises(Refusal) as caught:
        gate.run(FakeJudge())
    assert caught.value.code == "gate-cap-reached"


def test_a_waiting_row_runs_again_at_the_same_head(tmp_path, monkeypatch):
    rows = {"VR-001": {"owner": "0001-a", "level": "ui-e2e", "tier": "e2e", "check": check("pass.py")}}
    gate = make_gate(tmp_path, monkeypatch, rows)
    assert gate.run()["result"] == "waiting"
    record = afkv2_config.data_folder() / "install.txt"
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_text("browser_driver 1.10.1 2026-11-11T00:00:00\n", encoding="utf-8")
    again = gate.run()
    assert again["ran"] is True and again["result"] == "passed"


def test_the_real_commands_run_and_send_back_a_rules_2_plan(tmp_path, monkeypatch):
    gate = make_gate(tmp_path, monkeypatch, THREE_ROWS)
    script = AFKV2 / "skills" / "autopilot" / "scripts" / "end_gate.py"

    def cli(verb, payload):
        done = subprocess.run([sys.executable, str(script), verb], input=json.dumps(payload).encode("utf-8"),
                              capture_output=True, timeout=300, cwd=gate.built.work)
        return done.returncode, json.loads(done.stdout)

    code, answer = cli("run", {"plan": str(gate.plan), "session": "claude"})
    assert code == 0 and answer["result"] == "failed" and answer["cap_reached"] is False
    code, back = cli("back", {"plan": str(gate.plan), "rows": ["VR-002"]})
    assert code == 0 and back["reopened"] == ["0002-b"]
    walk.VERBS["end"]({"plan": str(gate.plan)})
    assert "VR-002" in walk.VERBS["end"]({"plan": str(gate.plan)})["gate"]

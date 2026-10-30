"""The integration row of the run: a dry run of the walk on real git, the commands in their own processes.

The run has 3 subtasks. One is done, one parks on a one-way door, and its dependent parks with it.
The gate and the CI record stay in process: the plan check is the recorded fake, and no CI runs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

AFKV2 = Path(__file__).resolve().parents[2]
SCRIPTS = AFKV2 / "skills" / "autopilot" / "scripts"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(AFKV2 / "ports"))

import plan_fixture  # noqa: E402
import start_gate  # noqa: E402
import walk  # noqa: E402
from plan_fixture import contract_text, git  # noqa: E402

FAKE = Path(__file__).resolve().parent / "fakes" / "fake_check_plan.py"
TDD = AFKV2 / "skills" / "execute" / "scripts" / "tdd_log.py"
REVIEW = AFKV2 / "skills" / "code-review" / "scripts" / "review_rounds.py"
CI_WATCH = AFKV2 / "skills" / "create-change-request" / "scripts" / "ci_watch.py"


def command(script, verb, cwd, **payload):
    done = subprocess.run([sys.executable, str(script), verb], cwd=cwd, input=json.dumps(payload).encode("utf-8"), capture_output=True, timeout=120)
    return json.loads(done.stdout)


def test_one_done_one_parked_with_its_dependent_and_the_records_only_on_the_run_branch(tmp_path, monkeypatch):
    built = plan_fixture.build(tmp_path, {
        "0001-a": contract_text("0001-a"),
        "0002-b": contract_text("0002-b", blocked=["0001-a"]),
        "0003-c": contract_text("0003-c", blocked=["0002-b"]),
    })
    plan, work = str(built.plan), built.work
    monkeypatch.chdir(work)
    monkeypatch.setattr(start_gate, "CHECK_PLAN", FAKE)
    monkeypatch.setattr(start_gate, "forge_answer", lambda code: {"ok": True, "authenticated": True})
    feature_files_before = set(git(work, "ls-tree", "-r", "--name-only", "HEAD").splitlines())

    assert command(SCRIPTS / "walk.py", "locate", work)["plan"].endswith("plan")
    assert start_gate.check_start(plan)["ok"]

    assert command(SCRIPTS / "walk.py", "next", work, plan=plan)["subtask"] == "0001-a"
    started = command(SCRIPTS / "walk.py", "start", work, plan=plan, subtask="0001-a")
    assert started["ok"] and started["base"] == git(work, "rev-parse", "HEAD")
    test_command = f'"{sys.executable}" -c "import os, sys; sys.exit(0 if os.path.exists(\'src/0001-a.py\') else 1)"'
    assert command(TDD, "red", work, plan=plan, subtask="0001-a", behavior="a", command=test_command)["ok"]
    built.commit_code("src/0001-a.py", "def a():\n    return 1\n", "[0001-a] a")
    assert command(TDD, "green", work, plan=plan, subtask="0001-a", behavior="a")["ok"]
    built.push()
    assert command(SCRIPTS / "walk.py", "decide", work, plan=plan, subtask="0001-a", fork="a name", options="A vs B", chosen="A", evidence="the contract", reverse="rename")["id"] == "D-1"
    assert command(SCRIPTS / "walk.py", "status", work, plan=plan, subtask="0001-a", status="reviewing")["ok"]
    assert command(REVIEW, "begin", work, plan=plan, subtask="0001-a", change="7", concerns=[{"name": "logic", "why": "code"}])["ok"]
    assert command(REVIEW, "record", work, plan=plan, subtask="0001-a", findings=[])["ok"]
    assert command(REVIEW, "finish", work, plan=plan, subtask="0001-a")["stopped_by"] == "clean"
    assert command(SCRIPTS / "walk.py", "set-change", work, plan=plan, change="7")["ok"]

    refused = command(SCRIPTS / "walk.py", "done", work, plan=plan, subtask="0001-a")
    assert [item["code"] for item in refused["error"]["failures"]] == ["no-ci-watch"]  # no watch has run on change 7
    assert command(CI_WATCH, "status", work, id="7")["state"] == "none"
    monkeypatch.setattr(walk, "ci_state", lambda change: "finished")  # the real watch runs in the change request tests
    assert walk.VERBS["done"]({"plan": plan, "subtask": "0001-a"})["commits"] == [git(work, "rev-parse", "HEAD")]
    assert built.status_of("0001-a") == "done"

    assert command(SCRIPTS / "walk.py", "next", work, plan=plan)["subtask"] == "0002-b"
    assert command(SCRIPTS / "walk.py", "start", work, plan=plan, subtask="0002-b")["ok"]
    parked = command(SCRIPTS / "walk.py", "park", work, plan=plan, subtask="0002-b", reason="one-way door", fork="a data migration", options="A vs B", recommendation="A")
    assert parked["inherited"] == ["0003-c"] and parked["id"] == "D-2"
    assert command(SCRIPTS / "walk.py", "next", work, plan=plan)["finished"] is True

    report = command(SCRIPTS / "walk.py", "end", work, plan=plan)
    assert report["done"] == ["0001-a"] and [item["subtask"] for item in report["parked"]] == ["0002-b", "0003-c"]
    assert built.status_of("0002-b") == "blocked(one-way door)"
    assert built.status_of("0003-c") == "blocked(waits on 0002-b)"

    ledger = (built.plan / "DECISIONS.md").read_text(encoding="utf-8")
    journal = (built.plan / "JOURNAL.md").read_text(encoding="utf-8")
    assert "## D-1 — a name" in ledger and "## D-2 — parked: a data migration" in ledger
    assert "- Parked: 0002-b; dependents: 0003-c" in ledger
    for line in ("decision(D-1)", "| 0001-a | done", "| 0002-b | parked(one-way door)", "| 0003-c | park-inherited(waiting on 0002-b)", "run end (1/3 done, 2 parked)"):
        assert line in journal

    run_files = set(git(built.run, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    assert {"plan/PLAN.md", "plan/DECISIONS.md", "plan/JOURNAL.md", "plan/run.json", "plan/review/0001-a.tdd.json", "plan/review/0001-a.rounds.json"} <= run_files
    assert all(name.startswith("plan/") for name in run_files)
    assert git(built.run, "status", "--porcelain") == ""

    feature_files = set(git(work, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    assert feature_files - feature_files_before == {"src/0001-a.py"}
    assert git(work, "log", "--format=%s", "-1") == "[0001-a] a"
    assert git(work, "status", "--porcelain") == ""

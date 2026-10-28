"""Cleanup: the five steps, the kept files, and the report's survivors, panes and strays.

The transport, the kind probe and the permission check are stand-ins; processes, the operating-system job and the
run folder are real.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
sys.path.insert(0, str(PLUGIN_ROOT / "adapters" / "transport"))
from team import cleanup, entry, knowledge, manifest, resolver  # noqa: E402
import process  # noqa: E402

RUN = "agent-team-topology"
WINDOWS = sys.platform == "win32"
OLD = "2001-01-01T00:00:00Z"


class Transport:
    """A stand-in transport kind: records each call and answers from `answers`."""

    def __init__(self, log: list):
        self.calls = log
        self.answers = {
            "agent-stop": (0, {"stopped": True, "method": "killed the process tree", "pane_closed": True,
                               "pane_id": ""}),
            "agent-list": (0, {"agents": []}),
        }

    def __call__(self, kind, verb, payload, root=None, env=None):
        self.calls.append(("transport", verb, payload))
        code, body = self.answers[verb]
        if verb == "agent-stop" and "pane_id" in body and payload.get("handle"):
            body = {**body, "pane_id": payload["handle"]}
        return code, json.dumps(body) + "\n", ""


class Team:
    def __init__(self, tmp: Path):
        self.tmp, self.root = tmp, tmp / "team"
        self.calls: list = []
        self.transport = Transport(self.calls)
        self.permission_ok = True
        self.host = entry.Host(root=self.root, main=tmp, cwd=tmp, env={}, dispatch=self.transport,
                               resolve_kind=lambda cwd, env=None: {"kind": "multiplexer"},
                               check_permission=self.permission, config=lambda key: None)
        manifest.adopt_manifest(self.root, RUN, "contact-session")
        self.dir = self.root / RUN

    def permission(self, root, env=None):
        if self.permission_ok:
            return {"ok": True, "says": "ok"}
        return {"ok": False, "says": "the spawn permission check refused"}

    def agent(self, agent_id: str, state: str = "working", **fields) -> None:
        manifest.record_entry(self.root, RUN, {"agent_id": agent_id, "stage": "execute", "pattern_step": "build",
                                               "role": "builder", "model": "implementation@claude",
                                               "lifespan": "Step", "agent_name": f"goal-{agent_id}", **fields})
        path = {"starting": [], "working": ["working"], "finished": ["working", "finished"], "lost": ["lost"],
                "cleaned": ["lost", "cleaned"], "unkillable": ["lost", "unkillable"]}[state]
        for to in path:
            manifest.move_entry(self.root, RUN, agent_id, to)

    def pane(self, agent_id: str, **fields) -> None:
        self.agent(agent_id, handle=f"pane-{agent_id}", transport_kind="multiplexer", **fields)

    def process(self, pid: int, label: str, started_at: object) -> None:
        manifest.record_entry(self.root, RUN, {"pid": pid, "owner": "contact", "label": label,
                                               "started_at": started_at})

    def state(self, agent_id: str) -> str:
        data = manifest.read_manifest(self.root, RUN)
        return next(a["state"] for a in data["agents"] if a["agent_id"] == agent_id)

    def files(self) -> list[Path]:
        """Fill the message area, the knowledge store and the resolved pattern; answer every file made."""
        made = []
        for rel in ("inbox/a1-1.json", "processed/a1-0.json", "bodies/a1-1", "signals/a1.json",
                    "supervisors/a1/1.claim", "charters/builder.md", "checkpoints/builder.json", "logs/a1.log",
                    "permission.json", "result-a1.md"):
            path = self.dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
            made.append(path)
        knowledge.write_entry(self.root, RUN, author="a1", role="builder", model="implementation@claude",
                              ground="g", stage="execute", body="a fact")
        made.extend(knowledge.store_path(self.root, RUN).iterdir())
        pattern = resolver.resolved_path(self.root, RUN)
        pattern.write_text("{}", encoding="utf-8")
        return made + [pattern]

    def clean(self) -> tuple[int, dict]:
        return cleanup.run_cleanup(RUN, self.host)


@pytest.fixture
def team(tmp_path):
    return Team(tmp_path)


def sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])


@pytest.fixture
def child():
    proc = sleeper()
    yield proc
    proc.kill()
    proc.wait()


def stops(team: Team) -> list[dict]:
    return [payload for kind, verb, payload in team.calls if verb == "agent-stop"]


# ---- step 1: kills and the entries they leave -------------------------------------------------------------

def test_an_unkillable_process_is_reported_by_agent_name_and_process_id_and_every_file_is_kept(team, child):
    made = team.files()
    team.agent("a1", pid=child.pid)
    code, report = team.clean()
    assert code == 1 and report["finished"] is False and child.poll() is None, "no started-at: nothing is killed"
    assert [(u["agent_name"], u["pid"]) for u in report["unkillable"]] == [("goal-a1", child.pid)]
    assert "identity unknown" in report["unkillable"][0]["reason"] and team.state("a1") == "unkillable"
    assert all(path.exists() for path in made) and manifest.manifest_path(team.root, RUN).exists()
    assert report["kept"] == cleanup.KEPT and report["deleted"] == []
    assert any("goal-a1" in line and str(child.pid) in line for line in report["says"])


def test_a_recorded_id_that_now_names_another_process_is_not_killed_and_is_reported_already_gone(team, child):
    team.agent("a1", pid=child.pid, started_at=OLD)
    team.process(child.pid, "a1 supervisor", OLD)
    code, report = team.clean()
    assert child.poll() is None, "the process that took the id lives"
    assert code == 0 and report["finished"] is True
    assert {"pid": child.pid, "label": "a1 supervisor", "owner": "contact", "method": "already gone"} \
        in report["already_gone"]
    assert any(g.get("agent_id") == "a1" for g in report["already_gone"])


def test_a_matching_live_process_is_killed_and_its_entry_removed(team):
    proc = sleeper()
    try:
        team.process(proc.pid, "inbox wait", process.creation_time(proc.pid))
        team.agent("a1", state="cleaned")
        code, report = team.clean()
        assert code == 0 and proc.wait(timeout=15) is not None
        assert report["stopped"] == [{"pid": proc.pid, "label": "inbox wait", "owner": "contact",
                                      "method": "killed the process tree"}]
    finally:
        proc.kill()
        proc.wait()


def test_a_failed_kill_of_a_process_entry_keeps_its_entry_names_it_and_holds_the_files(team, child, monkeypatch):
    team.process(child.pid, "a1 supervisor", process.creation_time(child.pid))
    monkeypatch.setattr(entry.process, "stop", lambda pid, **k: {"stopped": False, "reason": "1 survived",
                                                                  "survivors": [pid]})
    code, report = team.clean()
    assert code == 1 and report["kept"] == cleanup.KEPT
    assert [(p["label"], p["pid"], p["survivors"]) for p in report["processes_left"]] == \
        [("a1 supervisor", child.pid, [child.pid])]
    assert manifest.read_manifest(team.root, RUN)["processes"][0]["pid"] == child.pid


def test_a_failed_pane_close_is_named_and_the_entry_is_unkillable(team):
    team.pane("a1")
    team.transport.answers["agent-stop"] = (0, {"stopped": True, "method": "pane only", "pane_closed": False,
                                                "pane_id": ""})
    code, report = team.clean()
    assert code == 1 and team.state("a1") == "unkillable"
    assert report["panes_open"] == [{"agent_id": "a1", "agent_name": "goal-a1", "pane_id": "pane-a1"}]
    assert any("pane-a1" in line for line in report["says"])


def test_a_terminal_close_that_fails_is_named_by_its_terminal_identifier(team):
    team.agent("a1", transport_kind="desktop", terminal_id="T-7")
    team.transport.answers["agent-stop"] = (0, {"stopped": True, "method": "closed", "pane_closed": False,
                                                "terminal_id": "T-7"})
    code, report = team.clean()
    assert stops(team)[0]["terminal_id"] == "T-7"
    assert code == 1 and report["panes_open"] == [{"agent_id": "a1", "agent_name": "goal-a1", "terminal_id": "T-7"}]


def test_a_failed_agent_stop_call_marks_the_entry_unkillable(team):
    team.pane("a1")
    team.permission_ok = False
    code, report = team.clean()
    assert code == 1 and team.state("a1") == "unkillable"
    assert "permission" in report["unkillable"][0]["reason"]


def test_an_entry_with_nothing_recorded_moves_to_cleaned_and_is_named_by_agent_id_and_name(team):
    team.agent("a1")
    code, report = team.clean()
    assert code == 0 and report["nothing_recorded"] == [{"agent_id": "a1", "agent_name": "goal-a1"}]


def test_a_starting_entry_moves_through_lost_to_cleaned(team, child):
    team.agent("a1", state="starting")
    team.agent("a2", pid=child.pid)
    code, report = team.clean()
    assert code == 1 and team.state("a1") == "cleaned"
    assert report["nothing_recorded"] == [{"agent_id": "a1", "agent_name": "goal-a1"}]


def test_a_second_cleanup_retries_an_unkillable_entry_and_finishes(team, child):
    team.agent("a1", pid=child.pid)
    assert team.clean()[0] == 1
    child.kill()
    child.wait()
    code, report = team.clean()
    assert code == 0 and report["finished"] and not team.dir.exists()
    assert [g["agent_id"] for g in report["already_gone"]] == ["a1"]


def test_process_entries_stop_before_agent_entries(team, child, monkeypatch):
    team.pane("a1")
    team.process(child.pid, "a1 supervisor", process.creation_time(child.pid))
    real = entry.process.stop
    monkeypatch.setattr(entry.process, "stop", lambda pid, **k: (team.calls.append(("process", pid)), real(pid, **k))[1])
    team.clean()
    assert [c[0] if c[0] == "process" else c[1] for c in team.calls][:2] == ["process", "agent-stop"]


def test_cleaned_entries_get_no_stop(team):
    team.pane("a1", state="cleaned")
    assert team.clean()[0] == 0 and stops(team) == []


# ---- strays ----------------------------------------------------------------------------------------------

def test_strays_are_listed_by_name_and_pane_and_never_stopped(team):
    team.pane("a1")
    team.transport.answers["agent-list"] = (0, {"agents": [{"agent_name": "goal-a1", "pane_id": "pane-a1"},
                                                           {"agent_name": "goal-stray", "pane_id": "p7"}]})
    code, report = team.clean()
    assert code == 0 and report["strays"] == [{"agent_name": "goal-stray", "pane_id": "p7"}]
    assert [s.get("handle") for s in stops(team)] == ["pane-a1"]
    assert any("goal-stray" in line and "p7" in line for line in report["says"])


def test_agent_list_exit_3_is_reported_and_the_cleanup_finishes(team):
    team.transport.answers["agent-list"] = (3, {"unsupported": True, "reason": "no pane ids"})
    code, report = team.clean()
    assert code == 0 and report["strays_note"] == cleanup.NO_LIST and cleanup.NO_LIST in report["says"]


def test_an_agent_list_failure_is_named_and_holds_nothing(team):
    team.transport.answers["agent-list"] = (4, {"unavailable": True, "reason": "herdr is down"})
    code, report = team.clean()
    assert code == 0 and "herdr is down" in report["strays_note"]


# ---- steps 2 to 5 ----------------------------------------------------------------------------------------

def test_a_finished_cleanup_deletes_the_four_parts_in_order_and_keeps_a_result_file_outside(team, monkeypatch):
    outside = team.tmp / "plan" / "review" / "0001-adversary.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("report", encoding="utf-8")
    team.files()
    team.pane("a1")
    before = sorted(p for p in team.tmp.rglob("*") if team.root not in p.parents and p != team.root)
    order = []
    real = cleanup._remove
    monkeypatch.setattr(cleanup, "_remove", lambda path: (order.append(path.name), real(path))[1])
    code, report = team.clean()
    assert code == 0 and report["finished"] and report["kept"] == ""
    assert report["deleted"] == ["message area", "knowledge store", "resolved pattern", "manifest"]
    assert not team.dir.exists() and outside.read_text(encoding="utf-8") == "report"
    assert order.index("knowledge") > max(order.index(n) for n in ("inbox", "supervisors", "charters", "checkpoints"))
    assert order.index("knowledge") < order.index("pattern.json") < order.index("manifest.json")
    after = sorted(p for p in team.tmp.rglob("*") if team.root not in p.parents and p != team.root)
    assert after == before, "nothing from the store is written anywhere else"


def test_an_interrupted_cleanup_keeps_the_manifest_and_the_next_one_finishes_it(team, monkeypatch):
    team.files()
    real = cleanup._remove

    def refuse_the_store(path):
        if path.name == "knowledge":
            raise PermissionError("in use")
        real(path)

    monkeypatch.setattr(cleanup, "_remove", refuse_the_store)
    code, report = team.clean()
    assert code == 1 and report["deleted"] == ["message area"] and "in use" in " ".join(report["says"])
    assert manifest.manifest_path(team.root, RUN).exists() and not (team.dir / "inbox").exists()
    assert resolver.resolved_path(team.root, RUN).exists()
    monkeypatch.setattr(cleanup, "_remove", real)
    code, report = team.clean()
    assert code == 0 and not team.dir.exists()


def test_a_link_in_the_run_directory_is_removed_and_its_target_kept(team):
    target = team.tmp / "elsewhere"
    target.mkdir()
    (target / "keep.md").write_text("k", encoding="utf-8")
    link = team.dir / "linked"
    if WINDOWS:
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)
    assert team.clean()[0] == 0
    assert not team.dir.exists() and (target / "keep.md").read_text(encoding="utf-8") == "k"


def test_a_foreign_manifest_is_neither_read_nor_changed_and_nothing_is_deleted(team):
    made = team.files()
    path = manifest.manifest_path(team.root, RUN)
    path.write_text(json.dumps({"format_version": 99}), encoding="utf-8")
    code, report = team.clean()
    assert code == 4 and report["unavailable"] and team.calls == []
    assert json.loads(path.read_text(encoding="utf-8")) == {"format_version": 99}
    assert all(p.exists() for p in made)


def test_a_run_with_no_folder_has_nothing_to_clean(team):
    shutil.rmtree(team.dir)
    code, report = team.clean()
    assert code == 0 and report["finished"] and team.calls == [] and not team.dir.exists()


def test_a_run_folder_with_no_manifest_is_deleted(team):
    team.files()
    manifest.manifest_path(team.root, RUN).unlink()
    assert team.clean()[0] == 0 and not team.dir.exists()


# ---- command line ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [[], ["not json"], ["{}"], ['{"run": "x", "y": 1}'], ['{"run": "../x"}']])
def test_the_command_line_takes_one_object_with_a_safe_run(argv, capsys):
    assert cleanup.main(argv) == 2
    assert json.loads(capsys.readouterr().out)["error"] is True


def test_the_command_line_prints_the_report_and_its_exit_code(team, monkeypatch, capsys):
    monkeypatch.setattr(entry.Host, "discover", classmethod(lambda cls, *a, **k: team.host))
    assert cleanup.main([json.dumps({"run": RUN})]) == 0
    assert json.loads(capsys.readouterr().out)["finished"] is True


# ---- integration: the operating-system job and the wait job ------------------------------------------------

AGENT = """
import subprocess, sys, time
out = sys.argv[1]
child = subprocess.Popen([sys.executable, "-c", sys.argv[2], out + ".grand"])
wmi = sys.argv[3]
if wmi:
    done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                           "(Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
                           "@{CommandLine='" + wmi + "'}).ProcessId"], capture_output=True, text=True, timeout=60)
    wmi = done.stdout.strip()
open(out + ".tmp", "w").write(f"{child.pid} {wmi}")
import os; os.replace(out + ".tmp", out)
time.sleep(120)
"""
CHILD = """
import subprocess, sys, time
grand = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open(sys.argv[1] + ".tmp", "w").write(str(grand.pid))
import os; os.replace(sys.argv[1] + ".tmp", sys.argv[1])
time.sleep(120)
"""


def _wait_for(path: Path, seconds: float = 60) -> str:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if path.exists():
            return path.read_text(encoding="utf-8")
        time.sleep(0.1)
    raise AssertionError(f"{path} never appeared")


def _gone(pids: list[int], seconds: float = 15) -> list[int]:
    end = time.monotonic() + seconds
    alive = [p for p in pids if process.alive(p)]
    while alive and time.monotonic() < end:
        time.sleep(0.2)
        alive = [p for p in alive if process.alive(p)]
    return alive


def _job_tree(tmp: Path, wmi: str = "") -> tuple[subprocess.Popen, int, int, int, int | None]:
    """Start an agent under the headless kind's job owner; it starts a child, which starts a grandchild."""
    sys.path.insert(0, str(PLUGIN_ROOT / "adapters" / "transport" / "headless"))
    import headless
    status, out = tmp / "status.json", tmp / "pids"
    argv = [sys.executable, str(PLUGIN_ROOT / "adapters" / "transport" / "headless" / "job.py"),
            "--status", str(status), "--log", str(tmp / "agent.log"), "--cwd", str(tmp), "--",
            sys.executable, "-c", AGENT, str(out), CHILD, wmi]
    owner = headless._spawn_owner(argv, dict(os.environ))
    agent = json.loads(_wait_for(status))["pid"]
    child_pid, _, wmi_pid = _wait_for(out).partition(" ")
    grand = int(_wait_for(Path(str(out) + ".grand")))
    return owner, agent, int(child_pid), grand, int(wmi_pid) if wmi_pid.strip() else None


@pytest.mark.skipif(not WINDOWS, reason="the Windows job object seam (SDD §13 V30)")
def test_closing_the_job_owner_ends_every_process_of_the_agents_tree(tmp_path):
    owner, agent, child_pid, grand, _ = _job_tree(tmp_path)
    try:
        assert all(process.alive(p) for p in (agent, child_pid, grand))
        owner.kill()                # TerminateProcess on the owner alone: its job handle closes
        owner.wait()
        assert _gone([agent, child_pid, grand]) == [], "the kill-on-job-close limit ends the whole tree"
    finally:
        for pid in (agent, child_pid, grand):
            process.kill_tree(pid, force=True, wait_s=5)


@pytest.mark.skipif(not WINDOWS, reason="Windows Management Instrumentation is Windows only (SDD §13 Q10)")
def test_a_process_started_through_wmi_survives_the_job_and_cleanup_kills_it_only_when_registered(team, tmp_path):
    script = tmp_path / "wmi_sleep.py"
    script.write_text("import time\ntime.sleep(300)\n", encoding="utf-8")
    assert " " not in sys.executable + str(script), "the WMI command line is quoted without spaces"
    owner, agent, child_pid, grand, wmi = _job_tree(tmp_path, f"{sys.executable} {script}")
    try:
        assert wmi is not None and process.alive(wmi), "a job member started a process through WMI"
        owner.kill()
        owner.wait()
        assert _gone([agent, child_pid, grand]) == []
        assert process.alive(wmi), "WMI's process is outside the job and outside the tree"
        assert team.clean()[0] == 0 and process.alive(wmi), "cleanup stops nothing the manifest does not name"
        manifest.adopt_manifest(team.root, RUN, "contact-session")
        team.process(wmi, "agent helper", process.creation_time(wmi))
        code, report = team.clean()
        assert code == 0 and _gone([wmi]) == []
        assert [s["pid"] for s in report["stopped"]] == [wmi]
    finally:
        for pid in (agent, child_pid, grand, wmi):
            if pid:
                process.kill_tree(pid, force=True, wait_s=5)


def test_a_wait_job_ended_with_its_session_is_found_gone_removed_and_reported(team):
    env = {**os.environ, "AFK_TEAM_ROOT": str(team.root), entry.AFK_TEAM_RUN: RUN}
    job = subprocess.Popen([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-team.py"), "wait", "{}"],
                           cwd=str(PLUGIN_ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    orphans: list[int] = []
    try:
        end = time.monotonic() + 60
        while not manifest.read_manifest(team.root, RUN)["processes"] and time.monotonic() < end:
            time.sleep(0.2)
        assert [p["label"] for p in manifest.read_manifest(team.root, RUN)["processes"]] == [entry.WAIT_LABEL]
        time.sleep(1)               # the job has started the inbox wait under it
        orphans = process.tree(job.pid)[1:]
        job.kill()                  # the session ends: the job is killed, so its last command never runs
        job.wait()
        assert manifest.read_manifest(team.root, RUN)["processes"], "its entry stays in the manifest"
        code, report = team.clean()
        assert code == 0 and [(g["label"], g["method"]) for g in report["already_gone"]] == \
            [(entry.WAIT_LABEL, "already gone")]
    finally:
        for pid in [job.pid, *orphans]:
            process.kill_tree(pid, force=True, wait_s=5)

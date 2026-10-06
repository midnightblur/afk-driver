"""Occupancy of linked worktrees (PRD D6, A2, A3): who may change files in a worktree another session uses."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import test_protected_branch_guard as base
from test_protected_branch_guard import run

repo = base.repo
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
LIB = PLUGIN_ROOT / "hooks" / "lib"
SESSION_HOOK = PLUGIN_ROOT / "hooks" / "protected-branch-occupancy.py"


def load(name: str):
    sys.path.insert(0, str(LIB))
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner = importlib.util.module_from_spec(importlib.util.spec_from_file_location(
    "worktree_owner_under_test", PLUGIN_ROOT / "scripts" / "worktree_owner.py"))
owner.__spec__.loader.exec_module(owner)


@pytest.fixture
def procs():
    """Live helper processes: each stands for another harness; `ident(p)` is its `pid:ctime`."""
    started: list[subprocess.Popen] = []

    def start() -> subprocess.Popen:
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
        started.append(proc)
        time.sleep(0.2)
        return proc

    yield start
    for proc in started:
        proc.kill()
        proc.wait()


def ident(proc: subprocess.Popen) -> str:
    return f"{proc.pid}:{owner.creation_time(proc.pid)}"


def touch_in(worktree: Path, owner_id: str, session: str = "s1", **env):
    return run("claude", worktree, "Bash", {"command": "touch f.txt"}, {"session_id": session},
               AFK_WORKTREE_OWNER=owner_id, **env)


def record_of(worktree: Path) -> dict:
    gitdir = Path(base.git(worktree, "rev-parse", "--absolute-git-dir"))
    common = Path(base.git(worktree, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    return json.loads((common / "afk-occupancy" / f"{gitdir.name}.json").read_text(encoding="utf-8"))


def test_the_first_session_registers_and_a_second_live_one_is_refused(repo, procs):
    first, second = procs(), procs()
    assert touch_in(repo["topic"], ident(first), "alpha").returncode == 0
    done = touch_in(repo["topic"], ident(second), "beta")
    assert done.returncode == 2
    text = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "alpha" in text and str(first.pid) in text and "since" in text and "Move:" in text
    assert [o["session"] for o in record_of(repo["topic"])["occupants"]] == ["alpha"]


def test_the_same_identity_passes_again_and_is_recorded_once(repo, procs):
    proc = procs()
    for _ in range(3):
        assert touch_in(repo["topic"], ident(proc), "alpha").returncode == 0
    [only] = record_of(repo["topic"])["occupants"]
    assert only["pid"] == proc.pid and only["since"]


def test_a_refused_session_is_not_registered_so_the_holder_is_never_blocked(repo, procs):
    first, second = procs(), procs()
    assert touch_in(repo["topic"], ident(first)).returncode == 0
    assert touch_in(repo["topic"], ident(second), "beta").returncode == 2
    assert touch_in(repo["topic"], ident(first)).returncode == 0


def test_reads_never_register_or_refuse(repo, procs):
    first, second = procs(), procs()
    assert touch_in(repo["topic"], ident(first)).returncode == 0
    done = run("claude", repo["topic"], "Bash", {"command": "git status"}, AFK_WORKTREE_OWNER=ident(second))
    assert done.returncode == 0


def test_a_dead_occupant_is_dropped(repo, procs):
    gone = procs()
    gone_id = ident(gone)
    assert touch_in(repo["topic"], gone_id, "old").returncode == 0
    gone.kill()
    gone.wait()
    live = procs()
    assert touch_in(repo["topic"], ident(live), "new").returncode == 0
    assert [o["session"] for o in record_of(repo["topic"])["occupants"]] == ["new"]


def test_a_recycled_pid_is_dead(repo, procs):
    held, newcomer = procs(), procs()
    assert touch_in(repo["topic"], ident(held), "old").returncode == 0
    path = next((repo["main"] / ".git" / "afk-occupancy").glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["occupants"][0]["ctime"] = "1"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert touch_in(repo["topic"], ident(newcomer), "new").returncode == 0


def test_an_unreadable_creation_time_counts_as_occupied(repo, procs, monkeypatch):
    occupancy = load("occupancy")
    place = {"kind": "linked", "common": repo["main"] / ".git", "gitdir": repo["main"] / ".git" / "worktrees" / "topic",
             "root": str(repo["topic"])}
    mine = {"pid": os.getpid(), "ctime": owner.creation_time(os.getpid()), "group": "", "session": "a"}
    assert occupancy.claim(place, mine) is None
    monkeypatch.setattr(occupancy, "owner_module", lambda: type("O", (), {"state": staticmethod(
        lambda pid, ctime: "unknown")}))
    other = dict(mine, pid=mine["pid"] + 1, session="b")
    assert occupancy.claim(place, other)["session"] == "a"


@pytest.mark.parametrize("first_env,second_env,allowed", [
    ({"AFK_WORKTREE_GROUP": "team"}, {"AFK_WORKTREE_GROUP": "team"}, True),
    ({"AFK_WORKTREE_GROUP": "team"}, {"AFK_WORKTREE_GROUP": "other"}, False),
    ({"AFK_WORKTREE_GROUP": "team"}, {}, False),
    ({"HERDR_ENV": "1", "HERDR_TAB_ID": "t1"}, {"HERDR_ENV": "1", "HERDR_TAB_ID": "t1"}, True),
    ({"HERDR_ENV": "1", "HERDR_TAB_ID": "t1"}, {"HERDR_ENV": "1", "HERDR_TAB_ID": "t2"}, False),
    ({"HERDR_TAB_ID": "t1"}, {"HERDR_TAB_ID": "t1"}, False),
    ({"HERDR_ENV": "1", "HERDR_TAB_ID": "t1"}, {"AFK_WORKTREE_GROUP": "herdr-tab:t1"}, True),
    ({"HERDR_ENV": "1", "HERDR_TAB_ID": "t1", "AFK_WORKTREE_GROUP": "x"},
     {"HERDR_ENV": "1", "HERDR_TAB_ID": "t1", "AFK_WORKTREE_GROUP": "y"}, False),
])
def test_a_group_is_a_team_or_a_herdr_tab(repo, procs, first_env, second_env, allowed):
    one, two = procs(), procs()
    assert touch_in(repo["topic"], ident(one), "alpha", **first_env).returncode == 0
    done = touch_in(repo["topic"], ident(two), "beta", **second_env)
    assert (done.returncode == 0) is allowed


def test_the_main_checkout_is_never_registered(repo, procs):
    proc = procs()
    done = touch_in(repo["main"], ident(proc))
    assert done.returncode == 2
    assert not (repo["main"] / ".git" / "afk-occupancy").exists()


def test_a_protected_worktree_is_refused_for_its_branch_before_occupancy(repo, procs):
    proc = procs()
    done = touch_in(repo["protected"], ident(proc))
    assert done.returncode == 2 and "protected" in done.stderr
    assert not (repo["main"] / ".git" / "afk-occupancy").exists()


def test_the_record_lives_apart_from_the_cleanup_records(repo, procs):
    proc = procs()
    assert touch_in(repo["topic"], ident(proc)).returncode == 0
    names = {p.name for p in (repo["main"] / ".git" / "afk-occupancy").iterdir()}
    assert names == {"topic.json"}
    assert not (repo["main"] / ".git" / "afk-worktrees").exists()


def test_a_session_changing_a_worktree_it_names_registers_there(repo, procs):
    first, second = procs(), procs()
    assert touch_in(repo["topic"], ident(first), "alpha").returncode == 0
    done = run("claude", repo["main"], "Bash", {"command": f"touch {repo['topic'] / 'g.txt'}"},
               {"session_id": "beta"}, AFK_WORKTREE_OWNER=ident(second))
    assert done.returncode == 2 and "alpha" in done.stderr


def test_a_foreign_occupant_of_the_sessions_own_worktree_gets_the_move_hint(repo, procs):
    first, second = procs(), procs()
    assert touch_in(repo["topic"], ident(first), "alpha").returncode == 0
    done = touch_in(repo["topic"], ident(second), "beta")
    assert "write inside this session's worktree" not in json.loads(done.stdout)[
        "hookSpecificOutput"]["permissionDecisionReason"]


def test_a_fresh_lock_refuses_as_busy_and_a_stale_one_is_taken_over(repo, procs):
    proc = procs()
    assert touch_in(repo["topic"], ident(proc)).returncode == 0
    lock = repo["main"] / ".git" / "afk-occupancy" / "topic.json.lock"
    lock.write_text("", encoding="utf-8")
    done = touch_in(repo["topic"], ident(proc))
    assert done.returncode == 2 and "occupancy record busy" in done.stderr
    old = time.time() - 60
    os.utime(lock, (old, old))
    assert touch_in(repo["topic"], ident(proc)).returncode == 0
    assert not lock.exists()


def test_two_sessions_racing_for_a_worktree_leave_one_holder(repo, procs):
    first, second = procs(), procs()
    env = {"first": ident(first), "second": ident(second)}
    commands = []
    for name, owner_id in env.items():
        commands.append(subprocess.Popen(
            [sys.executable, str(base.GUARD)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
            cwd=repo["topic"], env=base.clean_env("claude", AFK_WORKTREE_OWNER=owner_id)))
    outs = []
    for (name, _), proc in zip(env.items(), commands):
        out, _ = proc.communicate(json.dumps(base.envelope_of(repo["topic"], "Bash", {"command": "touch f"},
                                                              {"session_id": name})))
        outs.append('"deny"' in out)
    assert sorted(outs) == [False, True]
    assert len(record_of(repo["topic"])["occupants"]) == 1


def start_envelope(cwd: Path, session: str) -> dict:
    return {"session_id": session, "cwd": str(cwd), "hook_event_name": "SessionStart", "source": "startup"}


def session_start(cwd: Path, owner_id: str, session: str, **env):
    return subprocess.run([sys.executable, str(SESSION_HOOK)], input=json.dumps(start_envelope(cwd, session)),
                          text=True, capture_output=True, cwd=cwd,
                          env=base.clean_env("claude", AFK_WORKTREE_OWNER=owner_id, **env), timeout=60)


def test_session_start_registers_first_then_advises_the_second(repo, procs):
    first, second = procs(), procs()
    done = session_start(repo["topic"], ident(first), "alpha")
    assert done.returncode == 0 and done.stdout.strip() == ""
    assert [o["session"] for o in record_of(repo["topic"])["occupants"]] == ["alpha"]
    done = session_start(repo["topic"], ident(second), "beta")
    assert done.returncode == 0
    context = json.loads(done.stdout)["hookSpecificOutput"]
    assert context["hookEventName"] == "SessionStart" and "alpha" in context["additionalContext"]
    assert "permissionDecision" not in done.stdout


def test_session_start_in_the_main_checkout_or_outside_git_is_silent(repo, procs, tmp_path):
    proc = procs()
    for cwd in (repo["main"], tmp_path):
        done = session_start(cwd, ident(proc), "alpha")
        assert done.returncode == 0 and done.stdout.strip() == ""
    assert not (repo["main"] / ".git" / "afk-occupancy").exists()


def test_session_start_never_fails(repo):
    done = subprocess.run([sys.executable, str(SESSION_HOOK)], input="{broken", text=True, capture_output=True,
                          cwd=repo["topic"], env=base.clean_env("claude"), timeout=60)
    assert done.returncode == 0 and done.stdout.strip() == ""


def test_the_session_hook_is_registered_for_both_harnesses():
    for name, root in (("hooks.json", "CLAUDE_PLUGIN_ROOT"), ("hooks.codex.json", "PLUGIN_ROOT")):
        manifest = json.loads((PLUGIN_ROOT / "hooks" / name).read_text(encoding="utf-8"))
        commands = [h["command"] for group in manifest["hooks"]["SessionStart"] for h in group["hooks"]]
        assert any(f"${{{root}}}/hooks/protected-branch-occupancy.py" in c for c in commands), name


def test_f5_003_a_lock_replaced_between_observation_and_takeover_survives(tmp_path, monkeypatch):
    occ = load("occupancy")
    monkeypatch.setattr(occ, "LOCK_WAIT", 0.3)
    record = tmp_path / "afk-occupancy" / "w.json"
    lock = Path(f"{record}.lock")
    lock.parent.mkdir()
    lock.write_text("", encoding="utf-8")
    old = time.time() - 60
    os.utime(lock, (old, old))
    seen = [0]
    real = Path.stat

    def stat(self, *args, **kwargs):
        if str(self) == str(lock):
            seen[0] += 1
            if seen[0] == 2:  # a fresh holder takes the lock after the stale observation
                self.unlink()
                os.close(os.open(self, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    with pytest.raises(occ.Busy):
        with occ.locked(record):
            pass
    assert lock.exists()


def test_f5_005_a_busy_record_never_recommends_the_busy_worktree(repo, procs):
    proc = procs()
    assert touch_in(repo["topic"], ident(proc)).returncode == 0
    (repo["main"] / ".git" / "afk-occupancy" / "topic.json.lock").write_text("", encoding="utf-8")
    done = touch_in(repo["topic"], ident(proc))
    reason = json.loads(done.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "retry in a moment; if it stays busy, move to a new worktree." in reason
    assert "write inside this session's worktree" not in reason


def test_f7_002_a_held_session_cannot_copy_into_a_worktree_another_live_session_holds(repo, procs):
    main, topic = repo["main"], repo["topic"]
    mine = base.add_worktree(main, "mine", "mine-branch")
    a, b = ident(procs()), ident(procs())
    meter = PLUGIN_ROOT / "hooks" / "protected-branch-meter.py"
    assert touch_in(topic, b, session="sB").returncode == 0
    assert touch_in(mine, a, session="sA").returncode == 0
    held_call = {"session_id": "sA", "cwd": str(main), "tool_name": "Bash", "tool_input": {"command": "make"}}
    run("claude", main, "Bash", {"command": "make"}, {"session_id": "sA"}, AFK_WORKTREE_OWNER=a)
    (main / "tracked.txt").write_text("changed\n", encoding="utf-8")
    after = subprocess.run([sys.executable, str(meter)], input=json.dumps(dict(held_call, hook_event_name="PostToolUse")),
                           text=True, capture_output=True, cwd=main, env=base.clean_env("claude", AFK_WORKTREE_OWNER=a))
    assert "tracked.txt" in after.stdout
    into_b = run("claude", main, "Bash", {"command": f"cp -- tracked.txt {(topic / 'saved.txt').as_posix()}"},
                 {"session_id": "sA"}, AFK_WORKTREE_OWNER=a)
    assert into_b.returncode == 2 and "in use by another live session" in into_b.stderr
    into_mine = run("claude", main, "Bash", {"command": f"cp -- tracked.txt {(mine / 'saved.txt').as_posix()}"},
                    {"session_id": "sA"}, AFK_WORKTREE_OWNER=a)
    assert into_mine.returncode == 0, into_mine.stderr

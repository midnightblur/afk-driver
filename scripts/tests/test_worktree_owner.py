"""Worktree ownership: the harness process, not the short-lived hook that ran."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "worktree_owner.py"


def load():
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner = load()
BASE = Path(getattr(sys, "_base_executable", None) or sys.executable)


def find_in_child() -> str:
    """Source for a child process that prints `find_owner()` as JSON."""
    code = (f"import sys, json; sys.path.insert(0, {str(SCRIPT.parent)!r}); import worktree_owner; "
            "print(json.dumps(worktree_owner.find_owner()))")
    return f"subprocess.run([sys.executable, '-c', {code!r}], capture_output=True, text=True).stdout"


def harness_env(owner_process: str | None = None) -> dict:
    environ = dict(os.environ, PYTHONHOME=sys.base_prefix)
    environ["PATH"] = str(BASE.parent) + os.pathsep + environ["PATH"]
    if owner_process:
        environ["AFK_OWNER_PROCESS"] = owner_process
    return environ


def test_state_of_this_process_is_alive():
    me = os.getpid()
    assert owner.state(me, owner.creation_time(me)) == "alive"


def test_a_pid_with_another_creation_time_is_a_recycled_one_and_dead():
    me = os.getpid()
    assert owner.state(me, "1") == "dead"


def test_an_unreadable_creation_time_is_unknown(monkeypatch):
    monkeypatch.setattr(owner, "exists", lambda pid: True)
    monkeypatch.setattr(owner, "creation_time", lambda pid: None)
    assert owner.state(os.getpid(), "1") == "unknown"


def test_a_pid_that_does_not_exist_is_dead():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    time.sleep(0.2)
    assert owner.state(child.pid, "1") == "dead"


def test_stale_recovery_and_new_creation_cannot_overlap(tmp_path, monkeypatch):
    lock = tmp_path / ".lock"
    lock.mkdir()
    (lock / "holder").write_text("123:old", encoding="utf-8")
    checking, resume = threading.Event(), threading.Event()

    def delayed_state(pid, ctime):
        if ctime == "old":
            checking.set()
            assert resume.wait(10)
            return "dead"
        return "alive"

    monkeypatch.setattr(owner, "state", delayed_state)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(owner.creation_lock, str(tmp_path), "123:new")
        assert checking.wait(10)
        second = pool.submit(owner.creation_lock, str(tmp_path), "456:new")
        try:
            time.sleep(0.3)
            assert not second.done()
        finally:
            resume.set()
        assert first.result(timeout=10)
        assert not second.result(timeout=10)
    assert (lock / "holder").read_text(encoding="utf-8") == "123:new"


def test_owner_is_the_first_ancestor_that_is_not_a_shell_or_interpreter(monkeypatch):
    processes = {
        40: (30, "python.exe"),
        30: (20, "bash.exe"),
        20: (10, "ownerhost.exe"),
        10: (0, "terminal.exe"),
    }
    created = {40: "40", 30: "30", 20: "20", 10: "10"}
    monkeypatch.setattr(owner, "snapshot", lambda: processes)
    monkeypatch.setattr(owner, "creation_time", lambda pid: created.get(pid))

    assert owner.find_owner(40) == {"pid": 20, "ctime": "20", "name": "ownerhost.exe"}


def test_a_creator_that_exited_leaves_the_recorded_owner_alive(tmp_path):
    """The record names the selected owner, so the short-lived creator's exit changes nothing."""
    inner = f"import subprocess, sys; print({find_in_child()}, flush=True)"
    holder = subprocess.Popen([str(BASE), "-c", inner + ";import time;time.sleep(20)"],
                              stdout=subprocess.PIPE, text=True, cwd=tmp_path,
                              env=harness_env(owner.basename(BASE.name)))
    try:
        line = holder.stdout.readline()
        record = json.loads(line)
        assert owner.state(record["pid"], record["ctime"]) == "alive"
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.3)
    assert owner.state(record["pid"], record["ctime"]) in ("dead", "unknown")
    assert list(tmp_path.iterdir()) == []


def test_cli_state_and_find_answer(tmp_path):
    me = os.getpid()
    done = subprocess.run([sys.executable, str(SCRIPT), "state", str(me), owner.creation_time(me)],
                          capture_output=True, text=True)
    assert done.stdout.strip() == "alive"
    assert subprocess.run([sys.executable, str(SCRIPT), "bogus"], capture_output=True).returncode == 2

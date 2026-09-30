"""Worktree ownership: the harness process, not the short-lived hook that ran."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = PLUGIN_ROOT / "scripts" / "worktree_owner.py"


def load():
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


owner = load()


def fake_harness(tmp_path: Path) -> Path:
    """A copy of the interpreter under a harness-like name."""
    suffix = ".exe" if os.name == "nt" else ""
    target = tmp_path / f"fakeharness{suffix}"
    shutil.copy(sys.executable, target)
    return target


def harness_env() -> dict:
    environ = dict(os.environ, PYTHONHOME=sys.base_prefix)
    environ["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environ["PATH"]
    return environ


def test_state_of_this_process_is_alive():
    me = os.getpid()
    assert owner.state(me, owner.creation_time(me)) == "alive"


def test_a_pid_with_another_creation_time_is_unknown_never_alive():
    me = os.getpid()
    assert owner.state(me, "1") == "unknown"


def test_a_pid_that_does_not_exist_is_dead():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    time.sleep(0.2)
    assert owner.state(child.pid, "1") == "dead"


def test_owner_is_the_first_ancestor_that_is_not_a_shell_or_interpreter(tmp_path):
    harness = fake_harness(tmp_path)
    inner = (
        "import subprocess, sys;"
        f"sys.stdout.write(subprocess.run([sys.executable, {str(SCRIPT)!r}, 'find'],"
        "capture_output=True, text=True).stdout)"
    )
    done = subprocess.run([str(harness), "-c", inner], capture_output=True, text=True,
                          env=harness_env(), timeout=60)
    if done.returncode != 0:
        pytest.skip(f"cannot run a renamed interpreter here: {done.stderr[:200]}")
    found = json.loads(done.stdout)
    assert found["name"].lower().startswith("fakeharness")
    assert found["ctime"]


def test_a_creator_that_exited_leaves_the_recorded_owner_alive(tmp_path):
    """The record names the harness, so the short-lived creator's exit changes nothing."""
    harness = fake_harness(tmp_path)
    inner = (
        "import subprocess, sys, json;"
        f"out = subprocess.run([sys.executable, {str(SCRIPT)!r}, 'find'], capture_output=True, text=True).stdout;"
        "print(out)"
    )
    holder = subprocess.Popen([str(harness), "-c", inner + ";import time;time.sleep(20)"],
                              stdout=subprocess.PIPE, text=True, env=harness_env())
    try:
        line = holder.stdout.readline()
        if not line.strip():
            pytest.skip("cannot run a renamed interpreter here")
        record = json.loads(line)
        assert owner.state(record["pid"], record["ctime"]) == "alive"
    finally:
        holder.kill()
        holder.wait()
    time.sleep(0.3)
    assert owner.state(record["pid"], record["ctime"]) in ("dead", "unknown")


def test_cli_state_and_find_answer(tmp_path):
    me = os.getpid()
    done = subprocess.run([sys.executable, str(SCRIPT), "state", str(me), owner.creation_time(me)],
                          capture_output=True, text=True)
    assert done.stdout.strip() == "alive"
    assert subprocess.run([sys.executable, str(SCRIPT), "bogus"], capture_output=True).returncode == 2

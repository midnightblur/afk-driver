"""Worktree ownership: the harness process, not the short-lived hook that ran."""
from __future__ import annotations

import importlib.util
import json
import os
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


def _repo_with_record(tmp_path, owners: list[dict]) -> tuple[Path, Path]:
    repo, linked = tmp_path / "repo", tmp_path / "linked"
    repo.mkdir()
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-C", str(repo)]
    subprocess.run([*git, "init", "-q", "-b", "dev"], check=True)
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "seed"], check=True)
    subprocess.run([*git, "worktree", "add", "-q", "-b", "w", str(linked)], check=True)
    folder = repo / ".git" / "afk-worktrees"
    folder.mkdir()
    record = folder / "linked.json"
    record.write_text(json.dumps({"name": "linked", "path": linked.as_posix(), "branch": "w",
                                  "owner": owners[0], "owners": owners}), encoding="utf-8")
    return linked, record


def test_add_owner_keeps_every_earlier_owner_and_adds_the_pane_agent(tmp_path):
    earlier = [{"pid": 11, "ctime": "1"}, {"pid": 12, "ctime": "2"}]
    linked, record = _repo_with_record(tmp_path, earlier)
    assert Path(owner.add_owner(str(linked), 4242, "999")) == record
    written = json.loads(record.read_text(encoding="utf-8"))
    assert written["owners"] == [*earlier, {"pid": 4242, "ctime": "999"}] and written["owner"] == earlier[0]
    owner.add_owner(str(linked / "."), 4242, "999")
    assert json.loads(record.read_text(encoding="utf-8"))["owners"].count({"pid": 4242, "ctime": "999"}) == 1


def test_add_owner_answers_none_for_a_worktree_no_record_names(tmp_path):
    linked, record = _repo_with_record(tmp_path, [{"pid": 11, "ctime": "1"}])
    record.unlink()
    assert owner.add_owner(str(linked), 4242, "999") is None


def test_add_owner_refuses_an_owner_with_no_creation_time(tmp_path):
    linked, record = _repo_with_record(tmp_path, [{"pid": 11, "ctime": "1"}])
    before = record.read_text(encoding="utf-8")
    for empty in ("", None):
        try:
            owner.add_owner(str(linked), 4242, empty)
        except ValueError as refused:
            assert "creation time" in str(refused)
        else:
            raise AssertionError("an owner the prune can never judge dead was written")
    assert record.read_text(encoding="utf-8") == before


def test_add_owner_gives_up_after_waiting_for_a_held_record_lock(tmp_path, monkeypatch):
    linked, record = _repo_with_record(tmp_path, [{"pid": 11, "ctime": "1"}])
    monkeypatch.setattr(owner, "LOCK_WAIT", 0.5)
    Path(f"{record}.lock").write_text("holder", encoding="utf-8")
    began = time.monotonic()
    try:
        owner.add_owner(str(linked), 4242, "999")
    except OSError as busy:
        assert "lock" in str(busy) and time.monotonic() - began >= 0.5
    else:
        raise AssertionError("add_owner wrote the record while another writer held its lock")
    assert json.loads(record.read_text(encoding="utf-8"))["owners"] == [{"pid": 11, "ctime": "1"}]
    assert Path(f"{record}.lock").read_text(encoding="utf-8") == "holder"


def test_add_owner_takes_over_a_stale_record_lock(tmp_path):
    linked, record = _repo_with_record(tmp_path, [{"pid": 11, "ctime": "1"}])
    lock = Path(f"{record}.lock")
    lock.write_text("", encoding="utf-8")
    old = time.time() - owner.LOCK_STALE - 5
    os.utime(lock, (old, old))
    owner.add_owner(str(linked), 4242, "999")
    assert {"pid": 4242, "ctime": "999"} in json.loads(record.read_text(encoding="utf-8"))["owners"]
    assert not lock.exists()


@pytest.mark.parametrize("stale, fresh", [("the stale holder", "a fresh holder"), ("", "")])
def test_a_stale_takeover_that_moved_a_fresh_lock_gives_it_back(tmp_path, monkeypatch, stale, fresh):
    lock = tmp_path / "r.json.lock"
    lock.write_text(stale, encoding="utf-8")
    old = time.time() - owner.LOCK_STALE - 5
    os.utime(lock, (old, old))
    real = os.rename

    def late(src, dst):                    # a fresh holder replaced the stale lock after the age check
        if str(src) == str(lock) and ".stale." in str(dst):
            os.remove(lock)
            lock.write_text(fresh, encoding="utf-8")
        return real(src, dst)

    monkeypatch.setattr(owner.os, "rename", late)
    owner._take_if_stale(str(lock))
    assert lock.read_text(encoding="utf-8") == fresh and time.time() - lock.stat().st_mtime < owner.LOCK_STALE
    assert [q.name for q in tmp_path.iterdir()] == ["r.json.lock"]


def test_the_lock_release_leaves_a_lock_another_holder_took(tmp_path):
    lock = tmp_path / "r.json.lock"
    with owner.record_lock(str(tmp_path / "r.json")):
        lock.write_text("another holder", encoding="utf-8")
    assert lock.read_text(encoding="utf-8") == "another holder"
    lock.unlink()
    with owner.record_lock(str(tmp_path / "r.json")):
        assert lock.exists()
    assert not lock.exists()


def test_a_failed_token_write_leaves_no_lock(tmp_path, monkeypatch):
    real = open

    class Broken:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()

        def write(self, text):
            raise OSError("disk full")

    monkeypatch.setattr("builtins.open", lambda path, mode="r", *a, **k: Broken(real(path, mode, *a, **k))
                        if mode == "x" else real(path, mode, *a, **k))
    with pytest.raises(OSError, match="disk full"):
        with owner.record_lock(str(tmp_path / "r.json")):
            pass
    assert not (tmp_path / "r.json.lock").exists()


def test_parallel_add_owner_calls_keep_every_owner(tmp_path):
    linked, record = _repo_with_record(tmp_path, [{"pid": 11, "ctime": "1"}])
    start_at = time.time() + 3
    code = (f"import sys, time; sys.path.insert(0, {str(SCRIPT.parent)!r}); import worktree_owner; "
            f"time.sleep(max(0, {start_at!r} - time.time())); "
            f"worktree_owner.add_owner({str(linked)!r}, int(sys.argv[1]), 'c' + sys.argv[1])")
    children = [subprocess.Popen([sys.executable, "-c", code, str(n)]) for n in range(100, 108)]
    assert [c.wait(timeout=120) for c in children] == [0] * 8
    owners = json.loads(record.read_text(encoding="utf-8"))["owners"]
    assert sorted(o["pid"] for o in owners) == [11, *range(100, 108)]


def test_patient_retries_a_sharing_refusal_and_gives_up_after_its_tries(monkeypatch):
    monkeypatch.setattr(owner.time, "sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("in use")
        return "done"

    assert owner.patient(flaky) == "done" and len(calls) == 3
    calls.clear()
    with pytest.raises(PermissionError):
        owner.patient(lambda: calls.append(1) or (_ for _ in ()).throw(PermissionError("in use")))
    assert len(calls) > 3


def test_the_lock_removal_waits_out_a_sharing_refusal(tmp_path, monkeypatch):
    monkeypatch.setattr(owner.time, "sleep", lambda s: None)
    lock = tmp_path / "r.json.lock"
    lock.write_text("t", encoding="utf-8")
    real, refusals = os.remove, []

    def busy(path):
        if len(refusals) < 2:
            refusals.append(path)
            raise PermissionError("in use")
        return real(path)

    monkeypatch.setattr(owner.os, "remove", busy)
    owner._remove(str(lock))
    assert not lock.exists() and len(refusals) == 2


@pytest.mark.parametrize("refusals, added", [(2, True), (10_000, False)])
def test_append_owner_retries_a_refused_replace_and_leaves_no_scratch_file(tmp_path, monkeypatch, refusals, added):
    monkeypatch.setattr(owner.time, "sleep", lambda s: None)
    record = tmp_path / "w.json"
    record.write_text(json.dumps({"path": "w", "owners": [{"pid": 11, "ctime": "1"}]}), encoding="utf-8")
    real, seen = os.replace, []

    def busy(src, dst):
        if len(seen) < refusals:
            seen.append(src)
            raise PermissionError("in use")
        return real(src, dst)

    monkeypatch.setattr(owner.os, "replace", busy)
    try:
        owner.append_owner(str(record), {"pid": 7, "ctime": "c"})
    except PermissionError:
        assert not added
    pids = [o["pid"] for o in owner.owners_of(json.loads(record.read_text(encoding="utf-8")))]
    assert pids == ([11, 7] if added else [11])
    assert sorted(q.name for q in tmp_path.iterdir()) == ["w.json"]

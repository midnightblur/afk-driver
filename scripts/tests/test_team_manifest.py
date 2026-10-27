"""Run manifest module: lifecycle table, directory mutex, atomic publish, adoption, foreign files."""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from team import manifest  # noqa: E402

FEATURE = "feat-x"
STATES = ("starting", "working", "parked", "finished", "lost", "cleaned", "unkillable")
ALLOWED = {
    "starting": {"working", "lost"},
    "working": {"parked", "finished", "lost", "cleaned", "unkillable"},
    "parked": {"working", "lost", "cleaned", "unkillable"},
    "finished": {"cleaned", "unkillable"},
    "lost": {"cleaned", "unkillable"},
    "cleaned": set(),
    "unkillable": {"cleaned"},
}
MOVES = [(s, t) for s in STATES for t in STATES + ("gone",)]
LEGAL = [m for m in MOVES if m[1] in ALLOWED[m[0]]]
ILLEGAL = [m for m in MOVES if m[1] not in ALLOWED[m[0]]]


def agent(agent_id: str = "a1", **extra) -> dict:
    entry = {"agent_id": agent_id, "role": "builder", "model": "opus", "stage": "execute",
             "pattern_step": "build", "lifespan": "Step"}
    entry.update(extra)
    return entry


def process(pid: int = 7, **extra) -> dict:
    entry = {"pid": pid, "owner": "session-1", "label": "inbox wait", "started_at": "1700000000.25"}
    entry.update(extra)
    return entry


@pytest.fixture
def root(tmp_path: Path) -> Path:
    manifest.adopt_manifest(tmp_path, FEATURE, "session-1")
    return tmp_path


def lock_of(root: Path) -> Path:
    return manifest.manifest_path(root, FEATURE).with_name("manifest.lock")


def force_state(root: Path, agent_id: str, state: str) -> None:
    path = manifest.manifest_path(root, FEATURE)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["agents"]:
        if entry["agent_id"] == agent_id:
            entry["state"] = state
    path.write_text(json.dumps(data), encoding="utf-8")


def release_later(lock: Path, delay: float = 0.3) -> threading.Thread:
    thread = threading.Thread(target=lambda: (time.sleep(delay), shutil.rmtree(lock, ignore_errors=True)))
    thread.start()
    return thread


def test_new_manifest_carries_the_header(root: Path) -> None:
    data = manifest.read_manifest(root, FEATURE)
    assert data == {"format_version": 1, "feature": FEATURE, "owning_session": "session-1",
                    "owner_generation": 1, "agents": [], "processes": []}
    assert manifest.manifest_path(root, FEATURE) == root / FEATURE / "manifest.json"


def test_read_of_a_missing_manifest_is_none(tmp_path: Path) -> None:
    assert manifest.read_manifest(tmp_path, FEATURE) is None


def test_a_new_agent_entry_starts_in_starting_with_every_field(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    [entry] = manifest.read_manifest(root, FEATURE)["agents"]
    assert entry["state"] == "starting"
    assert entry["owner_generation"] == 1
    assert entry["park_until"] is None and entry["requester"] is None
    assert set(entry) == set(manifest.AGENT_FIELDS)


def test_utc_times_to_the_second_are_stored(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent(started_at="2026-10-19T18:38:12Z"))
    manifest.record_entry(root, FEATURE, {"agent_id": "a1", "park_until": "2026-10-19T20:00:00Z",
                                          "park_reason": "provider limit"})
    [entry] = manifest.read_manifest(root, FEATURE)["agents"]
    assert (entry["started_at"], entry["park_until"]) == ("2026-10-19T18:38:12Z", "2026-10-19T20:00:00Z")


def test_a_new_agent_entry_in_another_state_is_refused(root: Path) -> None:
    with pytest.raises(manifest.TransitionRefused, match="new -> working"):
        manifest.record_entry(root, FEATURE, agent(state="working"))


def test_record_updates_fields_but_never_the_state(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    manifest.record_entry(root, FEATURE, {"agent_id": "a1", "pid": 42, "pane_label": "g builder opus hi"})
    [entry] = manifest.read_manifest(root, FEATURE)["agents"]
    assert entry["pid"] == 42 and entry["role"] == "builder"
    with pytest.raises(manifest.ManifestError, match="move_entry"):
        manifest.record_entry(root, FEATURE, {"agent_id": "a1", "state": "working"})


def test_a_name_another_entry_holds_is_refused_and_nothing_is_written(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent("a1", agent_name="g-builder", pane_label="g builder"))
    manifest.record_entry(root, FEATURE, agent("a2"))
    for taken in ({"agent_name": "g-builder"}, {"pane_label": "g-builder"}, {"agent_name": "g builder"}):
        with pytest.raises(manifest.NameTaken, match="a1"):
            manifest.record_entry(root, FEATURE, {"agent_id": "a2", **taken})
    with pytest.raises(manifest.NameTaken, match="a1"):
        manifest.record_entry(root, FEATURE, agent("a3", agent_name="g-builder"))
    agents = manifest.read_manifest(root, FEATURE)["agents"]
    assert [(a["agent_id"], a["agent_name"]) for a in agents] == [("a1", "g-builder"), ("a2", None)]
    manifest.record_entry(root, FEATURE, {"agent_id": "a1", "agent_name": "g-builder", "pid": 9})
    with pytest.raises(manifest.NameTaken) as refused:
        manifest.record_entry(root, FEATURE, {"agent_id": "a2", "pane_label": "a-free", "agent_name": "g-builder"})
    assert "'g-builder'" in str(refused.value) and "a-free" not in str(refused.value)


def test_a_cleaned_entry_takes_no_more_fields(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    manifest.move_entry(root, FEATURE, "a1", "lost")
    manifest.move_entry(root, FEATURE, "a1", "cleaned")
    with pytest.raises(manifest.ManifestError, match="cleaned"):
        manifest.record_entry(root, FEATURE, {"agent_id": "a1", "pid": 9})
    assert manifest.read_manifest(root, FEATURE)["agents"][0]["pid"] is None


@pytest.mark.parametrize("bad", [
    {"agent_id": "a1", "role": "builder"},
    agent(colour="red"),
    agent(pid="12"),
    agent(pid=-1),
    agent(pid=True),
    agent(pid=1.5),
    agent(lifespan="Forever"),
    agent(park_until="tomorrow"),
    agent(park_until="2026-10-19 18:38:12Z"),
    agent(started_at="2026-10-19T18:38:12+00:00"),
    agent(owner_generation=5),
    process(owner=None),
    process(started_at=True),
    process(started_at=""),
], ids=lambda bad: ",".join(f"{k}={v!r}" for k, v in bad.items() if k not in ("role", "model", "stage",
                                                                             "pattern_step", "label")))
def test_malformed_entries_are_refused(root: Path, bad: dict) -> None:
    with pytest.raises(manifest.ManifestError):
        manifest.record_entry(root, FEATURE, bad)
    data = manifest.read_manifest(root, FEATURE)
    assert data["agents"] == [] and data["processes"] == []


def test_a_process_entry_has_no_state_and_is_removed_by_id(root: Path) -> None:
    manifest.record_entry(root, FEATURE, process())
    manifest.record_entry(root, FEATURE, process(8, started_at=1700000001.5))
    procs = manifest.read_manifest(root, FEATURE)["processes"]
    assert procs == [process(), process(8, started_at=1700000001.5)]
    with pytest.raises(manifest.ManifestError):
        manifest.record_entry(root, FEATURE, process(9, state="working"))
    assert manifest.remove_process(root, FEATURE, 7) is True
    assert manifest.remove_process(root, FEATURE, 7) is False
    assert [p["pid"] for p in manifest.read_manifest(root, FEATURE)["processes"]] == [8]


@pytest.mark.parametrize("source,target", LEGAL)
def test_every_allowed_move_succeeds(root: Path, source: str, target: str) -> None:
    manifest.record_entry(root, FEATURE, agent())
    force_state(root, "a1", source)
    manifest.move_entry(root, FEATURE, "a1", target)
    assert manifest.read_manifest(root, FEATURE)["agents"][0]["state"] == target


@pytest.mark.parametrize("source,target", ILLEGAL)
def test_every_other_move_is_refused_by_name(root: Path, source: str, target: str) -> None:
    manifest.record_entry(root, FEATURE, agent())
    force_state(root, "a1", source)
    with pytest.raises(manifest.TransitionRefused) as refused:
        manifest.move_entry(root, FEATURE, "a1", target)
    assert f"{source} -> {target}" in str(refused.value)
    assert refused.value.move == ("a1", source, target)
    assert manifest.read_manifest(root, FEATURE)["agents"][0]["state"] == source


def test_a_resume_is_a_new_entry_and_the_old_line_closes(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent("a1", session_id="s-9"))
    manifest.move_entry(root, FEATURE, "a1", "working")
    manifest.move_entry(root, FEATURE, "a1", "lost")
    manifest.move_entry(root, FEATURE, "a1", "cleaned")
    with pytest.raises(manifest.TransitionRefused):
        manifest.move_entry(root, FEATURE, "a1", "starting")
    manifest.record_entry(root, FEATURE, agent("a2", session_id="s-9"))
    states = {e["agent_id"]: e["state"] for e in manifest.read_manifest(root, FEATURE)["agents"]}
    assert states == {"a1": "cleaned", "a2": "starting"}


def test_moving_an_unknown_agent_is_refused(root: Path) -> None:
    with pytest.raises(manifest.ManifestError, match="no entry"):
        manifest.move_entry(root, FEATURE, "ghost", "working")


def test_a_new_contact_session_takes_over_the_run(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    data = manifest.adopt_manifest(root, FEATURE, "session-2")
    assert (data["owning_session"], data["owner_generation"]) == ("session-2", 2)
    assert [e["agent_id"] for e in data["agents"]] == ["a1"]
    assert list(root.joinpath(FEATURE).glob("manifest*.json")) == [manifest.manifest_path(root, FEATURE)]


def test_the_owning_session_adopting_again_changes_nothing(root: Path) -> None:
    before = manifest.manifest_path(root, FEATURE).read_bytes()
    data = manifest.adopt_manifest(root, FEATURE, "session-1")
    assert data["owner_generation"] == 1
    assert manifest.manifest_path(root, FEATURE).read_bytes() == before


def test_an_entry_written_after_a_takeover_copies_the_new_generation(root: Path) -> None:
    manifest.adopt_manifest(root, FEATURE, "session-2")
    manifest.record_entry(root, FEATURE, agent("a2"))
    assert manifest.read_manifest(root, FEATURE)["agents"][0]["owner_generation"] == 2


@pytest.mark.parametrize("call", [
    lambda r: manifest.record_entry(r, FEATURE, agent()),
    lambda r: manifest.move_entry(r, FEATURE, "a1", "working"),
    lambda r: manifest.remove_process(r, FEATURE, 7),
], ids=["record", "move", "remove"])
@pytest.mark.parametrize("with_dir", [False, True], ids=["no-run-dir", "empty-run-dir"])
def test_writes_need_an_adopted_manifest(tmp_path: Path, call, with_dir: bool) -> None:
    if with_dir:
        tmp_path.joinpath(FEATURE).mkdir()
    with pytest.raises(manifest.ManifestError, match="adopt_manifest"):
        call(tmp_path)
    assert not manifest.manifest_path(tmp_path, FEATURE).exists()


@pytest.mark.parametrize("body", [{"format_version": 99}, {"format_version": True}, {"format_version": "1"},
                                  {"format_version": 1.5}, [1, 2]], ids=["99", "true", "text", "float", "list"])
def test_an_unknown_format_version_is_foreign_reported_once_and_kept(tmp_path: Path, capsys, body) -> None:
    path = manifest.manifest_path(tmp_path, FEATURE)
    path.parent.mkdir(parents=True)
    original = json.dumps(body)
    path.write_text(original, encoding="utf-8")
    for call in (lambda: manifest.read_manifest(tmp_path, FEATURE),
                 lambda: manifest.record_entry(tmp_path, FEATURE, agent()),
                 lambda: manifest.move_entry(tmp_path, FEATURE, "a1", "working"),
                 lambda: manifest.remove_process(tmp_path, FEATURE, 7),
                 lambda: manifest.adopt_manifest(tmp_path, FEATURE, "session-1")):
        with pytest.raises(manifest.ForeignManifest):
            call()
    assert capsys.readouterr().err.count("foreign") == 1
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("call", [
    pytest.param(lambda root: manifest.read_manifest(root, FEATURE), id="read"),
    pytest.param(lambda root: manifest.record_entry(root, FEATURE, agent()), id="record"),
    pytest.param(lambda root: manifest.move_entry(root, FEATURE, "a1", "working"), id="move"),
    pytest.param(lambda root: manifest.remove_process(root, FEATURE, 7), id="remove"),
    pytest.param(lambda root: manifest.adopt_manifest(root, FEATURE, "session-2"), id="adopt"),
])
def test_a_manifest_that_is_not_utf8_is_refused_and_kept(tmp_path: Path, call) -> None:
    path = manifest.manifest_path(tmp_path, FEATURE)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xfe{")
    with pytest.raises(manifest.ManifestError, match="UTF-8"):
        call(tmp_path)
    assert path.read_bytes() == b"\xff\xfe{"


def test_a_stale_lock_is_stolen_and_the_write_lands(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    lock.mkdir()
    (lock / "owner").write_text("dead-holder", encoding="utf-8")
    old = time.time() - manifest.LOCK_STALE - 5
    os.utime(lock, (old, old))
    monkeypatch.setattr(manifest, "LOCK_WAIT", 2.0)
    manifest.record_entry(root, FEATURE, agent())
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]
    assert not lock.exists()
    assert not list(root.joinpath(FEATURE).glob("manifest.lock.stale*"))


def test_a_live_lock_makes_the_writer_wait_then_give_up(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    lock.mkdir()
    monkeypatch.setattr(manifest, "LOCK_WAIT", 0.3)
    start = time.monotonic()
    with pytest.raises(manifest.ManifestBusy):
        manifest.record_entry(root, FEATURE, agent())
    assert time.monotonic() - start >= 0.3
    assert lock.exists()
    assert manifest.read_manifest(root, FEATURE)["agents"] == []


def mkdir_refused(monkeypatch, times: int, while_held: Path | None = None, error: type = PermissionError) -> None:
    """os.mkdir raises `error` `times` times, then works; `while_held` goes at the last refusal."""
    real_mkdir, calls = os.mkdir, []

    def refused(path, *args):
        calls.append(path)
        if len(calls) <= times:
            if while_held is not None and len(calls) == times:
                shutil.rmtree(while_held)
            raise error("access denied")
        return real_mkdir(path, *args)

    monkeypatch.setattr(manifest.os, "mkdir", refused)
    monkeypatch.setattr(manifest.time, "sleep", lambda _s: None)


def test_a_writer_waits_out_a_lock_held_past_a_hundred_polls(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    lock.mkdir()
    mkdir_refused(monkeypatch, 150, while_held=lock, error=FileExistsError)
    manifest.record_entry(root, FEATURE, agent())
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]


def test_a_lock_folder_being_deleted_is_waited_out(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    lock.mkdir()
    mkdir_refused(monkeypatch, 150, while_held=lock)
    manifest.record_entry(root, FEATURE, agent())
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]


def test_a_refused_lock_lands_on_the_hundredth_retry(root: Path, monkeypatch) -> None:
    mkdir_refused(monkeypatch, 100)
    manifest.record_entry(root, FEATURE, agent())
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]


def test_a_refused_lock_gives_up_after_a_hundred_retries_not_as_busy(root: Path, monkeypatch) -> None:
    mkdir_refused(monkeypatch, 101)
    with pytest.raises(manifest.ManifestError, match="access denied") as error:
        manifest.record_entry(root, FEATURE, agent())
    assert not isinstance(error.value, manifest.ManifestBusy)


def test_a_waiting_writer_proceeds_once_the_lock_is_released(root: Path) -> None:
    lock = lock_of(root)
    lock.mkdir()
    thread = release_later(lock)
    start = time.monotonic()
    manifest.record_entry(root, FEATURE, agent())
    thread.join()
    assert time.monotonic() - start >= 0.25
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]


@pytest.mark.parametrize("thief_holds", [False, True], ids=["thief-let-go", "thief-holds"])
def test_a_writer_whose_lock_was_taken_mid_write_redoes_it(root: Path, monkeypatch, thief_holds) -> None:
    lock = lock_of(root)
    path = manifest.manifest_path(root, FEATURE)
    writes: list[int] = []
    threads: list[threading.Thread] = []
    real_fsync = os.fsync

    def stolen_during_write(fd: int) -> None:
        real_fsync(fd)
        writes.append(fd)
        if len(writes) == 1:  # a thief takes the lock and publishes its own change
            (lock / "owner").write_text("thief", encoding="utf-8")
            data = json.loads(path.read_text(encoding="utf-8"))
            data["processes"].append(process())
            path.write_text(json.dumps(data), encoding="utf-8")
            if thief_holds:
                threads.append(release_later(lock, 0.2))
            else:
                shutil.rmtree(lock)

    monkeypatch.setattr(manifest.os, "fsync", stolen_during_write)
    manifest.record_entry(root, FEATURE, agent())
    for thread in threads:
        thread.join()
    data = manifest.read_manifest(root, FEATURE)
    assert [e["agent_id"] for e in data["agents"]] == ["a1"]
    assert [p["pid"] for p in data["processes"]] == [7]
    assert len(writes) == 2
    assert sorted(p.name for p in root.joinpath(FEATURE).iterdir()) == ["manifest.json"]


def test_the_lock_is_refreshed_before_the_publish_check(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    real_fsync, real_replace, real_owner = os.fsync, os.replace, manifest._owner
    writes: list[int] = []
    tried: list[Path] = []
    held: list[bool] = []

    def slow_write(fd: int) -> None:
        real_fsync(fd)
        writes.append(fd)
        old = time.time() - manifest.LOCK_STALE - 5
        os.utime(lock, (old, old))

    def contended(at: Path) -> str | None:
        if writes and not tried:  # a contender tries a steal at the publish check, then at the rename
            tried.append(at)
            manifest._steal_if_stale(lock)
            held.append(lock.exists())
        return real_owner(at)

    def contended_replace(src, dst) -> None:
        manifest._steal_if_stale(lock)
        held.append(lock.exists())
        real_replace(src, dst)

    monkeypatch.setattr(manifest.os, "fsync", slow_write)
    monkeypatch.setattr(manifest, "_owner", contended)
    monkeypatch.setattr(manifest.os, "replace", contended_replace)
    manifest.record_entry(root, FEATURE, agent())
    assert held == [True, True]
    assert len(writes) == 1
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]


def judged_stale(root: Path, owner: str) -> Path:
    lock = lock_of(root)
    lock.mkdir()
    (lock / "owner").write_text(owner, encoding="utf-8")
    old = time.time() - manifest.LOCK_STALE - 5
    os.utime(lock, (old, old))
    return lock


def steal_with(monkeypatch, lock: Path, before_steal=None, before_give_back=None, in_use: int = 0) -> None:
    """Run one steal; the hooks run just before the stealing rename and the give-back rename."""
    real_rename, refused = os.rename, []

    def rename(src, dst) -> None:
        if Path(src) == lock and before_steal:
            before_steal()
        if Path(dst) == lock:
            if before_give_back:
                before_give_back()
            if len(refused) < in_use:
                refused.append(src)
                raise PermissionError("in use")
        real_rename(src, dst)

    monkeypatch.setattr(manifest.os, "rename", rename)
    monkeypatch.setattr(manifest.time, "sleep", lambda _s: None)
    manifest._steal_if_stale(lock)


def graves(root: Path) -> list[Path]:
    return list(root.joinpath(FEATURE).glob("manifest.lock.stale*"))


def test_a_steal_judged_before_a_refresh_gives_the_lock_back(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "live-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: os.utime(lock))
    assert (lock / "owner").read_text(encoding="utf-8") == "live-holder"
    assert not graves(root)


def test_a_give_back_rides_out_a_file_in_use_error(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "live-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: os.utime(lock), in_use=3)
    assert (lock / "owner").read_text(encoding="utf-8") == "live-holder"
    assert not graves(root)


def test_a_lock_replaced_since_the_judgement_is_given_back(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "dead-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: (lock / "owner").write_text("new-holder", encoding="utf-8"))
    assert (lock / "owner").read_text(encoding="utf-8") == "new-holder"
    assert not graves(root)


def newcomer(lock: Path, owner: str | None = None):
    """A writer that makes the lock folder in the give-back gap, and claims it when `owner` is given."""
    def arrive() -> None:
        lock.mkdir()
        if owner is not None:
            (lock / "owner").write_text(owner, encoding="utf-8")
    return arrive


@pytest.mark.skipif(os.name == "nt", reason="POSIX rename replaces an empty folder")
def test_an_unclaimed_folder_in_the_give_back_gap_is_replaced_by_the_holder_lock(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "live-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: os.utime(lock), before_give_back=newcomer(lock))
    assert (lock / "owner").read_text(encoding="utf-8") == "live-holder"
    assert not graves(root)


@pytest.mark.skipif(os.name != "nt", reason="Windows rename refuses any existing folder")
def test_an_unclaimed_folder_in_the_give_back_gap_wins_on_windows(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "live-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: os.utime(lock), before_give_back=newcomer(lock))
    assert lock.is_dir()
    assert not (lock / "owner").exists()
    assert not graves(root)


def test_a_claimed_lock_in_the_give_back_gap_wins(root: Path, monkeypatch) -> None:
    lock = judged_stale(root, "live-holder")
    steal_with(monkeypatch, lock, before_steal=lambda: os.utime(lock), before_give_back=newcomer(lock, "newcomer"))
    assert (lock / "owner").read_text(encoding="utf-8") == "newcomer"
    assert not graves(root)


def test_a_writer_does_not_claim_a_lock_given_back_over_its_folder(root: Path, monkeypatch) -> None:
    lock = lock_of(root)
    real_mkdir = os.mkdir

    def given_back(path, *args) -> None:
        real_mkdir(path, *args)
        if Path(path) == lock:  # a stealer's give-back lands on the new folder before the claim
            (lock / "owner").write_text("live-holder", encoding="utf-8")

    monkeypatch.setattr(manifest.os, "mkdir", given_back)
    monkeypatch.setattr(manifest, "LOCK_WAIT", 0.3)
    with pytest.raises(manifest.ManifestBusy):
        manifest.record_entry(root, FEATURE, agent())
    assert (lock / "owner").read_text(encoding="utf-8") == "live-holder"
    assert manifest.read_manifest(root, FEATURE)["agents"] == []


def test_an_unreadable_lock_owner_does_not_stop_the_publish(root: Path, monkeypatch) -> None:
    real_owner, real_fsync = manifest._owner, os.fsync
    unreadable: list[Path] = []
    writes: list[int] = []

    def unreadable_after_the_write(lock: Path) -> str | None:
        if writes and not unreadable:
            unreadable.append(lock)
            return None
        return real_owner(lock)

    def counted(fd: int) -> None:
        writes.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(manifest, "_owner", unreadable_after_the_write)
    monkeypatch.setattr(manifest.os, "fsync", counted)
    manifest.record_entry(root, FEATURE, agent())
    assert [e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]] == ["a1"]
    assert unreadable == [lock_of(root)]
    assert len(writes) == 1


def disk_full(*_args):
    raise OSError("disk full")


@pytest.mark.parametrize("step", ["fsync", "replace"])
def test_a_failed_publish_leaves_the_old_manifest_and_no_temporary_file(root: Path, monkeypatch, step) -> None:
    path = manifest.manifest_path(root, FEATURE)
    before = path.read_bytes()
    monkeypatch.setattr(manifest.os, step, disk_full)
    with pytest.raises(manifest.ManifestError, match="disk full"):
        manifest.record_entry(root, FEATURE, agent())
    assert path.read_bytes() == before
    assert sorted(p.name for p in root.joinpath(FEATURE).iterdir()) == ["manifest.json"]


def publish_with_temp_in_use(root: Path, monkeypatch, refusals: int) -> list[str]:
    """Fail the rename while deleting the temporary file is refused `refusals` times; return the .tmp files left."""
    real_unlink = pathlib.Path.unlink
    refused: list[Path] = []

    def in_use(self, *args, **kwargs):
        if self.name.endswith(".tmp") and len(refused) < refusals:
            refused.append(self)
            raise PermissionError("in use")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "unlink", in_use)
    monkeypatch.setattr(manifest.time, "sleep", lambda _s: None)
    monkeypatch.setattr(manifest.os, "replace", disk_full)
    with pytest.raises(manifest.ManifestError, match="disk full"):
        manifest.record_entry(root, FEATURE, agent())
    return [p.name for p in root.joinpath(FEATURE).iterdir() if p.suffix == ".tmp"]


def test_a_temporary_file_in_use_briefly_is_still_removed(root: Path, monkeypatch, capsys) -> None:
    assert publish_with_temp_in_use(root, monkeypatch, 3) == []
    assert capsys.readouterr().err == ""


def test_a_temporary_file_in_use_for_good_is_left_and_named(root: Path, monkeypatch, capsys) -> None:
    left = publish_with_temp_in_use(root, monkeypatch, 1000)
    assert len(left) == 1
    assert left[0] in capsys.readouterr().err


def test_a_failed_owner_write_frees_the_lock(root: Path, monkeypatch) -> None:
    real = pathlib.Path.open

    def broken(self, *args, **kwargs):
        if self.name == "owner":
            raise OSError("disk full")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", broken)
    with pytest.raises(manifest.ManifestError, match="disk full"):
        manifest.record_entry(root, FEATURE, agent())
    assert not lock_of(root).exists()


WRITER = """
import sys
sys.path.insert(0, sys.argv[1])
from team import manifest
root, feature, tag, count = sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
for n in range(count):
    manifest.record_entry(root, feature, {"agent_id": f"{tag}-{n}", "role": "r", "model": "m",
                                          "stage": "s", "pattern_step": "p", "lifespan": "Turn"})
"""


def test_two_racing_writers_lose_no_update(root: Path) -> None:
    count = 25
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(SCRIPTS), str(root), FEATURE, tag, str(count)],
                              stderr=subprocess.PIPE, text=True) for tag in ("x", "y")]
    for proc in procs:
        _, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
    ids = {e["agent_id"] for e in manifest.read_manifest(root, FEATURE)["agents"]}
    assert ids == {f"{tag}-{n}" for tag in ("x", "y") for n in range(count)}


def test_the_checkpoint_path_comes_from_feature_and_role(tmp_path: Path) -> None:
    path = manifest.checkpoint_path(tmp_path, FEATURE, "reviewer")
    assert path == tmp_path / FEATURE / "checkpoints" / "reviewer.json"
    assert path.parent.parent == manifest.manifest_path(tmp_path, FEATURE).parent
    assert manifest.checkpoint_path(tmp_path, FEATURE, "builder") != path
    assert manifest.checkpoint_path(tmp_path, "feat-y", "reviewer") != path


@pytest.mark.parametrize("name", ["", "..", "a/b", "a\\b", ".", "a:b", "a\0b"])
def test_unsafe_names_are_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(manifest.ManifestError):
        manifest.checkpoint_path(tmp_path, FEATURE, name)
    with pytest.raises(manifest.ManifestError):
        manifest.manifest_path(tmp_path, name)

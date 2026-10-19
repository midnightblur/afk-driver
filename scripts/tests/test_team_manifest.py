"""Run manifest module: lifecycle table, directory mutex, atomic publish, adoption, foreign files."""
from __future__ import annotations

import json
import os
import subprocess
import sys
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


def agent(agent_id: str = "a1", **extra) -> dict:
    entry = {"agent_id": agent_id, "role": "builder", "model": "opus", "stage": "execute",
             "pattern_step": "build", "lifespan": "Step"}
    entry.update(extra)
    return entry


@pytest.fixture
def root(tmp_path: Path) -> Path:
    manifest.adopt_manifest(tmp_path, FEATURE, "session-1")
    return tmp_path


def force_state(root: Path, agent_id: str, state: str) -> None:
    path = manifest.manifest_path(root, FEATURE)
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data["agents"]:
        if entry["agent_id"] == agent_id:
            entry["state"] = state
    path.write_text(json.dumps(data), encoding="utf-8")


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


@pytest.mark.parametrize("bad", [
    {"agent_id": "a1", "role": "builder"},
    agent(colour="red"),
    agent(pid="12"),
    agent(lifespan="Forever"),
    agent(park_until="tomorrow"),
    {"pid": 7, "owner": "a1"},
])
def test_malformed_entries_are_refused(root: Path, bad: dict) -> None:
    with pytest.raises(manifest.ManifestError):
        manifest.record_entry(root, FEATURE, bad)
    assert manifest.read_manifest(root, FEATURE)["agents"] == []


def test_a_process_entry_has_no_state_and_is_removed_by_id(root: Path) -> None:
    manifest.record_entry(root, FEATURE, {"pid": 7, "owner": "session-1", "label": "inbox wait",
                                          "started_at": "1700000000.25"})
    [proc] = manifest.read_manifest(root, FEATURE)["processes"]
    assert proc == {"pid": 7, "owner": "session-1", "label": "inbox wait", "started_at": "1700000000.25"}
    with pytest.raises(manifest.ManifestError):
        manifest.record_entry(root, FEATURE, {"pid": 8, "owner": "a1", "label": "x", "started_at": "1",
                                              "state": "working"})
    assert manifest.remove_process(root, FEATURE, 7) is True
    assert manifest.remove_process(root, FEATURE, 7) is False
    assert manifest.read_manifest(root, FEATURE)["processes"] == []


@pytest.mark.parametrize("source", STATES)
@pytest.mark.parametrize("target", STATES + ("gone",))
def test_every_move_follows_the_table(root: Path, source: str, target: str) -> None:
    manifest.record_entry(root, FEATURE, agent())
    force_state(root, "a1", source)
    if target in ALLOWED[source]:
        manifest.move_entry(root, FEATURE, "a1", target)
        assert manifest.read_manifest(root, FEATURE)["agents"][0]["state"] == target
    else:
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


def test_a_new_contact_session_adopts_the_manifest(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    data = manifest.adopt_manifest(root, FEATURE, "session-2")
    assert (data["owning_session"], data["owner_generation"]) == ("session-2", 2)
    assert [e["agent_id"] for e in data["agents"]] == ["a1"]
    again = manifest.adopt_manifest(root, FEATURE, "session-2")
    assert again["owner_generation"] == 2
    assert list(root.joinpath(FEATURE).glob("manifest*.json")) == [manifest.manifest_path(root, FEATURE)]
    manifest.record_entry(root, FEATURE, agent("a2"))
    entry = manifest.read_manifest(root, FEATURE)["agents"][1]
    assert entry["owner_generation"] == 2


def test_writes_need_an_adopted_manifest(tmp_path: Path) -> None:
    with pytest.raises(manifest.ManifestError, match="adopt_manifest"):
        manifest.record_entry(tmp_path, FEATURE, agent())


def test_an_unknown_format_version_is_foreign_reported_once_and_kept(tmp_path: Path, capsys) -> None:
    path = manifest.manifest_path(tmp_path, FEATURE)
    path.parent.mkdir(parents=True)
    original = json.dumps({"format_version": 99, "anything": True})
    path.write_text(original, encoding="utf-8")
    for call in (lambda: manifest.read_manifest(tmp_path, FEATURE),
                 lambda: manifest.record_entry(tmp_path, FEATURE, agent()),
                 lambda: manifest.adopt_manifest(tmp_path, FEATURE, "session-1")):
        with pytest.raises(manifest.ForeignManifest):
            call()
    assert capsys.readouterr().err.count("foreign") == 1
    assert path.read_text(encoding="utf-8") == original


def test_a_stale_lock_is_stolen(root: Path, monkeypatch) -> None:
    lock = manifest.manifest_path(root, FEATURE).with_name("manifest.lock")
    lock.mkdir()
    (lock / "owner").write_text("dead-holder", encoding="utf-8")
    old = time.time() - manifest.LOCK_STALE - 5
    os.utime(lock, (old, old))
    monkeypatch.setattr(manifest, "LOCK_WAIT", 2.0)
    manifest.record_entry(root, FEATURE, agent())
    assert not lock.exists()
    assert not list(root.joinpath(FEATURE).glob("manifest.lock.stale*"))


def test_a_live_lock_makes_the_writer_wait_then_give_up(root: Path, monkeypatch) -> None:
    lock = manifest.manifest_path(root, FEATURE).with_name("manifest.lock")
    lock.mkdir()
    monkeypatch.setattr(manifest, "LOCK_WAIT", 0.3)
    with pytest.raises(manifest.ManifestBusy):
        manifest.record_entry(root, FEATURE, agent())
    assert lock.exists()
    assert manifest.read_manifest(root, FEATURE)["agents"] == []


def test_no_temporary_file_is_left_after_a_write(root: Path) -> None:
    manifest.record_entry(root, FEATURE, agent())
    assert sorted(p.name for p in root.joinpath(FEATURE).iterdir()) == ["manifest.json"]


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
    assert manifest.checkpoint_path(tmp_path, FEATURE, "reviewer") == path
    assert manifest.checkpoint_path(tmp_path, FEATURE, "builder") != path


@pytest.mark.parametrize("name", ["", "..", "a/b", "a\\b", "."])
def test_unsafe_names_are_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(manifest.ManifestError):
        manifest.checkpoint_path(tmp_path, FEATURE, name)
    with pytest.raises(manifest.ManifestError):
        manifest.manifest_path(tmp_path, name)

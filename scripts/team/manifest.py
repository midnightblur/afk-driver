"""The run manifest: one JSON file per feature listing a team run's agents and background processes.

Writes are `adopt_manifest`, `record_entry`, `move_entry` and `remove_process`; `read_manifest` serves every
read. Each write takes the run's directory mutex and publishes by write-then-rename, so a reader sees the old
file or the new one. An agent's state changes only along `TRANSITIONS`; any other move raises
`TransitionRefused` naming it. A file of an unknown format version is foreign: never read, never changed.

Layout under the caller's ignored agent directory `root`: `<root>/<feature>/manifest.json`, its lock folder
`manifest.lock`, and one running checkpoint per role at `<root>/<feature>/checkpoints/<role>.json`.
Timestamps on agent entries are UTC ISO 8601 to the second, `YYYY-MM-DDTHH:MM:SSZ`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

FORMAT_VERSION = 1
KNOWN_VERSIONS = (1,)
LOCK_STALE = 10.0
LOCK_WAIT = 30.0

STATES = ("starting", "working", "parked", "finished", "lost", "cleaned", "unkillable")
# Allowed next states, rows A1 to A7 of the signed lifecycle table; cleaned is terminal
TRANSITIONS = {
    "starting": ("working", "lost"),
    "working": ("parked", "finished", "lost", "cleaned", "unkillable"),
    "parked": ("working", "lost", "cleaned", "unkillable"),
    "finished": ("cleaned", "unkillable"),
    "lost": ("cleaned", "unkillable"),
    "cleaned": (),
    "unkillable": ("cleaned",),
}
LIFESPANS = ("Turn", "Step", "Feature")

_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
# field -> (kind, required on a new entry); kinds: text, int, iso, ostime, state, lifespan
AGENT_FIELDS = {
    "agent_id": ("text", True), "transport_kind": ("text", False), "handle": ("text", False),
    "started_at": ("iso", False), "pid": ("int", False), "stage": ("text", True),
    "pattern_step": ("text", True), "role": ("text", True), "model": ("text", True),
    "state": ("state", False), "park_reason": ("text", False), "park_until": ("iso", False),
    "terminal_id": ("text", False), "pane_label": ("text", False), "agent_name": ("text", False),
    "owner_generation": ("int", True), "lifespan": ("lifespan", True), "requester": ("text", False),
    "session_id": ("text", False),
}
PROCESS_FIELDS = {"pid": ("int", True), "owner": ("text", True), "label": ("text", True),
                  "started_at": ("ostime", True)}
HEADER_FIELDS = ("format_version", "feature", "owning_session", "owner_generation", "agents", "processes")

_REPORTED: set[tuple[str, str]] = set()


class ManifestError(Exception):
    """A malformed manifest or entry, or a write the manifest cannot take."""


class TransitionRefused(ManifestError):
    """An agent state move the lifecycle table does not allow; `move` is (agent-id, from, to)."""

    def __init__(self, agent_id: str, source: str | None, target: object):
        self.move = (agent_id, source, target)
        super().__init__(f"refused move for agent {agent_id}: {source or 'new'} -> {target} "
                         f"(allowed from {source or 'new'}: {', '.join(TRANSITIONS.get(source, ('starting',))) or 'none, terminal'})")


class ForeignManifest(ManifestError):
    """A manifest of an unknown format version: not read, not changed, not deleted."""


class ManifestBusy(ManifestError):
    """The manifest's lock stayed held by a live writer past `LOCK_WAIT` seconds."""


def _name(value: object, what: str) -> str:
    if not isinstance(value, str) or value in ("", ".", "..") or any(c in value for c in "/\\:\0"):
        raise ManifestError(f"unsafe {what} {value!r}: a non-empty name without path separators")
    return value


def manifest_path(root: str | os.PathLike, feature: str) -> Path:
    """The feature's manifest file under the ignored agent directory `root`."""
    return Path(root) / _name(feature, "feature identifier") / "manifest.json"


def checkpoint_path(root: str | os.PathLike, feature: str, role: str) -> Path:
    """The running checkpoint of `role` in the feature's run: one per role per run."""
    return Path(root) / _name(feature, "feature identifier") / "checkpoints" / f"{_name(role, 'role')}.json"


def _kind_ok(kind: str, value: object) -> bool:
    if kind == "text":
        return isinstance(value, str) and value != ""
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if kind == "iso":
        return isinstance(value, str) and _ISO.fullmatch(value) is not None
    if kind == "ostime":
        return (isinstance(value, str) and value != "") or (
            isinstance(value, (int, float)) and not isinstance(value, bool))
    if kind == "state":
        return value in STATES
    return value in LIFESPANS


def _check(entry: object, fields: dict, what: str, full: bool) -> dict:
    if not isinstance(entry, dict):
        raise ManifestError(f"{what} must be a JSON object, got {type(entry).__name__}")
    unknown = sorted(set(entry) - set(fields))
    if unknown:
        raise ManifestError(f"{what} has unknown fields: {', '.join(unknown)}")
    for field, (kind, required) in fields.items():
        value = entry.get(field)
        if value is None:
            if full and required:
                raise ManifestError(f"{what} lacks required field {field}")
            continue
        if not _kind_ok(kind, value):
            raise ManifestError(f"{what} field {field} has an invalid value {value!r} ({kind})")
    return entry


def _check_manifest(data: object, feature: str) -> dict:
    if not isinstance(data, dict) or sorted(data) != sorted(HEADER_FIELDS):
        raise ManifestError(f"manifest of {feature} must hold exactly the fields {', '.join(HEADER_FIELDS)}")
    if data["feature"] != feature or not _kind_ok("text", data["owning_session"]) \
            or not _kind_ok("int", data["owner_generation"]) or data["owner_generation"] < 1:
        raise ManifestError(f"manifest of {feature} has a malformed header")
    if not isinstance(data["agents"], list) or not isinstance(data["processes"], list):
        raise ManifestError(f"manifest of {feature} needs agents and processes lists")
    for entry in data["agents"]:
        _check(entry, AGENT_FIELDS, "agent entry", full=True)
        if entry.get("state") is None:
            raise ManifestError(f"agent entry {entry['agent_id']} lacks a state")
    for entry in data["processes"]:
        _check(entry, PROCESS_FIELDS, "process entry", full=True)
    return data


def _load(path: Path, feature: str) -> dict | None:
    for _ in range(50):
        try:
            text = path.read_text(encoding="utf-8")
            break
        except FileNotFoundError:
            return None
        except PermissionError:  # Windows: the file is mid-rename
            time.sleep(0.02)
    else:
        raise ManifestError(f"manifest {path} stayed unreadable")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ManifestError(f"manifest {path} is not JSON: {exc}") from None
    version = data.get("format_version") if isinstance(data, dict) else None
    if version not in KNOWN_VERSIONS or isinstance(version, bool):
        if (str(path), repr(version)) not in _REPORTED:
            _REPORTED.add((str(path), repr(version)))
            print(f"manifest: foreign file {path} (format version {version!r}); not read, not changed",
                  file=sys.stderr)
        raise ForeignManifest(f"{path} has unknown format version {version!r}")
    return _check_manifest(data, feature)


def read_manifest(root: str | os.PathLike, feature: str) -> dict | None:
    """The feature's manifest as a dict, or None when the run has none. Takes no lock."""
    return _load(manifest_path(root, feature), feature)


def _owner(lock: Path) -> str:
    try:
        return (lock / "owner").read_text(encoding="utf-8")
    except OSError:
        return ""


def _steal_if_stale(lock: Path) -> None:
    try:
        age = time.time() - lock.stat().st_mtime
    except OSError:
        return
    if age <= LOCK_STALE:
        return
    judged = _owner(lock)
    grave = lock.with_name(f"{lock.name}.stale.{os.getpid()}.{uuid.uuid4().hex}")
    try:
        os.rename(lock, grave)  # only one contender wins the rename
    except OSError:
        return
    if _owner(grave) != judged:  # a fresh lock replaced the stale one: give it back
        try:
            os.rename(grave, lock)
            return
        except OSError:
            pass
    shutil.rmtree(grave, ignore_errors=True)


def _acquire(lock: Path) -> str:
    token = f"{os.getpid()}-{uuid.uuid4().hex}"
    end = time.monotonic() + LOCK_WAIT
    while True:
        try:
            os.mkdir(lock)
        except FileExistsError:
            _steal_if_stale(lock)
            if time.monotonic() >= end:
                raise ManifestBusy(f"manifest lock {lock} held past {LOCK_WAIT:g}s") from None
            time.sleep(0.02)
            continue
        except FileNotFoundError:
            raise ManifestError(f"no run directory {lock.parent}; call adopt_manifest first") from None
        (lock / "owner").write_text(token, encoding="utf-8")
        return token


def _release(lock: Path, token: str) -> None:
    if _owner(lock) == token:
        shutil.rmtree(lock, ignore_errors=True)


def _publish(path: Path, data: dict) -> None:
    temp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(data, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    for _ in range(50):
        try:
            os.replace(temp, path)
            return
        except PermissionError:  # Windows: a reader holds the file open
            time.sleep(0.02)
    temp.unlink(missing_ok=True)
    raise ManifestError(f"could not publish {path}: the file stayed locked")


def _write(root, feature: str, change: Callable[[dict | None], dict | None]) -> dict | None:
    """Apply `change` to the current manifest under the mutex; publish its result unless it returns None."""
    path = manifest_path(root, feature)
    lock = path.with_name("manifest.lock")
    while True:
        token = _acquire(lock)
        try:
            current = _load(path, feature)
            result = change(current)
            if result is None:
                return current
            _check_manifest(result, feature)
            if _owner(lock) != token:  # the lock was taken from this writer: redo under a fresh one
                continue
            _publish(path, result)
            return result
        finally:
            _release(lock, token)


def adopt_manifest(root: str | os.PathLike, feature: str, session: str) -> dict:
    """Open the feature's run for contact session `session`: create the manifest, or take it over.

    A takeover by another session rewrites the owning session and adds 1 to the owner generation.
    """
    _name(feature, "feature identifier")
    if not _kind_ok("text", session):
        raise ManifestError("adopt_manifest needs a non-empty contact session")
    manifest_path(root, feature).parent.mkdir(parents=True, exist_ok=True)

    def change(current: dict | None) -> dict | None:
        if current is None:
            return {"format_version": FORMAT_VERSION, "feature": feature, "owning_session": session,
                    "owner_generation": 1, "agents": [], "processes": []}
        if current["owning_session"] == session:
            return None
        return {**current, "owning_session": session, "owner_generation": current["owner_generation"] + 1}

    return _write(root, feature, change)


def _existing(current: dict | None, feature: str) -> dict:
    if current is None:
        raise ManifestError(f"no manifest for {feature}; call adopt_manifest first")
    return current


def record_entry(root: str | os.PathLike, feature: str, entry: dict) -> dict:
    """Add or update one entry: an agent entry (keyed by `agent_id`) or a process entry (keyed by `pid`).

    A new agent entry starts in `starting` and copies the header's owner generation. An update merges the
    given fields; its state changes only through `move_entry`.
    """
    if not isinstance(entry, dict):
        raise ManifestError("an entry must be a dict")
    agent = "agent_id" in entry
    fields = AGENT_FIELDS if agent else PROCESS_FIELDS
    what = "agent entry" if agent else "process entry"
    _check(entry, fields, what, full=False)
    if agent and "owner_generation" in entry:
        raise ManifestError("owner_generation is copied from the manifest header, not given")

    def change(current: dict | None) -> dict:
        data = _existing(current, feature)
        key, rows = ("agent_id", data["agents"]) if agent else ("pid", data["processes"])
        if entry.get(key) is None:
            raise ManifestError(f"{what} lacks required field {key}")
        found = next((row for row in rows if row[key] == entry[key]), None)
        if found is None:
            row = {field: None for field in fields}
            row.update(entry)
            if agent:
                if row["state"] not in (None, "starting"):
                    raise TransitionRefused(entry["agent_id"], None, row["state"])
                row["state"] = "starting"
                row["owner_generation"] = data["owner_generation"]
            else:
                row = {field: row[field] for field in fields}
            _check(row, fields, what, full=True)
            rows.append(row)
        else:
            if agent and entry.get("state") not in (None, found["state"]):
                raise ManifestError(f"agent {found['agent_id']} state changes only through move_entry")
            found.update(entry)
        return data

    return _write(root, feature, change)


def move_entry(root: str | os.PathLike, feature: str, agent_id: str, to: str) -> dict:
    """Move agent `agent_id` to state `to` along a lifecycle table edge; raise `TransitionRefused` otherwise."""

    def change(current: dict | None) -> dict:
        data = _existing(current, feature)
        found = next((row for row in data["agents"] if row["agent_id"] == agent_id), None)
        if found is None:
            raise ManifestError(f"no entry holds agent-id {agent_id}")
        if to not in TRANSITIONS[found["state"]]:
            raise TransitionRefused(agent_id, found["state"], to)
        found["state"] = to
        return data

    return _write(root, feature, change)


def remove_process(root: str | os.PathLike, feature: str, pid: int) -> bool:
    """Drop the process entry `pid` once its process is killed or gone; False when no entry holds it."""
    removed: list[bool] = []

    def change(current: dict | None) -> dict | None:
        data = _existing(current, feature)
        kept = [row for row in data["processes"] if row["pid"] != pid]
        removed.append(len(kept) != len(data["processes"]))
        return {**data, "processes": kept} if removed[-1] else None

    _write(root, feature, change)
    return removed[-1]

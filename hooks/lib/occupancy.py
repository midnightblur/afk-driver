"""Who uses a linked worktree (PRD D6, A2, A3): one live holder, or one team.

A mutation in a linked worktree registers the session's harness process (`pid:ctime`) in
`<common>/afk-occupancy/<gitdir name>.json`. Another live identity outside the holder's group is refused.
A refused session is never registered, so the holder is never blocked by it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
LOCK_STALE = 10.0
LOCK_WAIT = 2.0


class Busy(Exception):
    """The occupancy record is held by another process past the wait."""


def owner_module():
    spec = importlib.util.spec_from_file_location("afk_worktree_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def group() -> str:
    """`AFK_WORKTREE_GROUP`, else the herdr tab every pane of a team shares, else none."""
    named = os.environ.get("AFK_WORKTREE_GROUP", "").strip()
    if named:
        return named
    tab = os.environ.get("HERDR_TAB_ID", "").strip()
    return f"herdr-tab:{tab}" if os.environ.get("HERDR_ENV") == "1" and tab else ""


def identity(session: str) -> dict | None:
    """This session's harness process and group; None when no owner can be named."""
    module = owner_module()
    found = module.env_owner() or module.find_owner()
    if not found or not found.get("ctime"):
        return None
    return {"pid": int(found["pid"]), "ctime": str(found["ctime"]), "group": group(), "session": session}


def record_path(place: dict) -> Path:
    return Path(place["common"]) / "afk-occupancy" / f"{Path(place['gitdir']).name}.json"


@contextmanager
def locked(path: Path):
    """Cross-process lock `<record>.lock`: O_EXCL create, taken over after LOCK_STALE s, LOCK_WAIT s patience."""
    path.parent.mkdir(exist_ok=True)
    lock = Path(f"{path}.lock")
    end = time.monotonic() + LOCK_WAIT
    while True:
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:
                seen = lock.stat()
                if time.time() - seen.st_mtime > LOCK_STALE:
                    again = lock.stat()  # a lock replaced since the observation is not the stale one
                    if (again.st_ino, again.st_mtime_ns) == (seen.st_ino, seen.st_mtime_ns):
                        lock.unlink(missing_ok=True)  # residual window: a swap between this stat and unlink
                    continue
            except OSError:
                continue
            if time.monotonic() >= end:
                raise Busy(str(lock))
            time.sleep(0.05)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def read(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [o for o in data.get("occupants", []) if isinstance(o, dict) and o.get("pid") and o.get("ctime")]
    except (OSError, ValueError, AttributeError):
        return []


def claim(place: dict, who: dict) -> dict | None:
    """Register `who` in the worktree; the foreign live occupant that bars it, else None.

    Dead occupants (including a recycled pid) are dropped; an unreadable creation time stays occupied.
    """
    path = record_path(place)
    module = owner_module()
    with locked(path):
        before = read(path)
        live = [o for o in before if module.state(int(o["pid"]), str(o["ctime"])) != "dead"]
        mine = lambda o: o["pid"] == who["pid"] and str(o["ctime"]) == who["ctime"]  # noqa: E731
        foreign = [o for o in live if not mine(o) and not (who["group"] and o.get("group") == who["group"])]
        if not foreign and not any(mine(o) for o in live):
            live.append({"pid": who["pid"], "ctime": who["ctime"], "group": who["group"],
                         "session": who["session"], "since": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        if live != before:
            temp = Path(f"{path}.{os.getpid()}.tmp")
            temp.write_text(json.dumps({"path": place["root"], "occupants": live}), encoding="utf-8")
            os.replace(temp, path)
        return foreign[0] if foreign else None


def describe(place: dict, held: dict) -> str:
    name = held.get("session") or "an unnamed session"
    return (f"worktree {place['root']} is in use by another live session ({name}, pid {held['pid']}, "
            f"since {held.get('since') or 'an unknown time'})")


def advisory(place: dict, held: dict) -> str:
    return (f"{describe(place, held)}. Changing files here will be refused for this session; start in a "
            "worktree of its own (the harness's worktree tool, or the plugin's scripts/create-worktree), or "
            "set the same AFK_WORKTREE_GROUP for every agent of one team.")

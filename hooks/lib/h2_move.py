"""The H-2 move: name the worktree a refused session needs, start its creation, detached.

`plan()` returns the path at once and never waits for the checkout: `scripts/afk-move.py`
cuts the worktree and, inside a terminal workspace, types the `/cd` line into the pane.
One creation per session, keyed by the session id, else by the pane id. The helper writes
its outcome into the marker: `created` on success, `error` (create-worktree's `ERROR=` text)
on failure. The path comes from the creator's own placement call (`target`), run outside the
lock only when a move must be placed; a refused root or short name returns `error` at once
and starts nothing. `plan()` and the helper read and write the marker under the safe
writer's lock, so only one call records, replaces or restarts a move.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("AFK_PLUGIN_ROOT") or Path(__file__).resolve().parents[2])
RETRY_AFTER = 180  # seconds a recorded creation may stay unfinished before it is started again


def _load(name: str, file: str):
    """The plugin script `scripts/<file>`, loaded by path as module `name`."""
    spec = importlib.util.spec_from_file_location(name, PLUGIN_ROOT / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def owner_env() -> dict:
    """`AFK_WORKTREE_OWNER` for the harness above this hook, resolved while it is still alive."""
    try:
        module = _load("afk_worktree_owner", "worktree_owner.py")
        found = module.env_owner() or module.find_owner()
    except Exception:
        return {}
    return {"AFK_WORKTREE_OWNER": f"{found['pid']}:{found['ctime']}"} if found and found.get("ctime") else {}


def owner_is_dead(common: Path, name: str) -> bool:
    """Has the session that made worktree `name` ended?"""
    try:
        record = json.loads((common / "afk-worktrees" / f"{name}.json").read_text(encoding="utf-8"))
        return _load("afk_worktree_owner", "worktree_owner.py").all_dead(record)
    except Exception:
        return False


def spawn(argv: list[str], env: dict | None = None, cwd: str | None = None, log: str | None = None) -> None:
    """Start `argv` fully detached from this hook: it must outlive the hook's exit.

    `log` names a file that takes the helper's stdout and stderr, appended; without one both are dropped.
    """
    sink = open(log, "ab") if log else subprocess.DEVNULL
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": sink, "stderr": sink,
                    "close_fds": True, "env": dict(os.environ, **(env or {}))}
    if cwd:
        kwargs["cwd"] = cwd
    try:
        if os.name != "nt":
            subprocess.Popen(argv, start_new_session=True, **kwargs)
            return
        # CREATE_NO_WINDOW keeps every console child of the helper hidden; DETACHED_PROCESS would not.
        flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        try:
            subprocess.Popen(argv, creationflags=flags | 0x01000000, **kwargs)  # | CREATE_BREAKAWAY_FROM_JOB
        except OSError:
            subprocess.Popen(argv, creationflags=flags, **kwargs)
    finally:
        if log:
            sink.close()


def target(root: Path, name: str, facts: dict) -> tuple[str, str]:
    """`(path, "")` where `create-worktree --name <name>` puts the worktree, or `("", refusal)`."""
    try:
        placement = _load("afk_placement_for_move", "placement.py")
        verdict = placement.target_for(str(root), name)
    except Exception as problem:
        return "", f"placement: {problem}"
    if verdict.state == placement.REFUSED:
        return "", f"worktree root: {verdict.rule} {verdict.reason} - run /afk:setup"
    if verdict.state == placement.INSIDE:
        return verdict.target, ""
    folder = os.environ.get("AFK_WORKTREE_FOLDER") or facts.get("worktree_folder") or ".claude/worktrees"
    return str(root / folder / name), ""


def error_move(name: str, pane: str, why: str) -> dict:
    """The result for a move that is not under way: no path, and why."""
    return {"name": name, "path": "", "pane": pane, "error": why}


def new_move(root: Path, name: str, pane: str, facts: dict, marker: Path) -> dict:
    """The move record for worktree `name`, placed as the creator would place it, or `error_move()`."""
    path, refused = target(root, name, facts)
    if refused:
        return error_move(name, pane, refused)
    return {"name": name, "path": path, "pane": pane, "marker": str(marker)}


def plan(place: dict, envelope: dict, facts: dict) -> dict:
    """The move record `{"name", "path", "pane", "marker"}` this session is moved into, or `error_move()`."""
    common = Path(place["common"])
    root = common.parent if common.name == ".git" else Path(place["root"])
    pane = os.environ.get("HERDR_PANE_ID", "") if os.environ.get("HERDR_ENV") else ""
    session = str(envelope.get("session_id") or "")
    key = re.sub(r"[^A-Za-z0-9._-]", "_", session or f"{pane}:nosession")  # a pane id is inherited by child agents
    marker_dir = common / "afk-session"
    marker_dir.mkdir(exist_ok=True)
    marker = marker_dir / f"{key}.move"
    name = f"session-{uuid.uuid4().hex[:8]}"
    decided: dict = {}  # what settle chose: `chosen`, and `start` or `need` (a new move must be placed)

    def begin(chosen: dict) -> str:
        decided.update(chosen=chosen, start=True)
        return json.dumps(dict(chosen, started=time.time()))

    def settle(text: str, new: dict | None) -> str:
        """Under the marker's lock: keep or restart the recorded move, or record `new`."""
        try:
            chosen = json.loads(text) if text else None
        except ValueError:
            chosen = None  # every write is whole under the lock, so this marker is corrupt
        if isinstance(chosen, dict) and chosen.get("path"):
            if Path(chosen["path"]).exists():
                if not owner_is_dead(common, chosen["name"]):  # else an earlier session's worktree
                    chosen.pop("error", None)
                    decided["chosen"] = chosen
                    return text
            elif not chosen.get("created"):  # a created worktree since removed has spent its name
                started = chosen.get("started")
                age = time.time() - (started if isinstance(started, (int, float)) else marker.stat().st_mtime)
                if age < RETRY_AFTER:
                    decided["chosen"] = chosen
                    return text
                chosen.pop("error", None)
                return begin(chosen)
        if new is None:
            decided["need"] = True
            return text
        return begin(new)

    try:
        safe_write = _load("afk_safe_write_for_move", "safe_write.py")
        safe_write.update_locked(marker, lambda text: settle(text, None))
        if decided.get("need"):  # placement runs outside the lock, so a waiting call is never kept past its wait
            new = new_move(root, name, pane, facts, marker)
            if new.get("error"):
                return new
            decided.clear()
            safe_write.update_locked(marker, lambda text: settle(text, new))
    except Exception as problem:  # a held lock, an unreadable marker, a failed write
        return error_move(name, pane, f"move record: {problem}")
    chosen = {k: v for k, v in decided["chosen"].items() if k != "started"}  # the clock is the marker's own
    if not decided.get("start") or os.environ.get("AFK_MOVE_SPAWN") == "0":  # a test knob: name the path, cut nothing
        return chosen
    try:
        spawn([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-move.py"), "--repo", str(root),
               "--name", chosen["name"], "--session", session, "--provider", str(facts.get("name") or ""),
               "--pane", chosen["pane"], "--cwd", str(envelope.get("cwd") or root), "--marker", str(marker)],
              owner_env())
    except OSError as problem:
        why = f"the move helper did not start: {problem}"
        try:
            safe_write.update_locked(marker, lambda text: json.dumps(dict(json.loads(text), error=why)))
        except Exception:
            pass  # the move stays recorded as unfinished and is started again after RETRY_AFTER
        return error_move(chosen["name"], chosen["pane"], why)
    return chosen

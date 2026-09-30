"""The H-2 move: name the worktree a refused session needs, start its creation, detached.

`plan()` returns the path at once and never waits for the checkout: `scripts/afk-move.py`
cuts the worktree and, inside a terminal workspace, types the `/cd` line into the pane.
One creation per session, keyed by the pane id when there is one (the H-2 session id
changes on `/cd`), else by the session id. The helper writes its outcome into the marker:
`created` on success, `error` (create-worktree's `ERROR=` text) on failure.
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


def owner_env() -> dict:
    """`AFK_WORKTREE_OWNER` for the harness above this hook, resolved while it is still alive."""
    try:
        spec = importlib.util.spec_from_file_location("afk_worktree_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found = module.env_owner() or module.find_owner()
    except Exception:
        return {}
    return {"AFK_WORKTREE_OWNER": f"{found['pid']}:{found['ctime']}"} if found and found.get("ctime") else {}


def owner_is_dead(common: Path, name: str) -> bool:
    """Has the session that made worktree `name` ended?"""
    try:
        who = json.loads((common / "afk-worktrees" / f"{name}.json").read_text(encoding="utf-8")).get("owner") or {}
        spec = importlib.util.spec_from_file_location("afk_worktree_owner", PLUGIN_ROOT / "scripts" / "worktree_owner.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return bool(who.get("pid") and who.get("ctime")) and module.state(int(who["pid"]), str(who["ctime"])) == "dead"
    except Exception:
        return False


def spawn(argv: list[str], env: dict | None = None) -> None:
    """Start `argv` fully detached from this hook: it must outlive the hook's exit."""
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                    "close_fds": True, "env": dict(os.environ, **(env or {}))}
    if os.name != "nt":
        subprocess.Popen(argv, start_new_session=True, **kwargs)
        return
    # CREATE_NO_WINDOW keeps every console child of the helper hidden; DETACHED_PROCESS would not.
    flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    try:
        subprocess.Popen(argv, creationflags=flags | 0x01000000, **kwargs)  # | CREATE_BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen(argv, creationflags=flags, **kwargs)


def plan(place: dict, envelope: dict, facts: dict) -> dict:
    """`{"path", "name", "pane"}` of the worktree this session is being moved into."""
    common = Path(place["common"])
    root = common.parent if common.name == ".git" else Path(place["root"])
    pane = os.environ.get("HERDR_PANE_ID", "") if os.environ.get("HERDR_ENV") else ""
    session = str(envelope.get("session_id") or "")
    key = re.sub(r"[^A-Za-z0-9._-]", "_", pane or session or "nosession")
    marker_dir = common / "afk-session"
    marker_dir.mkdir(exist_ok=True)
    marker = marker_dir / f"{key}.move"
    name = f"session-{uuid.uuid4().hex[:8]}"
    folder = os.environ.get("AFK_WORKTREE_FOLDER") or facts.get("worktree_folder") or ".claude/worktrees"
    chosen = {"name": name, "path": str(root / folder / name), "pane": pane}
    chosen["marker"] = str(marker)
    try:
        with open(marker, "x", encoding="utf-8") as out:
            json.dump(chosen, out)
    except FileExistsError:
        try:
            chosen = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return chosen
        if Path(chosen["path"]).exists() and owner_is_dead(common, chosen["name"]):
            marker.unlink(missing_ok=True)  # an earlier session's worktree, not this one's
            return plan(place, envelope, facts)
        if Path(chosen["path"]).exists() or time.time() - marker.stat().st_mtime < RETRY_AFTER:
            return chosen
        marker.touch()
    if os.environ.get("AFK_MOVE_SPAWN") == "0":  # a test knob: name the path, cut nothing
        return chosen
    spawn([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-move.py"), "--repo", str(root),
           "--name", chosen["name"], "--session", session, "--provider", str(facts.get("name") or ""),
           "--pane", chosen["pane"], "--cwd", str(envelope.get("cwd") or root), "--marker", str(marker)],
          owner_env())
    return chosen

"""The H-2 move: name the worktree a refused session needs, start its creation, detached.

`plan()` returns the path at once and never waits for the checkout: `scripts/afk-move.py`
cuts the worktree and, inside a terminal workspace, types the `/cd` line into the pane.
One creation per session, keyed by the pane id when there is one (the H-2 session id
changes on `/cd`), else by the session id.
"""
from __future__ import annotations

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


def spawn(argv: list[str]) -> None:
    """Start `argv` fully detached from this hook: it must outlive the hook's exit."""
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                    "close_fds": True}
    if os.name != "nt":
        subprocess.Popen(argv, start_new_session=True, **kwargs)
        return
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
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
    folder = facts.get("worktree_folder") or ".claude/worktrees"
    chosen = {"name": name, "path": str(root / folder / name), "pane": pane}
    try:
        with open(marker, "x", encoding="utf-8") as out:
            json.dump(chosen, out)
    except FileExistsError:
        try:
            chosen = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return chosen
        if Path(chosen["path"]).exists() or time.time() - marker.stat().st_mtime < RETRY_AFTER:
            return chosen
        marker.touch()
    if os.environ.get("AFK_MOVE_SPAWN") == "0":  # a test knob: name the path, cut nothing
        return chosen
    spawn([sys.executable, str(PLUGIN_ROOT / "scripts" / "afk-move.py"), "--repo", str(root),
           "--name", chosen["name"], "--session", session, "--provider", str(facts.get("name") or ""),
           "--pane", chosen["pane"], "--cwd", str(envelope.get("cwd") or root)])
    return chosen

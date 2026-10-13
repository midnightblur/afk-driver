#!/usr/bin/env afk-python
"""SessionStart: register this session in its linked worktree and say when another live session holds it.

Advisory only: the line is injected as context; this handler never blocks and exits 0 on every path.
A crash names itself (CAPABILITIES.md "Hook failures").
"""
import json
import os
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent / "lib"


def run() -> None:
    sys.path.insert(0, str(LIB))
    import occupancy
    import protected_branch_guard as guard
    guard.deadline[0] = time.monotonic() + guard.DEADLINE_SECONDS
    envelope = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    if not isinstance(envelope, dict):
        return
    place = guard.placement(Path(envelope.get("cwd") or os.getcwd()))
    if place is None or place["kind"] != "linked":
        return
    who = occupancy.identity(str(envelope.get("session_id") or ""))
    held = occupancy.claim(place, who) if who else None
    if held:
        text = occupancy.advisory(place, held)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text},
                          "additional_context": text}))


if os.environ.get("AFK_ALLOW_PROTECTED") != "1":
    try:
        run()
    except BaseException as problem:  # fail open, but never silently
        try:
            sys.path.insert(0, str(LIB))
            import hook_failure
            hook_failure.crashed("protected-branch-occupancy.py", "SessionStart", problem, notify=True)
        except BaseException:
            pass
sys.exit(0)

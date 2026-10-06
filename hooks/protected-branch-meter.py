#!/usr/bin/env python3
"""PostToolUse: compare a guarded checkout with the snapshot the guard took before a shell call.

A difference is injected as context and starts the quarantine the guard enforces; this handler
never blocks and exits 0 on every path.
"""
import json
import os
import sys
import time
from pathlib import Path

LIB = Path(__file__).resolve().parent / "lib"


def run() -> None:
    sys.path.insert(0, str(LIB))
    import change_meter
    import protected_branch_guard as guard
    guard.deadline[0] = time.monotonic() + guard.DEADLINE_SECONDS
    envelope = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    if not isinstance(envelope, dict):
        return
    if guard.tool_class(str(envelope.get("tool_name") or ""), guard.provider_facts()) != "shell":
        return
    place = guard.placement(Path(envelope.get("cwd") or os.getcwd()))
    if place is None:
        return
    text = change_meter.after(place, change_meter.session_key(guard.Judge(str(envelope.get("session_id") or ""))))
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text},
                          "additional_context": text}))


if os.environ.get("AFK_ALLOW_PROTECTED") != "1":
    try:
        run()
    except BaseException:
        pass
sys.exit(0)

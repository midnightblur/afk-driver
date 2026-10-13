#!/usr/bin/env afk-python
"""PostToolUse: compare a guarded checkout with the snapshot the guard took before a shell call.

A difference is injected as context and starts the quarantine the guard enforces; this handler
never blocks and exits 0 on every path; a crash names itself (CAPABILITIES.md "Hook failures").
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
    cwd = Path(envelope.get("cwd") or os.getcwd())
    tool_input = envelope.get("tool_input") if isinstance(envelope.get("tool_input"), dict) else {}
    call, sha = change_meter.call_id(envelope, guard.command_of(tool_input))
    text = change_meter.after(change_meter.session_key(guard.Judge(str(envelope.get("session_id") or ""))), call, sha, cwd)
    if text:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text},
                          "additional_context": text}))


if os.environ.get("AFK_ALLOW_PROTECTED") != "1":
    try:
        run()
    except BaseException as problem:  # fail open, but never silently
        try:
            sys.path.insert(0, str(LIB))
            import hook_failure
            hook_failure.crashed("protected-branch-meter.py", "PostToolUse", problem, notify=True)
        except BaseException:
            pass
sys.exit(0)

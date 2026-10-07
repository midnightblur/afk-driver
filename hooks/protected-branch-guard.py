#!/usr/bin/env python3
"""PreToolUse gate: an agent changes a repository only from a linked worktree on an
unprotected branch. The manifest runs this file directly (no shell, no launcher);
the judge is lib/protected_branch_guard.py. If the judge cannot even load, this
entry still refuses inside a git work tree and allows outside one.
"""
import json
import os
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parent / "lib"


def unloadable(problem: BaseException) -> int:
    try:
        cwd = Path(json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}").get("cwd") or os.getcwd())
    except Exception:
        cwd = Path.cwd()
    walk = cwd
    while not walk.is_dir() and walk.parent != walk:
        walk = walk.parent
    while True:
        if (walk / ".git").exists():
            reason = ("protected-branch guard: refused to act. Cause: the guard could not load "
                      f"({problem}). Move: repair the plugin install, then retry.")
            sys.stderr.write(reason + "\n")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "permissionDecision": "deny",
                                                     "permissionDecisionReason": reason}}))
            return 0  # the JSON deny blocks at exit 0; the H-2 harness runs the command on exit 2
        if walk.parent == walk:
            return 0
        walk = walk.parent


if os.environ.get("AFK_ALLOW_PROTECTED") == "1":
    sys.exit(0)
try:
    sys.path.insert(0, str(LIB))
    import protected_branch_guard
except BaseException as error:
    sys.exit(unloadable(error))
sys.exit(protected_branch_guard.main())

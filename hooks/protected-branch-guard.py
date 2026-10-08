#!/usr/bin/env afk-python
"""PreToolUse gate: an agent changes a repository only from a linked worktree on an
unprotected branch. The manifest runs this file directly (no shell, no launcher);
the judge is lib/protected_branch_guard.py. If the judge cannot even load, or an
exception escapes it, this entry still refuses inside the envelope's git work tree and allows
outside one; an escaped exception also names itself on stderr (CAPABILITIES.md "Hook failures").
"""
import io
import json
import os
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parent / "lib"
ENVELOPE = [b""]  # read once, before the judge: a fallback must judge the same cwd the judge did


def unloadable(problem: BaseException, what: str = "could not load") -> int:
    try:
        cwd = Path(json.loads(ENVELOPE[0].decode("utf-8", "replace") or "{}").get("cwd") or os.getcwd())
    except Exception:
        cwd = Path.cwd()
    walk = cwd
    while not walk.is_dir() and walk.parent != walk:
        walk = walk.parent
    while True:
        if (walk / ".git").exists():
            reason = (f"protected-branch guard: refused to act. Cause: the guard {what} "
                      f"({problem}). Move: repair the plugin install, then retry.")
            sys.stderr.write(reason + "\n")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "permissionDecision": "deny",
                                                     "permissionDecisionReason": reason}}))
            return 0  # the JSON deny blocks at exit 0; the H-2 harness runs the command on exit 2
        if walk.parent == walk:
            return 0
        walk = walk.parent


try:
    ENVELOPE[0] = sys.stdin.buffer.read() if sys.stdin is not None else b""
except Exception:
    pass
sys.stdin = io.TextIOWrapper(io.BytesIO(ENVELOPE[0]), encoding="utf-8")
try:
    sys.path.insert(0, str(LIB))
    import protected_branch_guard
except BaseException as error:
    sys.exit(0 if os.environ.get("AFK_ALLOW_PROTECTED") == "1" else unloadable(error))
try:
    code = protected_branch_guard.main()
except SystemExit:
    raise
except BaseException as error:
    try:
        import hook_failure
        hook_failure.crashed("protected-branch-guard.py", "PreToolUse", error, notify=False)
    except BaseException:
        pass
    code = 0 if os.environ.get("AFK_ALLOW_PROTECTED") == "1" else unloadable(error, "crashed")
sys.exit(code)

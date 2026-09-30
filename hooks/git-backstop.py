#!/usr/bin/env python3
"""Git-side backstop for the protected-branch guard, called by the installed git hooks.

    git-backstop.py pre-commit
    git-backstop.py reference-transaction prepared     (ref lines on stdin)

The caller has already decided this is an agent-driven git call with no override. A
commit is refused in the main checkout and on a protected branch of a linked worktree.
A ref transaction is refused for the main checkout's own HEAD and the branch it has
checked out, and for a linked worktree's own protected branch. Creating refs (a new
worktree's branch), remote-tracking updates and no-op updates pass.

Exit 3 refuses; callers veto only on 3. Any other exit is a fault: the caller warns and
lets git continue, because the PreToolUse guard is the primary gate and this one must
never break git.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
REFUSED = 3
FRESH_LOCK_SECONDS = 10


def refuse(action: str, cause: str) -> int:
    import protected_branch_guard as guard
    sys.stderr.write(guard.refusal(action, cause, guard.hint_of(guard.provider_facts())) + "\n")
    return REFUSED


def pre_commit() -> int:
    import protected_branch_guard as guard
    cause = guard.Judge("").verdict(guard.placement(Path.cwd()))
    return refuse("commit", cause) if cause else 0


def creating_worktree(place: dict) -> bool:
    """`git worktree add` writes the new worktree's HEAD through the main context, mid-creation."""
    now = time.time()
    for lock in Path(place["common"]).glob("worktrees/*/HEAD.lock"):
        try:
            if now - lock.stat().st_mtime < FRESH_LOCK_SECONDS:
                return True
        except OSError:
            continue
    return False


def ref_transaction(lines: list[str]) -> int:
    import protected_branch_guard as guard
    place = guard.placement(Path.cwd())
    if place is None:
        return 0
    current = guard.branch_of(place)
    linked = place["kind"] != "main"
    judge = guard.Judge("")
    for line in lines:
        parts = line.split()
        if len(parts) != 3:
            continue
        old, new, ref = parts
        if old == new and not new.startswith("ref:"):
            continue  # nothing moves, as in a stash's internal `reset --hard` to the same commit
        if linked:
            if current and ref == f"refs/heads/{current}":
                cause = judge.verdict(place)
                if cause:
                    return refuse(f"update `{current}`", cause)
            continue
        if ref == "HEAD" and not creating_worktree(place):
            return refuse("move the main checkout's HEAD", "this is the main checkout")
        if current and ref == f"refs/heads/{current}":
            return refuse(f"update `{current}`", "this is the main checkout")
    return 0


def main(argv: list[str]) -> int:
    try:
        if argv[:1] == ["pre-commit"]:
            return pre_commit()
        if argv[:2] == ["reference-transaction", "prepared"]:
            return ref_transaction(sys.stdin.read().splitlines())
    except Exception as problem:
        sys.stderr.write(f"afk: git backstop skipped ({problem}).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

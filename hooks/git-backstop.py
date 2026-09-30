#!/usr/bin/env python3
"""Git-side backstop for the protected-branch guard, called by the installed git hooks.

    git-backstop.py pre-commit
    git-backstop.py reference-transaction prepared     (ref lines on stdin)

The caller has already decided this is an agent-driven git call with no override. A
commit is refused in the main checkout and on a protected branch of a linked worktree.
A ref transaction is refused only for the main checkout's own HEAD and for the branch
it has checked out, so creating refs (a new worktree's branch) and remote-tracking
updates pass. Exit 1 refuses. An internal fault warns and lets git continue: the
PreToolUse guard is the primary gate and this one must never break a human's git.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import protected_branch_guard as guard  # noqa: E402


def refuse(action: str, cause: str) -> int:
    sys.stderr.write(guard.refusal(action, cause, guard.hint_of(guard.provider_facts())) + "\n")
    return 1


def pre_commit() -> int:
    cause = guard.Judge("").verdict(guard.placement(Path.cwd()))
    return refuse("commit", cause) if cause else 0


def creating_worktree(place: dict) -> bool:
    """`git worktree add` writes the new worktree's HEAD through the main context, mid-creation."""
    return any(Path(place["common"]).glob("worktrees/*/HEAD.lock"))


def ref_transaction(lines: list[str]) -> int:
    place = guard.placement(Path.cwd())
    if place is None or place["kind"] != "main":
        return 0
    current = guard.branch_of(place)
    for line in lines:
        parts = line.split()
        if len(parts) != 3:
            continue
        ref = parts[2]
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

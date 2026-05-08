"""FakeClaude — substitutes for the real ``claude --print /afk-go`` subprocess.

The real claude_runner closure spawns a subprocess and parses its exit code.
For scenarios, we stand in a callable that:

1. Records the call (key + attempt number).
2. Performs an optional side effect on the worktree (writes files, commits,
   leaves dirty, etc.) — the side effect is what makes a scenario realistic
   because the real runner inspects the branch tip + dirty state after every
   claude call.
3. Returns a fixed ``ClaudeOutcome``.

Per-key plans are ordered: ``plan("P2P-1", test_fail_step(), success_committing(...))``
makes the first call fail and the second succeed (used to exercise the runner
retry loop). When the plan list is exhausted, the last step repeats — pure
convenience, scenarios usually only call once.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from afk_driver.runner import ClaudeOutcome


@dataclass
class Step:
    outcome: ClaudeOutcome
    side_effect: Callable[[Path, str], None] = field(
        default=lambda path, key: None
    )


def success_committing(files: dict[str, str]) -> Step:
    """Write files into the worktree and ``git commit`` them.
    Mirrors a well-behaved claude session that did its job correctly.
    """

    def _apply(path: Path, key: str) -> None:
        _write_files(path, files)
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", f"[{key}] fake-claude work")

    return Step(ClaudeOutcome("success", detail="committed"), _apply)


def success_no_commit(files: dict[str, str]) -> Step:
    """Write files into the worktree but DO NOT commit.
    Mirrors the P2P-1233 failure mode: claude session edited code and exited
    success without running git commit. The runner's auto-commit safety net
    must catch the dirty tree.
    """

    def _apply(path: Path, key: str) -> None:
        _write_files(path, files)

    return Step(ClaudeOutcome("success", detail="dirty"), _apply)


def success_no_change() -> Step:
    """Return success without touching anything.
    Mirrors a no-op claude session: the runner's pre/post head_sha gate must
    convert this success into an aborted SubTask ("no code changes detected").
    """
    return Step(ClaudeOutcome("success", detail="no-op"), lambda p, k: None)


def test_fail_step(detail: str = "tests failed") -> Step:
    return Step(ClaudeOutcome("test_fail", detail=detail), lambda p, k: None)


def timeout_step(detail: str = "wall-clock cap exceeded") -> Step:
    return Step(ClaudeOutcome("timeout", detail=detail), lambda p, k: None)


def other_step(detail: str = "exit 2") -> Step:
    return Step(ClaudeOutcome("other", detail=detail), lambda p, k: None)


class FakeClaude:
    def __init__(self) -> None:
        self._plans: dict[str, list[Step]] = {}
        self._calls_per_key: dict[str, int] = {}
        self.call_history: list[tuple[str, int]] = []

    def plan(self, subtask_key: str, *steps: Step) -> "FakeClaude":
        if not steps:
            raise ValueError(f"FakeClaude.plan({subtask_key!r}) needs ≥1 Step")
        self._plans[subtask_key] = list(steps)
        return self

    def __call__(
        self, subtask_key: str, worktree_path: Path, cap_s: int
    ) -> ClaudeOutcome:
        plan = self._plans.get(subtask_key)
        if plan is None:
            return ClaudeOutcome(
                "other",
                detail=f"FakeClaude: no plan registered for {subtask_key}",
            )
        attempt = self._calls_per_key.get(subtask_key, 0) + 1
        self._calls_per_key[subtask_key] = attempt
        self.call_history.append((subtask_key, attempt))
        idx = min(attempt - 1, len(plan) - 1)
        step = plan[idx]
        step.side_effect(worktree_path, subtask_key)
        return step.outcome


def _write_files(path: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"FakeClaude git {args} failed in {cwd}: {proc.stderr.strip()}"
        )

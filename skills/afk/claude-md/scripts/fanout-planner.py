"""Fan-out decision planner (pure functional core).

Given a target steering-note path, its desired content, the per-worktree state
of that file, and the 11xxx allowed-path boundary, decide one action per
worktree: write | skip(reason) | noop | refuse.

Pure: no git, no filesystem, no clock. Every worktree fact arrives as an input,
so the whole decision matrix is exhaustively unit-testable on synthetic facts.
The imperative shell (fanout-shell, subtask 0009) enumerates worktrees, reads
their states, calls computeFanOutPlan, and executes the returned Plan.

Binding contract:
  SDD §8 "Fan-out planner" — plan(path, content, worktreeStates, boundary) -> Plan
  SDD §9 — functional core of the functional-core/imperative-shell split
  ADR-0002 — the decision matrix + fail-closed path boundary

The path boundary is supplied by the caller as a list of glob patterns. In
production the claude-md skill bakes that constant (ADR-0005: 11xxx*/** +
tools/payable/**, excluding the neutral root CLAUDE.md and root GLOSSARY*); the
planner stays agnostic so tests can drive synthetic boundaries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence

# --- decision actions (the four ADR-0002 branches) --------------------------
WRITE = "write"
SKIP = "skip"
NOOP = "noop"
REFUSE = "refuse"

# --- boundary verdicts ------------------------------------------------------
ALLOW = "allow"
# REFUSE is reused as the boundary-level verdict when the path is out of bounds.


@dataclass(frozen=True)
class WorktreeState:
    """Facts about the target file in one worktree (gathered by the shell).

    worktree     -- identifier/path of the worktree (echoed back in the decision)
    dirty        -- True if the target file has uncommitted local modifications
    current_content -- the file's current content, or None if it does not exist;
                       only consulted on the dirty branch (noop vs skip)
    """

    worktree: str
    dirty: bool = False
    current_content: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    worktree: str
    action: str  # WRITE | SKIP | NOOP | REFUSE
    reason: str = ""


@dataclass(frozen=True)
class Plan:
    boundary_verdict: str  # ALLOW | REFUSE
    per_worktree: List[Decision] = field(default_factory=list)


def _normalize(path: str) -> str:
    """Forward-slash, strip a single leading './' — boundary matching is POSIX-style."""
    p = path.replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _glob_to_regex(pattern: str) -> str:
    r"""Translate a path glob to an anchored regex.

    Supports the three tokens the boundary needs:
      **  -> matches any characters incl. '/'   (recursive subtree)
      *   -> matches any characters except '/'   (one segment)
      ?   -> matches a single non-'/' character
    Everything else is matched literally.
    """
    out = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                out.append(".*")
                i += 2
                # swallow a trailing slash after ** so 'a/**' also matches 'a'
                if i < n and pattern[i] == "/":
                    i += 1
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    out.append("$")
    return "".join(out)


def _within_boundary(path: str, boundary: Sequence[str]) -> bool:
    """True iff the normalized path matches at least one boundary glob."""
    norm = _normalize(path)
    for pattern in boundary:
        if re.match(_glob_to_regex(_normalize(pattern)), norm):
            return True
    return False


def _decide_one(state: WorktreeState, content: str) -> Decision:
    """The ADR-0002 inner matrix for a single in-boundary worktree."""
    if not state.dirty:
        # clean or absent -> write (create or overwrite)
        return Decision(state.worktree, WRITE)
    # dirty: compare against desired content
    if state.current_content == content:
        return Decision(state.worktree, NOOP, "dirty but already equals desired")
    return Decision(state.worktree, SKIP, "dirty-conflict: differs from desired, left untouched")


def computeFanOutPlan(
    path: str,
    content: str,
    worktree_states: Sequence[WorktreeState],
    boundary: Sequence[str],
) -> Plan:
    """Pure planner entry point (SDD §8 "Fan-out planner").

    Returns a Plan with a boundary verdict and one Decision per worktree.

    Fail-closed: if the target path is outside the allowed boundary, the verdict
    is REFUSE and every worktree decision is REFUSE -- computed before any write
    could occur (ADR-0002).
    """
    if not _within_boundary(path, boundary):
        return Plan(
            boundary_verdict=REFUSE,
            per_worktree=[
                Decision(s.worktree, REFUSE, "path outside allowed boundary (fail-closed)")
                for s in worktree_states
            ],
        )

    return Plan(
        boundary_verdict=ALLOW,
        per_worktree=[_decide_one(s, content) for s in worktree_states],
    )

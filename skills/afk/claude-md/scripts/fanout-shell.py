"""Imperative fan-out shell (the only part that touches git and disk).

Drives steering-note propagation across a developer's worktrees (SDD §7, §8;
design-ADR-0002):

  1. enumerate worktrees  (git worktree list --porcelain)
  2. read each worktree's state of the target file  (exists / dirty / content)
  3. call the pure planner  (fanout-planner.computeFanOutPlan)
  4. execute the plan  — current worktree FIRST and it must succeed; siblings
     best-effort and independent (one skip/failure never rolls back another)
  5. return a reconcile summary  (written / noop / skipped+reason / refused / failed)

All decision logic lives in the pure planner; this module is the imperative
shell of the functional-core/imperative-shell split. Real git/filesystem access
is injected (``list_worktrees`` / ``read_state`` / ``write_file``) so the
coordination logic is unit-testable on a fake worktree set with no real disk;
``propagateSteeringNote`` wires the real implementations.

Binding contract:
  SDD §7 — propagation sequence + failure-and-recovery matrix
  SDD §8 "Fan-out shell" — propagate(path, content) -> Summary
  ADR-0002 — best-effort / current-worktree-first / fail-closed boundary

The 11xxx write-boundary (ADR-0005: 11xxx*/** + tools/payable/**, excluding the
neutral root CLAUDE.md / root GLOSSARY*) is BAKED here, not injected per call —
the shell is part of the claude-md skill, and the frozen public signature takes
no boundary argument. Root files are refused by fail-closed default because no
allowed glob matches them.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

# --- load the sibling planner (hyphenated filename -> load by path) ----------
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_planner():
    spec = importlib.util.spec_from_file_location(
        "fanout_planner", os.path.join(_HERE, "fanout-planner.py")
    )
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules.setdefault("fanout_planner", mod)
    spec.loader.exec_module(mod)
    return mod


_planner = _load_planner()
WorktreeState = _planner.WorktreeState
computeFanOutPlan = _planner.computeFanOutPlan
WRITE, SKIP, NOOP, REFUSE = _planner.WRITE, _planner.SKIP, _planner.NOOP, _planner.REFUSE

# --- the baked 11xxx boundary (ADR-0005) ------------------------------------
# Allowed-only globs: the planner refuses anything that matches no entry, so the
# neutral root CLAUDE.md and root GLOSSARY* are excluded automatically (no glob
# below matches a bare root file). "11xxx*" -> 11 + three placeholder digits +
# the rest of the service-dir name.
BAKED_BOUNDARY: Tuple[str, ...] = ("11???*/**", "tools/payable/**")


@dataclass
class Summary:
    """The reconcile summary surfaced to the developer (SDD §7)."""

    path: str
    boundary_verdict: str
    primary: Optional[str] = None
    primary_ok: bool = False
    written: List[str] = field(default_factory=list)
    noop: List[str] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)   # (worktree, reason)
    refused: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)    # (worktree, error)
    warnings: List[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [f"fan-out: {self.path}  [boundary: {self.boundary_verdict}]"]
        if self.primary is not None:
            lines.append(f"  primary: {self.primary}  ({'ok' if self.primary_ok else 'NOT WRITTEN'})")
        for wt in self.written:
            lines.append(f"  written  {wt}")
        for wt in self.noop:
            lines.append(f"  noop     {wt}  (already equals desired)")
        for wt, reason in self.skipped:
            lines.append(f"  skipped  {wt}  ({reason})")
        for wt in self.refused:
            lines.append(f"  refused  {wt}  (outside 11xxx boundary)")
        for wt, err in self.failed:
            lines.append(f"  FAILED   {wt}  ({err})")
        for w in self.warnings:
            lines.append(f"  warn: {w}")
        return "\n".join(lines)


# --- real git / filesystem implementations (injected by default) ------------

def _run_git(args: Sequence[str], cwd: Optional[str] = None) -> str:
    out = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )
    return out.stdout


def _git_list_worktrees(cwd: Optional[str] = None) -> List[str]:
    """Worktree roots from `git worktree list --porcelain`. May raise on failure."""
    text = _run_git(["worktree", "list", "--porcelain"], cwd=cwd)
    roots: List[str] = []
    for line in text.splitlines():
        if line.startswith("worktree "):
            roots.append(os.path.normpath(line[len("worktree "):].strip()))
    return roots


def _current_worktree_root(cwd: Optional[str] = None) -> str:
    return os.path.normpath(_run_git(["rev-parse", "--show-toplevel"], cwd=cwd).strip())


def _read_state(worktree_root: str, rel_path: str) -> WorktreeState:
    """Read the target file's facts in one worktree (exists / dirty / content)."""
    target = os.path.join(worktree_root, rel_path)
    if os.path.isfile(target):
        with open(target, "r", encoding="utf-8") as fh:
            content: Optional[str] = fh.read()
    else:
        content = None
    # Any porcelain status for the path (modified, staged, or untracked) => dirty:
    # we must not clobber uncommitted work.
    status = _run_git(["status", "--porcelain", "--", rel_path], cwd=worktree_root)
    dirty = bool(status.strip())
    return WorktreeState(worktree=worktree_root, dirty=dirty, current_content=content)


def _write_file(worktree_root: str, rel_path: str, content: str) -> None:
    target = os.path.join(worktree_root, rel_path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(content)


# --- the orchestration core (pure-ish; all I/O injected) ---------------------

def _propagate(
    path: str,
    content: str,
    *,
    worktrees: Sequence[str],
    primary: str,
    read_state: Callable[[str, str], "WorktreeState"],
    write_file: Callable[[str, str, str], None],
    boundary: Sequence[str],
    enumerate_warning: Optional[str] = None,
) -> Summary:
    """Execute the plan over an already-enumerated worktree set.

    ``primary`` (the current worktree) is ordered first and is the only write
    whose failure aborts the whole op; siblings are independent best-effort.
    """
    # Order primary first, then siblings as enumerated (deduped, primary removed).
    ordered = [primary] + [w for w in worktrees if w != primary]

    states = [read_state(w, path) for w in ordered]
    plan = computeFanOutPlan(path, content, states, boundary)

    summary = Summary(path=path, boundary_verdict=plan.boundary_verdict, primary=primary)
    if enumerate_warning:
        summary.warnings.append(enumerate_warning)

    # Fail-closed: an out-of-boundary path refuses everywhere; no write occurs.
    if plan.boundary_verdict == REFUSE:
        summary.refused = [d.worktree for d in plan.per_worktree]
        summary.primary_ok = False
        return summary

    for decision in plan.per_worktree:
        wt = decision.worktree
        is_primary = wt == primary
        if decision.action == WRITE:
            try:
                write_file(wt, path, content)
            except Exception as exc:  # noqa: BLE001 - surface any I/O failure
                if is_primary:
                    # Primary write must succeed -> abort the whole op (SDD §7).
                    summary.failed.append((wt, str(exc)))
                    summary.primary_ok = False
                    summary.warnings.append("primary write failed — aborting fan-out")
                    return summary
                summary.failed.append((wt, str(exc)))  # sibling: warn + continue
                continue
            summary.written.append(wt)
            if is_primary:
                summary.primary_ok = True
        elif decision.action == NOOP:
            summary.noop.append(wt)
            if is_primary:
                summary.primary_ok = True   # already equals desired => primary satisfied
        elif decision.action == SKIP:
            summary.skipped.append((wt, decision.reason))
            if is_primary:
                summary.warnings.append(f"primary skipped ({decision.reason}) — note not refreshed in current worktree")
        elif decision.action == REFUSE:
            summary.refused.append(wt)

    return summary


# --- public entry point (SDD §8 "Fan-out shell", frozen signature) ----------

def propagateSteeringNote(path: str, content: str) -> Summary:
    """Propagate a steering note at ``path`` across the developer's worktrees.

    The current worktree is the primary (written first, must succeed); siblings
    are best-effort. On `git worktree list` failure or a single worktree, writes
    the primary only and warns. Returns a reconcile Summary.
    """
    primary = _current_worktree_root()
    warning: Optional[str] = None
    try:
        worktrees = _git_list_worktrees()
    except Exception as exc:  # noqa: BLE001
        worktrees = [primary]
        warning = f"`git worktree list` failed ({exc}) — wrote primary only"
    if len(worktrees) <= 1:
        worktrees = [primary]
        if warning is None:
            warning = "single worktree — wrote primary only"

    return _propagate(
        path,
        content,
        worktrees=worktrees,
        primary=primary,
        read_state=_read_state,
        write_file=_write_file,
        boundary=BAKED_BOUNDARY,
        enumerate_warning=warning,
    )


if __name__ == "__main__":  # pragma: no cover - manual smoke
    import sys

    if len(sys.argv) != 3:
        print("usage: fanout-shell.py <relative-path> <content>", file=sys.stderr)
        sys.exit(2)
    print(propagateSteeringNote(sys.argv[1], sys.argv[2]).render())

"""A real git repository for the run tests: a feature branch, a bare remote, and a run branch with a plan."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

FEATURE = "feat/x"
RUN = f"{FEATURE}-run"
APPROVED = "> Division: approved 2026-10-30"
DEFAULT_ROWS = "| static | `git --version` | the tool runs |\n| unit | `git status --short` | the tests run |"


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, f"git {args}: {done.stderr}"
    return done.stdout.strip()


def contract_text(subtask, blocked=(), produces=None, consumes=(), rows=DEFAULT_ROWS, extra=""):
    produces = produces if produces is not None else [f"src/{subtask}.py#def {subtask[5:]}( — the code"]
    blockers = "\n".join(f"- {item}" for item in blocked) or "(none)"
    wanted = "\n".join(f"- {line}" for line in produces) or "(none)"
    used = "\n".join(f"- {line}" for line in consumes) or "(none)"
    return f"""# {subtask}

## Goal
Build {subtask}.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8

## Scope
- src/**

## Seams
(none)

## Acceptance
- [ ] it works (PRD §AC-001)

## Produces
{wanted}

## Consumes
{used}

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
{rows}

## Context excerpts
> (PRD §AC-001) it works

## Parent PRD
docs/PRD.md

## Parent SDD
docs/SDD.md

## Blocked by
{blockers}

## Conflict procedure
Record it or stop.
{extra}"""


def plan_text(subtasks, approval=APPROVED, header_extra=""):
    rows = "\n".join(f"| {rank} | {subtask} | title | pending | — | static | — |" for rank, subtask in enumerate(subtasks, 1))
    return f"""# Execution Plan

> Parent ticket: T-1   Mode: cited
> Last updated: 2020-01-01 (status column)
{approval}
{header_extra}

## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
{rows}

Status values: pending, done.
"""


@dataclass
class Fixture:
    root: Path
    work: Path
    run: Path
    plan: Path
    remote: Path

    def commit_code(self, name, text, message):
        path = self.work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        git(self.work, "add", name)
        git(self.work, "commit", "-qm", message)
        return git(self.work, "rev-parse", "HEAD")

    def push(self):
        git(self.work, "push", "-q", "origin", FEATURE)

    def status_of(self, subtask):
        for line in (self.plan / "PLAN.md").read_text(encoding="utf-8").splitlines():
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) > 3 and cells[1] == subtask:
                return cells[3]
        raise AssertionError(f"no row {subtask}")


def build(root, contracts, approval=APPROVED, header_extra=""):
    """`contracts` maps a subtask id to its contract text, in rank order."""
    root = Path(root)
    remote, work, run = root / "remote.git", root / "work", root / "work-run"
    work.mkdir()
    git(root, "init", "-q", "--bare", str(remote))
    git(work, "init", "-q", "-b", FEATURE)
    git(work, "config", "user.name", "t")
    git(work, "config", "user.email", "t@t.test")
    git(work, "config", "commit.gpgsign", "false")
    git(work, "remote", "add", "origin", str(remote))
    (work / "README.md").write_text("a repository\n", encoding="utf-8")
    git(work, "add", "README.md")
    git(work, "commit", "-qm", "start")
    git(work, "push", "-qu", "origin", FEATURE)
    git(work, "worktree", "add", "-q", "--detach", str(run))
    git(run, "checkout", "-q", "--orphan", RUN)
    git(run, "rm", "-rfq", ".")
    plan = run / "plan"
    plan.mkdir()
    (plan / "PLAN.md").write_text(plan_text(list(contracts), approval, header_extra), encoding="utf-8")
    for subtask, text in contracts.items():
        (plan / f"{subtask}.md").write_text(text, encoding="utf-8")
    git(run, "add", "plan")
    git(run, "commit", "-qm", "plan")
    return Fixture(root, work, run, plan, remote)

---
name: autopilot
description: /afkv2:autopilot — builds an approved plan hands-off, one subtask at a time, a fresh subagent each, into one Draft change. Refuses a plan that fails its check, has no division approval or is a v1 plan. Rules reversible plan calls and parks one-way doors with their dependents. Use to build from a plan.
---

# /afkv2:autopilot

Starting this skill authorizes commits and pushes on the feature branch, commits on the run branch, and the Draft change. The journal copy of `archive` is the 1 run record that lands on the feature branch. A human merges the change. Never run /afkv2:gc.

## Input

| Value | Source |
|-------|--------|
| plan folder | the invocation; else `plan` in the answer of `locate` |
| `app`, the address of a running app | the `> App:` line of PLAN.md; an `app` in the invocation replaces its address. A line that names a start command: start the app and pass its address. A live tier (`api`, `e2e`, `browser`) in a plan whose line names no app refuses at the gate, even with an `app` in the invocation |

## The commands

`<python> <this skill's folder>/scripts/start_gate.py check`, `<python> <this skill's folder>/scripts/walk.py <verb>` and `<python> <this skill's folder>/scripts/end_gate.py <verb>`, with one JSON object on stdin, from the worktree of the feature branch. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object; exit 0 is ok, 1 is refused, 2 is unreadable input. Every `walk.py` payload except that of `locate` holds `plan`.

## Steps

1. **Find the plan.** `locate`. It adds the worktree of `<feature branch>-run` when none exists.
2. **Pass the gate.** `check` with `plan` and optional `app`. A refusal lists each failure in `error.failures`: show every one to the developer and stop. `v1-plan` names 2 options: finish on v1, or slice again with `/afkv2:to-subtasks`. The gate writes nothing.
3. **Walk.** Repeat until `next` answers `finished: true`:
   1. `status` of `ci_watch.py` in `/afkv2:create-change-request`, with the `change` that `start` answered, when the run has a change. A red CI gets one line to the developer; the walk goes on.
   2. `next`. `give_up: true` means 3 subagents gave no result: `park` with `by: "autopilot"`, and go to the next pass.
   3. `start` with `subtask` and optional `app`. A refusal `contract-mismatch` or `gate-cannot-run`: `park` with `by: "autopilot"`, and name the failure in `reason`.
   4. Start one fresh subagent with `brief` as its whole prompt. It runs `/afkv2:execute`.
   5. Read its last lines, and route them by the table below. Read the tracker through `next`: the report does not move the walk.
4. **End gate.** When `next` answers `finished: true` and every subtask is done, `run` of `end_gate.py` with `plan` and `session` (`claude` or `codex`, the provider of this session). Start it in the background and wait for it to exit: a run takes up to 3600 s before its last row starts, plus 2 runs of 1800 s at most for that row. It runs each high-level row once against the live build, calls the judge when every row passed, and writes the gate record. Route its `result`:

   | `result` | Next action |
   |----------|-------------|
   | `passed`, `none` | step 5 |
   | `waiting` | step 5. Each row of `waiting` names what the gate could not reach: the developer meets it at ship |
   | `failed` | `back` with `plan` and `rows`, the `row` of each entry of `failed`. Then step 3 again; the next `run` runs every row |
   | `failed` with `cap_reached: true` | step 5: 3 gate runs failed, and the run waits for the developer. No `back` |

   A refusal `gate-cap-reached` (3 failed gate runs) or `no-verification`: step 5, and tell the developer that the run waits for them. With a parked subtask, skip the end gate.
5. **End.** `end`. Its answer lists `done`, `parked`, `waiting` and `rulings`. Then `archive`: it copies `plan/JOURNAL.md` to `<spec dir>/runs/<run branch>.md` in the linked worktree of the feature branch, never the main checkout, with each `/` of the branch name as `-`, and commits it on the feature branch when it changed. Its answer holds `path`, `committed`, `commit` (the newest commit of the copy) and `ship`. Then push the feature branch, also when `committed` is false. Only the `ship` of `archive` counts: `end` adds a journal line, so its own `ship` is false after a walk. A refusal: correct its cause and run `archive` again. A `## Parent PRD` outside the feature worktree refuses `no-spec-dir`.
6. **Report to the developer.** One line per ruling: its id, the question and the ruling. One line per park: the subtask, why, and the ledger id. One line per failed or waiting gate row: its journey, its subtasks and why.
7. **Ship.** `ship: true` from `archive`: run the "Ship" section of `/afkv2:create-change-request` with `id`, `plan`, `gate` (the `path` of `run`) and `ticket` (the `> Parent ticket:` line of `PLAN.md`). Name the `commit` of `archive` in its `description`, not in `proofs`: it was pushed after the reviews stopped. `ship: false`: stop; `gate` of `archive` names a gate record that stops it. The change stays Draft.

| Last lines of the subagent | Next action |
|----------------------------|-------------|
| `RESULT: done` | next pass |
| `RESULT: parked` | next pass: `park` has blocked the dependents |
| `RESULT: stopped`, with `CALL: <JSON>` | rule the plan call (below), then start a fresh subagent: `start` gives the same subtask, with the ruling in `brief` |
| anything else, or nothing | next pass: `next` gives the same subtask again |

Two-way doors of your own follow [DOORS.md](DOORS.md), with `by: "autopilot"`.

## Rule the plan call

You are the orchestrator, and the rule is yours: an executor never rules its own call. Decide the kinds yourself from the `CALL`. Its own `kinds` are a proposal.

| Kind | The call | Result of `rule` |
|------|----------|------------------|
| `scope` | a file the work needs sits outside the subtask's `## Scope` | ruled |
| `file-owner` | which subtask owns a file; pass `applies_to` with each subtask that gets the ruling | ruled |
| `subtask-order` | the order of two subtasks; pass `first` and `then` | ruled, unless it goes against `## Blocked by`. A running `then` goes back to `pending` |
| `acceptance` | a change to an acceptance criterion | parks |
| `one-way` | a one-way door or a tie | parks |
| `cost` | a cost trade-off | parks |

`rule` with `subtask`, `kinds`, `question`, `options`, `reversible`, `inside_goal`, `ruling`, `evidence`, `reverse` and optional `supersedes`. `inside_goal` is false when the ruling changes what the plan's acceptance criteria promise. A call with a parking kind, or with `reversible` or `inside_goal` false, parks with its dependents; so does a 4th call on one subtask. The answer holds `ruled`. The ruling reaches the executor in `brief`, and the developer in step 6.

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `start-refused` | the gate lists each failure | step 2 |
| `not-run-branch` | the plan folder is not `plan/` at the root of a run branch | pass the path from `locate` |
| `not-feature-branch`, `no-run-branch` | no feature branch, or no run branch | run from the feature branch, or slice with `/afkv2:to-subtasks` |
| `no-feature-worktree`, `no-spec-dir` | `archive` finds no linked worktree of the feature branch, or no contract names a `## Parent PRD` inside that worktree | check the feature branch out in a linked worktree, or correct the plan; run `archive` again |
| `not-ended` | the last journal line is not the run end | `end`, then `archive` |
| `subtask-in-flight`, `blocked-by`, `parked`, `already-done` | this subtask cannot start now | `next` names the one that can |
| `contract-mismatch`, `gate-cannot-run` | a consumed anchor is missing, or a gate cannot run | `park` |
| `not-running`, `not-finished`, `change-differs` | an executor's verb went wrong | the executor reads them; see `/afkv2:execute` |
| `not-finished` of `run` | a failure with a `subtask` is not done; a failure with `subtask: null` names uncommitted changes in the feature worktree | a subtask: step 3. Uncommitted changes: step 5, and name the files to the developer |
| `gate-cap-reached`, `no-verification` | 3 gate runs failed, or the spec folder has no VERIFICATION.md | step 5; the run waits for the developer |
| `no-such-subtask`, `git-failed`, `bad-state`, `bad-payload` | `reason` names the fault | correct it, or report it to the developer |

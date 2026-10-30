---
name: autopilot
description: /afkv2:autopilot — builds an approved plan hands-off, one subtask at a time, a fresh subagent each, into one Draft change. Refuses a plan that fails its check, has no division approval or is a v1 plan. Rules reversible plan calls and parks one-way doors with their dependents. Use to build from a plan.
---

# /afkv2:autopilot

Starting this skill authorizes commits and pushes on the feature branch, commits on the run branch, and the Draft change. A human merges the change.

## Input

| Value | Source |
|-------|--------|
| plan folder | the invocation; else `plan` in the answer of `locate` |
| `app`, the address of a running app | the invocation; none given: a live tier (`api`, `e2e`, `browser`) refuses at the gate |

## The commands

`<python> <this skill's folder>/scripts/start_gate.py check` and `<python> <this skill's folder>/scripts/walk.py <verb>`, with one JSON object on stdin, from the worktree of the feature branch. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object; exit 0 is ok, 1 is refused, 2 is unreadable input. Every `walk.py` payload except that of `locate` holds `plan`.

## Steps

1. **Find the plan.** `locate`. It adds the worktree of `<feature branch>-run` when none exists.
2. **Pass the gate.** `check` with `plan` and optional `app`. A refusal lists each failure in `error.failures`: show every one to the developer and stop. `v1-plan` names 2 options: finish on v1, or slice again with `/afkv2:to-subtasks`. The gate writes nothing.
3. **Walk.** Repeat until `next` answers `finished: true`:
   1. `status` of `ci_watch.py` in `/afkv2:create-change-request`, with the `change` that `start` answered, when the run has a change. A red CI gets one line to the developer; the walk goes on.
   2. `next`. `give_up: true` means 3 subagents gave no result: `park` with `by: "autopilot"`, and go to the next pass.
   3. `start` with `subtask` and optional `app`. A refusal `contract-mismatch` or `gate-cannot-run`: `park` with `by: "autopilot"`, and name the failure in `reason`.
   4. Start one fresh subagent with `brief` as its whole prompt. It runs `/afkv2:execute`.
   5. Read its last lines, and route them by the table below. Read the tracker through `next`: the report does not move the walk.
4. **End.** `end`. Its answer lists `done`, `parked`, `waiting`, `rulings` and `ship`.
5. **Report to the developer.** One line per ruling: its id, the question and the ruling. One line per park: the subtask, why, and the ledger id.
6. **Ship.** `ship: true`: run the "Ship" section of `/afkv2:create-change-request` with `id` and `plan`. `ship: false`: stop. The change stays Draft.

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

`rule` with `subtask`, `kinds`, `question`, `options`, `reversible`, `inside_goal`, `ruling`, `evidence`, `reverse` and optional `supersedes`. `inside_goal` is false when the ruling changes what the plan's acceptance criteria promise. A call with a parking kind, or with `reversible` or `inside_goal` false, parks with its dependents; so does a 4th call on one subtask. The answer holds `ruled`. The ruling reaches the executor in `brief`, and the developer in step 5.

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `start-refused` | the gate lists each failure | step 2 |
| `not-run-branch` | the plan folder is not `plan/` at the root of a run branch | pass the path from `locate` |
| `not-feature-branch`, `no-run-branch` | no feature branch, or no run branch | run from the feature branch, or slice with `/afkv2:to-subtasks` |
| `subtask-in-flight`, `blocked-by`, `parked`, `already-done` | this subtask cannot start now | `next` names the one that can |
| `contract-mismatch`, `gate-cannot-run` | a consumed anchor is missing, or a gate cannot run | `park` |
| `not-running`, `not-finished`, `change-differs` | an executor's verb went wrong | the executor reads them; see `/afkv2:execute` |
| `no-such-subtask`, `git-failed`, `bad-state`, `bad-payload` | `reason` names the fault | correct it, or report it to the developer |

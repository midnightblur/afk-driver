---
name: execute
description: /afkv2:execute — runs one subtask of a plan end to end, test first, with its own commits, its review and its push to the one Draft change. Use when a brief from /afkv2:autopilot names a subtask.
---

# /afkv2:execute

You run in a fresh subagent, from the worktree of the feature branch. The brief holds `subtask`, `plan`, `contract`, `base`, `change`, `python` and any rulings.

## The commands

`<python> <this skill's folder>/scripts/tdd_log.py <verb>` and `<python> <this skill's folder>/../autopilot/scripts/walk.py <verb>`, with one JSON object on stdin. Every payload holds `plan` and `subtask`. Every answer is one JSON object; exit 0 is ok, 1 is refused, 2 is unreadable input.

## Steps

1. **Read.** Read the contract and `<plan>/DECISIONS.md`. `## Context excerpts` is your spec: open the parent PRD and SDD only for a question the excerpts leave open. A ruling in the brief binds over the contract. A decision entry binds over the passage it quotes.
2. **Read the ground.** Read each symbol that `## Seams` and `## Consumes` name. Read the module's `AGENTS.md` and the rules that match the files ahead.
3. **Build, test first.** For each behavior:
   1. Write the test. `red` with `behavior` and `command`: the test must fail, and only test files may have changed.
   2. Write the code. `green` with `behavior`: the same command must pass.
   3. Commit. Each subject starts `[<subtask>]`. Commit each time a behavior is green. Stay inside `## Scope`.

   Work with no behavior to test, such as prose or a config value: `no-test` with `why`.
4. **Open the change.** After the first commits, push. Never force-push. `change: none` in the brief: run "Open or update the change" of `/afkv2:create-change-request`, then `set-change` with `change`. After each push, run its "After each push" step: `start` of `ci_watch.py`.
5. **Verify.** `status` with `status: "verifying"`. Run each row of `## Verification`, in order. A row whose check cell starts `not applicable:` does not run. Each other row must pass. Grep each `## Produces` anchor. A row stays red after one targeted fix: `park`.
6. **Review.** `status` with `status: "reviewing"`. Run `/afkv2:code-review` with `subtask`, `plan`, `change` and `base`. Its `left.blocking` is not empty: `park` with the findings in `reason`. Each code fix there returns to step 5 for the rows it touches, and gets a push.
7. **Finish.** `done`. A refusal `not-finished` lists each gap in `error.failures`: close each gap, and run `done` again.
8. **Report.** End with the lines below.

## Forks

A two-way door or a one-way door: [DOORS.md](../autopilot/DOORS.md), with verbs `decide` and `park`.

A **plan call** goes to the orchestrator. An executor never changes its own Scope. Stop the work, commit what is green, and report `RESULT: stopped` with one `CALL`.

| Kind | The call |
|------|----------|
| `scope` | a file the work needs sits outside `## Scope` |
| `file-owner` | which subtask owns a file |
| `subtask-order` | the order of two subtasks |
| `acceptance` | a change to an acceptance criterion |
| `one-way` | a one-way door or a tie that is also a plan call |
| `cost` | a cost trade-off |

## The report

Your last lines, with nothing after them:

```
RESULT: done
```

```
RESULT: parked
```

```
RESULT: stopped
CALL: {"kinds": ["scope"], "question": "...", "options": "...", "recommendation": "...", "reversible": true, "inside_goal": true, "why": "..."}
```

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `not-red` | the test passes before the code exists | correct the test |
| `code-before-red` | code files changed before the test failed | commit finished work; move the rest out and write the test first |
| `no-red` | no failing test is on record for this behavior | `red` |
| `not-green` | the test still fails | fix the code |
| `timed-out` | the test command ran past its limit | narrow the command |
| `not-finished` | the list of gaps of `done` | close each gap |
| `not-running` | the row is not running | report it |
| `change-differs` | the run already has another change | use that change |
| `bad-state`, `git-failed` | `reason` names the fault | report it with `RESULT: parked` after `park` |

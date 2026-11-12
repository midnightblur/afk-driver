---
name: small-change
description: /afkv2:small-change — the small lane for a bug fix or a small enhancement, such as "fix X" or "add a link to Y". States the lane in 1 line, proves a bug's cause, shows 1 page round, writes no code before the developer's go, fixes test first, proves the fix with 1 high-level test, before and after, and stops to propose the medium lane when the work grows. Use to fix a bug or make a small change. A new feature starts at /afkv2:grill-requirements.
---

# /afkv2:small-change

The small lane: 1 page round, the developer's go, 1 high-level proof. Write no product code before the go.

## The commands

Run each command from the repository root, in the worktree of the branch. `<python>` is the Python in the setup install record (line `python`). `small_lane.py` takes 1 JSON object on stdin. Every answer is 1 JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input.

```sh step=lane
<python> "<this skill's folder>/scripts/small_lane.py" <verb>
```

## Steps

1. **Read the code, then state the lane.** Read the code that the request touches. Run `start` with `kind` (`bug` or `enhancement`), `why` (1 line) and `ticket` when the work has one. Show its `line` to the developer, who confirms or changes it. A change to the medium lane: stop, and name `/afkv2:grill-requirements`. Keep `doc`, `session` and `raw_file` of the answer for the page round.

2. **Prove the cause, or read the behavior.** A bug: run the loop of [DIAGNOSIS.md](DIAGNOSIS.md) and record its verdict with `diagnose` (`verdict`, `cause`). An enhancement: read the current behavior and cite it. Done when the page round has its facts.

3. **Draft the fix.** Run `plan`; it starts nothing.

   ```sh step=proposers-plan
   <python> "<this skill's folder>/scripts/small_proposers.py" plan --doc "<doc>"
   ```

   `count` 1: draft alone, and show `reason` in the banner. `count` 2: 1 Claude and 1 Codex proposer each draft the fix and its test plan, then each critiques the other, by the verbs and the stages of the engine docstring ([../use-lavish/scripts/proposer_engine.py](../use-lavish/scripts/proposer_engine.py)). Read the 4 files, never the pane output; a difference both critiques do not settle is 1 fork card. Run `cleanup` before step 4. A proposer failure: `cleanup`, then draft alone.

4. **Show 1 page round.** Write the round by `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)) and `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)), with `session.skill` `small-change`. The round shows:

   | Part | A bug | An enhancement |
   |------|-------|----------------|
   | the picture of the problem | how it happens, its flow and the conditions that reach it | now against proposed, with kept, changed, added and removed |
   | the fix | the fix of the verdict, or each fix as 1 option | the change |
   | the test plan | each test with its level; 1 high-level test is the proof | the same |
   | open questions | each 1 card | each 1 card |

   End the round with 1 `signoff` card: the go. Build, show, wait and ingest by `/afkv2:use-lavish`. A session with no human at a page opens no page: it stops and asks.

5. **Take the go.** Run `go` with `doc`, `card` (the go card) and `test_plan` (the test plan of the round, as text). `no-go-mark`: answer the notes in 1 more round. `code-before-go`: move the code out of the branch, and run `go` again.

6. **Fix, test first.** Write each test before its code; commit each time a test turns green. The high-level test comes first. A bug: run `before` with `command` (the high-level test) before any fix; it must fail, and its log is the before evidence. `before` and `gate` start the live build of the repository config when its address does not answer, and stop it after.

7. **Stop when it grows.** The work needs a format that other skills read, a new module or a design choice: write no more code. Run `grow` with `reason` (1 line). Show its `proposal` on the page with the reason. The developer decides.

8. **Run the small gate.** Run `gate` with `behavior`, `level` (`api`, `ui-e2e` or `acceptance`), `command` (the high-level test), `test` (its file) and `session` (`claude` or `codex`). `result` `fail` or `flaky`: fix test first, then run `gate` again. `verdict` `fail`: read the failed checks of the verdict in the gate record, fix the test or the code, and run `gate` again. `judge` not null: the judge gave no verdict, and ship waits for it. A bug: show the before log and the after log on the page.

9. **Ship.** Run `/afkv2:create-change-request` with the gate record `path` of `gate`. Its proof lines name the high-level test; for a bug, its evidence holds the before log and the after log.

## Refusals

| Code | Meaning | Next action |
|------|---------|-------------|
| `bad-payload` | a field is missing or wrong, such as a `why` of 2 lines or a low-level `level` | fix the field |
| `no-lane` | no lane is started in this worktree | `start` |
| `no-diagnosis` | a bug has no verdict | step 2 |
| `no-go-mark` | the go card holds no sign mark of the developer, or no go is on record | 1 more round |
| `code-before-go` | code changed before the go | move the code out, then `go` again |
| `grew-past-small` | the lane stopped at `grow` | the developer picks the lane |
| `not-red` | the high-level test passes before the fix | correct the test |
| `fix-before-before` | code changed after the go, before `before` ran | move the fix out, run `before`, then fix |
| `no-before` | a bug reached the gate with no before evidence | `before` |
| `live-start-failed` | `before` could not start the live build of the repository config | fix the build, or its live block, and run `before` again |
| `no-shell` | no Git Bash on Windows | install Git for Windows |
| `git-failed` | `reason` names the fault | report it |

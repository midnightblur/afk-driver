---
name: propose-verification
description: /afkv2:propose-verification — turns a settled PRD and SDD into a verification plan. Claude and Codex each draft and critique a plan, the developer steers it on the page, the live build is proven, and the skill writes VERIFICATION.md. Use when the design is settled and the feature needs a verification plan, or to change one.
---

# /afkv2:propose-verification

Two proposers draft the plan, each critiques the other, and you reconcile one plan. The page shows it from high to low; the developer steers it with notes. Then you prove the live build, and write `VERIFICATION.md`.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json` | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |
| `GRILL-LOG.md` and the page documents | written by `/afkv2:grill-requirements` | stop and name them and the writer |
| `PRD.md` and the requirement ADRs | written by `/afkv2:to-prd` | stop and name them and the writer |
| `SDD.md` and the design ADRs | written by `/afkv2:propose-solution` | stop and name them and the writer |

Read only what is on disk, and the code. A later session continues from the page document and `GRILL-LOG.md` alone. A requirement or a design point that the specs leave out is a gap: name it, and send the developer to its writer.

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. On a refusal, fix what `reason` names and run the command again; when no fix exists, stop and report it.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/verification_files.py" start --ticket "<ticket key>" [--target "<target branch>"]
   ```

   Pass `--target` when the feature merges into a branch other than the default branch. `missing-input`: stop and show `missing` and `writer`. The answer holds `spec_dir`, `prd`, `sdd`, `log`, `requirement_adrs`, `design_adrs`, `verification`, `verification_exists`, `doc`, `session`, `resume`, `raw_file` and `live`. `resume` true: take the page over by `/afkv2:use-lavish` "Take over a page" ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)), read `doc`, honour every steer in it, and continue at step 4. `verification_exists` true: this session changes a plan; read `verification`, keep every row id, and retire a row in place, never drop it.

2. **Read the input and the code.** Read `prd`, `sdd`, both ADR folders, `log` and the page documents in `<spec_dir>/pages/`. Start the code reading in background subagents: the tests that exist per level, the contract tests per service boundary that the change crosses, and how the app starts, where it answers and how it stops. Done when each acceptance criterion and each boundary has the facts its rows need.

3. **Draft by 2 proposers.** Run `plan`. It starts nothing.

   ```sh step=proposers-plan
   <python> "<this skill's folder>/scripts/verification_proposers.py" plan --doc "<doc>"
   ```

   The answer is `{count, tools, reason}`. `count` 1: draft alone by [DRAFT.md](DRAFT.md), and show `reason` in the banner. `count` 2: 1 Claude and 1 Codex proposer draft, by R-1 to R-4. For a herdr command you run yourself, use the herdr playbook ([../herdr-playbook/SKILL.md](../herdr-playbook/SKILL.md)).

   | Step | Do |
   |------|----|
   | R-1 Same inputs | Write the brief, a Markdown file in a scratch folder: the paths of `prd`, `sdd`, both ADR folders and `log`, the path of [DRAFT.md](DRAFT.md), a digest of the code reading with its citations, and each steer. A file that `HEAD` does not hold goes into the brief in full. Run `start`. |
   | R-2 Draft alone | Run `wait`. Each proposer writes a whole plan to `DRAFT.md` in its own worktree. |
   | R-3 Critique | Run `critique`, then `wait` again. Each proposer writes what it would change in the plan of the other, and why, to `CRITIQUE.md`. The second `wait` answers `files`: the 4 paths. |
   | R-4 Reconcile | Read the 4 files, never the pane output. A part that both critiques accept becomes 1 plan. Each other difference becomes 1 fork card (a `debate` item) with both sides, each side naming its tool. Write the round input of step 4 now, outside the worktrees. Then run `cleanup`: it removes the worktrees and their files. |

   ```sh step=proposers-start
   <python> "<this skill's folder>/scripts/verification_proposers.py" start --doc "<doc>" --brief "<brief>" --base HEAD
   ```

   `wait` has no time limit. On Claude, run it as a background command the harness tracks: its exit wakes you.

   ```sh step=proposers-wait
   <python> "<this skill's folder>/scripts/verification_proposers.py" wait --doc "<doc>"
   ```

   ```sh step=proposers-critique
   <python> "<this skill's folder>/scripts/verification_proposers.py" critique --doc "<doc>"
   ```

   ```sh step=proposers-cleanup
   <python> "<this skill's folder>/scripts/verification_proposers.py" cleanup --doc "<doc>"
   ```

   A refusal coded `no-herdr`, `worktree-failed`, `herdr-failed`, `not-submitted`, `pane-gone` or `no-draft` is a proposer failure: run `cleanup`, and draft alone. `cleanup-failed` lists each pane and worktree in `left`: close or delete each by the playbook, then run `cleanup` again. On a resume, read `stage` in `<doc stem>.proposers.json` beside `doc`, and run the next verb: `planned` `start`, `drafting` `wait`, `drafted` `critique`, `critiquing` `wait`, `critiqued` R-4, `failed` `cleanup`.

4. **Work one round.** Load the page rules of `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)) and the page guide `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)). The page shows the whole plan from high to low: per story, its user journeys and API scenarios, then the low-level rows; each row with its level, its data and its environment. A fork card holds each point still in dispute. The live build card of step 5 joins the first round that needs it. Write the round input, a JSON file in a scratch folder: `banner`, `items`, and `maps` and `replies` when they change. You never write page HTML. Done when every item carries a decision, or names why you could not take it.

5. **Prove the live build.** By `live` of step 1:

   | `live` | Do |
   |--------|----|
   | `block` true | run `live-check`. Green and `proven_here` true: done. Green and `proven_here` false: run `live-prove` with no `--live`. Red: 1 card with the refusal, and the fix you propose. |
   | `block` false | propose `start`, `address`, `ready_seconds`, `stop` and `needs` (variable names only) from the code reading, on 1 card. After the developer settles it, run `live-prove` with that block. |
   | the build has no live app | 1 `confirm` card that says so and why. Only the developer's `accept` mark settles it; the plan then holds `app: {"none": "<card id>"}`. |

   ```sh step=live-check
   <python> "<this skill's folder>/../../scripts/live_build.py" check
   ```

   ```sh step=live-prove
   <python> "<this skill's folder>/../../scripts/live_build.py" prove --live '<block JSON>'
   ```

   A green `live-prove` writes the block into `.afkv2/config.json`: commit that file on the feature branch. A red one is 1 more round with the refusal on its card. Done when the block is proven at a commit of this feature, or the `none` card holds the mark.

6. **Build and show the round.** Done when `present` answers ok.

   ```sh step=build
   <python> "<this skill's folder>/../use-lavish/scripts/round_document.py" build --doc "<doc>" --session "<session>" --ticket "<ticket key>" --round-input "<round input>"
   ```

   ```sh step=present
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" present --doc "<doc>" --scan "<log>"
   ```

   Read each refusal and notice by `/afkv2:use-lavish` "After each show". On `show`, the page host is not available: print the round as Markdown in chat, with every card id, and write the reply of the developer to `raw_file`.

7. **Wait for the answer.** On Claude, run `wait` as a background command the harness tracks. On Codex, end your turn after `present`: the Stop hook hands the raw response back as your next prompt; write it to `raw_file`, word for word.

   ```sh step=wait
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

8. **Read the answer.** Read each card and each note by [../use-lavish/ROUND-PASS.md](../use-lavish/ROUND-PASS.md), answer each note by the answer rules of `/afkv2:use-lavish`, and apply the readings. A steer binds every later decision. Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   ```sh step=apply-readings
   <python> "<this skill's folder>/../use-lavish/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

9. **Save the state.** Copy the notes of this round into the log. A card still open: go to step 4. Done when the log matches this round.

   ```sh step=sync
   <python> "<this skill's folder>/scripts/verification_files.py" sync --doc "<doc>" --log "<log>"
   ```

10. **Write the plan.** Write the plan file by [VERIFICATION-FORMAT.md](VERIFICATION-FORMAT.md) "The plan file", from the page document and the input of step 2 only; ask no new question. Then run `write`. Each refusal of [VERIFICATION-FORMAT.md](VERIFICATION-FORMAT.md) "Refusals of write" is 1 more round or 1 fix of the plan file. Done when the answer is ok.

    ```sh step=write
    <python> "<this skill's folder>/scripts/verification_files.py" write --spec-dir "<spec dir>" --plan "<plan file>" --doc "<doc>" [--target "<target branch>"]
    ```

    `index_missing` true: the spec folder has no `INDEX.md`, so tell the developer to run `/afkv2:to-prd`.

11. **Finish.** End the page session:

    ```sh step=end
    <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" end --doc "<doc>"
    ```

    Commit the spec folder on the feature branch. Tell the developer the next skill is `/afkv2:to-subtasks`. Done when the commit exists.

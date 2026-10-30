---
name: to-subtasks
description: /afkv2:to-subtasks — cuts a settled PRD and SDD into a plan on the run branch, one cited contract per subtask, checks it, and waits for the developer to approve the division on the page. Use when the design is settled and the feature needs a plan.
---

# /afkv2:to-subtasks

The plan is `plan/` at the root of the run branch `<feature branch>-run`: `PLAN.md` and one contract per subtask. The run branch holds run files only; the spec folder stays on the feature branch. `/afkv2:autopilot` refuses a plan that fails its check or has no approved division.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json`, with a tracker kind | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |
| `PRD.md` and the requirement ADRs | written by `/afkv2:to-prd` | stop and name the file and `/afkv2:to-prd` |
| `SDD.md` and the design ADRs | written by `/afkv2:propose-solution` | stop and name the file and `/afkv2:propose-solution` |

Read only these files and the code. A requirement or a design point they leave out is a gap of the skill that writes them: name it, and send the human there.

## The commands

Run each command from the worktree of the feature branch, at the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. On a refusal, fix what `reason` names and run the command again; when no fix exists, stop and report it.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/plan_files.py" start --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. `sdd-not-ready`: stop and show `problems` and `writer`. `not-feature-branch`: run from the worktree of the feature branch. The answer holds `spec_dir`, `prd`, `sdd`, `parent_prd`, `parent_sdd`, `requirement_adrs`, `design_adrs`, `run_branch`, `worktree`, `plan`, `plan_exists`, `doc`, `session`, `resume`, `raw_file` and `raw_pending`. It creates the run branch and its worktree when they do not exist. `raw_pending` true: an answer waits in `raw_file`, so go to step 9. `resume` true: read `doc`, honour every steer in it, and continue at the first unfinished step.

2. **Read the sources.** Read `prd`, `sdd` and each file in `requirement_adrs` and `design_adrs`, in a background subagent that returns the ids and the sections you can cite. Done when you hold the list of PRD ids, SDD sections and ADRs.

3. **Cut the plan.** Follow [SLICING.md](SLICING.md). Write `<plan>/PLAN.md` by [PLAN-FORMAT.md](PLAN-FORMAT.md) and one `<plan>/NNNN-<slug>.md` per subtask by [SUBTASK-CONTRACT.md](SUBTASK-CONTRACT.md). Done when each settled requirement has a subtask and each subtask has its contract.

4. **Check the plan.** Done when both answers are ok. Each failure names its file and its rule.

   ```sh step=check
   <python> "<this skill's folder>/scripts/check_plan.py" "<plan>"
   ```

   ```sh step=citations
   <python> "<this skill's folder>/scripts/plan_files.py" citations --plan "<plan>" --spec-dir "<spec dir>"
   ```

5. **Commit the plan on the run branch.** Done when the answer is ok.

   ```sh step=commit
   <python> "<this skill's folder>/scripts/plan_files.py" commit --plan "<plan>" --message "<message>"
   ```

   `not-a-run-file` lists each file that does not belong there: move it out.

6. **Build the division round.** Write a JSON file in a scratch folder, with one sentence per subtask on why the cut is there: `{"<subtask id>": "<sentence>"}`. Done when `division` answers ok.

   ```sh step=division
   <python> "<this skill's folder>/scripts/plan_files.py" division --plan "<plan>" --doc "<doc>" --session "<session>" --ticket "<ticket key>" --why "<why file>"
   ```

   The script writes the one sign-off card, which shows every subtask. You write no page HTML. A later plan change takes back an earlier approval: run this step again after each change.

7. **Show the round.** Done when `present` answers ok.

   ```sh step=present
   <python> "<this skill's folder>/../grill/scripts/page_round.py" present --doc "<doc>"
   ```

   A refusal holds the failed `verb`. On `check` or `render`, the human has not seen this round: fix the named field, then run `division` again with `--replace`. On `show`, the page host is not available: print the card as Markdown in chat, with its id, take the human's reply as the raw response, write it to `raw_file`, and go to step 9 (the raw response form of this path is not verified until the page engine merges).

8. **Wait for the answer.** The answer reaches you with no chat message from the human.

   **On Claude**, run this command as a background command the harness tracks. Its exit tells you the answer is in `raw_file`. Do other work or end your response until then.

   ```sh step=wait
   <python> "<this skill's folder>/../grill/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

   **On Codex**, leave that command out. End your turn after `present`. The Stop hook waits for the answer and hands the raw response back as your next prompt. Write that text to `raw_file`, word for word. When the hook cannot wait, the human sends one chat message after Send: run `wait` then. Live check, run by the owner: [CODEX-LIVE-CHECK.md](CODEX-LIVE-CHECK.md).

9. **Read the answer.** Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/../grill/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   A lone `Sign` mark settles the card. Read each other signal by the round pass in [../visualize/components/card.md](../visualize/components/card.md), and each note by [../visualize/components/notes-and-replies.md](../visualize/components/notes-and-replies.md). Write the result to a JSON file and apply it. The keys of that file: [../grill/SKILL.md](../grill/SKILL.md), step 7.

   ```sh step=apply-readings
   <python> "<this skill's folder>/../grill/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

   The card returned to open: change the plan, then go to step 4. A note that asks for no change gets a reply, and the same plan goes to step 6 again.

10. **Write the approval.** Done when `approve` answers ok.

    ```sh step=approve
    <python> "<this skill's folder>/scripts/plan_files.py" approve --plan "<plan>" --doc "<doc>" --spec-dir "<spec dir>"
    ```

    It refuses `not-approved` until the developer has settled the card of this exact plan. On a pass it writes the line `> Division: approved <YYYY-MM-DD>` in `PLAN.md`, commits it on the run branch, and writes the `Plan` row of `INDEX.md`. `index_missing` true means the spec folder has no `INDEX.md`, so tell the human to run `/afkv2:to-prd`.

11. **Finish.** Commit `doc` and `INDEX.md` on the feature branch. Tell the human the next skill is `/afkv2:autopilot`. Done when the worktree of the feature branch is clean.

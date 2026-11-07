---
name: propose-solution
description: /afkv2:propose-solution — turns a settled PRD into a design. Asks the critical-aspect questions in a fixed order, proposes a top-down draft with fork cards on the page, and writes SDD.md and design ADRs. Use when the PRD is settled and the feature needs a design, or to change a design.
---

# /afkv2:propose-solution

The agent proposes a complete design, and the human vets it and adjusts it. First a short set of critical-aspect questions, each under a picture of how things are now. Then the whole draft from the top down, with each real choice as a fork card. The session is one page document, and the result is `SDD.md` and design ADRs.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json`, with a tracker kind | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |
| `GRILL-LOG.md` with a passed exit gate, and the page documents | written by `/afkv2:grill-requirements` | stop and name them and `/afkv2:grill-requirements` |
| `PRD.md` and the requirement ADRs | written by `/afkv2:to-prd` | stop and name the file and `/afkv2:to-prd` |

Read only what is on disk, and the code. A later session continues from the page document and `GRILL-LOG.md` alone. A requirement the PRD left out is a gap of the grill: name it, and send the human to `/afkv2:grill-requirements`.

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. On a refusal, fix what `reason` names and run the command again; when no fix exists, stop and report it.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/design_files.py" start --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. The answer holds `spec_dir`, `prd`, `log`, `requirement_adrs`, `sdd`, `sdd_exists`, `adr_dir`, `doc`, `session`, `resume`, `raw_file` and `raw_pending`. `unverified_external` lists what the grill could not verify. `resume` true: take the page over by `/afkv2:use-lavish` "Take over a page" ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)), with the `Takeover` row of step 2, read `doc`, honour every steer in it, run the `read-ticket` command of step 2, and continue at step 3. `raw_pending` true: an answer waits in `raw_file`, so go to step 7. `sdd_exists` true: this session changes a design, so read `sdd` and `adr_dir`, and let each card state what the SDD holds and what the change is.

2. **Read the input and the code.** Read the ticket into a file in a scratch folder. Step 5 passes `<ticket file>` to the build, so the first round shows the ticket card.

   ```sh step=read-ticket
   <python> "<this skill's folder>/../grill-requirements/scripts/read_ticket.py" --ticket "<ticket key>" --out "<ticket file>"
   ```

   On a refusal, report its `reason` to the human and leave `--ticket-file` out of each build: the first round then shows no ticket card.

   Read `prd`, `requirement_adrs`, `log` and the grill documents in `<spec_dir>/pages/`. Read the repository glossary and `STAPLES.md`, when they exist; a staple the PRD accepted is a design input. Start the code reading in background subagents. Write one row per load-bearing premise ([DRAFT.md](DRAFT.md) "Premises"). Done when each critical aspect and each layer has the facts its picture and its card need.

   ```sh step=row
   <python> "<this skill's folder>/scripts/design_files.py" row --log "<log>" --kind "<kind>" --text "<text>"
   ```

3. **See what comes next.** Done when you know the phase.

   ```sh step=next
   <python> "<this skill's folder>/scripts/design_round.py" next --doc "<doc>"
   ```

   | `phase` | Do |
   |---------|----|
   | `aspects` | step 4 with [ASPECTS.md](ASPECTS.md): ask the entries of `aspects_to_ask` in their order, and return each of `aspects_open` |
   | `proposers` | every aspect is settled: the solution proposers below, then step 4 as for `draft` |
   | `draft` | step 4 with [DRAFT.md](DRAFT.md): propose `layers_to_ask` from the top down, and return each of `layers_open` and `locked_open` |
   | `write` | step 9 |

   **The solution proposers.** `proposers.py` drives herdr; for a herdr command you run yourself, use the herdr playbook ([../herdr-playbook/SKILL.md](../herdr-playbook/SKILL.md)). Run `plan`. It starts nothing.

   ```sh step=proposers-plan
   <python> "<this skill's folder>/scripts/proposers.py" plan --doc "<doc>"
   ```

   The answer is `{count, tools, reason}`. `count` 1: you draft alone, and the answer is the `proposers` field of the first draft round input, as it is. `count` 2: 1 Claude and 1 Codex proposer draft, by R-1 to R-5.

   | Step | Do |
   |------|----|
   | R-1 Same inputs | Write the brief, a Markdown file in a scratch folder: the paths of `prd`, `requirement_adrs` and `log`, a digest of the code reading with its citations, each settled aspect with its reading, and each steer. A file that `HEAD` does not hold goes into the brief in full. No proposer sees the draft of the other. Run `start`. |
   | R-2 Draft alone | Run `wait`. Each proposer writes a whole design, every layer, to `DRAFT.md` in its own worktree. |
   | R-3 Critique | Run `critique`, then `wait` again. Each proposer reads the draft of the other and writes what it would change, and why, to `CRITIQUE.md`. The second `wait` answers `files`: the 4 paths. |
   | R-4 Reconcile | Read the 4 files, never the pane output. A part that both critiques accept in writing becomes 1 design. Each other difference becomes 1 fork card, and each option names its tool in `by`. Write the round input of step 4 now, outside the worktrees: `cleanup` removes the worktrees and their files. Then run `cleanup`. |
   | R-5 Show | Put the `proposers` object of the `cleanup` answer into the round input, as it is. The banner says how many solution proposers drafted, or why only 1 did. |

   ```sh step=proposers-start
   <python> "<this skill's folder>/scripts/proposers.py" start --doc "<doc>" --brief "<brief>" --base HEAD
   ```

   `wait` has no time limit. On Claude, run it as a background command the harness tracks: its exit wakes you.

   ```sh step=proposers-wait
   <python> "<this skill's folder>/scripts/proposers.py" wait --doc "<doc>"
   ```

   ```sh step=proposers-critique
   <python> "<this skill's folder>/scripts/proposers.py" critique --doc "<doc>"
   ```

   ```sh step=proposers-cleanup
   <python> "<this skill's folder>/scripts/proposers.py" cleanup --doc "<doc>"
   ```

   A refusal coded `no-herdr`, `worktree-failed`, `herdr-failed`, `not-submitted`, `pane-gone` or `no-draft` is a proposer failure: run `cleanup`. Its `proposers` then has count 1 with reason `proposer-failed`, and you draft alone. `cleanup-failed` lists each pane and worktree in `left`: close or delete each by the playbook, then run `cleanup` again; the draft round waits until then. On a resume in this phase, read `stage` in the state file `<doc stem>.proposers.json` beside `doc`, and run the next verb: `planned` `start`, `drafting` `wait`, `drafted` `critique`, `critiquing` `wait`, `critiqued` R-4, `failed` `cleanup`. A refusal coded `not-started`, `same-tool`, `not-planned` or `not-drafted` means the proposers cannot go on: run `cleanup`, and draft alone.

4. **Work one round.** Load the page rules and forms of `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)) for page order and wording, and the page guide `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)). Verify premises, weigh the options, and take every decision the rules allow ([DRAFT.md](DRAFT.md) "Cards"). Then write the round input, a JSON file in a scratch folder: `banner`, `items`, and `maps` and `replies` when they change. The build draws the maps of the aspects, the layers and the human-locked set; `maps` holds only your own. You never write page HTML. Done when every item carries a decision, or names why you could not take it.

   An item has the page document fields, plus these fields of the input only:

   | Field | Effect |
   |-------|--------|
   | `aspect: "<key>"` | the card asks that critical aspect. It is a `confirm` card or a fork. The body root must be a picture of the current state, with the question in its `children`. The build refuses any other shape, and any order but the fixed one. |
   | `layer: "<L1..L9>"` | the card belongs to that layer. The build refuses it until every aspect is settled, and refuses a layer before the ones above it. |
   | `locked: "<HL-n>"` | the `signoff` card of that human-locked aspect. |
   | `fork: {question, options, why_open, recommended, picture}` | the build writes a `debate` card with the options side by side. A `debate` card has no other form. |
   | `decided`, `carries` | as in [../grill-requirements/SKILL.md](../grill-requirements/SKILL.md), step 4. A card that carries a tagged card has the same tag. |

   The first draft round input also holds `proposers`, from step 3. The build writes its banner line. On a resume in phase `draft` with no draft round yet, run `plan` again: after `cleanup` it answers the same `proposers` object from the state file. When the R-4 round input is lost, the 4 files are lost too: draft alone, with `proposers` count 1, your own tool and reason `proposer-failed`.

5. **Build and show the round.** Done when `present` answers ok.

   ```sh step=build
   <python> "<this skill's folder>/scripts/design_round.py" build --doc "<doc>" --session "<session>" --ticket "<ticket key>" --round-input "<round input>" --ticket-file "<ticket file>"
   ```

   ```sh step=present
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" present --doc "<doc>" --scan "<log>"
   ```

   `present` runs check, render and show, and scans the page and the log for secrets. Report its notices by `/afkv2:use-lavish` "After each show". A refusal holds the failed `verb`. On `check` or `render`, the human has not seen this round: fix the named field in the round input, then run `build` again with `--replace`. It works only on a round that `present` did not try to show. A shown round with no answer refuses `round-shown`, because the human may be answering it in the browser: wait for the answer. On `show`, the page host is not available: print the round as Markdown in chat, with every card id, take the human's reply as the raw response, write it to `raw_file`, and go to step 7 (the raw response form of this path is not verified until the page engine merges).

6. **Wait for the answer.** The answer reaches you with no chat message from the human.

   **On Claude**, run this command as a background command the harness tracks. Its exit tells you the answer is in `raw_file`. Do other work or end your response until then.

   ```sh step=wait
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

   **On Codex**, leave that command out. End your turn after `present`. The Stop hook waits for the answer and hands the raw response back as your next prompt. Write that text to `raw_file`, word for word. When the hook cannot wait, the human sends one chat message after Send: run `wait` then. Live check, run by the owner: [CODEX-LIVE-CHECK.md](CODEX-LIVE-CHECK.md).

   **Side questions** from the page's btw? button: as in [../grill-requirements/SKILL.md](../grill-requirements/SKILL.md), step 6 "Side questions". The round stays open. Show your answers with:

   ```sh step=reply
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" reply --doc "<doc>" --reply-file "<reply file>"
   ```

7. **Read the answer.** Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   The engine settles a lone mark, and sends every other signal to `needs_reading`. The answer lists `needs_reading`, `returned`, `steers`, `blocked` and the raw `signals`. Read each card and each note by the round pass in [../use-lavish/ROUND-PASS.md](../use-lavish/ROUND-PASS.md), and answer each note by the answer rules of `/afkv2:use-lavish`. Write the result to a JSON file and apply it:

   ```sh step=apply-readings
   <python> "<this skill's folder>/../use-lavish/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

   The keys of the readings file: [../grill-requirements/SKILL.md](../grill-requirements/SKILL.md), step 7. A `signoff` card settles only by a `sign` mark, so return it with `open`. A settled-round card never changes: a point in `returned`, and an asking card still open or blocked at the end of the round, gets one new card with `carries` in the next round. A steer binds every later decision. Write a human line `take over` as an `Escape` row, by [../grill-requirements/ROUNDS.md](../grill-requirements/ROUNDS.md).

8. **Save the state.** Copy the notes of this round into the log, word for word. Update each `Premise` row that changed. Real work outside this ticket gets a `Spinoff` row. Go to step 3. Done when the log matches this round.

   ```sh step=sync
   <python> "<this skill's folder>/scripts/design_files.py" sync --doc "<doc>" --log "<log>"
   ```

9. **Write the design.** Write `sdd` by [SDD-FORMAT.md](SDD-FORMAT.md) and the records by [ADR-FORMAT.md](ADR-FORMAT.md), into `adr_dir`. The page document and the input of step 2 are your whole source; ask no new question. A point you cannot write is one more round: go to step 4. Done when each settled point stands in the SDD or a record, and each settled fork names its card id there.

10. **Run the design gate.** First confirm each judgment check in [DRAFT.md](DRAFT.md). Done when the answer is ok.

    ```sh step=gate
    <python> "<this skill's folder>/scripts/design_files.py" gate --doc "<doc>" --spec-dir "<spec dir>"
    ```

    It lists every failure in `error.failures`. Each failure is one more round or one change to the design files. On a pass it writes the gate row and the `SDD` and `Design ADRs` rows of `INDEX.md`; `index_missing` true means the spec folder has no `INDEX.md`, so tell the human to run `/afkv2:to-prd`.

11. **Finish.** End the page session, so the page says that the session ended and stops showing 'Working...':

   ```sh step=end
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" end --doc "<doc>"
   ```

   Run the check in the guide's "Freestyle is the marked escape" section and report candidate components. Commit the spec folder on the feature branch. Tell the human the next skill is `/afkv2:to-subtasks`. Done when the gate answered ok and the commit exists.

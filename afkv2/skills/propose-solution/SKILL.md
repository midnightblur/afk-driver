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
| `GRILL-LOG.md` with a passed exit gate, and the page documents | written by `/afkv2:grill` | stop and name them and `/afkv2:grill` |
| `PRD.md` and the requirement ADRs | written by `/afkv2:to-prd` | stop and name the file and `/afkv2:to-prd` |

Read only what is on disk, and the code. A later session continues from the page document and `GRILL-LOG.md` alone. A requirement the PRD left out is a gap of the grill: name it, and send the human to `/afkv2:grill`.

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. On a refusal, fix what `reason` names and run the command again; when no fix exists, stop and report it.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/design_files.py" start --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. The answer holds `spec_dir`, `prd`, `log`, `requirement_adrs`, `sdd`, `sdd_exists`, `adr_dir`, `doc`, `session`, `resume`, `raw_file` and `raw_pending`. `unverified_external` lists what the grill could not verify. `resume` true: read `doc`, honour every steer in it, and continue at step 3. `raw_pending` true: an answer waits in `raw_file`, so go to step 7. `sdd_exists` true: this session changes a design, so read `sdd` and `adr_dir`, and let each card state what the SDD holds and what the change is.

2. **Read the input and the code.** Read `prd`, `requirement_adrs`, `log` and the grill documents in `<spec_dir>/pages/`. Read the repository glossary and `STAPLES.md`, when they exist; a staple the PRD accepted is a design input. Start the code reading in background subagents. Write one row per load-bearing premise ([DRAFT.md](DRAFT.md) "Premises"). Done when each critical aspect and each layer has the facts its picture and its card need.

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
   | `draft` | step 4 with [DRAFT.md](DRAFT.md): propose `layers_to_ask` from the top down, and return each of `layers_open` and `locked_open` |
   | `write` | step 9 |

4. **Work one round.** Load the page guide `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)). Verify premises, weigh the options, and take every decision the rules allow ([DRAFT.md](DRAFT.md) "Cards"). Then write the round input, a JSON file in a scratch folder: `banner`, `items`, and `maps` and `replies` when they change. The build draws the maps of the aspects, the layers and the human-locked set; `maps` holds only your own. You never write page HTML. Done when every item carries a decision, or names why you could not take it.

   An item has the page document fields, plus these fields of the input only:

   | Field | Effect |
   |-------|--------|
   | `aspect: "<key>"` | the card asks that critical aspect. It is a `confirm` card or a fork. The body root must be a picture of the current state, with the question in its `children`. The build refuses any other shape, and any order but the fixed one. |
   | `layer: "<L1..L9>"` | the card belongs to that layer. The build refuses it until every aspect is settled, and refuses a layer before the ones above it. |
   | `locked: "<HL-n>"` | the `signoff` card of that human-locked aspect. |
   | `fork: {question, options, why_open, recommended, picture}` | the build writes a `debate` card with the options side by side. A `debate` card has no other form. |
   | `decided`, `carries` | as in [../grill/SKILL.md](../grill/SKILL.md), step 4. |

   Before the first draft round, offer the draft to the second-provider slot. It is off in this version, and answers no forks. Add each entry of `forks` to the round as a fork card.

   ```sh step=second-provider
   <python> "<this skill's folder>/scripts/second_provider.py" review --draft "<round input>"
   ```

5. **Build and show the round.** Done when `present` answers ok.

   ```sh step=build
   <python> "<this skill's folder>/scripts/design_round.py" build --doc "<doc>" --session "<session>" --ticket "<ticket key>" --round-input "<round input>"
   ```

   ```sh step=present
   <python> "<this skill's folder>/../grill/scripts/page_round.py" present --doc "<doc>"
   ```

   `present` runs check, render and show. A refusal holds the failed `verb`. On `check` or `render`, the human has not seen this round: fix the named field in the round input, then run `build` again with `--replace`, which rewrites the current round when it has no answer. On `show`, the page host is not available: print the round as Markdown in chat, with every card id, take the human's reply as the raw response, write it to `raw_file`, and go to step 7 (the raw response form of this path is not verified until the page engine merges).

6. **Wait for the answer.** The answer reaches you with no chat message from the human.

   **On Claude**, run this command as a background command the harness tracks. Its exit tells you the answer is in `raw_file`. Do other work or end your response until then.

   ```sh step=wait
   <python> "<this skill's folder>/../grill/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

   **On Codex**, leave that command out. End your turn after `present`. The Stop hook waits for the answer and hands the raw response back as your next prompt. Write that text to `raw_file`, word for word. When the hook cannot wait, the human sends one chat message after Send: run `wait` then. Live check, run by the owner: [CODEX-LIVE-CHECK.md](CODEX-LIVE-CHECK.md).

7. **Read the answer.** Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/../grill/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   The engine settles a lone mark, and sends every other signal to `needs_reading`. The answer lists `needs_reading`, `returned`, `steers`, `blocked` and the raw `signals`. Read each card by the round pass in [../visualize/components/card.md](../visualize/components/card.md), and each note by [../visualize/components/notes-and-replies.md](../visualize/components/notes-and-replies.md). Write the result to a JSON file and apply it:

   ```sh step=apply-readings
   <python> "<this skill's folder>/../grill/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

   The keys of the readings file: [../grill/SKILL.md](../grill/SKILL.md), step 7. A settled-round card never changes: a point in `returned`, and an asking card still open or blocked at the end of the round, gets one new card with `carries` in the next round. A steer binds every later decision. Write a human line `take over` as an `Escape` row, by [../grill/ROUNDS.md](../grill/ROUNDS.md).

8. **Save the state.** Update each `Premise` row that changed. Real work outside this ticket gets a `Spinoff` row. Go to step 3. Done when the log matches this round.

9. **Write the design.** Write `sdd` by [SDD-FORMAT.md](SDD-FORMAT.md) and the records by [ADR-FORMAT.md](ADR-FORMAT.md), into `adr_dir`. The page document and the input of step 2 are your whole source; ask no new question. A point you cannot write is one more round: go to step 4. Done when each settled point stands in the SDD or a record, and each settled fork names its card id there.

10. **Run the design gate.** First confirm each judgment check in [DRAFT.md](DRAFT.md). Done when the answer is ok.

    ```sh step=gate
    <python> "<this skill's folder>/scripts/design_files.py" gate --doc "<doc>" --spec-dir "<spec dir>"
    ```

    It lists every failure in `error.failures`. Each failure is one more round or one change to the design files. On a pass it writes the gate row and the `SDD` and `Design ADRs` rows of `INDEX.md`; `index_missing` true means the spec folder has no `INDEX.md`, so tell the human to run `/afkv2:to-prd`.

11. **Finish.** Run the check in the guide's "Freestyle is the marked escape" section and report candidate components. Commit the spec folder on the feature branch. Tell the human the next skill is `/afkv2:to-subtasks`. Done when the gate answered ok and the commit exists.

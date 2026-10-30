---
name: grill
description: /afkv2:grill — grills a ticket into settled requirements. Reads the ticket with its comments and links, takes an optional round 0, runs requirement rounds on the page, keeps the claim ledger, and ends at the exit gate. Writes GRILL-LOG.md, the page document and glossary terms. Use to start the requirements of a ticket or to resume a grill.
---

# /afkv2:grill

The team works first. Each round shows the human the whole picture at once: what the agent decided, what only the human can call, and why. The grill ends at the exit gate, when every point is settled.

## Input

| Value | Source | When it is missing |
|-------|--------|--------------------|
| ticket key | the invocation | stop and name it |
| `.afkv2/config.json`, with a tracker kind | written by `/afkv2:setup` | stop and name the file and `/afkv2:setup` |

Read only what is on disk and in the tracker. A later session continues from `GRILL-LOG.md` and the page document alone.

## The commands

Run each command from the repository root. `<python>` is the Python in the setup install record (line `python`). Every answer is one JSON object: `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}`; exit 0 is ok, 1 is refused, 2 is unreadable input. On a refusal, fix what `reason` names and run the command again; when no fix exists, stop and report it.

## Steps

1. **Start.** Done when the answer is ok.

   ```sh step=start
   <python> "<this skill's folder>/scripts/grill_start.py" --ticket "<ticket key>"
   ```

   `missing-input`: stop and show `missing` and `writer`. The answer holds `doc`, `log`, `session`, `raw_file` and `resume`. `resume` true: run step 2 again, read the section `## Requirements grill` of `log` and the `doc`, honour every `Steer` row and an `Escape` row, and continue at the first unfinished step of the current round, or at step 3 when `doc` does not exist yet. `raw_pending` true: an answer waits in `raw_file`, so go to step 7.

2. **Read the ticket.** Done when the file holds the ticket, every comment and every link you can read.

   ```sh step=read-ticket
   <python> "<this skill's folder>/scripts/read_ticket.py" --ticket "<ticket key>" --out "<ticket file>"
   ```

   Keep `<ticket file>` in a scratch folder. Report `comments_cut` and each `unread_links` entry to the human in round 1; the ticket card shows them. Read the context the ticket points at: a linked document, a named file. Read the repository glossary and `STAPLES.md`, when they exist.

3. **Offer round 0.** Ask once in chat: the human may write their own reading of the ticket, or skip. Start the code reading in background subagents at the same time, so the work overlaps the wait. A human reading is unverified input: every claim in it gets a `Ledger` row. Save the words exactly:

   ```sh step=row
   <python> "<this skill's folder>/scripts/grill_log.py" row --log "<log>" --kind "<kind>" --text "<text>"
   ```

   Use `--text-file <file>` in place of `--text` for text with quotes or line breaks. Row kinds and grammar: [GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md). Skipped: write no row. Done when the human answered and the claims are in the ledger.

4. **Work one round.** Load [ROUNDS.md](ROUNDS.md) and the page guide `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)). Verify claims, weigh the options, take every decision the rules allow, and write the `Ledger` rows as they change. Then write the round input, a JSON file in a scratch folder: `banner`, `items`, and `maps` and `replies` when they change. You never write page HTML. Done when every item carries a decision, or names why you could not take it.

   An item has the page document fields, plus 2 fields of the input only:

   | Field | Effect |
   |-------|--------|
   | `critical: true` | the card asks a critical-aspect question: how an existing code area, data set or flow must change. The body root must be a picture of the current state, with the question in its `children`. The build refuses any other shape. |
   | `decided: {decision, alternatives, evidence, grade, why, reverse, depends_on}` | on a `decided` card, the build writes these fields into the body. A gap makes it a `confirm` card and the answer lists it in `degraded`. |

5. **Build and show the round.** Done when `present` answers ok.

   ```sh step=build
   <python> "<this skill's folder>/scripts/round_document.py" build --doc "<doc>" --session "<session>" --ticket "<ticket key>" --round-input "<round input>" --ticket-file "<ticket file>"
   ```

   ```sh step=present
   <python> "<this skill's folder>/scripts/page_round.py" present --doc "<doc>"
   ```

   `present` runs check, render and show. A refusal holds the failed `verb`. On `check`, fix the named field. On `show`, the page host is not available: print the round as Markdown in chat, with every card id, take the human's reply as the raw response, write it to `raw_file`, and go to step 7 (the raw response form of this path is not verified until the page engine merges).

6. **Wait for the answer.** The answer reaches you with no chat message from the human.

   **On Claude**, run this command as a background command the harness tracks. Its exit tells you the answer is in `raw_file`. Do other work or end your response until then.

   ```sh step=wait
   <python> "<this skill's folder>/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

   **On Codex**, leave that command out. End your turn after `present`. The Stop hook waits for the answer and hands the raw response back as your next prompt. Write that text to `raw_file`, word for word. When the hook cannot wait, the human sends one chat message after Send: run `wait` then. Live check, run by the owner: [CODEX-LIVE-CHECK.md](CODEX-LIVE-CHECK.md).

7. **Read the answer.** Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   The engine settles a lone mark, and sends every other signal to `needs_reading`. The answer lists `needs_reading`, `returned`, `steers`, `blocked` and the raw `signals`. Read each card by the round pass in [../visualize/components/card.md](../visualize/components/card.md), and each note by [../visualize/components/notes-and-replies.md](../visualize/components/notes-and-replies.md). Write the result to a JSON file and apply it:

   ```sh step=apply-readings
   <python> "<this skill's folder>/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

   | Key | Entry | Use |
   |-----|-------|-----|
   | `settle` | `{item, note, reading}` | a clear note settles the point; the reply with your reading is written for you |
   | `open` | `{item, reply}` | the signals are unclear or in conflict, or the note is on an `info` card |
   | `unblock` | item id | the point it waited on settled |
   | `replies` | `{text, about}` | every other note: a steer word for word, an answer |

   A settled-round card never changes: a point in `returned` gets one new card in the next round. A human line `take over` is the escape: [ROUNDS.md](ROUNDS.md).

8. **Save the state.** Done when the log holds this round's settled rows and owner notes, and each resolved term is in the glossary.

   ```sh step=sync
   <python> "<this skill's folder>/scripts/grill_log.py" sync --doc "<doc>" --log "<log>"
   ```

   Write each term the human verified in this round. The glossary is the one `GLOSSARY-MAP.md` names for this area, else `GLOSSARY.md` at the repository root. Use `--pending` in place of `--glossary` and `--definition` for a candidate term that waits on a round.

   ```sh step=term
   <python> "<this skill's folder>/scripts/grill_log.py" term --log "<log>" --glossary "<glossary>" --term "<term>" --definition "<definition>"
   ```

9. **Next round, or the exit gate.** Points remain: go to step 4. The tree looks exhausted: run the devil's-advocate pass ([ROUNDS.md](ROUNDS.md)), then bring its findings as the last round. Then confirm the judgment checks in [GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md) "Exit gate" and run the mechanical check:

   ```sh step=gate
   <python> "<this skill's folder>/scripts/grill_log.py" gate --doc "<doc>" --log "<log>"
   ```

   It lists every failure in `error.failures`. Each failure is one more round or one more row.

10. **Finish.** Run the check in the guide's "Freestyle is the marked escape" section and report candidate components. Commit the spec folder and the glossary on the feature branch. Tell the human the next skill is `/afkv2:to-prd`. Done when the gate answered ok and the commit exists.

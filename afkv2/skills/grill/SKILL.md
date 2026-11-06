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

   `missing-input`: stop and show `missing` and `writer`. The answer holds `doc`, `log`, `session`, `raw_file`, `resume` and `takeover`.

   `resume` true: take the page over by `/afkv2:use-lavish` "Take over a page" ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)), with the `Takeover` row of step 3. Run step 2 again, read the section `## Requirements grill` of `log` and the `doc`, honour every `Steer` row and an `Escape` row, and continue at the first unfinished step of the current round, or at step 3 when `doc` does not exist yet.

   `takeover` holds a session: the grill of this ticket ended, and this call comes back to it with new input. Take the page over by `/afkv2:use-lavish` "Take over a page", with the `Takeover` row, read `log` and `doc`, and run steps 2 and 3, so round 0 takes the new input. The rounds that follow: [ROUNDS.md](ROUNDS.md) "Coming back".

   On a resume and on a take-over, a page whose `schema` is `afkv2.page/0` or `afkv2.page/1` was made before the session's lists. The first round input builds `sections` from its settled points, each with a change line of cause `finding` that says it was built from the settled points, and holds `upgrade: true`.

   `raw_pending` true: an answer waits in `raw_file`, so go to step 7.

2. **Read the ticket.** Done when the file holds the ticket, every comment and every link you can read.

   ```sh step=read-ticket
   <python> "<this skill's folder>/scripts/read_ticket.py" --ticket "<ticket key>" --out "<ticket file>"
   ```

   Keep `<ticket file>` in a scratch folder. Report `comments_cut` and each `unread_links` entry to the human in round 1; the ticket card shows them. Read the context the ticket points at: a linked document, a named file. Read the repository glossary and `STAPLES.md`, when they exist.

3. **Offer round 0.** Ask once in chat: the human may write their own reading of the ticket, or skip. Start the code reading in background subagents at the same time, so the work overlaps the wait. A human reading is unverified input: every claim in it gets a `Ledger` row. Save the words exactly:

   ```sh step=row
   <python> "<this skill's folder>/scripts/grill_log.py" row --log "<log>" --kind "<kind>" --text "<text>"
   ```

   Use `--text-file <file>` in place of `--text` for text with quotes or line breaks. Row kinds and grammar: [GRILL-LOG-FORMAT.md](GRILL-LOG-FORMAT.md). A `Round 0` row holds 1 text, and `row` replaces it. After a take-over, write its old words first, then a blank line and the new input. Skipped: write no row. Done when the human answered and the claims are in the ledger.

4. **Work one round.** Load [ROUNDS.md](ROUNDS.md), the page and answer rules of `/afkv2:use-lavish` ([../use-lavish/SKILL.md](../use-lavish/SKILL.md)), and the page guide `/afkv2:visualize` ([../visualize/SKILL.md](../visualize/SKILL.md)). Verify claims, weigh the options, take every decision the rules allow, and write the `Ledger` rows as they change. Then write the round input, a JSON file in a scratch folder: `banner`, `items`, and `maps` and `replies` when they change, and the entries of the session's lists that changed ([ROUNDS.md](ROUNDS.md) "The session's content"). You never write page HTML. Done when every item carries a decision, or names why you could not take it.

   An item has the page document fields, plus 3 fields of the input only:

   | Field | Effect |
   |-------|--------|
   | `critical: true` | the card asks a critical-aspect question: how an existing code area, data set or flow must change. The body root must be a picture of the current state, with the question in its `children`. The build refuses any other shape. |
   | `decided: {decision, alternatives, evidence, grade, why, reverse, depends_on}` | on a `decided` card, the build writes these fields into the body as labelled blocks (`card` page). A gap makes it a `confirm` card and the answer lists it in `degraded`. |
   | `carries: [<old card id>]` | this new card asks a returning point again. The build writes it into the card's `carries` field; each id must be a card of an earlier round. The page shows the old cards in the new card's history. Every point the round pass returns needs one such card; the build refuses the next round without it. A mention in other text or in `depends_on` carries nothing. |

5. **Build and show the round.** Done when `present` answers ok.

   ```sh step=build
   <python> "<this skill's folder>/../use-lavish/scripts/round_document.py" build --doc "<doc>" --session "<session>" --ticket "<ticket key>" --round-input "<round input>" --ticket-file "<ticket file>"
   ```

   `build` also writes `session.links`, so the page links each ticket, change and commit reference. It takes the templates from the config, the `origin` remote and the Jira base URL of the tracker port (`../use-lavish/scripts/page_links.py`), and leaves out a kind it cannot find.

   ```sh step=present
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" present --doc "<doc>" --scan "<log>"
   ```

   `present` runs check, render and show, and scans the page and the log for secrets. Report its notices by `/afkv2:use-lavish` "After each show". A refusal holds the failed `verb`. On `check` or `render`, the human has not seen this round: fix the named field in the round input, then run `build` again with `--replace`. It works only on a round that `present` did not try to show. A shown round with no answer refuses `round-shown`, because the human may be answering it in the browser: wait for the answer. On `show`, the page host is not available: run the round in chat by [ROUNDS.md](ROUNDS.md) "Without a page".

6. **Wait for the answer.** The human picks a mark on each card, writes each note as a lavish annotation, and sends both with Send to Agent in the lavish panel. The answer reaches you with no chat message from the human. The engine keeps each round send beside `doc` until ingest. After a wait or a session that stopped, run the wait again: a kept send answers at once. An ingest that refuses the answer moves the kept send to the file its error names; the next wait reads the page.

   **On Claude**, run this command as a background command the harness tracks. Its exit tells you the answer is in `raw_file`. The host's prompts, from which the engine built that text, are in `<raw file>.prompts.json`. Do other work or end your response until then.

   ```sh step=wait
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" wait --doc "<doc>" --raw-file "<raw file>"
   ```

   **On Codex**, leave that command out. End your turn after `present`. The Stop hook waits for the answer and hands the raw response back as your next prompt. Write that text to `raw_file`, word for word. When the hook cannot wait, the human sends one chat message after Send to Agent: run `wait` then. Live check, run by the owner: [CODEX-LIVE-CHECK.md](CODEX-LIVE-CHECK.md).

   **Side questions.** The page's btw? button sends only its question, at once, to the wait (or the Stop hook). The wait asks it in your terminal pane, and the page shows the answer. The marks the human queued stay queued. A side question does not wake you. When the `wait` answer lists questions in `btw`, no terminal pane could take them: write one short Markdown answer for each to `<reply file>`, show it, and keep the round open. Then go to step 7 if `raw_file` holds a path, else run `wait` again.

   ```sh step=reply
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" reply --doc "<doc>" --reply-file "<reply file>"
   ```

7. **Read the answer.** Done when `needs_reading` is empty and every note has a reply.

   ```sh step=ingest
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" ingest --doc "<doc>" --raw-file "<raw file>"
   ```

   The engine settles a lone mark, and sends every other signal to `needs_reading`. The answer lists `needs_reading`, `returned`, `steers`, `blocked` and the raw `signals`. Read each card and each note by the round pass in [../use-lavish/ROUND-PASS.md](../use-lavish/ROUND-PASS.md), and reply to each note by the answer rules of `/afkv2:use-lavish`. Write the result to a JSON file and apply it:

   ```sh step=apply-readings
   <python> "<this skill's folder>/../use-lavish/scripts/round_document.py" apply-readings --doc "<doc>" --readings "<readings>"
   ```

   | Key | Entry | Use |
   |-----|-------|-----|
   | `settle` | `{item, note, reading, changed}` | a clear note settles the point; the reply with your reading is written for you. A `signoff` card refuses `signoff-needs-mark`: only a `sign` mark settles it |
   | `open` | `{item, reply, changed}` | the signals are unclear or in conflict, or the note is on an `info` or `signoff` card |
   | `unblock` | item id | the point it waited on settled |
   | `replies` | `{text, notes, changed}` | every other note, a steer included: an answer. `notes` lists each note id it answers |

   `changed` is optional: the ids of the elements the answer changed. An id that names nothing refuses `bad-link`.

   A settled-round card never changes: a point in `returned`, and an asking card still open or blocked at the end of the round, gets one new card with `carries` in the next round. A human line `take over` is the escape: [ROUNDS.md](ROUNDS.md).

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

   It lists every failure in `error.failures`. Each failure is one more round or one more row. On a pass after a take-over, the answer adds `stale` and `changed`: tell the developer both by [ROUNDS.md](ROUNDS.md) "Coming back".

10. **Finish.** End the page session, so the page says that the session ended and stops showing 'Working...':

   ```sh step=end
   <python> "<this skill's folder>/../use-lavish/scripts/page_round.py" end --doc "<doc>"
   ```

   Run the check in the guide's "Freestyle is the marked escape" section and report candidate components. Commit the spec folder and the glossary on the feature branch. Tell the human the next skill is `/afkv2:to-prd`. Done when the gate answered ok and the commit exists.

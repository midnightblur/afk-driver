# Codex live check of the grill

The owner runs this check (plan decision D-S-8). It needs afkv2 enabled in the global Codex config, the page engine, and the tracker port merged.

1. In a repository with `.afkv2/config.json`, open a Codex session and run `/afkv2:grill-requirements <ticket key>`. Skip round 0.
2. Expected: the agent shows round 1 and ends its turn. It runs no `use-lavish/scripts/page_round.py wait`.
3. Mark one card with accept. Annotate a second card with one clear note. Click Send to Agent in the lavish panel. Send no chat message.
4. Expected: the agent starts a new turn by itself and runs `use-lavish/scripts/page_round.py ingest`.
5. Expected in the page document: the first card is `settled_by_mark`, the second is `settled_by_note` with a reading, and the round reply states that reading.
6. Expected in `GRILL-LOG.md`: both `Settled` rows, and the note word for word.
7. Repeat steps 2 to 4, and wait 10 minutes before Send.

A failure at step 4 means the fallback in the skill's step 6, one chat message after Send. Report it to the owner of the plan.

## Side question on Codex

Run Codex in a herdr pane. The Stop hook types `/side <question>` into that pane and reads no answer yet.

1. Show a round as in steps 1 and 2. On the page, click btw?, type one question, and click Ask.
2. Expected: the Codex pane shows `/side <question>` typed and submitted while the Stop hook waits, and a side chat opens. The page shows "Asked in the Codex side chat. Read the answer in the terminal." The agent starts no new turn.
3. Record with `herdr pane read <pane>`: the line that shows the question, the answer lines, the line that marks the end of the answer, and the key that closes the side chat.
4. Give the record to the owner of the plan. The answer is read only after its markers are in `HARNESSES["codex"]` of `engine/side_question.py` (plugin root).

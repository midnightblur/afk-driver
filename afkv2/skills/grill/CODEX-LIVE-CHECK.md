# Codex live check of the grill

The owner runs this check (plan decision D-S-8). It needs afkv2 enabled in the global Codex config, the page engine, and the tracker port merged.

1. In a repository with `.afkv2/config.json`, open a Codex session and run `/afkv2:grill <ticket key>`. Skip round 0.
2. Expected: the agent shows round 1 and ends its turn. It runs no `page_round.py wait`.
3. Mark one card with accept. On a second card, write one clear note. Send the round. Send no chat message.
4. Expected: the agent starts a new turn by itself and runs `page_round.py ingest`.
5. Expected in the page document: the first card is `settled_by_mark`, the second is `settled_by_note` with a reading, and the round reply states that reading.
6. Expected in `GRILL-LOG.md`: both `Settled` rows, and the note word for word.
7. Repeat steps 2 to 4, and wait 10 minutes before Send.

A failure at step 4 means the fallback in the skill's step 6, one chat message after Send. Report it to the owner of the plan.

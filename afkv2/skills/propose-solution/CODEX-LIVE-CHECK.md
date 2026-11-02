# Codex live check of propose-solution

The owner runs this check (plan decision D-S-8). It needs afkv2 enabled in the global Codex config, the page engine merged, and a spec folder with `PRD.md` and a grill log with a passed gate.

1. In that repository, open a Codex session and run `/afkv2:propose-solution <ticket key>`.
2. Expected: the agent shows round 1, with a picture above the first question, and ends its turn. It runs no `page_round.py wait`.
3. Mark one fork card with an option. On a second card, write one clear note. Send the round. Send no chat message.
4. Expected: the agent starts a new turn by itself and runs `page_round.py ingest`.
5. Expected in `pages/propose-solution-<session id>.json`: the fork card is `settled_by_mark`, the second card is `settled_by_note` with a reading, and the round reply states that reading.

A failure at step 4 means the fallback in the skill's step 6, one chat message after Send. Report it to the owner of the plan.

# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — component type names and props in the guide before the registry exists
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — the guide names registry types and props now, and the S1 registry schema replaces them when it merges vs B — the guide waits for the S1 registry
- Chosen: A — SDD §4 fixes the component fields (`type`, `id`, `props`, `style`, `children`, `html`) but leaves props to "the type's own schema", which S1 0003/0004 write; the PLAN.md cross-session rule says to build against the frozen contract until the producer merges. Names: `map`, `graph`, `table`, `sequence`, `run-strip`, `chip`, `text`, `freestyle`; each entry of the document `maps` list is a `map` component; map node `state` is `open`, `settled` or `focus`; banner fields `settled`, `unlocks`, `parked` (lists of text); freestyle takes `props.reason`. The test runs `engine check` on every example once the S1 engine exists, so a name the registry does not know shows as a red test, not as silent drift.
- Supersedes: none
- To reverse: rename the types and props in `afkv2/skills/visualize/**` and the fake validator in `afkv2/tests/skills/test_visualize.py` to the S1 registry names

## D-2 — one component page per component, no PRD ids in the guide
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — SKILL.md spine plus one page per component under `components/` vs B — one large file with every entry
- Chosen: A — the owner's V-7 note settles the guide as "SKILL.md + component pages", and an author loads only the pages it uses. The pages name components by name; the PRD catalog ids live only in the test, because an agent that reads the guide does not read the PRD, and the plugin genericity gate reads `CMP-<n>` as a ticket id.
- Supersedes: none
- To reverse: merge the pages into one file; the test reads the entry headings

## D-3 — an option of a debate card is a table column
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — the guide shows debate options side by side as table columns with component ids `<item id>-opt-<letter>` vs B — invent an `options` item field
- Chosen: A — SDD §4 item fields have no options field (signed HL-1, so B would change a signed schema); a table is the component that holds things side by side. How the page offers the option mark is the engine's (S1 0003).
- Supersedes: none
- To reverse: change the debate example in `components/card.md` when the S1 card renderer names its option form

## D-4 — an unsettled point moves to the next round as a new card
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f004)
- Options: A — a new card with a new id in the next round, whose body names the old card id vs B — the old card stays answerable in its settled round
- Chosen: A — SDD §6 says "a settled round is never rewritten" and SDD §4 says an item id is "never reused", so only a new card keeps both rules; B would change a settled round when the point settles later.
- Supersedes: none
- To reverse: change `components/card.md` when the S1 engine defines how a round chip marks a carried point

## D-5 — the carry rule covers every round and only cards that ask the human
- 2026-10-30 · decided by execute (0006-visualize-skill, review findings 0006-visualize-skill/f016, f028, f029)
- Options: A — carry each asking card (`decided`, `confirm`, `debate`, `signoff`) still `open` or `blocked` in any round, once, and leave `info` cards in their round vs B — carry only the sent round's points, all kinds
- Chosen: A — SDD §6 moves a settled card to `open` on a note or a `reopen` mark in any round, and PRD WE-02 requires the card to return with both signals shown; B would strand those cards and would copy every `info` card into every later round, because an `info` card never leaves `open`. This refines D-4, which still holds for the new card and the new id
- Supersedes: none
- To reverse: change `components/card.md` when the S1 engine defines how it returns a card

## D-6 — the agent never changes a card in a settled round
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f032)
- Options: A — the agent changes only cards of the current round, and a signal on an older card returns as one new card in the next round vs B — the agent also sets `state` on the older card
- Chosen: A — SDD §6 refuses a document that rewrites a settled round and says the reopen "is recorded in the next round"; B breaks that signed rule. Whether ingest itself marks the older card is not verified, because the S1 engine is not on this branch. This corrects the part of D-5 that spoke of a card returned "in any round" as a card the pass changes
- Supersedes: D-5, only for writes into a settled round
- To reverse: change `components/card.md` when the S1 engine defines how it records a reopen on an older card

## D-7 — a write-in reads like a note, with signal `write-in`
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f043)
- Options: A — the agent reads a write-in as it reads a note and settles by note with signal `write-in` vs B — a write-in always returns the point to `open`
- Chosen: A — SDD §6 sends a write-in to needs-reading, so an agent must read it, and B would return a clear answer forever. SDD §4 gives no field for how a write-in is stored, so the `signal` value is this guide's until the S1 engine names it
- Supersedes: none
- To reverse: change `components/card.md` and the `WRITE_IN` value in the test when the S1 engine names the signal

## D-8 — 2 conflicting steers on one node go to the human
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f036)
- Options: A — the agent states the conflict and asks vs B — the newer steer replaces the older one
- Chosen: A — the glossary makes a steer a standing rule until the session ends; B would narrow that rule with no source, and A adds no new rule
- Supersedes: none
- To reverse: edit `components/notes-and-replies.md` and the glossary entry

## D-9 — a write-in returns as a `confirm` card
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f045)
- Options: A — a write-in returns the point to `open`, and the new card is a `confirm` card that states it as the agent's reading, which a lone accept mark settles vs B — settle by note with signal `write-in` (D-7) vs C — park the fork
- Chosen: A — SDD §6 says "settled-by-note has a note id and a reading", and a write-in has no note id, so B breaks a signed rule. A stays inside the signed state rules and the point still settles in the next round, so no decision is needed from the human. D-7 was wrong on this point
- Supersedes: D-7
- To reverse: change `components/card.md` when the S1 engine defines how it stores a write-in

## D-10 — 0009 and 0010 may write the shared test fakes and fixtures
- 2026-10-30 · decided by the plan author (slicing defect fix, sent to this session mid-run)
- Options: A — add `afkv2/tests/skills/fakes/*` and `afkv2/tests/skills/fixtures/**` to `## Scope` of 0009 and 0010 vs B — keep the Scope, and each integration row cannot write the fixture PRD, SDD, engine fakes and fake page mark it needs
- Chosen: A — the integration rows of 0009 and 0010 need those files. 0007 and 0008 already list `fakes/*` and run first in this session, so these are sequential edits, not 2 writers at the same time. The plan check is clean after the edit
- Supersedes: none
- To reverse: remove the 2 paths from `## Scope` of 0009 and 0010

## D-11 — a `signoff` card settles only by a `sign` mark; an `info` card never settles
- 2026-10-30 · decided by execute (0006-visualize-skill, review findings 0006-visualize-skill/f052, f053)
- Options: A — only `decided`, `confirm` and `debate` cards settle by a clear note; a `signoff` card returns to `open` unless a lone `sign` mark settled it, and a note on an `info` card gets a reply only vs B — every kind settles by a clear note
- Chosen: A — a `signoff` card holds wording only a human may approve, so a note that asks for a change must not settle it (inferred from the card kind table; no spec line states it). An `info` card asks nothing, so nothing there can settle. A costs at most one more round
- Supersedes: none
- To reverse: edit the round pass in `components/card.md` and the rule test

## D-12 — no limit by card kind on a settle by note
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f056)
- Options: A — keep the signed state rule for every card kind, and state how to read a signal: a note that asks for a change is not clear, a `reopen` or `changes` mark always disagrees, and a note on an `info` card answers nothing vs B — limit a settle by note to some card kinds (D-11) vs C — park the limit for the human
- Chosen: A — SDD §6 says only "agent reads the note as clear" and is signed under HL-4, so B narrows a signed rule and needs the human. A only applies the signed words "clear" and "in conflict", so a `signoff` card with a `changes` mark still returns, and no decision is needed from the human
- Supersedes: D-11
- To reverse: edit the round pass in `components/card.md` and the rule test

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

## D-13 — a note that states a change in full can settle a point
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f061)
- Options: A — a note is not clear only when it leaves the answer open vs B — every note that asks for a change is not clear (part of D-12)
- Chosen: A — the signed rule says "agent reads the note as clear", and the design interview settled owner notes that stated a change (GRILL-LOG V-2, V-7), so B narrows it. The other parts of D-12 stay
- Supersedes: D-12, only for a note that asks for a change
- To reverse: edit the round pass in `components/card.md` and the rule test

## D-14 — a note that changes sign-off wording is not a clear note; the older-card point stays open
- 2026-10-30 · decided by execute (0006-visualize-skill, review findings 0006-visualize-skill/f066, f067)
- Options: A — a note that changes the wording of a `signoff` card returns as a new card with the new wording, and a note that affirms the wording can still settle vs B — every clear note settles a `signoff` card
- Chosen: A — the human has not signed the new wording, and the design record re-signed after a change (GRILL-LOG, sign-off rows), so the note leaves the answer open. This limits no card kind, so D-12 stands. The test-helper line in `.claude/wiring-ious.md` is dropped, because the wiring gate cannot close it. How ingest records a note on a card of a settled round stays open and not verified; plan-s1 0005 owns it (acceptance "A note on a settled item reopens it"), and `components/card.md` follows what that slice ships
- Supersedes: none
- To reverse: edit the round pass in `components/card.md` and `ROUND_PASS` in the test

## D-15 — correction of D-14: the sign-off rule touches a signed rule, and the call is open for the human
- 2026-10-30 · decided by execute (0006-visualize-skill, review finding 0006-visualize-skill/f070)
- Options: A — keep the conservative rule, correct the record, and report the call to the human vs B — remove the rule and let a note that changes sign-off wording settle
- Chosen: A — D-14 said "limits no card kind", which is wrong: the rule applies to `signoff` cards only, it narrows D-12 and D-13 for them, and it touches the signed state rule (HL-4). An agent cannot settle that. The rule stays until the human rules, because a wrong return costs one more round and a wrong settle records a signature the human did not give. The older-card follow-up now has a mechanism: `test_older_card_shape_is_replaced_once_ingest_merges` fails once plan-s1 0005 merges and names the `_note_on_an_older_card` fixture to replace
- Supersedes: D-14, only for its record
- To reverse: remove the `signoff` sentence from the round pass in `components/card.md` and `ROUND_PASS` in the test

## D-16 — the adversarial gate does not run here, and the slice stops
- 2026-10-30 · decided by execute (0006-visualize-skill)
- Options: A — stop with `adversary_unrun` vs B — spawn the gate with no URL vs C — adapt the gate to a document probe and report success
- Chosen: A — this repository has no live app and no build gate that can bring one up, and driven mode allows no waiver; only the human may rule that the gate does not apply. B can only answer "environment unreachable", and C is a waiver under another name. Dependents of this slice wait for the human's ruling
- Supersedes: none
- To reverse: the human rules that the gate does not apply to this plan; the row then goes to `done`

## D-17 — owner ruling R-1: skip the adversarial gate for afkv2
- 2026-10-30 · decided by the owner (brief, section "Owner rulings")
- Options: A — skip execute Step 10.5 for every afkv2 slice vs B — every slice stops with the gate owed
- Chosen: A — owner: "Skip for afkv2". There is no running app to attack. Each slice writes `adversary: skipped (owner ruling R-1)` in the journal
- Supersedes: execute Step 10.5 "Mandatory in driven mode"; D-16 "the slice stops"
- To reverse: the owner withdraws R-1

## D-18 — owner ruling R-2: at most 3 review rounds, fix only critical and high
- 2026-10-30 · decided by the owner (brief, section "Owner rulings")
- Options: A — at most 3 rounds per slice, and only critical and high findings get a fix vs B — the settle loop with its 10-round cap
- Chosen: A — medium and low findings stay on the PR as advisory, with no fix and no dispute round. After round 3, an open critical or high finding parks the slice; otherwise the gate passes. For 0006 this passes the gate: findings f074 to f078 are medium or low, as the executor reported
- Supersedes: `skills/afk/review/SETTLEMENT.md` 10-round settle loop, for this build
- To reverse: the owner withdraws R-2

## D-19 — owner ruling R-3: a note that changes sign-off wording needs a sign mark
- 2026-10-30 · decided by the owner (brief, section "Owner rulings")
- Options: A — the card goes back for a `sign` mark vs B — the note settles the card
- Chosen: A — the owner chose this. `afkv2/skills/visualize/components/card.md` already states it, so no code changes. This closes the open call in D-15 and finding f074
- Supersedes: D-15, only its open call
- To reverse: edit `components/card.md` and the test that pins the rule

## D-20 — owner ruling R-4: pre-commit gate skip accepted for afkv2
- 2026-10-30 · decided by the owner (brief, section "Owner rulings")
- Options: A — `AFK_SKIP_PRECOMMIT_GATES=1` on any afkv2 commit vs B — skip only on the v1 layout friction
- Chosen: A — PR CI catches the rest, and the ship gate must be green. Skipped commits stay listed in the journal
- Supersedes: the brief's narrower rule on v1 friction
- To reverse: the owner withdraws R-4

## D-21 — the glossary Steer entry keeps the whole-session form and adds the map-node form
- 2026-10-30 · decided by execute (0006-visualize-skill, Step 12 glossary reconcile)
- Options: A — Steer covers a note on a map node or about the whole session vs B — Steer covers a note on a map node only
- Chosen: A — PRD AC-038 and ADR-0002 (requirements) define the map-node form, and `components/notes-and-replies.md` follows it; GRILL-LOG line 117 records a page-level steer, so B drops a form that the design record used. Whether the S1 engine stores a whole-session steer is not verified, because that engine is not on this branch
- Supersedes: none
- To reverse: edit the Steer entry in `afkv2/GLOSSARY.md`

## D-22 — round 0 happens in chat, not on the page
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — chat, with the words verbatim on a `Round 0` row of GRILL-LOG.md vs B — a page round numbered 0
- Chosen: A — the signed schema has round n ≥ 1 (SDD §4), and contract SK-07 says "optional round 0; requirement rounds on the page"
- Supersedes: none
- To reverse: add a round-0 page form to the schema and the build verb of `round_document.py`

## D-23 — engine call forms the SDD leaves open are assumed in one wrapper
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — one wrapper `page_round.py` assumes every verb takes the document path, `poll` answers `raw`, `render` answers `page`, `ingest DOC --raw-file FILE` vs B — the skill states engine commands directly
- Chosen: A — one file changes when S1 0003 to 0005 merge; the assumed forms are unverified until then
- Supersedes: none
- To reverse: change `_engine` calls in `page_round.py` and `fake_engine.py`

## D-24 — the spec folder of a ticket is the config spec folder plus the ticket slug
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — `<spec_folder>/<ticket slug>` with non-word characters replaced by `-` vs B — one flat spec folder for all tickets
- Chosen: A — GRILL-LOG.md and pages/ are per ticket, and B collides on the second ticket
- Supersedes: none
- To reverse: change `ticket_slug` and `start` in `grill_start.py`

## D-25 — the grill rules are rewritten in sibling files of the skill
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — `ROUNDS.md` and `GRILL-LOG-FORMAT.md` hold the rules, with the claim ledger verified by read-only `rg` subagents vs B — point at the v1 grill files
- Chosen: A — v1 is off when v2 runs (decision 46 drops the investigate ledger), and the owner steer keeps the round model, the card kinds, explicit marks, the ledger and the exit gate
- Supersedes: none
- To reverse: replace the sibling files with pointers

## D-26 — critical and decided are build input only
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — the builder enforces the picture rule and the six decided-card fields, then strips both fields vs B — add them to the document schema
- Chosen: A — the document stays schema afkv2.page/0, and the rule is deterministic at the one place cards are written
- Supersedes: none
- To reverse: add the fields to SDD §4 and keep them in `_item`

## D-27 — GitHub ticket links are text references plus a reverse search, capped at 20
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — references in body and comments, then `issue-search` for `"#N"`, with a cap of 20 links and the rest in `unread_links` vs B — references only
- Chosen: A — decision 63 asks for links, and GitHub has no link field; a live `gh issue list --search '"#153"'` returned issue 153, so whether the search finds mentions in other issues is unverified
- Supersedes: none
- To reverse: drop the search in `_github_links`

## D-28 — a sync writes rows from every grill document of the ticket
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — `sync` regenerates rows from all `pages/grill-*.json`, oldest session first vs B — only the current document, which drops the settled rows and owner notes of an older session from the log
- Chosen: A — keeps the row grammar and keeps every owner note on the log
- Supersedes: none
- To reverse: read one document in `sync`

## D-29 — a reopened older card stops returning when a later card names it
- 2026-10-30 · decided by execute (0007-grill-skill)
- Options: A — a card of a later round than the last note on the old card that names its id carries it vs B — add a carried marker to the document
- Chosen: A — a settled round is never rewritten and the schema has no marker; the older-card ingest shape is unverified until S1 0005 (D-14, D-15)
- Supersedes: none
- To reverse: read the engine's own field in `returning` once S1 0005 merges

## D-30 — a new card carries an old point only through an explicit carries field
- 2026-10-30 · decided by execute (0007-grill-skill, review round 1)
- Options: A — a build input field `carries`, written into the body as a `<card>-carries` text the checks read vs B — any mention of the old id in the body counts
- Chosen: A — B lets a card that only depends on an open point hide it, and the point then never returns; A still meets the guide's rule that the new card's body names the old id
- Supersedes: none
- To reverse: restore the body-wide search in `_carries_card`

## D-31 — a round the engine refused is corrected with build --replace
- 2026-10-30 · decided by execute (0007-grill-skill, review round 1)
- Options: A — an explicit `--replace` that rewrites a current round with no answer vs B — run the engine check on a temporary copy before the document is written
- Chosen: A — the check's handling of a path other than the session document is unverified until S1 merges, and A needs no engine call
- Supersedes: none
- To reverse: remove `_drop_unanswered_round` and check before the write

## D-32 — 0010 plan check gets 2 more refusals from SDD §7
- 2026-10-30 · decided by the plan author (plan update sent to this session mid-run; SDD §7 rows in commit 05ef43e8)
- Options: A — add 2 Acceptance bullets and 2 unit tests to 0010 vs B — leave 0010 as sliced, so the v1 defects repeat
- Chosen: A — SDD §7 assigns both rows to the 0010 plan-check test. The check refuses a gate the repository cannot run unless the plan names it not applicable, and refuses a check path that no Scope in the subtask's chain owns. Merged origin/feat/afkv2 at b3ae5fac first, by merge and not by rebase
- Supersedes: none
- To reverse: remove the 2 bullets and the addition to the unit row of 0010

## D-33 — the 0007 anchor becomes `name: grill`
- 2026-10-30 · decided by autopilot (orchestrator, plan check finding on the built 0007)
- Options: A — change the anchor in `## Produces` of 0007 and `## Consumes` of 0008 to `name: grill` vs B — remove one `/afkv2:grill` from the skill file
- Chosen: A — the plan check allows an anchor only if it greps once. The file has `/afkv2:grill` in both the description and the title, and both are correct. `name: grill` greps once and is the form 0010 uses
- Supersedes: the anchor text in 0007 and 0008
- To reverse: restore `/afkv2:grill` in both contracts

## D-34 — correction of D-33: the 0007 anchor is `description: /afkv2:grill`
- 2026-10-30 · decided by autopilot (orchestrator, plan check finding on D-33)
- Options: A — `description: /afkv2:grill` vs B — `name: grill`
- Chosen: A — the plan check refuses `name: grill` as shorter than 12 characters. I committed D-33 before I read the check result. The new anchor greps once, and the check is clean
- Supersedes: D-33, only its anchor text
- To reverse: restore `/afkv2:grill` in both contracts

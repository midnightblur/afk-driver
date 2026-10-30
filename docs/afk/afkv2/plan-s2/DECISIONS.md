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

## D-35 — the seam ground held, although the diff script reports drift
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish, Step 4 ground diff)
- Options: A — read the drift as noise: `git diff 22ab4de0 HEAD` over every path outside `docs/afk/afkv2`, `afkv2` and `.claude` is empty, so the code INV-002 read is byte-identical vs B — a new investigation run at the current head
- Chosen: A — `ground_diff.py` exits 1 with 728 places, but every `+` row is spec prose added after the ledger, and the `-` rows come from a seed run with one `--subject`, while the ledger ran 4 roots; the seed script takes one subject. B would re-read identical code. Not verified: whether a 4-root seed run would come back clean
- Supersedes: execute `CITED-MODE.md` "On drift, re-investigate rather than patch", for this seam
- To reverse: run `/afk:investigate` on `build_description` at the head of this branch

## D-36 — the tracker payloads follow the port's own contract file on the S3 branch
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — build the fake and the calls from `afkv2/ports/tracker/CONTRACT.md` at `origin/feat/afkv2-s3` (not merged) vs B — only from SDD §3, and adjust when S3 merges
- Chosen: A — the plan's cross-session rule fixes the contract through the SDD, and SDD §3 names no carrier for the receipt and no text the receipt hashes. S3 settled them (its D-17 and later rows): `preview` path in `attachment-put` and `description-put`, `description_hash` and `block` from `issue-get`, `figure_token` and `block_text` from `md-to-adf`. B makes a guaranteed rework
- Supersedes: SDD §3 "description-put {key, adf, expect_hash, receipt}" and "attachment-put {key, png}", as S3's ledger already does
- To reverse: change `call` sites in `publish.py` and `fakes/fake_jira_port.py`

## D-37 — the run area of a spec folder is `run/`, and git ignores it
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — `<spec folder>/run/` with a `.gitignore` of `*` that the preview writes vs B — the afkv2 data folder vs C — commit the preview with the spec folder
- Chosen: A — SDD §4 puts "Publish preview + receipt" in the "spec folder run area", and PRD AC-070 lists what merges with the change, and a preview is not in that list. B moves it out of the place the SDD names
- Supersedes: none
- To reverse: change `run_dir` in `prd_files.py start`

## D-38 — the preview is one HTML file and the yes is a chat message; to-prd calls no engine verb
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — a self-contained HTML file drawn from the ADF nodes the publish sends, and the developer's yes in chat vs B — a page document and an engine round for the preview
- Chosen: A — SDD §4 fixes `session.skill ∈ grill, propose-solution, propose-verification`, so to-prd cannot own a signed page document (HL-1), and SDD §7 says only "show preview" and "yes". A also shows the nodes that go to the ticket, and not a second rendering of the Markdown
- Supersedes: SDD §8 module diagram, edge "to-prd → page engine"
- To reverse: add `to-prd` to the session skill values, and draw the preview as a round

## D-39 — diagrams render with mermaid-cli on the machine, and each source renders once
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — `mmdc`, else `npx -y @mermaid-js/mermaid-cli` as v1 does, with the PNG cached by the hash of the source in the run area vs B — render at each preview
- Chosen: A — SDD §5 makes the receipt depend on the picture hashes, and a renderer may not give equal bytes twice (not verified for mermaid-cli), so B could break the equal read-back of a re-run. No SDD row or setup contract installs mermaid-cli, so the preview refuses `render-failed` and names the install; setup can add it later
- Supersedes: none
- To reverse: drop `_rendered`, and render in `build_preview`

## D-40 — an id stays by its line, and `check` compares with the last commit
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — a dropped criterion keeps its line with `retired: <why>`, a new id is above the highest of its family, and text that moves to another id is refused; all against `git show HEAD:` vs B — a separate id ledger file vs C — a rule in prose only
- Chosen: A — AC-050 needs a mechanical check; A needs no new artifact, and keeps each id in the published text, so AC-055 still holds for a dropped criterion. C is a defect under the plugin's deterministic-first rule
- Supersedes: none
- To reverse: remove `renumber_problems` from `prd_files.py check`

## D-41 — the publish reads the ticket once before its first write
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — after the yes, `issue-get` and `attachment-list` first: an equal block means no write; a changed hash means `stale` before any upload vs B — go straight to `attachment-put`
- Chosen: A — SDD §5 asks a re-run after success to write nothing, and B uploads first. The port's own check just before the write stays the guard (ADR-0004 design); A only saves dead uploads. A local `uploads.json` lets a re-run reuse an upload and its media id, because `attachment-list` answers no media id
- Supersedes: none
- To reverse: remove the 2 reads and the 2 branches at the head of `publish_after_yes`

## D-42 — the published line comes after the read-back and before the deletes
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — write the line once the read-back passes; a run that wrote nothing adds a line only when that ticket and receipt have none vs B — write it last
- Chosen: A — the switch-back report must list a ticket that holds an afkv2 block, also when a delete failed. D-S-3 asks one line per publish, and a run that writes nothing is not a publish
- Supersedes: none
- To reverse: move `_record` after `_remove_unused`

## D-43 — to-prd imports the grill's envelope, config read and gate read
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — import `grill_common`, `grill_start` and `grill_log` from `skills/grill/scripts` vs B — copy them
- Chosen: A — one fact, one home: the spec folder rule (D-24) and the exit gate row have one parser each
- Supersedes: none
- To reverse: copy the 3 helpers into `skills/to-prd/scripts`

## D-44 — the v1 picture name lives in a `v1_facts.py`
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — `skills/to-prd/scripts/v1_facts.py` and `tests/skills/fakes/v1_facts.py`, as S3's D-35 keeps its v1 strings vs B — hide the name from the check with a split string
- Chosen: A — S3's D-35 rejects B because it defeats the check. The S1 plugin check flags a `v1_facts.py` until the exemption by file name that S3 owes lands: IOU in `.claude/wiring-ious.md`
- Supersedes: none
- To reverse: inline the name, once the check has a different exemption
## D-45 — the `npx` fallback stays as open advice; D-39's claim is corrected
- 2026-10-30 · decided by execute (0008-to-prd-jira-publish)
- Options: A — keep `npx -y @mermaid-js/mermaid-cli` when `mmdc` is absent and leave the review finding open vs B — remove the branch now
- Chosen: A — owner ruling R-2 keeps a medium finding open with no fix. Correction to D-39: GRILL-LOG.md, seam row "tracker port", states "setup installs markdown package + diagram renderer, no download at publish", so the `npx` branch goes against that row. D-39 did not cite it. No setup contract installs the renderer yet (checked: plan-s3 0011 and 0012 do not name it), so `mmdc` is absent on a new machine and the branch is the only way a diagram renders
- Supersedes: none
- To reverse: delete the `npx` branch in `render_mermaid`, once setup installs `mmdc`


## D-46 — the critical-aspect order lives in one table the script reads
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — one table in `ASPECTS.md`, parsed by `design_round.py`, with each aspect tagged through a generated map node vs B — a list in the script and a copy in the prose vs C — a new item field in the page document
- Chosen: A — one fact has one home, and the build can refuse a wrong order. The S1 schema has `additionalProperties: false` on an item, so C needs a contract change; a map node is already a field, and GRILL-LOG.md line 117 names the design layers as the map of this skill.
- Supersedes: none
- To reverse: move the table into the script, and keep the node names

## D-47 — an aspect card asks the human, and the draft waits for all aspects
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — an aspect card is `confirm` or a fork; one round may hold several aspects in order; a layer or sign-off card is refused until every aspect is settled vs B — one aspect per round, and any kind
- Chosen: A — decision 49 of issue 153 puts a short question and answer before the draft, so an aspect cannot be a `decided` or `info` card. B costs up to 11 rounds. An aspect the feature does not touch gets a `confirm` card that says what was checked, so silence never skips one.
- Supersedes: none
- To reverse: drop the check on kinds and the `aspects-first` refusal in `design_round.py`

## D-48 — the human-locked set of v1 stays, in compact form
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — keep the 6 aspects and the §0 register, in `DRAFT.md`, and let the gate compare the register with the sign-off cards vs B — no sign-off in the design skill
- Chosen: A — decision 94 of issue 153 keeps the approach of the v1 design grill, and the page model already has the `signoff` kind and the `sign` mark. Owner ruling R-3 applies to these cards.
- Supersedes: none
- To reverse: delete the table and `_register_problems`

## D-49 — design premises use the row kind `Premise`, not `Ledger`
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — a new kind `Premise` in the section `## Solution design` of `GRILL-LOG.md` vs B — the grill's `Ledger` kind
- Chosen: A — `prd_files._grill_rows` reads `- Ledger:` and `- Term:` rows over the whole log, so a pending design row of kind `Ledger` blocks a later run of to-prd.
- Supersedes: none
- To reverse: narrow `_grill_rows` to the grill's own section, then rename the kind

## D-50 — a session ends at its gate row; a later run is a change session
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — resume the newest document with no `Settled: design gate passed … · session <id>` row, else start a new session, and `sdd_exists` true means the session changes a design vs B — always resume the newest document
- Chosen: A — a passed session is closed, and one page document holds one session (SDD §4). A change writes a new ADR with `Superseded by` on the old one.
- Supersedes: none
- To reverse: `_open_session` in `design_files.py`

## D-51 — every debate card comes from a `fork` field
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — the build refuses a debate card with a hand-written body (`not-a-fork`), and a fork needs `why_open` vs B — accept any body and check it by review
- Chosen: A — the side-by-side shape is then a property of the build, not of care. The option convention (`<item id>-opt-<letter>`, label = column title) is confirmed on `origin/feat/afkv2-s1` commit ab931ae0: the real engine rendered both option marks of the fixture round. This supports D-3.
- Supersedes: none
- To reverse: drop `not-a-fork` in `design_round._tagged`

## D-52 — the second-provider slot is one command that answers off
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — `second_provider.py review --draft F` answers `{"state":"off","forks":[]}`, the skill calls it before the first draft round, and `forks` has the shape of the `fork` input vs B — a sentence in the skill and no code
- Chosen: A — the call site and the answer shape stay fixed, so P1 (decision 98) changes one script. Nothing is called in P0.
- Supersedes: none
- To reverse: delete the script and its step

## D-53 — the skill calls the grill's verbs and imports its helpers
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — the fences call `../grill/scripts/page_round.py` and `round_document.py apply-readings` directly, and `design_round.py` wraps only `build` vs B — a wrapper per verb
- Chosen: A — same precedent as D-43, and the only difference is the skill name in the session, which `round_document.main` fixes. The grill folder is outside Scope and stays unchanged.
- Supersedes: none
- To reverse: copy the verbs into this skill

## D-54 — the gate checks what a script can see; the rest is a checklist
- 2026-10-30 · decided by execute (0009-propose-solution-skill)
- Options: A — `design_files.py gate` lists points, aspects, layers, premises, SDD headings and blockers, blocking open questions, the register, ADR shape and settled forks, and writes the `SDD` and `Design ADRs` rows of INDEX.md; judgment checks stay in `DRAFT.md` vs B — all checks as prose
- Chosen: A — deterministic work goes in a script. A missing INDEX.md blocks nothing, and the answer says `index_missing`. The section list is read from the template in `SDD-FORMAT.md`, which has one home.
- Supersedes: none
- To reverse: delete the `gate` verb, and state the checks in `SKILL.md`

## D-55 — orchestrator ruling: 0008 builds to the frozen publish preview; no code change was needed
- 2026-10-30 · decided by the session orchestrator (ruling sent to this session mid-run; SDD §8 "Frozen on day 1" row "publish preview", commit a867cf98; plan-s3 D-17, D-29)
- Options: A — check 0008 against the frozen row and change only what differs vs B — rework the publish flow
- Chosen: A — `publish.py` already writes `ticket_key`, `receipt`, `description_hash` and `picture_hashes` in `preview.json` (plus its own `block_text`, `pictures`, `index`) and passes the path as `preview` to `attachment-put` and `description-put`. `fake_jira_port.py` refuses `bad-receipt` on a receipt, ticket, hash or picture-hash mismatch and computes the receipt again from the written block text. After the merge at 0272df31, `test_to_prd.py` and `test_propose_solution.py` give 161 passed, 3 skipped. The tests against the real S3 port skip on this branch until S3 merges; the 0008 executor reports that they passed against the S3 port code (not re-checked)
- Supersedes: none
- To reverse: none; this records a check

## D-56 — orchestrator ruling: 0010 emits the gate-not-applicable form that S3 0015 reads
- 2026-10-30 · decided by the session orchestrator (ruling sent to this session mid-run; plan-s3 D-68, D-70, D-71)
- Options: A — add the S3 form to 0010 Acceptance vs B — 0010 chooses its own form
- Chosen: A — S3 `start_gate.py` reads a check cell that starts `not applicable:` with a reason, and refuses another form as `bad-not-applicable`. A second form would make a valid plan refuse at the autopilot start. The new bullet is in `## Acceptance` of 0010, and the plan check is clean
- Supersedes: D-32, only its open phrase "names it not applicable", which now has this form
- To reverse: change the bullet and `NOT_APPLICABLE` in `start_gate.py`

## D-57 — the division page uses the session skill `propose-solution`
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — keep `session.skill` = `propose-solution`, with the file name `pages/propose-solution-division-<stamp>.json` vs B — add `to-subtasks` to the skill enum of SDD §4 vs C — no page
- Chosen: A — the S1 schema enum is signed under HL-1 and names grill, propose-solution and propose-verification only; the contract requires approval on the page. The S1 engine refuses any other file name (`_require_home`: `<skill>-<session id>.json`), seen in a one-off run with that engine. The session prefix `division-` sorts before the `s-` of a design session, so `design_files._open_session` of `/afkv2:propose-solution` takes the design session. Known limit: a spec folder that has a division document and no design document at all resumes the division document in that skill; the SDD then came from outside the chain.
- Supersedes: none
- To reverse: add `to-subtasks` to SDD §4 and change `PAGE_SKILL` in `plan_files.py`

## D-58 — the plan states the app in a `> App:` header line
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — a `> App: <address or start command>` or `> App: none` header line of PLAN.md vs B — a second argument of `check_plan.py` vs C — read the app from the repository config
- Chosen: A — S3 D-72 fixes the call as `check_plan.py <plan folder>` with no other input, and the check has to tell whether a live tier can run. An absent line reads as no app, so the check fails closed. The S3 gate takes its own `app` value at run time, which the skill does not change.
- Supersedes: none
- To reverse: `_app_of` in `check_plan.py`, the template in `PLAN-FORMAT.md`

## D-59 — a check path passes when the chain owns it or the file is on the feature branch
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — owned by a Scope of the chain, or already on the head of the feature branch vs B — owned by a Scope only
- Chosen: A — D-32 names the Scope rule, and S3 D-71 sends path-named commands to this check. With B every `./mvnw` or existing script refuses. The check reads the feature branch because the run branch holds no code; a run branch with no feature branch owns nothing, so it fails closed. The answer names the `base`. Limit of the reader: a word in a code span is a path only with a `/`, and a prose code span can read as a program (seen once: 0006 of this plan, which predates the check).
- Supersedes: none
- To reverse: `Base` and `_row_failures` in `check_plan.py`

## D-60 — the check reports a missing approval and does not fail on it
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — `division.approved` false on exit 0, and `bad-approval` only for a malformed line vs B — a failure when the line is missing
- Chosen: A — the check must pass before the developer can approve, because the division round refuses a plan that fails it. S3 reads the line itself in `start_gate.py`. The S3 fake reports `no-approval` from the check; the extra failure does not change the S3 result.
- Supersedes: none
- To reverse: `division_of` and `check_plan` in `check_plan.py`

## D-61 — citations resolve in a separate verb at the cut
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — `plan_files.py citations --plan --spec-dir` vs B — a rule of `check_plan.py`
- Chosen: A — the check takes the plan folder only (S3 D-72), runs on the run branch, and the run branch holds no spec file. The contract asks for citations at the cut. The grammar is in `SUBTASK-CONTRACT.md`: PRD, SDD and ADR citations resolve; a GRILL-LOG citation does not, because the skill reads only the PRD, the SDD and the ADRs.
- Supersedes: none
- To reverse: move `citation_failures` into `check_plan.py` with a spec-folder input

## D-62 — the approval binds to a digest of the committed plan
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — the card id holds a digest of PLAN.md and the contracts, and `approve` needs the newest division card settled on that digest vs B — any settled card approves
- Chosen: A — a note that changes the plan returns the card, and the new digest needs a new sign mark (owner ruling R-3). A sign on an older plan does not approve a changed one. Running `division` takes back an earlier approval line. The `> Division:` and `> Last updated:` lines and the line ends do not count in the digest. A later edit with no `division` run keeps the line: autopilot reads only the line, and the contract asks no more.
- Supersedes: none
- To reverse: `plan_digest` and `_approved_by_developer` in `plan_files.py`

## D-63 — the run branch starts empty by plumbing commands
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — `git mktree` and `git commit-tree`, then `git branch` vs B — `git checkout --orphan` vs C — `git worktree add --orphan`
- Chosen: A — B changes the feature worktree, and C needs git 2.42. The worktree path is `<toplevel>-run`, the same as `locate` in S3 `walk.py`, so autopilot reuses it. `commit` refuses any file outside `plan/` and any spec file under it.
- Supersedes: none
- To reverse: `_new_run_branch` in `plan_files.py`

## D-64 — the plan has no smoke gate, no sync-harness subtask, no review-policy line and no journal seed
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — leave them out of `PLAN-FORMAT.md` vs B — keep the v1 sections
- Chosen: A — no reader exists for them in afkv2 (K-8 P0, E-3), and S3 creates JOURNAL.md and DECISIONS.md on first write. S3 reads `/afk:` in a header line as a v1 plan, so the template holds none.
- Supersedes: none
- To reverse: add the rows to `PLAN-FORMAT.md`

## D-65 — `.claude/wiring-ious.md` gets the lines of this slice
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — add them, outside `## Scope`, as 0007, 0008 and 0009 did vs B — leave them out
- Chosen: A — the user rule on wiring requires a line for each artifact whose consumer comes later. No code changes outside Scope.
- Supersedes: none
- To reverse: delete the 3 lines

## D-66 — correction of D-59: the check does not read `./mvnw` as a path
- 2026-10-30 · decided by execute (0010-to-subtasks-skill)
- Options: A — state the correction here and leave the gap open as advice (owner ruling R-2) vs B — fix it in this slice
- Chosen: A — D-59 says that with the Scope rule alone "every `./mvnw`" refuses. That is wrong: review finding r-001 is right, a run of `check_paths` on `./mvnw test` answers no path. So an unowned one-part `./tool` passes the check, and S3 D-71 leaves such a command to this check. The feature-branch reason of D-59 still holds for a path with a folder, such as `scripts/run_all`. R-2 allows no fix for a medium finding, so the gap stays open on pull request 154, and the final report names it for the owner.
- Supersedes: D-59, only its `./mvnw` clause
- To reverse: test the slash before `removeprefix("./")` in `check_paths`, and add a test

## D-67 — orchestrator ruling: unique names for the 2 S2 v1 facts modules
- 2026-10-30 · decided by the session orchestrator (ruling sent to this session mid-run; SDD §7 row "two flat script modules with one name")
- Options: A — `to_prd_v1_facts.py` and `fake_v1_facts.py` vs B — keep `v1_facts.py`, which fails `afkv2/tests/test_module_names.py` on the merged tree
- Chosen: A — commit f6eec235. `ports/tracker/v1_facts.py` and `ports/tracker/cli.py` keep their names (S3). S1 `plugin_check.py` exempts `*v1_facts.py`, so both new names keep the v1-string exemption. A name check over the S1 and S3 branch tips and this tree finds no other duplicate. `test_to_prd.py`: 62 passed, 2 skipped. The check was not run on the merged tree, because S1 and S3 are not merged
- Supersedes: none
- To reverse: rename the 2 files and their importers

## D-68 — the orphan hunt: remove 2 unused verbs, add 2 IOUs
- 2026-10-30 · decided by autopilot (orchestrator, `/afk:verify-seams` non-final)
- Options: A — remove `round_document.py pending` and `prd_files.py row` vs B — keep them behind an IOU
- Chosen: A — commit 5120ee84. A blind reader, and a search of the S1, S3 and S4 plans, found no caller, so an IOU has no real anchor. Other skills call `set_row` and `pending` in-process. `test_grill.py` and `test_to_prd.py` give 142 passed, 3 skipped. The new IOUs cover the engine verb `ingest` (plan-s1 0005, still pending) and the owner-run `CODEX-LIVE-CHECK.md` files (D-S-8). Limit: the reader enumerated consumers itself and had no per-symbol ledgers, so its verdicts are weaker than the skill's standard. It did not audit `afkv2/GLOSSARY.md`
- Supersedes: none
- To reverse: revert commit 5120ee84

## D-69 — owner ruling R-5: one delta check for a late fix
- 2026-10-30 · decided by the owner (brief, section "Owner rulings")
- Options: A — one delta check of a critical or high fix in the last allowed round, or of a fix for a ruling after review settled vs B — no check of such a fix
- Chosen: A — the check reads only the fix commits' diff. It may confirm or reopen what those commits answer, and it raises a new finding only if a fix adds a critical or high defect. A reopened critical or high finding gets one more fix, and the slice parks if the next delta check fails. In this run it applies to the D-67 rename (f6eec235). No slice reached round 3, so no last-round fix needs it. The check also reads 5120ee84, which no ruling asked for, because it also came after review settled
- Supersedes: D-18, only where it gave a late fix no check
- To reverse: the owner withdraws R-5

# 0005-notes-ingest-live-test

## Goal
Add notes and replies (CMP-2) and the ingest verb: the human notes any element,
ingest writes the raw response with per-item signals into the document per the
§6 mark table, and points settle by mark, by a clear note (with the agent's
reading) or stay open on conflict. A past session's document reopens to read or
continue. Close with the live browser test of AC-042 on Edge.

## Complexity
complex

## Design refs
- SDD: SDD.md#§6 L5 — Domain Model — point states, mark table, invariants (signed HL-4)
- SDD: SDD.md#§4 L3 — Data Architecture — notes field, browser draft row
- SDD: SDD.md#§8 L7 — Module Decomposition — ported-vs-new row ingest
- ADR: adr/design/0002-point-states-and-ingest-rules.md
- ADR: adr/requirements/0002-a-clear-note-settles-a-point.md

## Scope
- afkv2/engine/ingest.py
- afkv2/engine/components/notes_*.py
- afkv2/engine/shell/notes*
- afkv2/engine/engine.py   # register the ingest verb
- afkv2/tests/engine/test_ingest.py
- afkv2/tests/live/test_page_live.md

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] ingest takes the document path and the raw response text, appends `{received, raw, signals[]}` to the current round, and writes signals without judgement (ADR-0001 design)
- [ ] Mark table: a lone accept, sign or option mark settles by mark; a note, a mark plus a note, 2 marks, `reopen`, `changes` or a write-in go to needs-reading; a conflict is 2 lines for one item (SDD §6)
- [ ] needs-reading goes to settled-by-note only when the agent writes its reading, and back to open when the agent finds the signals unclear or in conflict; settled-by-note shows a state that differs from settled-by-mark (PRD §AC-036)
- [ ] A mark and a note that disagree, or 2 marks that disagree, keep the point open (PRD §AC-037; PRD §WE-02 rounds 3 and 4 as a fixture)
- [ ] A note on a settled item reopens it, and the reopen is recorded in the next round; a note on a map node is recorded as a steer for that node (PRD §AC-038)
- [ ] The human writes, edits and deletes a note on every element: map node, card, settled item, diagram, freestyle fragment; note ids are `N-<round>-<item>`, minted by the engine; a deleted note keeps its id with `deleted` (SDD §4 item row "notes")
- [ ] Notes and replies render newest round first, each round collapsible, with the agent's replies on top (PRD §AC-033)
- [ ] A re-render while the human types keeps every unsent note: browser drafts are keyed by session id + round and cleared on send (PRD §AC-041)
- [ ] The engine opens any saved page document to read it or to continue it (PRD §AC-039)
- [ ] Live browser test (Playwright MCP + Edge) with many notes, long text, wide tables, many rounds and big diagrams: no content hidden or cut off; mark, note, edit and delete a note, collapse and send all work (PRD §AC-042)
- [ ] Seam-test: the raw response text the live test sends through lavish-axi 0.1.80 is what ingest reads, byte for byte (SDD §9b row "lavish host")

## Produces
- afkv2/engine/ingest.py#def cmd_ingest( — ingest verb
- afkv2/engine/ingest.py#def apply_mark_table( — §6 mark table
- afkv2/engine/components/notes_replies.py#def render_notes_replies( — CMP-2

## Consumes
- 0003-engine-core-schema-show-poll afkv2/engine/engine.py#def cmd_check( — invariants ingest output must pass
- 0003-engine-core-schema-show-poll afkv2/engine/engine.py#def cmd_poll( — the raw response ingest reads
- 0004-diagram-components afkv2/engine/components/diagram_graph.py#def render_graph( — big diagrams in the live test

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m compileall -q afkv2/engine` + `rg -F` each ## Produces anchor in its file (exactly 1 hit) | code builds; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/engine/test_ingest.py -q` | mark table, conflicts, WE-02, reopen, steer, note ids, invariants after ingest |
| e2e/browser | live test per `afkv2/tests/live/test_page_live.md`: Playwright MCP drives Edge on a page rendered from the stress fixture, performs every action, sends, then ingest reads the polled text | AC-042 on the real host; the lavish host seam end to end |

## Context excerpts
> (SDD §6 mark table) Mark table: a lone accept, sign or option mark settles by mark; `reopen`, `changes` and a write-in go to needs-reading. A conflict is 2 lines for one item.

> (ADR-0002 design) A point is open, blocked, needs-reading, settled-by-mark or settled-by-note. ingest settles a lone accept, sign or option mark; a note, a mark plus a note, 2 marks, reopen, changes or a write-in go to needs-reading, where the agent writes its reading or returns the point to open. The engine refuses settled-by-note without a note id and a reading, and refuses a rewrite of a settled round.

> (SDD §4 item row) | notes | list of {id, round, target, text, deleted} | yes | empty | — | id = `N-<round>-<item>`, minted by the engine; target = any element id | note id unique | |

> (SDD §4) | Browser draft of unsent answers | browser storage, key = session id + round | per session and round | none | cleared on send | key change only | no | no |

> (PRD §WE-02) | 3 | note "yes, notes can settle it", no mark | settled by note; reply: "settled by your note: notes may settle a point" |
> | 4 | mark accept on V-5's settled card plus note "only for terms" | open: mark and note disagree; the card returns with both signals shown |

> (PRD §AC-042) In the live browser test, no content is hidden or cut off, and every action works (mark, note, edit and delete a note, collapse, send). The test covers many notes, long text, wide tables, many rounds and big diagrams.

> (SDD §8 ported vs new) | ingest | none (v1 has no response parser, INV-003) | new | §6 mark table; note ids; conflict rule; draft key per session and round |

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0003-engine-core-schema-show-poll
- 0004-diagram-components

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

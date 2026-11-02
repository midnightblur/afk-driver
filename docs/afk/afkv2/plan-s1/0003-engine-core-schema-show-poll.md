# 0003-engine-core-schema-show-poll

## Goal
Build the page engine core: one command with verbs check, render, show and poll
(ingest is 0005), the schema `afkv2.page/0` validator, the component registry
with the base components (round banner, card, table, chip and styled text,
freestyle), the page shell grown from the v1 page kit, and show/poll through the
ported lavish launcher at lavish-axi 0.1.80. On Codex, show writes the "page
waiting" record and the afkv2 Stop hook waits for the answer and hands it back.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — page engine command contract
- SDD: SDD.md#§4 L3 — Data Architecture — page document v0 (signed HL-1)
- SDD: SDD.md#§6 L5 — Domain Model — invariants
- SDD: SDD.md#§8 L7 — Module Decomposition — rows page engine, Codex Stop hook; ported-vs-new rows engine show / poll, engine render / check
- SDD: SDD.md#§9 L8 — Tactical Patterns — Registry
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows lavish host, Codex Stop hook
- ADR: adr/design/0001-page-engine-verbs-and-schema-v0.md
- ADR: adr/design/0006-codex-page-wake-through-stop-hook.md
- ADR: adr/requirements/0001-page-engine-documents-only.md

## Scope
- afkv2/engine/engine.py
- afkv2/engine/registry.py
- afkv2/engine/schema/*
- afkv2/engine/components/base_*.py
- afkv2/engine/shell/*
- afkv2/engine/launcher.py
- afkv2/hooks/codex_stop.py
- afkv2/hooks/hooks.json   # add the Codex Stop hook entry
- afkv2/tests/engine/test_engine_core.py
- afkv2/tests/engine/fixtures/*
- afkv2/tests/live/CODEX-LIVE-CHECKS.md   # orchestrator ruling: this contract Acceptance names it
- .claude/wiring-ious.md   # orchestrator ruling: IOU lines only

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The engine is one command with verbs check, render, show, poll; each answers one JSON object, `{"ok": true, ...}` or `{"ok": false, "error": {"code", "reason"}}` naming item and field, with exit 0 ok, 1 refused, 2 unreadable input (SDD §3)
- [ ] check refuses a document that breaks schema `afkv2.page/0` and names the item and the field (PRD §AC-030)
- [ ] check enforces the §6 invariants: exactly one round is current; a settled round is never rewritten (compared with the last saved copy); settled-by-note has a note id and a reading; only ingest writes responses and signals (SDD §6)
- [ ] An unknown schema value is refused with its version number; the engine keeps a reader for every value it wrote (PRD §AC-040)
- [ ] The registry maps a type name to a schema and a renderer; an unknown type is refused; every component takes an open `style` field and may hold children; freestyle renders any HTML or SVG and the page marks it as freestyle (ADR-0001 design; PRD §AC-032)
- [ ] Base components render: round banner (CMP-1), card (CMP-4), table with any component in a cell (CMP-6), chip and styled text with the 4 semantic styles (CMP-9), freestyle (CMP-10); a chip renders inside a table cell (PRD §AC-031)
- [ ] Page order: round banner, notes and replies slot (filled by 0005), maps, cards; each round has its own colour and a round chip marks every item that needs the human in that round; no item is removed when a round settles (PRD §AC-033, §AC-034)
- [ ] The page document is saved in the feature spec folder as `pages/<skill>-<session id>.json`; the rendered HTML is a build product beside it (SDD §4)
- [ ] show and poll use the ported v1 launcher with afkv2 names and lavish-axi 0.1.80; wrapper exits 64 / 65 / 69 / 127 lead to the Markdown fallback (SDD §9b row "lavish host")
- [ ] Seam-test on lavish-axi 0.1.80: a rendered fixture is shown, a response is sent from the browser, and poll returns the host's raw composed response text verbatim. The test runs 0.1.80 without changing the global install; the global install is setup's (SDD §9b row "lavish host")
- [ ] On Codex, show writes one "page waiting" record per session in the afkv2 data folder; the Stop hook, when that record exists, waits up to 3600 s and returns `decision: block` with the raw response as `reason`; with no record it returns nothing (ADR-0006 design)
- [ ] Codex Stop-hook live check (page answer sent after 10 minutes reaches the agent) is an owner-run step in `afkv2/tests/live/CODEX-LIVE-CHECKS.md`; a failure means the fallback, one chat message after Send, reported to the owner (SDD §9b row "Codex Stop hook")
- [ ] The page shell, stylesheet, browser script, saved drafts, layout-audit fixes and tooltip layer of the v1 kit are reused with afkv2 names (PRD Implementation Decisions, V-11)
- [ ] Implements the public interface in SDD §8 rows "page engine" and "Codex Stop hook" unmodified (SDD §8)

## Produces
- afkv2/engine/engine.py#def cmd_check( — schema v0 + invariant check
- afkv2/engine/engine.py#def cmd_render( — document to page
- afkv2/engine/engine.py#def cmd_show( — open the page; on Codex write the waiting record
- afkv2/engine/engine.py#def cmd_poll( — raw response text
- afkv2/engine/schema/page-v0.schema.json#afkv2.page/0 — frozen schema v0
- afkv2/engine/registry.py#def register_component( — registry entry point
- afkv2/engine/launcher.py#def write_waiting_record( — Codex page-waiting record
- afkv2/hooks/codex_stop.py#def wait_for_answer( — Codex Stop hook

## Consumes
- 0001-skeleton-manifests-hooks afkv2/scripts/afkv2_config.py#def read_config( — spec folder and data folder
- 0001-skeleton-manifests-hooks afkv2/hooks/hooks.json#SubagentStart — the hook file the Stop entry joins

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m compileall -q afkv2/engine afkv2/hooks` + `rg -F` each ## Produces anchor in its file (exactly 1 hit) | code builds; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/engine/test_engine_core.py -q` | schema refusals name item + field; invariants; unknown version; registry; base components incl. chip in a cell; page order; envelope + exit codes |
| integration | seam-test: render a fixture, show it on lavish-axi 0.1.80 (exact version, global install untouched), send a response from Edge (Playwright MCP), poll returns the raw text verbatim; Stop hook run with a waiting record + a queued answer returns `block` + reason | the lavish host and Stop-hook seams on real output |

## Context excerpts
> (SDD §3 page engine row) | page engine | check, render, show, poll, ingest | page document path; ingest also takes the raw response text | `{"ok": true, ...}` per verb | `{"ok": false, "error": {"code", "reason"}}` naming item and field | 0 ok · 1 refused · 2 unreadable input |

> (SDD §4 document fields) | schema | string | no | — | — | equals `afkv2.page/0`; an unknown value is refused and named | — | version key |
> | session | object {id, skill, feature, ticket, started} | no | — | started: ISO-8601 UTC | skill ∈ grill, propose-solution, propose-verification | id unique per spec folder | |
> | maps | list of map | yes | empty | — | each node carries state and the round it last changed | node id unique | updated in place |
> | rounds | list of round | no | — | — | exactly one round is current; a settled round is never rewritten | n unique | |

> (SDD §4) The full round, item and component field tables are binding; read SDD §4 for them (signed HL-1).

> (SDD §6 invariants) | settled-by-note has a note id and a reading | page document | engine check | document refused, field named |
> | only ingest writes responses and signals | page document | engine check (signals carry ingest's stamp) | document refused |
> | a settled round is never rewritten | page document | engine check against the last saved copy | document refused |
> | exactly one round is current | page document | engine check | document refused |

> (SDD §8 ported vs new) | engine show / poll | v1 page launcher (INV-003) | extends | afkv2 names; provider facts and tooltip glossary re-homed; lavish pin 0.1.80 |
> | engine render / check | v1 page kit (INV-003) | reworked | new v0 validator and component-tree compiler; page shell, stylesheet, browser script and exit pattern reused |

> (SDD §9b) | lavish host | lavish-axi 0.1.80 (npm, published 2026-09-29; owner PIN-2) | serves the page, returns the composed response on poll | wrapper exits 64 / 65 / 69 / 127 → Markdown fallback | live browser test (PRD AC-042) on 0.1.80 asserts the raw response text that ingest reads |
> | Codex Stop hook | Codex hooks (docs: decision `block` + `reason` starts a continuation prompt; timeout default 600 s, no stated maximum) | the reason text becomes the next prompt | wait refused or cut → fallback one chat message | day-1 live check: a page answer sent after 10 minutes reaches the agent (unverified premise until then) |

> (ADR-0006 design) On Codex, show writes a "page waiting" record for the session. An afkv2 Stop hook, when that record exists, waits for the page answer (timeout 3600 s) and returns `block` with the raw response as reason. Claude keeps v1's tracked background poll. If the day-1 live check fails, the fallback is one chat message after Send, reported to the owner. Owner accepted the mechanism in R-5.

> (PRD Testing Decisions) Page engine: deterministic tests (schema checks, render snapshots, the response parser), with real page documents from this grill as fixtures. Plus the live browser test of AC-042, with Playwright MCP and Edge (decision 70).

> (PRD §AC-030) The agent writes only a page document. The engine renders it. A page document that breaks the schema is refused with the item and the field named.

> (PRD §AC-040) The engine opens a page document of every schema version it ever wrote. An unknown version is refused with its version number.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0001-skeleton-manifests-hooks

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

# 0006-visualize-skill

## Goal
Write `/afkv2:visualize`: the authoring guide for page documents. One entry per
component (CMP-1..CMP-10): what it holds, when to use it, how it looks, and one
example document fragment in schema v0. Includes the rule to show the current
state as a picture before a critical-aspect question.

## Complexity
standard

## Design refs
- SDD: SDD.md#§4 L3 — Data Architecture — page document v0 (frozen day 1)
- SDD: SDD.md#§9 L8 — Tactical Patterns — Registry, freestyle
- ADR: adr/requirements/0001-page-engine-documents-only.md

## Scope
- afkv2/skills/visualize/**
- afkv2/tests/skills/test_visualize.py

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The guide has one entry per CMP-1..CMP-10 with what it holds, when to use it and how it looks (PRD §SK-06)
- [ ] Each entry has an example fragment that uses only the schema v0 fields of SDD §4; every example document carries `schema: afkv2.page/0` (SDD §4)
- [ ] The guide says an agent writes only a page document, never HTML, and that freestyle is the marked escape; a repeated freestyle use is reported as a candidate component (ADR-0001 requirements; SDD §9)
- [ ] The guide states AC-043: before a critical-aspect question, show the current state as a picture (code area, data or flow) (PRD §AC-043)
- [ ] The skill names no upstream caller and no v1 name (PRD §AC-019)

## Produces
- afkv2/skills/visualize/SKILL.md#name: visualize — the authoring guide
- afkv2/skills/visualize/examples/all-components.json#afkv2.page/0 — one document using every component

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/visualize/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/visualize`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_visualize.py -q` (before S1's engine merges: example documents checked against the SDD §4 required fields; after: `engine check` on each example, exit 0) | every CMP has an entry and a schema-v0 example |

## Context excerpts
> (PRD §SK-06) | SK-06 | `/afkv2:visualize` | the authoring guide for page documents: each component, when to use it, how it looks | V-7 + owner note |

> (PRD Catalog CMP) | CMP-1 | round banner | round number, colour, what settled, what it unlocks, parked items |
> | CMP-2 | notes and replies | the human's notes and the agent's replies per round; newest round first; each round collapsible |
> | CMP-3 | map | any diagram that keeps the high-level view; coloured settled / open / current focus; as many per page as the topic needs |
> | CMP-4 | card | one per map node: decided, confirm, debate (fork) or settled |
> | CMP-5 | graph | nodes and arrows: maps, flow charts, module structure with grouped boxes |
> | CMP-6 | table | rows and cells; a cell may hold any component |
> | CMP-7 | sequence diagram | actors and ordered messages |
> | CMP-8 | simulated-run strip | the steps of a run in time order, current and proposed |
> | CMP-9 | chip and styled text | semantic styles: removed (strike-through, red), kept (grey chip), new or changed (blue chip), proposed (dashed) |
> | CMP-10 | freestyle | any HTML or SVG fragment; each use is marked |

> (SDD §4 component fields) | type | registry name or `freestyle` | no | — | — | unknown type refused | — | |
> | id | string | yes | — | — | needed to be a note target | unique when present | |
> | props | object | per type | — | — | checked by the type's own schema | — | |
> | style | CSS text | yes | — | — | any CSS | — | |
> | children | list of component | yes | empty | — | — | — | |
> | html | string | freestyle only | — | — | any HTML or SVG; the page marks it as freestyle | — | |

> (PRD §AC-043) Before a critical-aspect question, the grill and propose-solution pages show the current state as a picture (code area, data or flow).

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

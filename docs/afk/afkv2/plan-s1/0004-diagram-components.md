# 0004-diagram-components

## Goal
Add the diagram components to the registry: map (CMP-3), graph (CMP-5),
sequence diagram (CMP-7) and simulated-run strip (CMP-8). Each is one registry
entry with its own schema, renderer and styling, nests inside any other
component, and colours map nodes settled / open / current focus.

## Complexity
standard

## Design refs
- SDD: SDD.md#§4 L3 — Data Architecture — component fields
- SDD: SDD.md#§9 L8 — Tactical Patterns — Registry
- ADR: adr/design/0001-page-engine-verbs-and-schema-v0.md

## Scope
- afkv2/engine/components/diagram_*.py
- afkv2/engine/shell/diagram*
- afkv2/tests/engine/test_diagram_components.py
- afkv2/tests/engine/test_engine_core.py   # orchestrator ruling: only remove the scratch map registration from test_page_order_is_banner_slot_maps_cards

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] Map, graph, sequence diagram and simulated-run strip are registry entries; each checks its props with its own schema and refuses bad props naming the item and the field (SDD §4 component row "props")
- [ ] A map shows settled, open and current-focus nodes in different colours; a page may hold any number of maps (PRD §CMP-3)
- [ ] A graph draws nodes and arrows, including grouped boxes for module structure (PRD §CMP-5)
- [ ] A sequence diagram draws actors and ordered messages (PRD §CMP-7)
- [ ] A simulated-run strip draws the steps of a run in time order, current and proposed (PRD §CMP-8)
- [ ] A diagram renders inside a card and inside a table cell, and any component renders inside a diagram node label where the type allows children (PRD §AC-031)
- [ ] Each component owns its styling and takes the open `style` field (PRD Catalog CMP)
- [ ] Conforms to ADR-0001 design — a new component is one registry entry, no special case in the renderer (ADR-0001 design)

## Produces
- afkv2/engine/components/diagram_map.py#def render_map( — CMP-3
- afkv2/engine/components/diagram_graph.py#def render_graph( — CMP-5
- afkv2/engine/components/diagram_sequence.py#def render_sequence( — CMP-7
- afkv2/engine/components/diagram_run_strip.py#def render_run_strip( — CMP-8

## Consumes
- 0003-engine-core-schema-show-poll afkv2/engine/registry.py#def register_component( — registry entry point

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python -m compileall -q afkv2/engine/components` + `rg -F` each ## Produces anchor in its file (exactly 1 hit) | code builds; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/engine/test_diagram_components.py -q` | render snapshots; prop refusals; diagram in a card and in a table cell; map colours |

## Context excerpts
> (PRD Catalog CMP) | CMP-3 | map | any diagram that keeps the high-level view; coloured settled / open / current focus; as many per page as the topic needs |
> | CMP-5 | graph | nodes and arrows: maps, flow charts, module structure with grouped boxes |
> | CMP-7 | sequence diagram | actors and ordered messages |
> | CMP-8 | simulated-run strip | the steps of a run in time order, current and proposed |

> (PRD Catalog CMP) Every component may hold others and owns its styling. Every component takes an open style field (any CSS).

> (PRD §AC-031) Every component in CMP renders inside any other component, including a chip inside a table cell and a diagram inside a card.

> (SDD §9) | page components | Registry (type name → schema + renderer); freestyle as the open escape | ADR-0001 |

> (SDD §9 caption) A new component is one registry entry; a repeated freestyle use is the signal to add one.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0003-engine-core-schema-show-poll

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

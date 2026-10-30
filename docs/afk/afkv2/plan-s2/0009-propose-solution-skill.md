# 0009-propose-solution-skill

## Goal
Write `/afkv2:propose-solution`: the critical-aspect questions (CAT-A) in their
fixed order, a top-down draft, fork cards (debate items with the options side by
side) on the page, then SDD + design ADRs. Leave a slot for a second provider,
unused in P0.

## Complexity
complex

## Design refs
- SDD: SDD.md#§4 L3 — Data Architecture — item kinds (debate = fork card)
- SDD: SDD.md#§6 L5 — Domain Model — point states
- ADR: adr/design/0001-page-engine-verbs-and-schema-v0.md

## Scope
- afkv2/skills/propose-solution/**
- afkv2/tests/skills/test_propose_solution.py

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The skill asks the critical aspects in this order: entities, relations, keys, constraints, cascade; then API contract and compatibility, data migration, authorization, entity life cycle and states, other teams' modules, large data (PRD §CAT-A)
- [ ] Each fork card is a `debate` item whose body shows the options side by side; the session is one page document `pages/propose-solution-<session id>.json` (SDD §4)
- [ ] A picture of the current state (code area, data or flow) comes before each critical-aspect question (PRD §AC-043)
- [ ] The result is SDD.md + design ADRs in the spec folder; the skill reads only the PRD and grill output on disk and stops naming any missing input and its writer (PRD §AC-002, §AC-003)
- [ ] A second-provider slot exists and is off in P0 (PRD §SK-09; PRD Out of Scope P1)

## Produces
- afkv2/skills/propose-solution/SKILL.md#name: propose-solution — the design skill
- afkv2/skills/propose-solution/scripts/fork_cards.py#def build_fork_card( — debate item with options side by side

## Consumes
- 0008-to-prd-jira-publish afkv2/skills/to-prd/SKILL.md#name: to-prd — the PRD this skill reads

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/propose-solution/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/propose-solution`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_propose_solution.py -q` | CAT-A order; fork card shape has the SDD §4 required fields |
| integration | scripted dry run against recorded engine fakes: a PRD fixture gives a round document with the first CAT-A question after a picture, and a fork card | the skill drives the engine contract |

## Context excerpts
> (PRD §SK-09) | SK-09 | `/afkv2:propose-solution` | critical-aspect questions (CAT-A), top-down draft, fork cards (choice cards with options side by side) on the page; SDD + design ADRs; a slot for a second provider | F-3, K-7, V-9, decision 97 |

> (PRD §CAT-A) Asked in this order: entities, relations, keys, constraints, cascade; then API contract and compatibility, data migration, authorization, entity life cycle and states, other teams' modules, large data (K-7).

> (SDD §4 item row) | kind | decided \| confirm \| debate \| signoff \| info | no | — | — | — | — | |

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0008-to-prd-jira-publish

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

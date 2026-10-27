## Goal
Sync the AFK plugin AGENTS.md harness so the next agent discovers the glossary lifecycle and knows how to use or extend it, settle the candidate staple, and emit the trace matrix. Run `/afk:agents-md` scoped to this feature's net diff, then write `plan/TRACE.md` with every PRD Acceptance Criterion mapped to its subtask, commits, and proving test; flag unsatisfied rows.

## Complexity
standard

## Design refs
- SDD: SDD.md#14-l9--implementation-seams--change-impact — package shared scripts and update existing skill guidance
- ADR: adr/design/0003-separate-ownership-and-delivery-routing.md — repository manifests and glossary ownership remain distinct

## Scope
- AGENTS.md
- skills/afk/AGENTS.md
- skills/utils/glossary/AGENTS.md
- docs/afk/P2P-2067/plan/TRACE.md

## Seams
- use: SDD §14 row "Requirements and glossary skills" — document the requirements entry point (INV-012)
- use: SDD §14 row "Preflight" — document the Ready gate (INV-012)
- use: SDD §14 row "Settlement" — document the final-head gate (INV-012)
- use: SDD §14 row "Other glossary consumers" — document the one facade route (INV-012)
- use: SDD §14 row "Packaging" — point at the shipped shared scripts and spec (INV-012)

## Acceptance
- [ ] The nearest tooling AGENTS.md contains at most 3 dense sentences on invoking or extending the lifecycle and points to key types plus this spec. (SDD §14 row "Packaging")
- [ ] Plugin-root guidance contains exactly one awareness sentence leading to the leaf guidance. (SDD §14 row "Packaging")
- [ ] `/afk:agents-md` decides whether the PRD candidate becomes a staple or records an explicit no-op. (PRD §Implementation Decisions)
- [ ] `plan/TRACE.md` has one row per AC-001 through AC-039 and flags every unsatisfied row. (PRD §Acceptance Criteria)
- [ ] Implements the documentation responsibility implied by SDD §8 row "Command facade" without restating code. (SDD §8)

## Produces
- docs/afk/P2P-2067/plan/TRACE.md#Criterion (verbatim) — acceptance-to-commit and test trace matrix in the plugin change
- skills/utils/glossary/AGENTS.md#AFK glossary lifecycle — lazy-loaded extension guidance

## Consumes
- 0007-command-facade scripts/glossary_lifecycle/cli.py#class GlossaryCommandFacade — shipped invocation surface

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | grep the root awareness pointer and leaf file; enumerate AC-001 through AC-039 against `plan/TRACE.md` | guidance resolves and trace coverage is complete |

## Context excerpts
> (PRD §Implementation Decisions) "Candidate workflow staple: every feature defines terms during requirements, consults scoped terms, and reconciles them after implementation."
>
> (SDD §14 row "Packaging") "Add shared scripts and update existing skill prose."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0001-pure-domain-rules, 0002-repository-access, 0003-local-evidence, 0004-forge-anti-corruption-adapter, 0005-publication-coordination, 0006-application-use-cases, 0007-command-facade

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

## Goal
Implement one application handler per lifecycle command for define, consult, audit, reconcile, gate, and bootstrap, coordinating only through injected domain and port contracts.

## Complexity
complex

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — application use cases coordinate all four aggregates
- ADR: adr/design/0004-reconcile-before-proof.md — Ready and settlement require current reconciliation proof
- ADR: adr/design/0006-strict-solo-owner-decision-control.md — solo-owner evidence accepts only final or reject

## Scope
- scripts/glossary_lifecycle/application.py
- scripts/glossary_lifecycle/tests/test_application.py
- scripts/glossary_lifecycle/tests/fixtures/**

## Seams
- implement: SDD §14 row "Bootstrap and adoption" — require a prerequisite bootstrap and explicit migration path (INV-012)
- use: SDD §14 row "AFK configuration" — load target-branch controls at the pinned merge base (INV-012)
- use: SDD §14 row "Approval read" — authorize finalization only with current-head owner evidence (INV-012)
- use: SDD §14 row "Return to Draft" — route owner rejection to verified Draft state (INV-012)
- use: SDD §14 row "Comment transport" — publish immutable audit and reconciliation records (INV-012)
- use: SDD §14 row "Append-only reconstruction" — derive unresolved blockers from the full record stream (INV-012)
- use: SDD §14 row "Glossary Markdown" — define and reconcile canonical definitions (INV-012)
- use: SDD §14 row "Routing" — resolve areas, glossaries, and owner chains (INV-012)
- use: SDD §14 row "Git and local evidence" — persist pre-Draft evidence and refresh pinned state (INV-012)
- use: SDD §14 row "Semantic provider" — request bounded candidates after exact selection (INV-012)
- use: SDD §14 row "RE-07 prompt" — validate bound human decision evidence (INV-012)

## Acceptance
- [ ] Define, consult, audit, reconcile, gate, and bootstrap each have one typed handler and deterministic result ordering. (SDD §8)
- [ ] Consultation stores RE-01 and RE-03 before design or execution can start. (PRD §Acceptance Criteria)
- [ ] Ready and settlement fail when reconciliation evidence is stale, incomplete, rejected, or overridden only for intermediate work. (PRD §Acceptance Criteria)
- [ ] A repository without a glossary can proceed only through the separate bootstrap lifecycle. (PRD §Acceptance Criteria)
- [ ] Implements the public interface in SDD §8 row "Application use cases" unmodified. (SDD §8)
- [ ] Fixture lifecycle tests cover positive and negative outcomes for AC-001 through AC-039. (PRD §Testing Decisions)

## Produces
- scripts/glossary_lifecycle/application.py#class GlossaryLifecycleApplication — typed lifecycle command handlers

## Consumes
- 0001-pure-domain-rules scripts/glossary_lifecycle/domain.py#class GlossaryDomainRules — values, fingerprints, gates, and replay
- 0002-repository-access scripts/glossary_lifecycle/repository.py#class PinnedRepositoryAdapter — target controls, tracked sources, and definitions
- 0003-local-evidence scripts/glossary_lifecycle/evidence.py#class AtomicEvidenceAdapter — pre-Draft evidence lifecycle
- 0005-publication-coordination scripts/glossary_lifecycle/publication.py#class PublicationCoordinator — immutable forge publication

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/application.py` plus grep the Produces anchor | module compiles and handlers exist |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_application.py` | every command, transition, refusal, and stable result |
| integration | fixture-repository lifecycle matrix from first requirements through settlement | all ports compose and AC-001 through AC-039 remain reachable |

## Context excerpts
> (PRD §Acceptance Criteria) "A repository without a glossary uses a separate prerequisite bootstrap merge request that creates routes, an owning glossary, and owner declarations."
>
> (SDD §8 row "Application use cases") "Coordinate definition, consult, audit, reconcile, gate, and bootstrap | One handler per command | Domain rules and injected ports | All four"
>
> (ADR-0004) "Run reconciliation before computing the proof that permits Ready or settlement."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0001-pure-domain-rules, 0002-repository-access, 0003-local-evidence, 0005-publication-coordination

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

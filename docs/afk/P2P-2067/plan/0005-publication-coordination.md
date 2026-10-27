## Goal
Implement the immutable publication protocol that claims an operation, appends one glossary record, reads it back, checkpoints verified state, and compensates uncertain outcomes without editing history.

## Complexity
complex

## Review
opt-in: resilience, logic-correctness

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — publication coordination owns claim, append, verify, checkpoint, and compensate
- ADR: adr/design/0001-split-definition-and-publication-ledgers.md — forge comments form the append-only evidence ledger

## Scope
- scripts/glossary_lifecycle/publication.py
- scripts/glossary_lifecycle/tests/test_publication.py

## Seams
- implement: SDD §14 row "Comment transport" — namespace glossary records and reconcile by operation ID (INV-012)
- use: SDD §14 row "Forge registry" — publish through complete oldest-first notes and append-only comments (INV-012)
- use: SDD §14 row "Append-only reconstruction" — replay through the canonical codec and reducer (INV-012)

## Acceptance
- [ ] Every run appends a new UTF-8 RE-08 and never edits or deletes an earlier record. (PRD §Acceptance Criteria)
- [ ] An incomplete claim expires after 5 minutes on the provider clock and can be compensated safely. (SDD §10)
- [ ] A write advances only after read-back proves the operation ID and bytes. (SDD §10)
- [ ] Incomplete pagination, uncertain write, edit evidence gap, or malformed record blocks replay. (SDD §9b row "Forge note list and comment write")
- [ ] Implements the public interface in SDD §8 row "Publication coordination" unmodified. (SDD §8)
- [ ] Seam tests assert complete provider note history and surfaced failures. (SDD §14 row "Comment transport")

## Produces
- scripts/glossary_lifecycle/publication.py#class PublicationCoordinator — idempotent append and verification protocol

## Consumes
- 0001-pure-domain-rules scripts/glossary_lifecycle/domain.py#class GlossaryDomainRules — immutable record and replay rules
- 0004-forge-anti-corruption-adapter scripts/glossary_lifecycle/forge.py#class GlossaryForgeAdapter — normalized notes, comment write, actor, and clock

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/publication.py` plus grep the Produces anchor | module compiles and contract exists |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_publication.py` | state machine, replay, lease, and compensation rules |
| integration | publication tests against GitLab and GitHub fixture adapters with uncertain-write and pagination faults | provider history is verified before advance |

## Context excerpts
> (PRD §Acceptance Criteria) "Each audit or reconciliation run posts a new RE-08; no run edits a prior record."
>
> (SDD §8 row "Publication coordination") "Claim, append, verify, checkpoint, and compensate | Publication port | Forge port and codecs | Publication stream"
>
> (ADR-0001) "Keep glossary definitions in Git and publish audit, reconciliation, override, and attestation evidence as append-only merge-request records."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0001-pure-domain-rules, 0004-forge-anti-corruption-adapter

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

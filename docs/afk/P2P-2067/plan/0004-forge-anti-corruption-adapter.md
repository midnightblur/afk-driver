## Goal
Extend every AFK forge kind with provider-independent approval evidence and idempotent Ready/Draft state operations, then expose normalized notes, actors, clocks, and state through one glossary forge port.

## Complexity
complex

## Review
opt-in: resilience, logic-correctness

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — the anti-corruption adapter normalizes provider state
- ADR: adr/design/0005-generic-forge-approval-and-draft-verbs.md — approval and Draft are generic forge capabilities

## Scope
- adapters/forge/*/CONTRACT.md
- adapters/forge/*/forge.sh
- adapters/forge/*/adapter.json
- scripts/glossary_lifecycle/forge.py
- scripts/glossary_lifecycle/tests/test_forge.py
- scripts/tests/test_forge_adapters.py
- providers/CONFORMANCE.md

## Seams
- implement: SDD §14 row "Forge registry" — move manifests, contracts, scripts, tests, and conformance together (INV-012)
- implement: SDD §14 row "Approval read" — normalize current-head approvals with provider evidence IDs (INV-012)
- implement: SDD §14 row "Return to Draft" — make Draft idempotent and verify by read-back (INV-012)

## Acceptance
- [ ] GitLab, GitHub, and no-forge adapters expose the same approval-read and return-to-Draft verbs. (SDD §14 row "Forge registry")
- [ ] Stale, dismissed, superseded, or unprovable approvals fail closed. (PRD §Acceptance Criteria)
- [ ] Already-Draft succeeds, and provider success without matching read-back returns an error. (SDD §9b row "Forge Ready and Draft operations")
- [ ] Forge reads stop after 3 attempts. (SDD §10)
- [ ] Implements the public interface in SDD §8 row "Forge anti-corruption adapter" unmodified. (SDD §8)
- [ ] Seam tests assert provider JSON/text and the observed forge state, not wrapper intermediates. (SDD §14 row "Approval read")

## Produces
- scripts/glossary_lifecycle/forge.py#class GlossaryForgeAdapter — normalized forge port for approvals, notes, actors, clocks, and state
- adapters/forge/github/CONTRACT.md#glossary-approval-read — provider contract for current-head approval evidence
- adapters/forge/gitlab/CONTRACT.md#glossary-return-draft — provider contract for idempotent Draft state

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/forge.py` plus adapter registry and Produces-anchor checks | module and provider surfaces agree |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_forge.py scripts/tests/test_forge_adapters.py` | normalization and error rules |
| integration | provider conformance fixtures for GitLab, GitHub, and none, including pagination and read-back failures | real adapter command envelopes and parity |

## Context excerpts
> (SDD §8 row "Forge anti-corruption adapter") "Normalize change, notes, approvals, actors, clocks, and state | Forge port | Generic forge verbs | Owner decision and publication stream"
>
> (ADR-0005) "Add approval reading and return-to-Draft as generic forge-family capabilities."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

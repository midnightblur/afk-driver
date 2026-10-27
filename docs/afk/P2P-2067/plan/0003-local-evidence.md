## Goal
Implement atomic, digest-checked, common-directory storage for pre-Draft consultation and audit evidence, including safe expiry after proven inactivity.

## Complexity
complex

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — local evidence owns atomic pre-Draft evidence
- ADR: adr/design/0008-pinned-repository-and-atomic-local-evidence.md — storage uses the absolute Git common directory

## Scope
- scripts/glossary_lifecycle/evidence.py
- scripts/glossary_lifecycle/tests/test_evidence.py

## Seams
- implement: SDD §14 row "Git and local evidence" — combine pinned linked-worktree facts with atomic common-directory evidence behavior (INV-012)

## Acceptance
- [ ] A reader sees either the complete old record or the complete new record after flush and atomic replace. (SDD §9b row "Filesystem atomic replace and advisory lock")
- [ ] Lock conflict, replace failure, digest mismatch, or unknown activity parks and never deletes evidence. (SDD §9b row "Filesystem atomic replace and advisory lock")
- [ ] Evidence expires only after at least 30 days and proven inactivity. (SDD §10)
- [ ] Implements the public interface in SDD §8 row "Local evidence" unmodified. (SDD §8)
- [ ] Seam tests assert real Git linked-worktree output and host-visible atomic replace behavior on Windows and Unix. (SDD §14 row "Git and local evidence")

## Produces
- scripts/glossary_lifecycle/evidence.py#class AtomicEvidenceAdapter — evidence port implementation for linked worktrees

## Consumes
- 0002-repository-access scripts/glossary_lifecycle/repository.py#class PinnedRepositoryAdapter — absolute common-directory and worktree facts

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/evidence.py` plus grep the Produces anchor | module compiles and contract exists |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_evidence.py` | digest, expiry, activity, and failure rules |
| integration | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_evidence.py -k "linked_worktree or atomic"` on Windows and Unix runners | pinned common-directory resolution plus host-visible replace, lock-conflict, digest-failure, and unknown-activity output |

## Context excerpts
> (SDD §8 row "Local evidence") "Atomically read, write, and expire pre-Draft evidence | Evidence port | Filesystem implementation | Feature vocabulary run"
>
> (ADR-0008) "Store pre-Draft evidence under the absolute Git common directory with an advisory lock, flush, atomic replace, digest verification, and conservative expiry."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0002-repository-access

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

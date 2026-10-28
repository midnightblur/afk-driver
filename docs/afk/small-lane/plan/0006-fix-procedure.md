## Goal
Write the shared fix procedure: one markdown file beside `/afk:fix` that every agent caller reads in place to fix a failing check, finding or scenario inside its own branch — re-run once, record caller, input and failing path, fix test-first, run every tier, and return one of seven results. Repoint the lesson-capture links (escape analysis, workflow feedback) at it.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "shared fix procedure, read in place"
- SDD: SDD.md#§6 L5 — Domain Model — invariant "A failing check that passes on one re-run is never fixed by a code change and never parks a run"
- SDD: SDD.md#§8 L7 — Module Decomposition — row "shared fix procedure (beside fix)"
- SDD: SDD.md#§10 NFRs — row "Re-runs of a failure before diagnosing"
- ADR: adr/design/0001-in-place-fix-is-a-shared-procedure-file.md — procedure file read in place; seven results; `flaky` handling

## Scope
- skills/afk/fix/IN-PLACE-FIX.md
- skills/afk/fix/SKILL.md
- skills/afk/fix/ESCAPE-ANALYSIS.md
- skills/afk/fix/WORKFLOW-FEEDBACK.md
- skills/afk/lessons/LEDGER-FORMAT.md
- AGENTS.md

## Seams
- implement: shared fix procedure from `/afk:fix` phases — the new in-place procedure file (INV-022)
- implement: lesson capture links: `ESCAPE-ANALYSIS`, `WORKFLOW-FEEDBACK` — repointed at the procedure file (INV-022)

## Acceptance
- [ ] The procedure takes the failing check, finding or scenario the caller holds and re-runs the failure once before diagnosing; a failure that passes on that re-run returns `flaky` and changes no product code (PRD AC-029)
- [ ] Before changing code, the procedure records the caller, the input and the reachable failing path (SDD §14 row "shared fix procedure from `/afk:fix` phases")
- [ ] The procedure fixes test-first, runs every tier, and returns exactly one of `fixed`, `fail`, `blocked`, `design_conflict`, `needs_decision`, `adversary_fail`, `flaky` (SDD §3)
- [ ] An in-place fix never commits, pushes, opens a change or writes a ticket, and returns no diagnosis verdict; the no-commit rules of the fix skill move into the procedure (PRD AC-022)
- [ ] The procedure keeps escape analysis, spec reconciliation and the workflow lesson (PRD AC-023)
- [ ] The procedure names none of its callers (SDD §8)
- [ ] Escape analysis, workflow feedback, the lesson ledger format and `AGENTS.md` point at the procedure file instead of fix phases; workflow feedback uses the slice or finding id; the miss-class mapping pair moves together (SDD §14 row "lesson capture links: `ESCAPE-ANALYSIS`, `WORKFLOW-FEEDBACK`")
- [ ] Implements the public interface of SDD §8 row "shared fix procedure (beside fix)" unmodified (SDD §8)
- [ ] Conforms to ADR-0001 design — no silent pattern substitution (design ADR-0001)

## Produces
- skills/afk/fix/IN-PLACE-FIX.md#In-place fix results — the seven results and what each means for a caller

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged` (skill registry, genericity); `bash hooks/wiring-gate.sh`; grep the ## Produces anchor | prose gates pass; the procedure is reachable from its pointers |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh` (lesson append and digest), on Windows and WSL | lesson lockstep and everything else unchanged |

## Context excerpts
> (SDD §3) | shared fix procedure, read in place | an agent caller fixing inside its own branch | a human-invoked fix (goes through `/afk:fix`) | the failing check, finding or scenario the caller holds | `fixed` | `fail`, `blocked`, `design_conflict`, `needs_decision`, `adversary_fail`, `flaky` (ADR-0001) | re-runs the failure once before diagnosing; the caller's loop decides retries | compatible: the pointer moves from the skill to the file; `flaky` is new: every caller counts the check as passed for that run and writes one journal line naming it and both runs; no new executor status |
> (SDD §8) | shared fix procedure (beside fix) | in-place fix; serves the PRD's "return in place" (M2) | failing check, finding or scenario in → one of 7 results | tiers, `tdd` | — |
> (SDD §14 row "shared fix procedure from `/afk:fix` phases") INV-022: fix phases incl. escape analysis, spec reconciliation, workflow lesson | new file beside fix: re-run once (`flaky`), records caller, input, failing path; test-first; every tier; 7 results | INV-022: in-place callers `execute/SKILL.md:67,77,93,123`, `preflight/SKILL.md:99,125`, `bug/FIXER-PROMPT.md:29` (goes with `/afk:bug`); only `design_conflict` is routed today (`execute:67`); `grill-requirements/ROUND.md:162`, `review/checklists/refactor-safety.md:10`, `FRESHNESS.md:53`, `AGENTS.md:94`, `README.md:480,698,741` | six results map to existing statuses, `flaky` counts as passed with one journal line (§3); lesson lockstep (6 miss classes, unvalidated: `lesson-append.sh:59`); `fix/SKILL.md:14,107,110` no-commit rules move with the procedure
> (SDD §14 row "lesson capture links: …") INV-022: links point at fix phases (`AGENTS.md:153`, lesson `LEDGER-FORMAT.md:79-88`) | point at the procedure file; workflow feedback uses the slice or finding id | INV-022: lesson ledger lockstep | miss-class mapping pair moves together
> (PRD AC-022) An in-place fix never commits, pushes, opens a merge request or writes a ticket. It returns today's outcomes and no diagnosis verdict.
> (PRD AC-023) A fix keeps escape analysis, spec reconciliation and the workflow lesson in both modes.

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

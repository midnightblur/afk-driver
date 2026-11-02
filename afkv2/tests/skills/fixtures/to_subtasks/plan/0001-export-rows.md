## Goal
The export writes one row per order.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — the one module
- ADR: adr/design/0001-join-table-for-export-runs.md — how a run links

## Scope
- src/export.py
- tests/test_export.py

## Seams
(none)

## Acceptance
- [ ] The export writes one row per order. (PRD §AC-001)
- [ ] One day with 2 orders gives 2 rows. (PRD §WE-01; SDD §8)

## Produces
- src/export.py#def export_rows_for_day( — the rows of one day

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `git grep -n export_rows src/export.py` | the symbol exists |
| unit | `git grep -n one_row tests/test_export.py` | one row per order |

## Context excerpts
> (PRD §AC-001) The export writes one row per order.
> (ADR-0001 design) A join table keeps every run.

## Parent PRD
specs/PROJ-1/PRD.md

## Parent SDD
specs/PROJ-1/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in the SDD or an ADR is wrong, stop.

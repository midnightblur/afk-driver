## Goal
A clerk exports the orders of one day.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — the one module

## Scope
- src/endpoint.py

## Seams
(none)

## Acceptance
- [ ] The endpoint answers with the rows of the day. (PRD §AC-001; SDD §8)

## Produces
- src/endpoint.py#def export_endpoint_for_day( — the endpoint

## Consumes
- 0001-export-rows src/export.py#def export_rows_for_day( — the rows of one day

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `git grep -n export_endpoint src/endpoint.py` | the symbol exists |
| unit | `git grep -n export_rows src/export.py` | the endpoint has its rows |
| api | not applicable: this repository has no running app | the endpoint answers |

## Context excerpts
> (PRD §AC-001) The export writes one row per order.

## Parent PRD
specs/PROJ-1/PRD.md

## Parent SDD
specs/PROJ-1/SDD.md

## Blocked by
- 0001-export-rows

## Conflict procedure
If a binding decision in the SDD or an ADR is wrong, stop.

# 0016-dogfood-run

## Goal
Prove the merged chain by building `/afkv2:gc` with the installed beta, on Claude
and on Codex, instead of a toy repository (owner, 2026-11-02). Run setup and the
Codex live checks for real on the owner's machine, publish once to a throwaway
Jira ticket, and record every result.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — all seams with the real producers
- SDD: SDD.md#§9b External Seams & Failure Affordance — every row on real output
- SDD: SDD.md#§13 Open Questions — the 4 live checks

## Scope
- docs/afk/afkv2/plan-s4/DOGFOOD-RUN.md

## Seams
- use: v1 rule block written by install_block — the real setup run on the owner's machine (INV-004)
- use: v1 PRD block written by build_description — the live publish on the D-4 test ticket (INV-002)

## Acceptance
- [ ] Precondition: the S1, S2 and S3 pull requests are merged into `feat/afkv2`, the tag `afkv2-2.0.0-beta.1` exists, and the beta is installed from it on Claude and on Codex
- [ ] The owner-run Codex live checks passed: hook text in context after the trust review and after a compaction; a page answer after 10 minutes reaches the agent (PRD §AC-010, §AC-012, §AC-044)
- [ ] Setup on the owner's machine proves the hook, moves the v1 stubs, switches the plugins and installs lavish-axi 0.1.80; switch-back runs once and setup runs again (PRD §AC-015, §AC-016, §AC-017)
- [ ] Each `/afkv2:gc` ticket reaches a Draft change with green local tests, one on Claude and one on Codex, with a human who answers the grill and approves the plan; any other end state fails the run (PRD §AC-001)
- [ ] The PRD publish on the D-4 test ticket: a short section before and after the block stays unchanged; a v1-style block is replaced; read-back matches; Jira shows the long description (PRD §AC-052, §AC-057, §AC-059; SDD §9b row "Jira REST")
- [ ] The run is recorded in `docs/afk/afkv2/plan-s4/DOGFOOD-RUN.md`: each step, its provider, its result, and every failure with its owner

## Produces
- docs/afk/afkv2/plan-s4/DOGFOOD-RUN.md#Dogfood run — the run record

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python afkv2/scripts/plugin_check.py` exit 0 on the merged tree; `rg -F "Dogfood run" docs/afk/afkv2/plan-s4/DOGFOOD-RUN.md` | the merged plugin passes its check |
| unit | CI runs `afkv2/tests` on each Draft change | the tests stay green on real producers |
| integration | the dogfood run itself on Claude and on Codex, per DOGFOOD-RUN.md | AC-001 end to end |

## Context excerpts
> (PRD §AC-001) The dogfood run passes when `/afkv2:gc`, built with the installed beta from GitHub issues on this repository, reaches a Draft change with green local tests, on Claude and on Codex, with a human who answers the grill and approves the plan. Any other end state fails the run.

> (PRD Testing Decisions) Jira publish: proven on a throwaway Jira test ticket next to the dogfood run; the ticket is closed afterward.

> (PRD Further Notes, Parked) Q26: the owner gives the demo ticket by day 5.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
(none)

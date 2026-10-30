# 0016-chain-smoke-run

## Goal
Run the chain smoke run (AC-001) on day 4, after the S1, S2 and S3 pull requests
merged into `feat/afkv2`: re-run each session's skill tests against the real
engine and ports, run setup for real on the owner's machine, then take one
written test ticket on the toy repository through the whole chain on Claude and
on Codex, with the Jira publish on the D-4 test ticket.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — all seams with the real producers
- SDD: SDD.md#§9b External Seams & Failure Affordance — every row on real output
- SDD: SDD.md#§13 Open Questions — the 4 live checks

## Scope
- afkv2/tests/smoke/**
- docs/afk/afkv2/plan-s4/SMOKE-RUN.md

## Seams
- use: v1 rule block written by install_block — the real setup run on the owner's machine (INV-004)
- use: v1 PRD block written by build_description — the live publish on the D-4 test ticket (INV-002)

## Acceptance
- [ ] Precondition: the S1, S2 and S3 pull requests are merged into `feat/afkv2`, and the owner named the toy repository, the written test ticket and the D-4 Jira test project (PLAN.md "Inputs")
- [ ] Every S2 and S3 skill test that used a recorded fake passes against the real engine and the real ports (SDD §3 caption)
- [ ] The owner-run Codex live checks of plan-s1 passed: hook text in context after the trust review and after a compaction; a page answer after 10 minutes reaches the agent (PRD §AC-010, §AC-012, §AC-044)
- [ ] Setup on the owner's machine proves the hook, removes the v1 block, moves the v1 stubs, switches the plugins and installs lavish-axi 0.1.80; switch-back is rehearsed on a temp copy first (PRD §AC-015, §AC-016, §AC-017)
- [ ] The test ticket reaches a Draft change with green local tests, on Claude and on Codex, with a human who answers the grill and approves the plan; any other end state fails the run (PRD §AC-001)
- [ ] The PRD publish on the D-4 test ticket: a short section before and after the block stays unchanged; a v1-style block is replaced; read-back matches; Jira shows the long description (PRD §AC-052, §AC-057, §AC-059; SDD §9b row "Jira REST")
- [ ] The run is recorded in `docs/afk/afkv2/plan-s4/SMOKE-RUN.md`: each step, its provider, its result, and every failure with its owner

## Produces
- docs/afk/afkv2/plan-s4/SMOKE-RUN.md#Chain smoke run — the run record

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `afk-python afkv2/scripts/plugin_check.py` exit 0 on the merged tree; `rg -F "Chain smoke run" docs/afk/afkv2/plan-s4/SMOKE-RUN.md` | the merged plugin passes its check |
| unit | `afk-python -m pytest afkv2/tests -q` on the merged tree (the afkv2 tree is the changed module) | every session's tests against the real producers |
| integration | the chain run itself on Claude and on Codex, per SMOKE-RUN.md | AC-001 end to end |

## Context excerpts
> (PRD §AC-001) A chain smoke run passes when one written test ticket on the toy repository reaches a Draft change with green local tests, on Claude and on Codex, with a human who answers the grill and approves the plan. Any other end state fails the run.

> (PRD Testing Decisions) Jira publish: proven on a throwaway Jira test ticket during the chain smoke run (D-4).

> (PRD Further Notes, Parked) Q26: the owner gives the demo ticket by day 5.
> D-4: the owner names the Jira project for the throwaway test ticket by day 4.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

# 0012-smoke-api — contract checks in the feature's black-box acceptance file

## Goal
Author the integrated contract smoke specs for setup-per-repo: one test per VERIFICATION-PLAN.md API scenario (A1–A22) in the same `scripts/tests/test_setup_per_repo_acceptance.py` the journey subtask created, run by /afk:smoke-test as the gate. A contract check here drives one command, hook or guard rule and asserts its real exit status and printed lines, success and refusal, using the sandbox fixtures that file already holds. Read the black-box pattern of `scripts/tests/test_protected_branch_acceptance.py` and the plan's header first; author accordingly.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — every contract-table row
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — the module rows with no §3 row (A13, A14, A17–A22)

## Scope
- scripts/tests/test_setup_per_repo_acceptance.py

## Seams
(none — no SDD seam register row is implemented here; the checks assert the contracts other subtasks built)

## Acceptance
- [ ] Authored per the black-box pattern of `scripts/tests/test_protected_branch_acceptance.py` (read first; followed, not improvised) and reusing the journey file's sandbox fixtures (VERIFICATION-PLAN.md header)
- [ ] One test per VERIFICATION-PLAN.md API scenario A1–A22, each tracing to its SDD §3 row or §14 row and PRD criterion, each with its persistence refetch (VERIFICATION-PLAN.md ## API Scenarios)
- [ ] Asserts the REAL exit status and printed lines (success AND refusal), not an idealized answer: `WORKTREE_PATH=` and `ERROR=` lines, the guard's deny JSON, `configuration is valid` and each warning line, `account not available` (SDD §3)
- [ ] Every protected surface has its refused-agent test: the agent detector on with a target outside `<root>/<short name>`, an inline variable, a secret step without a terminal (SDD §5 AuthZ)
- [ ] Time budgets are reported, never asserted: tests fail on counts (no new file read, no network call) (GRILL-LOG Verification grill C-23)
- [ ] No API scenario is env-limited; every one passes on Windows and on Linux (VERIFICATION-PLAN.md ## API Scenarios; SDD §10 row "platforms")

## Produces
- scripts/tests/test_setup_per_repo_acceptance.py#def test_a1_setup_walk_steps — the first contract check; A2–A22 follow as `test_a<n>_…`

## Consumes
- 0011-smoke-e2e scripts/tests/test_setup_per_repo_acceptance.py#def test_u1_setup_over_several_repositories — the acceptance file and its sandbox fixtures

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier, plus `afk-python -m pytest scripts/tests/test_setup_per_repo_acceptance.py --collect-only -q` | the file loads; every contract check collects |
| unit | `unit` tier | every contract check goes green locally |

## Context excerpts
> (VERIFICATION-PLAN.md header) An "API scenario" is a contract check of one command, hook or guard rule: its exit status and its printed lines. Each test works in a sandbox: a temporary home folder, temporary git repositories, and stand-in `gh`, `glab` and Jira on `PATH`.

> (GRILL-LOG Verification grill C-23) A test fails on counts (no new file read, no network call); the 50, 10 and 20 ms times are only reported in the informational bench.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer, 0002-settings-reader, 0003-repository-list, 0004-placement, 0005-worktree-creator, 0006-worktree-guard, 0007-forge-account, 0008-jira-sign-in, 0009-settings-writer, 0010-setup-walk, 0011-smoke-e2e

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

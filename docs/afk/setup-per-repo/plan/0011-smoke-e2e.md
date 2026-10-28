# 0011-smoke-e2e — journey tests in the feature's black-box acceptance file

## Goal
Author the integrated journey smoke specs for setup-per-repo: one test per VERIFICATION-PLAN.md UI journey (U1–U11) in `scripts/tests/test_setup_per_repo_acceptance.py`, plus one skipped-with-reason test per live-run row (L1–L7), run by /afk:smoke-test as the gate. This repository has no browser suite: a journey is an end-to-end flow through the entry points a developer or a harness reaches, driven in a sandbox home with temporary git repositories and stand-in `gh`, `glab` and Jira on PATH. Read the black-box pattern of `scripts/tests/test_protected_branch_acceptance.py` and the plan's header first; author accordingly.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — the contract table every journey drives
- SDD: SDD.md#§9b External Seams & Failure Affordance — the live-only rows behind L1–L7

## Scope
- scripts/tests/test_setup_per_repo_acceptance.py
- scripts/tests/conftest.py

## Seams
(none — no SDD seam register row is implemented here; the journeys drive the seams other subtasks built)

## Acceptance
- [ ] Authored per the black-box pattern of `scripts/tests/test_protected_branch_acceptance.py` (read first; followed, not improvised): drives entry points only, checks only what is visible outside (VERIFICATION-PLAN.md header)
- [ ] One test per VERIFICATION-PLAN.md UI journey U1–U11, each named for its journey and tracing to its PRD User Story or criteria, each with its persistence reverify (VERIFICATION-PLAN.md ## UI Journeys)
- [ ] An agent session is the agent detector switched on; the developer is the detector switched off; the test plays the agent and passes the developer's answers to the scripts setup runs (VERIFICATION-PLAN.md header)
- [ ] L1–L7 are present as tests skipped with the live-run reason and flagged env-limited in the gate table, not left to fail the gate; L7 skips with the reason when no second Windows drive exists (VERIFICATION-PLAN.md L1–L7)
- [ ] AC-060 is covered for the commit gate and cleanup on an existing worktree outside the root; the rest of the set stays open per VERIFICATION-PLAN.md Gaps surfaced until the human enumerates or narrows it (PRD §Existing worktrees AC-060)
- [ ] Every runnable journey passes on Windows and on Linux (SDD §10 row "platforms")

## Produces
- scripts/tests/test_setup_per_repo_acceptance.py#def test_u1_setup_over_several_repositories — the first journey; U2–U11 and L1–L7 follow as `test_u<n>_…` / `test_l<n>_…`

## Consumes
- 0010-setup-walk skills/afk/setup/scripts/setup_walk.py#def walk_repositories( — the walk U1, U5, U6, U9, U10 drive
- 0005-worktree-creator scripts/create-worktree#ERROR=worktree root: — the refusal U2 and U10 assert
- 0006-worktree-guard hooks/lib/worktree_placement_rule.py#refused to create a worktree outside the worktree root — the deny text U2 asserts

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier, plus `afk-python -m pytest scripts/tests/test_setup_per_repo_acceptance.py --collect-only -q` | the file loads; every journey collects |
| unit | `unit` tier | the runnable (non-env-limited) journeys go green locally |

## Context excerpts
> (VERIFICATION-PLAN.md header) This repository has no running app, no browser suite and no REST suite. A "UI journey" here is an end-to-end flow through the entry points a developer or a harness reaches. An "API scenario" is a contract check of one command, hook or guard rule: its exit status and its printed lines. Each test works in a sandbox: a temporary home folder, temporary git repositories, and stand-in `gh`, `glab` and Jira on `PATH`. The test plays the agent and passes the developer's answers to the scripts setup runs. An agent session is the agent detector switched on; the developer is the detector switched off.

> (PRD §Testing Decisions) Worktree tests cut real worktrees in temporary repositories: inside a checkout, beside it, under a root, with a relative or `~` path, with a space in the path. No test covers a nested worktree today.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer, 0002-settings-reader, 0003-repository-list, 0004-placement, 0005-worktree-creator, 0006-worktree-guard, 0007-forge-account, 0008-jira-sign-in, 0009-settings-writer, 0010-setup-walk

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

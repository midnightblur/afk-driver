# 0015-autopilot-execute

## Goal
Write `/afkv2:autopilot` and the execute step it runs per subtask: refuse a plan
that fails the check, lacks the division approval or is a v1 plan; walk the plan
on the run branch one subtask at a time, each in a fresh subagent, TDD, commits
often, one Draft change; decide and record two-way doors; park one-way doors
with their dependents; run code-review per subtask.

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row plan contract (S3 reads); "Frozen on day 1" row plan contract
- SDD: SDD.md#§4 L3 — Data Architecture — row Plan contract
- ADR: adr/requirements/0006-spec-folder-vs-run-branch.md

## Scope
- afkv2/skills/autopilot/**
- afkv2/skills/execute/**
- afkv2/tests/skills/test_autopilot.py
- afkv2/tests/skills/test_execute.py
- afkv2/tests/autopilot/**   # fakes + fixtures for this slice only

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] autopilot refuses to start when the plan check fails or the PLAN.md header has no `> Division: approved <date>` line, and lists every failure (PRD §AC-060; PLAN.md decision D-S-2)
- [ ] `check_start` calls the cross-session input `check_plan` from 0010-to-subtasks-skill (plan-s2, `afkv2/skills/to-subtasks/scripts/check_plan.py#def check_plan(`). Until that pull request merges, tests run against a recorded fake under `afkv2/tests/autopilot/fakes/`, built from the 0010 contract (one JSON object that lists every failure; exit 0, 1 or 2; SDD §3 envelope) and the `> Division: approved <date>` line. No file goes under `afkv2/tests/skills/fakes/`: S2 owns that path (PRD §AC-060; SDD §3; PLAN.md decision D-S-2)
- [ ] It refuses a v1 plan folder and names the two options: finish on v1, or slice again with `/afkv2:to-subtasks` (PRD §AC-005)
- [ ] It parses the frozen contract sections (v1 subtask contract sections without materialized seams) (SDD §8 "Frozen on day 1" row "plan contract")
- [ ] Each subtask runs in a fresh subagent with TDD; a finished subtask has its own commits on the run's feature branch (PRD §AC-061)
- [ ] Plan, journal, decision ledger and review telemetry live in `plan/` on `<feature branch>-run`; code and spec stay on the feature branch (PRD §AC-071; PLAN.md decision D-S-1)
- [ ] A two-way door is decided and recorded in the decision ledger; a one-way door parks its subtask and every dependent, and the park is recorded for retro (PRD §AC-062)
- [ ] It pushes to one Draft change through `/afkv2:create-change-request` and runs `/afkv2:code-review` per subtask (PRD §SK-12)
- [ ] autopilot never starts a subtask whose gates cannot run in this repository: the start gate refuses before any work. A unit test proves it (SDD §7 v1 defects)
- [ ] As the orchestrator, autopilot rules a reversible plan call that stays inside the approved goal when an executor stops on it (a subtask's Scope, which subtask owns a file, the order of two subtasks), records the ruling in the decision ledger, sends it to the executor, and reports it to the human after; an executor never changes its own Scope; an acceptance-criterion change, a one-way door or a cost trade-off still parks. A unit test proves it: an executor park on a Scope call is ruled and recorded; an acceptance-criterion change still parks (PRD §AC-072)

## Produces
- afkv2/skills/autopilot/SKILL.md#name: autopilot — the plan walker
- afkv2/skills/execute/SKILL.md#name: execute — one subtask end to end
- afkv2/skills/autopilot/scripts/start_gate.py#def check_start( — plan check + approval + v1-plan refusal

## Consumes
- 0012-forge-tracker-port afkv2/ports/forge/cli.py#def forge_main( — push and change commands
- 0013-code-review-skill afkv2/skills/code-review/SKILL.md#name: code-review — per-subtask review
- 0014-change-request-ci-watch afkv2/skills/create-change-request/SKILL.md#name: create-change-request — the one Draft change

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/{autopilot,execute}/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/autopilot afkv2/skills/execute`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_autopilot.py -q` | start gate: failed check, missing approval, v1 plan, a gate the repository cannot run; park propagation to dependents |
| unit | `afk-python -m pytest afkv2/tests/skills/test_execute.py -q` | fresh subagent per subtask, TDD order, own commits; an executor park on a Scope call is ruled and recorded, an acceptance-criterion change still parks |
| integration | dry run on a fixture plan with 3 subtasks in a temp repository with a `-run` branch: one done, one parked as a one-way door with its dependent parked, ledger and journal lines written on the run branch only | the run-branch layout and park rule on real git |

## Context excerpts
> (PRD §SK-12) | SK-12 | `/afkv2:autopilot` | walks the plan one subtask at a time, a fresh subagent each; TDD (test-driven development); commits often; pushes to one Draft change; records two-way doors; rules reversible plan calls for its executors (AC-072); parks one-way doors with dependents | K-9, decision 23, 45 |

> (PRD §AC-005) v2 refuses a v1 plan folder and names the two options: finish on v1, or slice again with `/afkv2:to-subtasks`.

> (PRD §AC-060) `/afkv2:autopilot` refuses to start when the plan check fails or the division is not approved, and it lists every failure.

> (PRD §AC-061) Each subtask runs in a fresh subagent. A finished subtask has its own commits on the run's branch.

> (PRD §AC-062) A two-way door is decided and recorded in the decision ledger. A one-way door parks its subtask and every dependent subtask, and the park is recorded for retro.

> (PRD §AC-072) `/afkv2:autopilot`, as the orchestrator, rules a reversible plan call that stays inside the approved goal when an executor stops on it: a subtask's Scope, which subtask owns a file, the order of two subtasks. It records the ruling in the decision ledger, sends it to the executor, and reports it to the human after. The rule lives in the autopilot workflow, not in the core behaviors: an executor never changes its own Scope. A change to an acceptance criterion, a one-way door, or a cost trade-off still parks for the human (owner, 2026-10-30).

> (SDD §8 Frozen on day 1) | plan contract | v1 subtask contract sections without materialized seams; one format file + check script | S2 | S3 execute |
> (SDD §7 v1 defects) | a mandatory gate that needs a running app parks every subtask of a repository with no app, and the run finds it only after the work and the review | a gate that needs something the repository does not have is decided when the plan is cut: the plan names it not applicable, or the plan check refuses; autopilot never starts a subtask whose gates cannot run | 0010 plan-check test; 0015 start-gate test |

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0012-forge-tracker-port
- 0013-code-review-skill
- 0014-change-request-ci-watch

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

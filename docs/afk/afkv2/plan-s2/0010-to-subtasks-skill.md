# 0010-to-subtasks-skill

## Goal
Write `/afkv2:to-subtasks`: slice PRD + SDD into `plan/` (PLAN.md and one
contract per subtask, cited) on the run branch, the plan contract format file
(v1 subtask contract sections without materialized seams), the plan check script
(v1 validate_plan checks (a) graph and (b) anchors), and the division approval.

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row plan contract; "Frozen on day 1" row plan contract
- SDD: SDD.md#§4 L3 — Data Architecture — row Plan contract
- ADR: adr/requirements/0006-spec-folder-vs-run-branch.md

## Scope
- afkv2/skills/to-subtasks/**
- afkv2/tests/skills/test_to_subtasks.py
- afkv2/tests/skills/fakes/*
- afkv2/tests/skills/fixtures/**

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The format file states the v1 subtask contract sections without materialized seams; `/afkv2:autopilot` parses exactly these headings (SDD §8 "Frozen on day 1" row "plan contract")
- [ ] The check script runs the v1 checks (a) contract graph and (b) anchor quality and answers one JSON object with every failure listed; exit 0, 1 or 2 (GRILL-LOG A-5; SDD §3 envelope)
- [ ] The plan is written to `plan/` on the run branch `<feature branch>-run` (an orphan branch); no spec-folder file goes on the run branch (PRD §AC-071; PLAN.md decision D-S-1)
- [ ] After the developer approves the division on the page, the skill writes the PLAN.md header line `> Division: approved <YYYY-MM-DD>`; without it the plan is not approved (PRD §AC-060; PLAN.md decision D-S-2)
- [ ] Every subtask contract cites PRD and SDD sections; acceptance bullets end with a resolving citation (PRD §SK-10)
- [ ] The skill reads only PRD.md, SDD.md and ADRs on disk and stops naming any missing input and its writer (PRD §AC-002, §AC-003)
- [ ] The check script refuses a gate that needs something the repository does not have (for example a running app), unless the plan names that gate not applicable; one unit test proves this refusal (SDD §7 v1 defects)
- [ ] The check script refuses a check path that no Scope in the subtask's own chain owns (its Scope or the Scope of a subtask it waits on); one unit test proves this refusal (SDD §7 v1 defects)
- [ ] A gate the repository cannot run is named by the check cell of its `## Verification` row, which reads `not applicable: <reason>` (the form S3 0015 reads: `NOT_APPLICABLE` in `afkv2/skills/autopilot/scripts/start_gate.py`, plan-s3 D-70). The skill emits this form, and the check script refuses another form or an empty reason. A cannot-run gate is a live tier (`api`, `e2e`, `browser`, `e2e/browser`, `ui-e2e`) when the repository has no app, or a bare program in a code span that is not on PATH (plan-s3 D-71). One unit test each for the accepted form and the refused forms (SDD §7 v1 defects)

## Produces
- afkv2/skills/to-subtasks/SKILL.md#name: to-subtasks — the slicing skill
- afkv2/skills/to-subtasks/SUBTASK-CONTRACT.md### Conflict procedure — the frozen contract sections
- afkv2/skills/to-subtasks/scripts/check_plan.py#def check_plan( — graph + anchor check
- afkv2/skills/to-subtasks/scripts/check_plan.py#Division: approved — the approval line the check reads

## Consumes
- 0009-propose-solution-skill afkv2/skills/propose-solution/SKILL.md#name: propose-solution — the SDD this skill reads

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/to-subtasks/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/to-subtasks`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_to_subtasks.py -q` | check (a)/(b) findings on fixture plans; approval line parse; run-branch name; one refusal test each for a gate the repository cannot run and for a check path no Scope in the chain owns |
| integration | slice a fixture PRD + SDD into a temp repo: plan lands on `<branch>-run` only, check exit 0, approval line written after a fake page mark | the plan contract S3 reads |

## Context excerpts
> (PRD §SK-10) | SK-10 | `/afkv2:to-subtasks` | `plan/` with PLAN.md and one contract per subtask, cited to the PRD and SDD; plan check script; waits for the division approval | K-8, A-5 |

> (PRD §AC-060) `/afkv2:autopilot` refuses to start when the plan check fails or the division is not approved, and it lists every failure.

> (PRD §AC-071) The run branch holds only run files: the plan folder, journal, decision ledger and review telemetry. No spec-folder file is on the run branch.

> (SDD §8 Frozen on day 1) | plan contract | v1 subtask contract sections without materialized seams; one format file + check script | S2 | S3 execute |

> (GRILL-LOG A-5) Settled: A-5 plan check must pass and division approved before autopilot · decided-by agent R-1 · accepted 2026-10-29 · spec: decision 26; v1 validate_plan checks (a)(b) · reverse: make the check a warning

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0009-propose-solution-skill

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

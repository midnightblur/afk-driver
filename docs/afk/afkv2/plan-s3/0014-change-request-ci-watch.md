# 0014-change-request-ci-watch

## Goal
Write `/afkv2:create-change-request` and the CI watch: open the Draft change
with its description, one request per person, proofs, the mergeability case and
one self-critique; watch CI in the background after each push; mark Ready at
ship when review is settled and CI is green. The agent never merges.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — forge row
- ADR: adr/design/0007-forge-port-python-rewrite.md

## Scope
- afkv2/skills/create-change-request/**
- afkv2/tests/skills/test_change_request.py

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The change opens as Draft with a description, one request per person, proofs, the mergeability case and one self-critique (PRD §SK-14)
- [ ] CI watch runs in the background after each push and reports the result without blocking work; a red CI on the feature branch is allowed during work (PRD §AC-065)
- [ ] At ship, with review settled and CI green, the agent marks the change Ready; ship is refused while CI is red; the agent never merges (PRD §AC-064, §AC-065)
- [ ] All forge calls go through the forge port and behave the same on GitHub and GitLab (PRD §AC-066)

## Produces
- afkv2/skills/create-change-request/SKILL.md#name: create-change-request — the change-request skill
- afkv2/skills/create-change-request/scripts/ci_watch.py#def watch_ci( — background CI watch
- afkv2/skills/create-change-request/scripts/ci_watch.py#def mark_ready_if_green( — Ready only on settled review + green CI

## Consumes
- 0012-forge-tracker-port afkv2/ports/forge/forge_cli.py#def forge_main( — change and CI commands

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/create-change-request/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/create-change-request`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_change_request.py -q` | Ready refused on red CI or open review; no merge command reachable |
| integration | on this session's own Draft pull request: the watch reads the real CI state after a push and reports it | the forge port's CI answer on real output |

## Context excerpts
> (PRD §SK-14) | SK-14 | `/afkv2:create-change-request` + CI watch | Draft change, description, one request per person, proofs, mergeability case, one self-critique; background CI watch after each push; Ready at ship | K-11, K-12, K-13, decision 31 |

> (PRD §AC-064) The change opens as Draft. At ship, with review settled and CI green, the agent marks it Ready. The agent never merges.

> (PRD §AC-065) CI watch reports the CI result without blocking work. A red CI on the feature branch is allowed during work. Ship is refused while CI is red.

## Parent PRD
docs/afk/afkv2/PRD.md

## Parent SDD
docs/afk/afkv2/SDD.md

## Blocked by
- 0012-forge-tracker-port

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` (this plan folder's `DECISIONS.md`) and implemented; a
one-way door or a tie exits `design_conflict` quoting the SDD section + the
conflict. Never override off the record. Parked conflicts route back to
`/afk:grill-solution` for a superseding ADR.

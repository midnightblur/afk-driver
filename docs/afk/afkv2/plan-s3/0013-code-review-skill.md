# 0013-code-review-skill

## Goal
Write `/afkv2:code-review`: pick the review concerns per subtask, fix critical
and high findings, post medium and low findings on the change through the forge
port, and stop after round 3.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — forge row
- ADR: adr/design/0007-forge-port-python-rewrite.md

## Scope
- afkv2/skills/code-review/**
- afkv2/tests/skills/test_code_review.py

## Seams
(none — this slice touches no SDD §14 seam row; its §9b rows are in ## Acceptance and the PLAN.md seam register)

## Acceptance
- [ ] The skill picks concerns per subtask from the subtask's contract and diff (PRD §SK-13)
- [ ] Critical and high findings are fixed; medium and low findings are posted on the change through the forge port (PRD §AC-063)
- [ ] The review stops after round 3 whatever is left, and reports what is left (PRD §AC-063)
- [ ] At most 3 review rounds; only critical and high findings are fixed; the rest stay on the change request as advice. A unit test proves it (SDD §7 v1 defects)
- [ ] A critical or high fix made in round 3, or a fix made for a ruling after the review stopped, gets one delta check: it reads only the fix commits, and it may only confirm or reopen the findings or rulings those commits answer (PRD §AC-063)
- [ ] A reopened finding or ruling gets one more fix; when the next delta check reopens it, or the fix cannot be made, the change parks for the human. A unit test proves each path (PRD §AC-063)

## Produces
- afkv2/skills/code-review/SKILL.md#name: code-review — the review skill
- afkv2/skills/code-review/scripts/review_rounds.py#def next_round( — round counter with the cap of 3
- afkv2/skills/code-review/scripts/review_rounds.py#def delta_record( — delta check: confirm or reopen only, park on the second failure

## Consumes
- 0012-forge-tracker-port afkv2/ports/forge/forge_cli.py#def forge_main( — posts findings on the change

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | every `afkv2/skills/code-review/**/SKILL.md` has Agent Skills frontmatter (`name`, `description`); `afk-python -m compileall -q afkv2/skills/code-review`; `rg -F` each ## Produces anchor | skill files parse; declared symbols present |
| unit | `afk-python -m pytest afkv2/tests/skills/test_code_review.py -q` | round cap 3; severity routing: fix vs post; delta check scope, one more fix, park |

## Context excerpts
> (PRD §SK-13) | SK-13 | `/afkv2:code-review` | picks concerns per subtask; fixes critical and high; posts medium and low on the change; stops after 3 rounds | K-10, decision 25, 46 |

> (PRD §AC-063) `/afkv2:code-review` stops after round 3. Critical and high findings are fixed; medium and low findings are posted on the change. A critical or high fix made in round 3, or a fix made for a ruling after review settled, gets one delta check: it reads only the fix commits, and it may only confirm or reopen the findings or rulings those commits answer. A reopened finding gets one more fix; if the next delta check fails, the change parks for the human (owner, 2026-11-02).

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

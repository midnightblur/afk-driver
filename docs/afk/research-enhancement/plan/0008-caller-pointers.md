# 0008-caller-pointers — one pointer line per plug-in point

## Goal
Add one pointer line per chosen branch to the six caller skills — `/afk:grill-requirements` (PP-1), `/afk:grill-solution` (PP-2), `/afk:grill-verification` (PP-3), `/afk:review` (PP-4), `/afk:adversary` (PP-5), `/afk:fix` (PP-6) — naming `/afk:research` and/or `/afk:consult` with the documented trigger (an external claim, a consequential unknown, a configured route; never elapsed time) and the boundary the PRD fixes per row. Step order and concern rosters stay unchanged; the utilities never name a caller. Add one sentence to `skills/afk/claude-md/SKILL.md`: an accepted organization priority enters through the inclusion bar citing its RES id. A fixture proves a run with no trigger produces no research or consult artifact.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§3 L2 flowchart caption — callers point at the two utilities; the utilities never name a caller
- SDD: SDD.md#§7 use case "research run" — trigger: external claim, consequential unknown, configured route (never elapsed time)
- SDD: SDD.md#§14 row "caller skills `grill-requirements`, `grill-solution`, `grill-verification`, `review`, `adversary`, `fix` gaining a pointer line to `research` and `consult`" — +1 pointer line per chosen branch; step order and concern roster unchanged
- ADR: adr/requirements/0007-consultation-is-advisory-only.md — PP-4/PP-5 boundaries: no verdict change
- ADR: adr/requirements/0008-rejected-extensions.md — PP-4: no new concern; no counter-search route
- ADR: adr/requirements/0001-no-priorities-registry-now.md — the `/afk:claude-md` sentence

## Scope
- skills/afk/grill-requirements/SKILL.md
- skills/afk/grill-solution/SKILL.md
- skills/afk/grill-verification/SKILL.md
- skills/afk/review/SKILL.md
- skills/afk/adversary/SKILL.md
- skills/afk/fix/SKILL.md
- skills/afk/claude-md/SKILL.md
- scripts/tests/test_plugin_points.py

## Seams
- implement: §14 row "caller skills `grill-requirements`, `grill-solution`, `grill-verification`, `review`, `adversary`, `fix` gaining a pointer line to `research` and `consult`" — this subtask owns the six pointer lines (INV-004)

## Acceptance
- [ ] `/afk:grill-requirements` gains one line pointing at `/afk:research` for user problem, external practice, scope alternatives and organization priorities, and one at `/afk:consult` to prepare a round; the human still accepts every decision (PRD C5 PP-1)
- [ ] `/afk:grill-solution` gains one line pointing at `/afk:research` for official compatibility, constraints and implementation alternatives, and one at `/afk:consult`; code claims still link to closed or explicitly partial investigations (PRD C5 PP-2)
- [ ] `/afk:grill-verification` gains one line pointing at `/afk:research` for failure scenarios and standards-based obligations; obligations become proposed scenarios through the existing writers (PRD C5 PP-3)
- [ ] `/afk:review` gains one line pointing at `/afk:consult`: participants are ordinary concern reviewers under existing concern ids; no new concern; provenance stays in the consult artifacts (PRD C5 PP-4; ADR-0008)
- [ ] `/afk:adversary` gains one line pointing at `/afk:consult`: a second independent adversary, blind to the diff (PRD C5 PP-5)
- [ ] `/afk:fix` gains one line pointing at `/afk:consult` in diagnosis: competing hypotheses ranked; opt-in route (PRD C5 PP-6)
- [ ] Every pointer line states the trigger — an external claim, a consequential unknown, or a configured route — and that elapsed time never triggers (PRD C5 "Trigger for any row")
- [ ] No step number, step order, or concern roster in any of the six skills changes; `git diff` per file shows added lines only (SDD §14 row "caller skills … gaining a pointer line")
- [ ] `skills/afk/claude-md/SKILL.md` gains one sentence: an accepted organization priority enters CLAUDE.md through the inclusion bar citing its RES id; the propose-approve-write protocol is unchanged (ADR-0001; SIGNED-PACKETS.md §HL-6 row "skills/afk/claude-md/SKILL.md")
- [ ] `skills/utils/research/SKILL.md` and `skills/utils/consult/SKILL.md` name none of the six callers; a test greps both and finds no caller name (plugin `CLAUDE.md` "Downstream is blind to upstream")
- [ ] A fixture run of each plug-in point with no trigger writes no `research/` or `consult/` artifact (PRD AC-035)
- [ ] No pointer line reads a consultation disposition into a review finding class, a review verdict or an adversary verdict (PRD AC-018; ADR-0007)
- [ ] Every artifact in ## Produces exists at its declared anchor (SDD §8)

## Produces
- skills/afk/grill-requirements/SKILL.md#/afk:research — PP-1 pointer line (research + consult)
- skills/afk/grill-solution/SKILL.md#/afk:research — PP-2 pointer line (research + consult)
- skills/afk/grill-verification/SKILL.md#/afk:research — PP-3 pointer line (research)
- skills/afk/review/SKILL.md#/afk:consult — PP-4 pointer line (consult; existing concern ids)
- skills/afk/adversary/SKILL.md#/afk:consult — PP-5 pointer line (consult; blind to the diff)
- skills/afk/fix/SKILL.md#/afk:consult — PP-6 pointer line (consult; diagnosis, opt-in)
- skills/afk/claude-md/SKILL.md#citing its RES id — the one sentence on accepted priorities

## Consumes
- 0006-research-skill skills/utils/research/SKILL.md#name: research — the utility the pointer lines name
- 0007-consult-skill skills/utils/consult/SKILL.md#name: consult — the utility the pointer lines name

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep every ## Produces anchor; `git diff --numstat` on the six skill files shows 0 deleted lines; `python hooks/run-hook.py plugin stop-gates.sh` | pointer lines present; nothing removed; prose passes the plugin's Stop gates |
| unit | `python -m pytest scripts/tests/test_plugin_points.py -q` — each of the six SKILL.md files carries its pointer line with the trigger wording; neither utility SKILL.md names a caller; a no-trigger run produces no `research/` or `consult/` artifact (AC-035) | the pointer contract and the trigger rule |

## Context excerpts
> (PRD C5) | PP-1 | `/afk:grill-requirements` | user problem, external practice, scope alternatives, organization priorities | prepares a round; the human accepts decisions | · | PP-2 | `/afk:grill-solution` | official compatibility, constraints, implementation alternatives | code claims link to closed or explicitly partial investigations | · | PP-3 | `/afk:grill-verification` | failure scenarios, standards-based obligations | obligations become proposed scenarios through existing writers | · | PP-4 | `/afk:review` | — | participants are ordinary concern reviewers under existing concern ids; no new concern; provenance stays in AR-3..AR-5 | · | PP-5 | `/afk:adversary` | — | second independent adversary; blindness to the diff kept | · | PP-6 | `/afk:fix` (diagnosis) | — | competing hypotheses ranked; opt-in route |
> (PRD C5) Trigger for any row: an external claim, a consequential unknown, or a configured route. Elapsed time never triggers. Not a plug-in point: any human conversation, any synthesis skill, single-writer stamps, and investigation counter-search (ADR-0008).
> (PRD AC-035) Each PP-1..PP-7 caller runs research or consultation only on its documented trigger; a run with no trigger produces no research or consult artifact.
> (PRD "Implementation Decisions" row "Caller pointers (PP-1..PP-7)") one line per chosen branch | callers name the utility; the utility never names a caller
> (SDD §3 L2 flowchart caption) callers point at the two utilities; the utilities never name a caller; the dispatcher is the only site that spawns a provider CLI.
> (SDD §14 row "caller skills … gaining a pointer line to `research` and `consult`") step order and concern roster unchanged (INV-008, INV-004) | +1 pointer line per chosen branch | none (INV-004) | callers name the utility; the utility never names a caller | extends
> (SIGNED-PACKETS.md §HL-6 row "skills/afk/claude-md/SKILL.md") :10,29,35 | +1 sentence: accepted priority enters via the inclusion bar citing its RES id | protocol unchanged | compatible | revert
> (ADR-0001 requirements) A human-accepted priority is written into CLAUDE.md only by `/afk:claude-md` through its existing inclusion bar.
> (ADR-0008 requirements) No `council` review concern: participants are ordinary concern reviewers and provenance stays in the consult artifacts (PRD PP-4).

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
0006-research-skill, 0007-consult-skill

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

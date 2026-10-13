## Goal
Add the outcome status unrecorded_agent, in one change, to the 6 sites that change together: /afk:execute Step 13's table, the README status table, the GLOSSARY.md token list, mission control's exit regex in insights.py, /afk:autopilot step 4 with its report block, and the status-agnostic sentence of AGENTS.md:153. Step 4 gains the rule that a team park ends the walk. test_insights.py gains a case for the new exit. Separately, add unhomed_product_debt to /afk:preflight's park reasons in JOURNAL-FORMAT.md, a reason /afk:preflight already writes. The slice ends at these status and reason lists; the park that produces the status is another subtask.

## Complexity
mechanical

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "Outcome status set of /afk:execute omits unrecorded_agent" and "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt"
- SDD: SDD.md#§13 Open Questions — Q52
- ADR: adr/design/0015-a-change-that-only-adds-keeps-the-contract.md — both rows are extends: the existing contract holds and only gains

## Scope
- skills/afk/execute/SKILL.md
- skills/afk/execute/CITED-MODE.md   # read only: the 3 cited-mode statuses; stays a partial list
- skills/afk/autopilot/SKILL.md
- README.md
- GLOSSARY.md
- skills/afk/mission-control/scripts/mc/sections/insights.py
- skills/afk/mission-control/scripts/tests/test_insights.py
- AGENTS.md
- skills/afk/to-subtasks/JOURNAL-FORMAT.md

## Seams
- implement: §14 row "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt" — the reason added to /afk:preflight's park reasons (INV-022)

## Acceptance
- [ ] Seam (plan D-14): §14 row "Outcome status set of /afk:execute omits unrecorded_agent", grounded by INV-064 (closed with frontier) — the status added in one change to the 6 sites that change together (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] unrecorded_agent is added to /afk:execute Step 13's table (11 rows today, execute/SKILL.md:116-125), the README status table (README.md:598-611), the GLOSSARY.md token list (GLOSSARY.md:240) and the insights.py exit regex (insights.py:24), all in one change; the set grows from 14 tokens to 15 (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] /afk:autopilot step 4 gains the rule that a team park ends the walk, whether it arrives as a subtask's unrecorded_agent outcome or as the contact agent's own park of a subtask agent's start; no further subtask starts, and the Finish report (autopilot/SKILL.md:51-58) names the agent and lists each subtask not started, with a journal line recording it (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] The journal records the park with the existing parked({status}) line and the walk's end with the existing run end line; JOURNAL-FORMAT.md:34 gains no token for it (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] The status-agnostic sentence of AGENTS.md:153 is rewritten to name the team-park rule; CLAUDE.md, the one-line pointer @AGENTS.md, is not edited (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] test_insights.py gains a case that feeds a journal line with exit unrecorded_agent and asserts an action-level exit insight, as it does for rationale_unposted (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] CITED-MODE.md:149-162, the README state diagram (README.md:579-582), the tooltip seed (hooks/lavish-tips.json) and retro's park patterns stay as they are: they hold partial lists (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] GLOSSARY.md:240, which names the README table as canonical, keeps that pointer (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] One plan subtask adds the status in one change to every surface that names statuses, so producer and consumers land together (agent-decided, SDD §13 Q52)
- [ ] Every existing outcome line, Status cell and journal line stays valid (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")
- [ ] unhomed_product_debt is added to the park reasons of /afk:preflight in JOURNAL-FORMAT.md; the step id 4d stays outside the grammar's 1 to 7, and the PF-2 and PF-7 cap park keeps no reason token (SDD §14 row "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt")
- [ ] Every existing journal line stays valid, and no journal reader breaks (SDD §14 row "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt")
- [ ] Conforms to ADR-0015 — both changes only add, and every existing caller keeps the contract it has today (ADR-0015)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent")

## Produces
- skills/afk/execute/SKILL.md#unrecorded_agent — the status in Step 13's table
- skills/afk/mission-control/scripts/tests/test_insights.py#unrecorded_agent — the test case for the new exit
- skills/afk/to-subtasks/JOURNAL-FORMAT.md#unhomed_product_debt — the preflight park reason

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -L 'unrecorded_agent' skills/afk/execute/SKILL.md README.md GLOSSARY.md skills/afk/mission-control/scripts/mc/sections/insights.py skills/afk/autopilot/SKILL.md AGENTS.md skills/afk/mission-control/scripts/tests/test_insights.py` prints nothing; `grep -n 'unhomed_product_debt' skills/afk/to-subtasks/JOURNAL-FORMAT.md` | Produces anchors present; the status reaches the 6 sites in one change |
| static | `python -m py_compile skills/afk/mission-control/scripts/mc/sections/insights.py` | the changed regex module compiles |
| unit | `python -m pytest skills/afk/mission-control/scripts/tests/test_insights.py -q` | a journal line with exit unrecorded_agent becomes an action-level exit insight |
| unit | `python -m pytest skills/afk/mission-control/scripts/tests/test_contract.py -q` | mission control still reads the status set and the journal |
| unit | `bash skills/afk/execute/scripts/tests/plan-status-smoke.sh` | the plan Status cell still takes the status set |

## Context excerpts
> (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent", Existing contract) /afk:execute Step 13 ends a run with the OUTCOME line and drives the PLAN.md Status cell with the same status; its table lists 11 statuses, rationale_unposted among them (execute/SKILL.md:116-125) (INV-064 c-24101883), and points at execute/CITED-MODE.md:149-162 for the cited-mode three (:127). Two surfaces list all 14: the README table, which gives each status's meaning and next action (README.md:598-611), and the GLOSSARY.md token list (GLOSSARY.md:239-240), which calls that table the canonical one (c-bc41fffe). [...] AGENTS.md:153 binds the set: broadening it updates Step 13 and any skill naming a status, and autopilot's park handling is status-agnostic, so a new status needs no edit there; it names neither the README table, GLOSSARY.md nor CITED-MODE.md; CLAUDE.md is the one-line pointer @AGENTS.md (CLAUDE.md:1).

> (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent", Planned change) Add unrecorded_agent to Step 13's table, the README table, the GLOSSARY.md token list and the insights.py regex; give /afk:autopilot step 4 the rule that a team park ends the walk, whether it arrives as a subtask's unrecorded_agent outcome or as the contact agent's own park of a subtask agent's start, that no further subtask starts, and that the Finish report names the agent and lists each subtask not started, with a journal line recording it; rewrite the status-agnostic sentence of AGENTS.md:153 to name that rule; all in one change (§13 Q52; audit round 13; audit round 14, agent-decided). The journal records the park with the existing parked({status}) line and the walk's end with the existing run end line, so JOURNAL-FORMAT.md:34 gains no token; the subtasks not started are listed only in the Finish report (inferred from the planned edits, INV-064 c-c3971ebc). test_insights.py gains a case for the new exit, as FRESHNESS.md:53 records for rationale_unposted (c-bc66986d; inferred)

> (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent", Impacted flows) The 6 sites that change together: Step 13, the README table, GLOSSARY.md:240, insights.py:24, autopilot step 4 with its report block (:51-58) and AGENTS.md:153 (c-4698a280, c-979ab487); the state diagram, the tooltip seed, CITED-MODE.md and retro stay true as partial lists (c-e364c42d)

> (SDD §14 row "Outcome status set of /afk:execute omits unrecorded_agent", Conventions / landmines) Step 13's table is the set's home, and AGENTS.md's Lockstep paragraph binds it (AGENTS.md:153); GLOSSARY.md:240 names the README table as canonical instead, which the plan subtask leaves as it is (INV-064 c-bc41fffe; inferred). A new journal token instead of the existing lines would need an edit to JOURNAL-FORMAT.md, its one grammar home (c-ab7287fa). The status has no file to anchor an IOU in, so producer and consumers land together (correction of audit round 14). No test pins any prose surface, the set or the team-park rule; test_insights.py:18-34 pins only the rationale_unposted exit and plan-status-smoke.sh:86, :88 only that a blocked cell takes any reason (c-f9e9ba7b).

> (SDD §14 row "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt", Planned change) Add unhomed_product_debt to the park reasons of /afk:preflight in JOURNAL-FORMAT.md; /afk:preflight already writes this reason (S-205). The step id 4d stays outside the grammar's 1 to 7, and the PF-2 and PF-7 cap park has no reason token before or after the edit (INV-022 c-269eb108, c-7f7f7260)

> (SDD §14 row "skills/afk/to-subtasks/JOURNAL-FORMAT.md omits unhomed_product_debt", Conventions / landmines) JOURNAL-FORMAT.md is owned by /afk:to-subtasks. Its reason list copies preflight's routing table (:41-42, :54-55), and no lockstep or FRESHNESS row binds the copy (INV-022 c-fe0174cc, inference). No test pins the list. Compatibility: the change only adds; every existing journal line stays valid, with no migration or deploy order (S-205; c-0608c232, inference).

> (SDD §13 Q52) One plan subtask adds the status unrecorded_agent, in one change, to every surface that names statuses: /afk:execute Step 13, 11 statuses today (skills/afk/execute/SKILL.md:114-125); /afk:autopilot step 4 (skills/afk/autopilot/SKILL.md:37-39), which gains the rule that a team park ends the walk [...]; the README status table, 14 tokens (README.md:598-611); the GLOSSARY.md token list, 14 tokens (GLOSSARY.md:240); mission control's status list, 8 of the 13 failure statuses (skills/afk/mission-control/scripts/mc/sections/insights.py:24); and AGENTS.md's Lockstep sentence that autopilot's park handling is status-agnostic (AGENTS.md:153), which that rule makes stale. The status comes from the park after exit 5 or a verb timeout (§3). [...] Counts recounted at 5c9d420 (GRILL-LOG.md:745 (1))

> (ADR-0015) A change takes extends when every existing caller keeps the contract it has today and the change only adds: a key, a row, a field, a line, a step or a count (S-199).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

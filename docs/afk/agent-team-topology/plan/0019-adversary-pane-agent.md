## Goal
Make the adversary of /afk:execute Step 10.5 a new pane agent (an agent in its own terminal pane) for each attempt. It keeps its blind diet, writes its own named report, and sends finished carrying only the format version and the result path to its report target, so the verdict travels in the report file. /afk:execute waits for that finished message and reads the verdict from the file. The start, the finished message and /afk:execute's wait ship in one change, the reader before the key. The slice ends at Step 10.5 and the adversary skill; the subagent fallback's report write is another subtask.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "/afk:execute Step 10.5: the adversary"
- SDD: SDD.md#§13 Open Questions — V4, V5, V40
- ADR: adr/design/0006-role-result-file-and-finished-message.md — result file plus finished with the path; the `ADVERSARY:` line names the brief's report path

## Scope
- skills/afk/adversary/SKILL.md
- skills/afk/execute/SKILL.md
- hooks/stop-gates.sh

## Seams
- (none — the one §14 row this slice changes is excepted (partial INV-035); listed under ## Acceptance)

## Acceptance
- [ ] Excepted seam §14 row "/afk:execute Step 10.5: the adversary" (partial INV-035, human exception of 2026-10-02, GRILL-LOG.md:711; plan D-1, D-17): before this subtask merges, §13 V4, V5 are proven at build as listed in ## Verification, and the change follows the row's Planned change cell (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] Each adversary attempt starts a new pane agent that keeps the blind diet: an attempt that saw any diff, test, finding or commit is tainted (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The adversary writes its own named report; its finished message carries the format version and the result path only and goes to its report target, with a short copy to the contact agent (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The `ADVERSARY:` line keeps its grammar and names the brief's report path (agent-decided, SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] /afk:execute Step 10.5 waits for the adversary's finished message and reads the verdict from the report file; the hard rule that reads every verdict from the spawning call's own result (execute/SKILL.md:135 in the SDD row, :137 at 1210110) no longer covers the adversary (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] With no stage map entry the adversary is an implicit single-role step with lifespan Turn, named `solo:` followed by the role in its start request, and runs the model its tier names (agent-decided, SDD §13 Q33)
- [ ] Only the contact agent messages the adversary, with no branch content, and Stop-gate output reaches it only after its verdict is recorded (agent-decided, SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The adversary writes a checkpoint in the run; a replacement after a death reads it, and a fresh attempt after a tainted one does not (agent-decided, SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The changed lines are execute/SKILL.md:90, :135; adversary/SKILL.md:40, :47, :51; hooks/stop-gates.sh:134; the attempt cap at execute/SKILL.md:94, which still counts attempts, and the report's readers stay unchanged; DELEGATION.md:34, :36, :37 change in 0014-delegation-doctrine, and the fallback-only lines execute/SKILL.md:145 and AGENTS.md:180 in 0020-subagent-fallback-report-writers (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The respawn after a tainted or env_unreachable verdict at execute/SKILL.md:94, a missed role spawn, starts a new pane agent like a first attempt (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The start, the finished message and /afk:execute's wait ship in one change, the reader before the key (SDD §14 row "/afk:execute Step 10.5: the adversary")
- [ ] The build gate keeps its owner: the adversary writes only its own report file the gate names, never the gate's other files or its status (PRD AC-038)
- [ ] Conforms to ADR-0006 — the adversary writes its result to a file and sends finished with the path; the `ADVERSARY:` line keeps its shape (ADR-0006)
- [ ] The changed hooks/stop-gates.sh, a Stop-path source, passes native check M: it adds no repository-wide scan outside bounded_scan.py (SDD §13 V40)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "/afk:execute Step 10.5: the adversary")

## Produces
- skills/afk/adversary/SKILL.md#pane agent per attempt — the adversary started fresh per attempt with its blind diet

## Consumes
- 0015-team-skill-and-manifests skills/afk/team/SKILL.md#contact agent's run procedure — the contact agent starts the adversary

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'pane agent per attempt' skills/afk/adversary/SKILL.md`; `grep -n "contact agent's run procedure" skills/afk/team/SKILL.md`; `bash -n hooks/stop-gates.sh` | Produces and consumed anchors present; the changed gate script parses |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | skill frontmatter still valid |
| integration | V4, environment-gated on both harnesses with herdr: the probe "SessionStart in a pane agent" (providers/CONFORMANCE.md:432) re-run in a pane adversary with a repository-declared hook that prints a marker line; the probe row records whether the marker reaches the adversary | V4 |
| integration | V5, environment-gated on the human's Codex trust entry for a printing hook: the Codex cell of probe providers/CONFORMANCE.md:432 for a pane adversary, which reads its contract, specs and doctrine and records whether its SessionStart output arrives; recorded as a probe row | V5 |
| static | `python -m pytest scripts/tests/test_native_contract_events.py -q`; the native contract gate run on the change (`GATE_CACHE_DISABLE=1 gate_native_contract`, sourced as scripts/tests/test_native_contract_events.py:25-28 does) reports no check M finding | V40 for the changed hooks/stop-gates.sh |

## Context excerpts
> (SDD §14 row "/afk:execute Step 10.5: the adversary", Existing contract) execute/SKILL.md:90 runs /afk:adversary with the slice and the app URL in a fresh session; adversary/SKILL.md:14-15 take only those 2 arguments, and :19-21 set its diet: an attempt that saw any diff, test, finding or commit is tainted (INV-035 c-98977523). execute/SKILL.md:135 reads the verdict from the spawn result, else no verdict; adversary/SKILL.md:40-44 writes the slice's adversary report and the ADVERSARY: line (c-edf345a7). Routing: execute/SKILL.md:92-96, :119-120 (c-8f5617c9). The report is read by name or folder at gates.py:110-120, insights.py:204-233 (its first 4000 characters, for a verdict label), progress.py:75, overview.py:143, retro/SKILL.md:29, understand/SKILL.md:49, review/SKILL.md:167, README.md:588 and gc/SKILL.md:53 (c-4d06b173)

> (SDD §14 row "/afk:execute Step 10.5: the adversary", Planned change) The adversary is a new pane agent for each attempt, keeps its blind diet, and writes its own named report (S-155, AC-038). Its finished message carries the format version and the result path only (S-231) and goes to its report target, with a short copy to the contact agent (S-212, S-235); so the verdict travels in the report file. The ADVERSARY: line keeps its shape and names the brief's path (D-15), and mission control needs a verdict label the line lacks (INV-035 c-66a8e88b, inference). With no stage map entry the adversary is an implicit single-role step with lifespan Turn (D-09), named solo: followed by the role in its start request (Q33), and runs the model its tier names (D-10). Only the contact messages it, with no branch content, and Stop-gate output reaches it only after its verdict is recorded (D-21). It writes a checkpoint in the run; a replacement after a death reads it, and a fresh attempt after tainted does not (D-22). D-09, D-10, D-15, D-21, D-22 and Q33 are agent-decided

> (SDD §14 row "/afk:execute Step 10.5: the adversary", Impacted flows) Change: execute/SKILL.md:90, :135; adversary/SKILL.md:40, :47, :51 (INV-035 c-74341bf9, c-5a7bea40, inference); DELEGATION.md:34, :36, :37, which row C11 moves (c-fefa0ba6, inference); hooks/stop-gates.sh:134; under the fallback only, execute/SKILL.md:145, AGENTS.md:180 (c-a0778b4f, inference). [...] Unchanged: the attempt cap at execute/SKILL.md:94, which still counts attempts (c-c14bcbfd, inference), and the report's readers (D-20, agent-decided; c-32458cb1, inference) (INV-035)

> (SDD §14 row "/afk:execute Step 10.5: the adversary", Conventions / landmines) Nothing pins the verdict label (INV-035 c-8bac0def), and class routing needs per-finding fields only the file holds (c-e8ac49bc, inference). The wiring gate can hold a read-only adversary's turn open on an orphan branch (wiring-gate.sh:135-140, :244; the report is exempt at :50), and the repository's own Stop list also runs (c-c22c6ab6, c-e5898831, c-376b0917, inference); D-21 settles taint only. The adversarial-gate lockstep does not fire (c-b194f4cb, inference); a new status for an adversary that started and sent no finished is lockstep with insights.py:24, /afk:execute Step 13 and REPORTING.md:29 (c-92d92b3f, inference). Ship the start, the finished message and /afk:execute's wait in one change, the reader before the key (c-bb5c6a01, inference). A silent live adversary stays working (S-241). [...] Compatibility: the ADVERSARY: line keeps its grammar; its channel moves from the spawn result to the report file (c-66a8e88b, inference; D-15). Rollback is not neutral: the pane switch set to subagent (AC-041, S-230) makes the adversary a subagent again, and /afk:execute then writes the returned report (D-15), against execute/SKILL.md:145 and AGENTS.md:180 (c-f42ee815, inference) [...]

> (SDD §13 V4) Whether a consuming repository's SessionStart or PreToolUse hooks put the branch's diff, tests or commits in front of a pane adversary. A hook that prints such material would taint every attempt and end the gate in adversary_fail (execute/SKILL.md:94). INV-035 c-9049aaa7; §14 row Step 10.5. Proven at build by: the probe 'SessionStart in a pane agent' (providers/CONFORMANCE.md:432) re-run in a pane adversary with a repository-declared hook that prints a marker line, on both harnesses

> (SDD §13 V5) Whether a Codex CLI pane adversary can read its contract, specs and doctrine, and receives its SessionStart output. [...] Still open: its SessionStart output, unproven because a printing Codex hook needs a trust entry (:432). INV-035 c-52e6da05; §14 row Step 10.5. Proven at build by: the Codex cell of probe :432, with the trust entry in place

> (PRD AC-038) The existing build, review and final-review gates keep their owners. A pattern role inside a gate is a worker that gate calls. A worker may write its own report file that the gate names; no worker writes the gate's other files or its status.

> (ADR-0006) The finished body is one JSON object with a format version and the result path; the path is empty when the agent wrote no result file (S-231). The team entry script ignores the target the sender wrote and delivers finished to the report target the manifest and the pattern name, in the order body, completion signal, target pane, contact inbox (S-212, S-235). … the `ADVERSARY:` line names the brief's report path (D-15, agent-decided).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0015-team-skill-and-manifests

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

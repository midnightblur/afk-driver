## Goal
Make the review gate's workers pane agents (agents in their own terminal panes) in /afk:execute Step 10 and /afk:preflight PF-3 (the feature review step). Each review round requests new reviewer agents with lifespan Turn and a brief of paths only; the skeptics and adjudicators are requested the same way, with one start request per adjudicator, one per dispute. The referee, the caller SETTLEMENT.md names, runs every forge-ledger duty itself; workers only review or fix. Each worker writes its result file in the run directory and sends finished with the path to its report target; the review orchestrator keeps merging, numbering and writing plan/review/. The same slice updates GLOSSARY.md:319, README.md:586 and the 7 other lines that restate the rule, after the glossary slice lands the terms pane agent and pane transport, and keeps the settle-loop lockstep in one commit. The slice ends at the review gate; the adversary, DELEGATION.md and the subagent fallback writers are other subtasks.

## Complexity
complex

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", "/afk:preflight PF-3 feature review", "GLOSSARY.md:319 and README.md:586", and the settle-change lines of "Spawn steps that start a role agent (S-208's list)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "File reads in a pane agent" (use)
- SDD: SDD.md#§13 Open Questions — V1, V2, V3, V23, V41
- ADR: adr/design/0006-role-result-file-and-finished-message.md — result file plus finished with the path
- ADR: adr/design/0010-report-target-per-role.md — finished goes to the report target, a short copy to the contact agent
- ADR: adr/requirements/0013-role-agents-are-pane-agents.md — the GLOSSARY.md:319 row is extends under this record

## Scope
- skills/afk/review/SKILL.md
- skills/afk/review/SETTLEMENT.md
- skills/afk/review/checklists/*.md
- skills/afk/review/*.md
- skills/afk/execute/SKILL.md
- skills/afk/preflight/SKILL.md
- skills/afk/to-subtasks/PLAN-TEMPLATE.md
- skills/utils/settle-change/SKILL.md
- scripts/tests/test_forge_ledger.py
- GLOSSARY.md
- README.md
- providers/CONFORMANCE.md

## Seams
- (none in validator form — this slice's 3 seams sit on §14 rows whose citations the plan validator cannot read; they are under ## Acceptance, plan D-14)

## Acceptance
- [ ] Seam (plan D-14): §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", grounded by INV-059 (closed with frontier) — the review workers become pane agents started per round, and the change follows the row's Planned change cell (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] Seam (plan D-14): §14 row "/afk:preflight PF-3 feature review", grounded by INV-059 (closed with frontier) — the worker change reaches PF-3 through /afk:review and SETTLEMENT.md:40, and the change follows the row's Planned change cell (SDD §14 row "/afk:preflight PF-3 feature review")
- [ ] Seam (plan D-14): §14 row "GLOSSARY.md:319 and README.md:586", grounded by INV-062 (closed with frontier) — both lines and the 7 other restating lines say the review workers are pane agents where the plugin is enabled and a pane transport is found, subagents otherwise (SDD §14 row "GLOSSARY.md:319 and README.md:586")
- [ ] Each review round requests new reviewer agents with lifespan Turn and a brief of paths only; the skeptics and adjudicators are requested the same way, with one start request per adjudicator, one per dispute, since each dispute gets a fresh adjudicator (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] /afk:review requests the concern workers and the skeptics; the caller's referee requests the adjudicators (SETTLEMENT.md:40) (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] The referee is the caller SETTLEMENT.md names: the subtask agent under /afk:autopilot, and the contact agent for PF-3. It runs every forge-ledger duty itself: reconstruct, post, the records, gate --phase progress before any fixer, the Settles: trailers, the summary and gate --phase closure (SETTLEMENT.md:17, :35-42), with its --trust identity on resume (:19). Workers only review or fix, and no worker runs forge_ledger.py (agent-decided, SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] forge_ledger.py, SETTLEMENT.md:17 and :35-42 stay unchanged, and every referee duty pinned by scripts/tests/test_forge_ledger.py:258, :378, :961, :1041, :1213, :1609 still passes (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] In a pane agent, such as the /afk:autopilot subtask agent, the start request names that agent as requester; in the contact session, for PF-3 or a review the human invokes, the contact agent starts the workers itself with an empty requester and their finished messages reach its inbox (agent-decided, SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] With no stage map entry each worker is an implicit single-role step with lifespan Turn, which a pane requester's start request names `solo:` followed by the role (agent-decided, SDD §13 Q33)
- [ ] A worker writes its result file in the run directory with no round tag and sends finished with that path to its report target; only the review orchestrator writes findings files under plan/review/, and the plan/review/ file names and grammars hold (agent-decided, SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] Merging, dedup and r-NNN numbering stay with the review orchestrator; the /afk:investigate run at review/SKILL.md:38 is stated as run inline by the review orchestrator, and a spawn-site check finds no spawn there (agent-decided, SDD §13 V23)
- [ ] The information diet of SETTLEMENT.md:93 binds pane briefs and every later message to a worker (agent-decided, SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] Every content brief the paths-only brief breaks is updated: review/SKILL.md:27, :43, :94, :102, :106, :148, delta-sweep.md:3, consistency-sweep.md:5 and SETTLEMENT.md:40; the tag rule of review/SKILL.md:25 narrows; execute/SKILL.md:137 no longer says to never wait on a completion notification (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] The Step 10 row's change list inside this slice's Scope changes: execute/SKILL.md:73, :137; review/SKILL.md:12, :25-27, :43, :94, :102, :106, :110, :148, :202; SETTLEMENT.md:12, :40, :93; the checklists api-contract.md:6, :26, design-quality.md:6, :37, domain-alignment.md:6, :26, resilience.md:6, :25, test-veracity.md:6, :23, :25, consistency-sweep.md:5 and delta-sweep.md:3; settle-change/SKILL.md:38, :48, :120. SETTLEMENT.md:12 and consistency-sweep.md:5 name no spawn mechanism and may hold (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] The missed role spawns settle-change/SKILL.md:53 (the fixer brief) and :89 (the pushback adjudication) start pane agents like the other review-loop roles; this slice owns every settle-change line the spawn rows list (plan D-23) (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The settle-loop lockstep holds: execute Step 10 routing, preflight PF-3 routing and the PF-3 Cycle-cell cap copy in skills/afk/to-subtasks/PLAN-TEMPLATE.md change in one commit (AGENTS.md:153) (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] At PF-3 the preflight session is the contact agent: it starts the reviewers and the adjudicators itself with an empty requester. The PF-3 Cycle cell shows the forge feature round that reconstruct returns (preflight/SKILL.md:106-108; PLAN-TEMPLATE.md:58-60), so a re-run PF-3 continues the count, and round tags stay referee-private (agent-decided, SDD §14 row "/afk:preflight PF-3 feature review")
- [ ] Preflight keeps the outcomes files, the PF-3 row, the Cycle cell and the journal line; preflight/SKILL.md:85, :87, :94, :96, :99, :115, :116, :118 stay unchanged (SDD §14 row "/afk:preflight PF-3 feature review")
- [ ] GLOSSARY.md:319 and README.md:586 say the review gate's workers are pane agents where the plugin is enabled and a pane transport is found, and subagents with the pane switch set to subagent or no pane transport; README.md:587 stays true while each concern keeps one reviewer (SDD §14 row "GLOSSARY.md:319 and README.md:586")
- [ ] The 7 other lines that restate the rule and sit in no other change list change with the 2 lines: review/SKILL.md:31, :33, :35, :47, :61, :197 and settle-change/SKILL.md:14 (agent-decided, SDD §14 row "GLOSSARY.md:319 and README.md:586")
- [ ] The 2 lines and the 7 restating lines ship in the same commit as the review spawn-step change or after it, and after the glossary slice adds the terms pane agent and pane transport; they name no packet id such as DOC-1 or TR-1 and no investigation id (SDD §14 row "GLOSSARY.md:319 and README.md:586")
- [ ] The build, review and final-review gates keep their owners; a worker writes only its own report file the gate names, never the gate's other files or its status (PRD AC-038)
- [ ] Each review round gets new reviewers that saw nothing of the build; each reviewer returns one findings set, which the review orchestrator merges and numbers (PRD AC-045)
- [ ] Conforms to ADR-0006 — a role agent writes its result to a file and sends finished with the path; the findings JSON and the `REVIEW:` line keep their shapes (ADR-0006)
- [ ] Conforms to ADR-0010 — the team entry script delivers finished to the report target the manifest and pattern name, with a short copy to the contact agent (ADR-0010)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves")
- [ ] The pane reviewer reads its brief, the diff and the checklists through the §9b file-read seam; on Codex this rests on V2 (SDD §9b row "File reads in a pane agent")

## Produces
- skills/afk/review/SKILL.md#lifespan Turn — reviewer agents started per round with lifespan Turn
- skills/afk/review/SETTLEMENT.md#one start request per adjudicator — the referee requests a fresh adjudicator per dispute

## Consumes
- 0001-glossary-terms GLOSSARY.md#**Pane agent** — the term the 2 lines use
- 0001-glossary-terms GLOSSARY.md#**Pane transport** — the term the 2 lines use
- 0015-team-skill-and-manifests skills/afk/team/SKILL.md#contact agent's run procedure — the contact agent starts the reviewers

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'lifespan Turn' skills/afk/review/SKILL.md`; `grep -n 'one start request per adjudicator' skills/afk/review/SETTLEMENT.md`; `grep -nF '**Pane agent**' GLOSSARY.md`; `grep -nF '**Pane transport**' GLOSSARY.md`; `grep -n "contact agent's run procedure" skills/afk/team/SKILL.md` | Produces and consumed anchors present |
| static | `grep -n 'fresh subagents' GLOSSARY.md README.md skills/afk/review/SKILL.md skills/utils/settle-change/SKILL.md` prints no line that says the review workers are always subagents | seam-test of §14 row "GLOSSARY.md:319 and README.md:586": the 2 lines and the 7 restating lines carry the new wording |
| static | `bash hooks/genericity-gate.sh` passes on the change | the changed lines name no packet or investigation id |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | skill frontmatter still valid |
| unit | `python -m pytest scripts/tests/test_forge_ledger.py -q` | every referee duty forge_ledger.py runs still passes; seam-test of the Step 10 and PF-3 rows: the forge ledger is unchanged |
| unit | V3 plan test: a reviewer started with an empty requester ends without sending finished; the test asserts the agent that waits on its result is told (at PF-3 that agent is the contact agent); the executor names the test file (SDD §0 leaves test fixture structure to the executor) | V3 |
| unit | V23 plan check: the V19 spawn-site check classes review/SKILL.md:38 and finds no spawn there once this subtask states the inline run | V23 |
| unit | V41 plan test in scripts/tests/test_forge_ledger.py: re-run PF-3 on a change with earlier feature rounds and show whether the 10-round cap of SETTLEMENT.md:75 counts over every PF-3 run of the change or per run | V41 |
| integration | V1, environment-gated on each harness: a new probe row in providers/CONFORMANCE.md in which a finished message is sent to a subagent report target | V1 |
| integration | V2, environment-gated on Codex CLI with herdr: the Codex cell of probe providers/CONFORMANCE.md:434 with a variable set on the pane, plus a Codex pane reviewer reading its brief, the diff and the checklist files; recorded as a probe row | V2; the Codex cell of §9b row "File reads in a pane agent" |

## Context excerpts
> (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", Existing contract) execute/SKILL.md:73 runs /afk:review with the slice and a round tag as the settle-loop referee; /afk:review is also reached from preflight/SKILL.md:85-87, settle-change/SKILL.md:38 and a standalone call (INV-059 c-383b35db). It starts one subagent per concern in one message, through a generic role (review/SKILL.md:43; PROVIDERS.md:24) [...] The caller's referee starts the adjudicators, a fresh one per dispute (SETTLEMENT.md:12, :40; c-794d2f08), and runs the forge ledger through forge_ledger.py (:17, :35-42). Under /afk:autopilot, Step 10 runs in the subtask agent (autopilot/SKILL.md:33), whose prompt grants no depth, so whether it starts its workers or runs them inline is not settled (DELEGATION.md:29, CAPABILITIES.md:15; c-22ba5118, inference)

> (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", Planned change) Each review round requests new reviewer agents with lifespan Turn and a brief of paths only, and the skeptics and adjudicators are requested the same way (S-155): one start request per adjudicator, one per dispute, since each dispute gets a fresh adjudicator (SETTLEMENT.md:12, :40; GRILL-LOG.md:745 (5)). /afk:review requests the concern workers and the skeptics; the caller's referee requests the adjudicators (SETTLEMENT.md:40). The referee is the caller SETTLEMENT.md names, the subtask agent under /afk:autopilot and the contact for PF-3; it runs every forge-ledger duty itself: reconstruct, post, the records, gate --phase progress before any fixer, the Settles: trailers, the summary and gate --phase closure (skills/afk/review/SETTLEMENT.md:17, :35-42), its --trust identity included on resume (:19). Workers only review or fix (GRILL-LOG.md:745 (5)). In a pane agent, such as the /afk:autopilot subtask agent, the request names that agent as requester (S-153, S-223); in the contact session, for PF-3 or a review the human invokes, the contact starts the workers itself with an empty requester, and their finished messages reach its inbox (D-01, agent-decided). With no stage map entry each worker is an implicit single-role step with lifespan Turn, which a pane requester's start request names solo: followed by the role (D-09, Q33, agent-decided). A worker writes its result file in the run directory with no round tag, and only the orchestrator writes findings files under plan/review/ (D-19, agent-decided). D-19 replaces the signed sentence of packet HL6-9 that each worker writes its result under plan/review/, the location the gate names (S-173). Each worker sends finished with the path to its report target (S-154, S-212). Merging and r-NNN numbering stay with the review orchestrator (S-155). The /afk:investigate run at review/SKILL.md:38 runs inline (D-03, agent-decided). The diet of SETTLEMENT.md:93 binds pane briefs and every later message (D-29, agent-decided)

> (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", Impacted flows) Change: execute/SKILL.md:73, :137; review/SKILL.md:12, :25-27, :43, :94, :102, :106, :110, :148, :202; SETTLEMENT.md:12, :40, :93; the checklists api-contract.md:6, :26, design-quality.md:6, :37, domain-alignment.md:6, :26, resilience.md:6, :25, test-veracity.md:6, :23, :25, consistency-sweep.md:5 and delta-sweep.md:3; settle-change/SKILL.md:38, :48, :120; DELEGATION.md:24, :29, :34; GLOSSARY.md:319; README.md:586; the feature's PRD.md:70 and GRILL-LOG.md:561. Unchanged: preflight/SKILL.md:85, :87, :94, :96, :99, :115, :116, :118; autopilot/SKILL.md:47; SETTLEMENT.md:35-42; PLAN-TEMPLATE.md:11, :58, :60, :66; PROVIDERS.md:24; SETTLEMENT.md:17; forge_ledger.py and every referee duty, pinned by scripts/tests/test_forge_ledger.py:258, :378, :961, :1041, :1213, :1609 (INV-059 c-8c046140, c-39d6fd60, c-45325d9a, c-812dcf3b). SETTLEMENT.md:12 and checklists/consistency-sweep.md:5 name no spawn mechanism, so they may hold (c-7976ab32, inference)

> (SDD §14 row "/afk:execute Step 10: /afk:review concern workers, skeptic and adjudicator waves", Conventions / landmines) The paths-only brief breaks the content briefs at review/SKILL.md:27, :43, :94, :102, :106, :148, delta-sweep.md:3, consistency-sweep.md:5 and SETTLEMENT.md:40 (INV-059 c-fd8cbfcb, c-75ef8cf9, c-64f3f24d); it undoes the Guardrails cut of CHANGELOG.md:2035 for 4 checklists and adds test-veracity's probe section (inference, not re-checked at the merge). The tag rule of review/SKILL.md:25 must narrow, and round-tagged paths already reach workers at :102 (c-fd8cbfcb). execute/SKILL.md:137, never wait on a completion notification, needs rewriting (c-00b08c44, c-bce9f559). native-contract-gate.sh:125-129 refuse harness tokens in skills (c-7ab95dfd). No test pins a wave (c-7ab95dfd). Each reviewer turn runs 2 Stop hooks of up to 300 s (hooks/hooks.json:136-153; c-8ae0ac8e, inference) [...] Settle-loop lockstep: Step 10, PF-3 routing and the PLAN-TEMPLATE.md Cycle copy change in one commit (AGENTS.md:153; c-fabef15e). Compatibility: reviewers stay fresh per round and blind; the plan/review/ file names and grammars hold because worker result files go in the run directory (D-19, which replaces the signed plan/review/ location of S-173; c-019450e1, c-843c0aea, inference). Rollback: the pane switch set to subagent (AC-041, S-230) [...] Ledger-only rounds need review.ledger-only-paths (SETTLEMENT.md:63-65) only for a worker file that enters a commit; a file in the git-ignored run directory never does [...] No script holds the 10-round cap; it is SETTLEMENT.md:75 prose (c-63449399, inference).

> (SDD §14 row "/afk:preflight PF-3 feature review", Planned change) The worker change of the Step 10 row reaches PF-3 through /afk:review and SETTLEMENT.md:40: new reviewer agents with lifespan Turn each round (S-155). The preflight session is the contact agent, so it starts the reviewers and the adjudicators itself with an empty requester, and their finished messages reach its inbox (D-01, agent-decided). The PF-3 Cycle cell shows the forge feature round that reconstruct returns (preflight/SKILL.md:106-108; PLAN-TEMPLATE.md:58-60), so a re-run PF-3 continues the count, and round tags stay referee-private (D-05, agent-decided; GRILL-LOG.md:745 (5); SETTLEMENT.md:35, :93). The referee is the caller SETTLEMENT.md names [...]; it runs every forge-ledger duty itself [...]. Workers only review or fix (GRILL-LOG.md:745 (5)). Preflight keeps the outcomes files, the PF-3 row, the Cycle cell and the journal line

> (SDD §14 row "/afk:preflight PF-3 feature review", Impacted flows) The preflight lines stay unchanged (preflight/SKILL.md:85, :87, :94, :96, :99, :115, :116, :118); the change arrives through review/SKILL.md:43, :110, :148, :202 and SETTLEMENT.md:40 (INV-059 c-06c14491, c-fd8cbfcb). On main, PF-3's deferral sweep reads the forge ledger, which needs finding ids (c-80b975ef, c-0d368151)

> (SDD §14 row "GLOSSARY.md:319 and README.md:586", Planned change) Both lines say the review gate's workers are pane agents where the plugin is enabled and a pane transport is found, and subagents with the pane switch set to subagent or no pane transport (S-160, AC-041; inferred). README.md:587 stays true while each concern keeps one reviewer. The 2 lines ship with or after the review spawn steps change (INV-062 c-17e74745)

> (SDD §14 row "GLOSSARY.md:319 and README.md:586", Impacted flows) [...] 12 other lines restate the rule: review/SKILL.md:12, :31, :33, :35, :43, :47, :61, :110, :148, :197; execute/SKILL.md:73; settle-change/SKILL.md:14. Of these, review :31, :33, :35, :47, :61, :197 and settle-change :14 sit in no change list of this SDD, so they would still contradict the new wording after the spawn change, and they change with the 2 lines (c-0e5ad163, c-27ce2b5d; agent-decided). Main's SETTLEMENT.md names no subagent (SETTLEMENT.md:12; GRILL-LOG.md:745 (5)), and preflight :85, :93, GLOSSARY.md:325 and LAVISH-TIPS.md:21 name no worker kind (c-39744eff). Nothing stored changes (c-e911e959)

> (SDD §14 row "GLOSSARY.md:319 and README.md:586", Conventions / landmines) Pane agent and pane transport have no GLOSSARY.md entry yet; both land before the 2 lines, so the slice that writes them depends on the glossary slice (LANGUAGE.md:36; FRESHNESS.md:44; INV-062 c-85e65e89, c-70cb6c76; §13 Q1). A packet id such as DOC-1 or TR-1, or an investigation id, written into either line blocks Stop; S-160, AC-045 and requirement ADR-0013 pass (genericity-gate.sh:247-251; c-0e0a01aa).

> (SDD §13 V23) Whether the /afk:investigate run at review/SKILL.md:38 is spawned; if it is, it is a role spawn S-208 does not place. D-03 (agent-decided): the review orchestrator runs it inline. … Proven at build by: the spawn-site check of V19, which finds no spawn at review/SKILL.md:38 once the review subtask states the inline run

> (SDD §13 V41) Whether the settle loop's 10-round cap counts across PF-3 re-runs. The Cycle cell shows the forge feature round that reconstruct returns (preflight/SKILL.md:106-108), and a stalemate is 10 rounds with open findings (skills/afk/review/SETTLEMENT.md:75); whether the cap counts rounds over every PF-3 run of the change or per run is unverified, since forge_ledger.py's cap logic was not read (GRILL-LOG.md:745 (8)). Proven at build by: a test that re-runs PF-3 on a change with earlier feature rounds and shows where the cap falls

> (SDD §9b row "File reads in a pane agent") Claude: reads an added folder, another session's scratchpad and the installed plugin's files. Codex: the shell reads an added folder, another session's scratchpad and the installed plugin's files; its Git bash starts with no /usr/bin on PATH, so a script exports it first (:315) | A Codex pane agent reads only through its shell, so a script that does not export PATH fails there (§13 rows for INV-035, INV-037, INV-038) | Probe :326, both cells |

> (SDD §13 V1) V1: Whether a subagent, such as Step 10's review orchestrator under /afk:autopilot, can be the report target of a sent finished message; the probes cover pane agents only (providers/CONFORMANCE.md:420-442). It stays open only where the review orchestrator runs as a subagent: under D-01 the requester at Step 10 is the subtask agent, a pane agent (inferred). INV-037 c-c1c9db98; §14 rows Step 10 and PF-3. Proven at build by: a new probe row in providers/CONFORMANCE.md, a finished message sent to a subagent report target on each harness

> (SDD §13 V2) V2: Whether a Codex CLI pane reviewer can read its brief, the diff and the checklist files, and gets its environment variables. Re-probe 2026-10-06, Codex CLI 0.160.0: its shell reads an added folder, another session's scratchpad and the installed plugin's files (providers/CONFORMANCE.md:438), so the reads are answered, and it carries the CODEX_ and HERDR_ markers and no PLUGIN_ROOT (:434). Still open: whether a variable set on the pane reaches the Codex shell; :434 records it for the Stop hook processes only. INV-037 c-360bdf33; §14 rows Step 10 and PF-3. Proven at build by: the Codex cell of probe :434 with a variable set on the pane

> (SDD §13 V3) Who is told when a reviewer started with an empty requester ends without sending finished. … Proven at build by: a test the plan carries for the review gate, in which a reviewer ends without finished and the agent that waits on its result is told. Under D-01 (agent-decided) the contact agent starts PF-3's reviewers itself, so it is that agent (inferred).

> (PRD AC-038) The existing build, review and final-review gates keep their owners. A pattern role inside a gate is a worker that gate calls. A worker may write its own report file that the gate names; no worker writes the gate's other files or its status.

> (PRD AC-045) Pane agents meet the gate rules: each review round gets new reviewers that saw nothing of the build; each reviewer returns one findings set, which the review orchestrator merges and numbers; the adversary stays blind to the diff and the tests.

> (ADR-0006) The requester picks the result path and writes it in the brief. A stage that already names a report location keeps it; otherwise the file goes in the run directory (S-173). The result files of review workers go in the run directory with no round tag, and only the review orchestrator writes findings files under plan/review/ (D-19, agent-decided). The started agent writes its result there, then sends finished. … The stage whose brief names the file owns its format, so the findings JSON and the `REVIEW:`, `ADVERSARY:` and `OUTCOME:` lines keep their shapes (S-171)

> (ADR-0010) The team entry script, not the agent, sends finished to that target. It ignores the target field the sender wrote and uses the target the manifest and the pattern name, so an agent cannot send it elsewhere (S-223, S-235). The contact agent gets a short copy of each finished, parked and exited message, for the manifest only (S-212, S-216).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0001-glossary-terms
0015-team-skill-and-manifests

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

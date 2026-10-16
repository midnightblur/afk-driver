## Goal
Add the wait script hooks/inbox-wait.sh (file name: plan decision D-3): one wait job per run that checks the contact agent's inbox every 10 seconds and exits once, on the first file in the inbox or when the earliest park-until time passes, so the harness's background-job exit notice wakes the contact agent. The same change adds the capability row to CAPABILITIES.md, one conformance probe per harness to providers/CONFORMANCE.md, the script's row to hooks/README.md, the AGENTS.md hooks entry, a CHANGELOG line and a hook-smoke case. The stall watchdog script and its existing wait loop are not edited. The slice ends at the script: arming and stopping the job is the team skill's work.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Wait script" binds the public interface
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "Wait job beside `stall-watchdog`, armed with `run_in_background`" (changes C13, C14)
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Harness wake on a background job's exit" and "Background job at session end"
- SDD: SDD.md#§6 L5 — Domain Model — a run has one wait job
- SDD: SDD.md#§7 L6 — Process & Coordination — use case "Wait for messages", effect E10 and the lost-wake failure row
- SDD: SDD.md#§13 Open Questions — Q4, Q27, V25
- ADR: adr/design/0008-one-wait-job-per-run.md — one wait job per run, checking the inbox every 10 seconds

## Scope
- hooks/inbox-wait.sh
- hooks/README.md
- CAPABILITIES.md
- providers/CONFORMANCE.md
- AGENTS.md (:228)
- CHANGELOG.md
- hooks/tests/hook-smoke.sh

## Seams
- implement: §9b row "Harness wake on a background job's exit" via §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`" — the wait script, its capability row and one conformance probe per harness (INV-058)

## Acceptance
- [ ] Implements the public interface in SDD §8 row "Wait script" unmodified: 2 command-line arguments, the inbox folder and an optional park-until time; it reads no environment variable and waits the way the stall watchdog already waits (SDD §8 row "Wait script")
- [ ] The script checks the inbox every 10 seconds and exits once, at the first of a file in the inbox or the earliest park-until time passing; with nothing parked it has no end time and ends on a file or when cleanup stops it (SDD §8 row "Wait script")
- [ ] The script looks in the inbox before its first wait, so a file that landed before the job started is not missed (ADR-0008)
- [ ] The park-until argument is an absolute time in UTC, ISO 8601, to the second, the form of the agent entry's park-until field, so the job ends when a parked agent is due; the argument's format is inferred from that field (PRD AC-029)
- [ ] The script watches only the contact agent's inbox, since no other agent has one (PRD AC-046)
- [ ] Where the harness wakes on a background job's exit, the job's exit wakes the contact agent to handle the inbox message without the human; where it cannot, the capability row says so, and the contact agent says so at run start and handles its inbox at its next turn (PRD AC-065)
- [ ] CAPABILITIES.md gains one capability row for a harness waking on a background job's exit, and providers/CONFORMANCE.md one conformance probe per harness: arm a job, idle, assert the agent is re-invoked (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`")
- [ ] The script lives under hooks/ with its hooks/README.md row, the AGENTS.md hooks entry (AGENTS.md:228) names it, and CHANGELOG.md gains a line; CLAUDE.md, the one-line pointer @AGENTS.md, is not edited (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`")
- [ ] The README row, the AGENTS.md entry and the changelog line name no harness and carry no ticket-shaped id; the script reads no all-caps variable, is LF and keeps its planned name, so registry check C, rule I and rule M pass; the wiring gate passes once its README row names it; providers/PARITY.md gets no row (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`")
- [ ] hooks/stall-watchdog.sh and its existing wait loop are not edited (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`")
- [ ] A run has one wait job: the script holds no guard against a second job, since the contact agent stops the job the manifest names before it starts the next (SDD §6)
- [ ] After the job ends, the contact agent handles every inbox message, then starts the next job; the wake comes up to 10 seconds after a file lands (SDD §7)
- [ ] When the wake is lost (the probe failed, the session ended, or a Codex contact agent), the next-turn check of the inbox and the manifest recovers the run (SDD §7)
- [ ] When the session ends while a wait job runs, the job's manifest entry stays, cleanup finds its process gone, removes the entry and reports it already gone, and the next-turn check resumes the agent (SDD §9b row "Background job at session end")
- [ ] Before this subtask merges, a probe per harness ends a session while a wait job runs and checks that the next turn's check of the inbox and the manifest recovers the run (SDD §13 V25)
- [ ] The per-harness conformance probe re-checks each harness version's wake on an inbox file; a Codex contact agent says at run start that results wait for the human's next message (SDD §13 Q4)
- [ ] ADR-0004's status line is not edited by this subtask; the edit to Superseded by ADR-0008 is the human's (SDD §13 Q27)
- [ ] Conforms to ADR-0008 — one wait job per run that exits at the first file or the earliest park-until time; no silent pattern substitution (ADR-0008)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Wait script")
- [ ] The seam-test for the harness wake asserts on the harness's real behaviour: per harness, an armed job's exit re-invokes the idle agent, or the capability row records that it does not (SDD §9b row "Harness wake on a background job's exit")

## Produces
- hooks/inbox-wait.sh#park_until_utc — the wait script: exits once on an inbox file or the earliest park-until time
- CAPABILITIES.md#background job wake — the capability row for a harness waking on a background job's exit

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash -n hooks/inbox-wait.sh && grep -n 'park_until_utc' hooks/inbox-wait.sh && grep -n 'background job wake' CAPABILITIES.md` | the script parses; the Produces anchors exist |
| unit | `bash hooks/tests/hook-smoke.sh`, new case: a file present before the first wait makes the script exit at once; a park-until time that passes makes it exit; with nothing parked and no file it keeps waiting until stopped | the wait script's two exits and its first look |
| static | `afk-python -m pytest scripts/tests/test_native_contract_events.py scripts/tests/test_skill_registry_gate.py -q` | rule A, rule I, rule M and registry check C stay green with the new script and rows |
| integration | Environment-gated per harness: a probe that ends a session while a wait job runs, then checks that the next turn's check of the inbox and the manifest recovers the run | V25; seam-test for the row "Background job at session end" |
| integration | Environment-gated per harness: one conformance probe row in providers/CONFORMANCE.md that arms the job, idles, and asserts the agent is re-invoked | Q4; seam-test for the row "Harness wake on a background job's exit" |

## Context excerpts
> (SDD §8 row "Wait script") | Wait script | Check the contact agent's inbox every 10 seconds and exit once, at the first of two events: a file is in the inbox, or the earliest park-until time passes (S-195, S-226). With nothing parked it has no end time: it ends on a file or when cleanup stops it. It looks in the inbox before its first wait (inferred, R46-WAIT card) | 2 command-line arguments: the inbox folder and an optional park-until time (R46-WAIT card, accepted as S-226); reads no environment variable (S-128); waits the way the stall watchdog already waits | none | Run (process entry) |
> (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`", Planned change) C13, C14: one capability row, one conformance probe per harness, a new wait script under hooks/ with its README row, the hooks list in AGENTS.md and a changelog line (S-105). The script checks the contact inbox every 10 seconds and takes 2 arguments, the inbox folder and an optional park-until time (S-226)

> (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`", Impacted flows) Every capability branch; every watchdog arm site and the preflight CI wait, all unchanged, since the change edits none of them. The new capability row and probe rows leave rule E, the twin test and the behavior registry unchanged (hooks/native-contract-gate.sh:90, :275-306; hooks/tests/hook-smoke.sh:822; scripts/behavior_registry.py:527-533). The new script passes registry check C, rule I and rule M if it reads no all-caps variable, is LF and keeps its planned name (hooks/skill-registry-gate.sh:157; native-contract-gate.sh:536, :751-755; .gitattributes:5); the wiring gate passes once its README row names it (hooks/wiring-gate.sh:8-9). Only the forge loops have tests (scripts/tests/test_forge_adapters.py:596-623); the watchdog and its arm sites are unguarded (INV-058)

> (SDD §14 row "Wait job beside `stall-watchdog`, armed with `run_in_background`", Conventions / landmines) The watchdog script and the existing wait loop are not edited; the new script waits the way the watchdog already waits, which replaces the signed 'no polling loop' (S-226, §12); it reads no environment variable, so registry check C has nothing to check (S-128). The README row, the AGENTS.md hooks entry (AGENTS.md:228) and the changelog line name no harness, or rule A fails (native-contract-gate.sh:97-153; scripts/tests/test_native_contract_events.py:143), and carry no ticket-shaped id (hooks/lib/sensitive-patterns.tsv:8). providers/PARITY.md claims one row per hook script (:3-4) but no code reads it, and 10 of 30 scripts have none, so the new script needs no row there (INV-058). Compatibility: only adds (S-246). Rollback: run cleanup first, so no wait job is left running, then revert the commit or install the previous plugin version (S-246)
> (SDD §9b row "Harness wake on a background job's exit") | Harness wake on a background job's exit | Claude Code 2.1.282 and Codex CLI 0.157.0, observed once each on Windows 11; trial T12 on Claude Code and Codex 0.158.0; no version pin in this repository | Claude Code: the job's exit re-invoked the idle top-level agent; in T12 a file landing in its inbox folder woke it the same way. Codex: the exit was logged and started no turn, in both trials (INV-011, T12). A contact agent that is itself a subagent was not tried | Wake absent → next-turn check of the inbox and the manifest; a Codex contact agent says so at run start (S-105, S-122, S-166). The wait job checks the inbox every 10 seconds and exits, so the wake comes up to 10 seconds after a file lands (S-226) | The conformance probe per harness (C13): arm a job, idle, assert the agent is re-invoked |
> (SDD §9b row "Background job at session end") | Background job at session end | Claude Code 2.1.282 headless and Codex CLI 0.157.0 interactive, observed once each | The job's shell is killed, so its last command never runs and no wake arrives; a child already running survives as an orphan until it exits by itself (INV-011) | The wait job's entry stays in the manifest; cleanup finds its process gone, removes the entry and reports it as already gone (S-117); the next-turn check resumes the agent (S-94) | A build-time probe per harness (§13 V25): end a session while a wait job runs, then check that the next turn's check of the inbox and the manifest recovers the run (S-94; audit L40, agent-decided) |
> (SDD §6) | I19 | A run has one wait job | Run | The contact agent. Before it starts a wait job, it stops the job the manifest names and removes that line: when an agent parks, after each job ends, and when it takes over a run. After a job ends, it handles every inbox message, then starts the next job (S-240) | Nothing else refuses a second job (inferred: S-240 names no other guard); the guard is the contact agent's own step (S-240) | S-195, S-240 |
> (SDD §7) | Wait for messages | The contact agent parks an agent, a wait job ends, or the contact agent takes over a run (S-240) | Stop the job the manifest names and remove its line, then start the next job; after a job ends, handle every inbox message first (S-240) | The job checks the inbox every 10 seconds and exits at the first file or the earliest park-until time (S-226) | Contact agent only (I19) |
> (SDD §7) | The contact agent's wake is lost (probe failed, session ended, or a Codex contact agent) | none | next-turn check of the inbox and the manifest by the contact agent or an adopting one (S-94, S-166) | human's next message | Contact agent |
> (SDD §7) | E10 | Write an envelope file into the contact agent's inbox directory; the wait job's 10-second check finds it, and the job's exit wakes the contact agent (S-226) | agent-send to the contact agent; for finished, the copy after the target pane (S-235), or, when the contact agent is the target, the one envelope, with no pane delivery before it (§3 'finished: order and partial failure'; inferred from S-215, AC-046) | Every started agent and the job supervisor | None: a delivered message is not taken back; a later message corrects it (S-196) | Nothing is typed into the contact's pane | Body file first, under a temporary name, then renamed. Then the envelope, also under a temporary name, then renamed (S-196, S-172) | message id | When the delivery fails, the body without an envelope stays as an orphan until cleanup. The command answers exit code 4 or exit code 2 (S-196); a failed finished copy answers exit code 4, naming the inbox (S-235) | The sender sends again with the same message id; for finished, the repeat check drops the second copy (S-196, S-235). Where no wake arrives (a Codex contact), the next-turn manifest check | Built into the script (S-196) | The contact agent | S-147, DLV-1, S-142, AC-046, T12, S-226, S-235 |
> (SDD §4) | park-until time | timestamp | yes | empty | absolute time: UTC, ISO 8601, to the second (S-232) | — | — | AC-029 | S-232 |
> (SDD §13 Q4) Q4: Trials answered the wake question once per harness (INV-011), and trial T12 repeated it for a file landing in the inbox: Claude Code wakes, Codex does not. The wait job now checks the inbox every 10 seconds and exits on a file (S-226), so the wake rides on the job's exit. A Codex contact agent says at run start that results wait for the human's next message (S-166). No probe covers the contact's wake on an inbox file (INV-031, INV-038 at skills/afk/bug/SKILL.md:69); D-01 depends on it. The per-harness probe (C13) re-checks each version; the next-turn check covers a failure. A contact agent that is itself a subagent was not tried
> (SDD §13 Q27) Q27: ADR-0004's status still reads Accepted; ADR-0008 supersedes it, and the status edit is outside this SDD. ADRs 0006 to 0016 were written into adr/design/ when this SDD landed, 2026-10-07, and §9, §12 and §14 cite them there
> (SDD §13 V25) V25: Whether the next-turn check recovers a run whose session ended while its wait job ran; no test in this repository covers it (§9b row Background job at session end; INV-011). Proven at build by: a probe per harness that ends a session while a wait job runs, then checks that the next turn's check of the inbox and the manifest recovers the run (S-94; audit L40, agent-decided)
> (PRD AC-029) **AC-029** A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time.
> (PRD AC-046) **AC-046** No message changes text the human has typed into the contact agent and not sent: a message never goes into the contact agent's input box. Where a tool delivers only by typing into a pane, the contact agent's messages land in its **inbox** (a folder that holds its messages). No other agent has an inbox. Every other agent gets its messages in its pane, and nobody types in those panes. A message that arrives while such a pane holds unsent text is submitted together with that text.
> (PRD AC-065) **AC-065** The contact agent handles an inbox message without the human's help where its harness can wake it. Where the harness cannot, the contact agent says so at run start and handles its inbox at its next turn.
> (ADR-0008) One wait job per run (S-195). It checks the contact agent's inbox every 10 seconds, and exits at the first file or at the earliest park-until time (S-226). It looks in the inbox before its first wait, so a file that landed before the job started is not missed (inferred, R46-WAIT card). With nothing parked it has no end time: it ends on a file or when cleanup stops it. The script takes 2 arguments, the inbox folder and an optional park-until time, and still reads no environment variable (R46-WAIT card, accepted as S-226; S-128). It waits the way the stall watchdog already waits.

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

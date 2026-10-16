C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-011-tracked-wake-job/COVERAGE.json

## Answer

Today one in-repo mechanism wakes an idle orchestrator from a background job: hooks/stall-watchdog.sh, started in a background shell in the spawn's own message (DELEGATION.md:36; armed at skills/afk/autopilot/SKILL.md:40 and skills/utils/investigate/SKILL.md:44). It polls every 60 s, exits 3 after 20 idle minutes, 4 at the 90-minute cap, 2 on a usage error, never 0 (hooks/stall-watchdog.sh:21-31, :50-66). It is not a hook (:9); no registered hook event fires on a job exit (hooks/hooks.json:3-71, hooks/hooks.codex.json:3-71). The wake is stated only as doctrine (DELEGATION.md:34). No CAPABILITIES.md row covers background execution or wake (CAPABILITIES.md:5-22), and no conformance probe proves it (providers/CONFORMANCE.md:15-42; providers/PARITY.md:116). preflight PF-6 runs forge `ci-wait` the same way (skills/afk/preflight/SKILL.md:194-212; pinned by scripts/tests/test_forge_adapters.py:125-160).

Live trials, Windows 11, one observation each (scratchpad/trials/TRIALS.md § T1-T4): on Claude Code 2.1.282 every tracked job that ended woke the idle top-level agent; a contact agent that is a subagent is not covered (c-413b0ca5, T1). On Codex CLI 0.157.0 the job exit is logged but starts no new turn, so the idle agent is not woken (c-563951fc, T3). At session end, on both harnesses, the harness kills the job's shell, so its completion and wake are lost; a child already running survives as an orphan (c-5815db4c; T2 headless print mode only, T4). No plugin document states this (c-62a7aea9; DELEGATION.md:38).

Settled design S-105 (GRILL-LOG.md:288) wakes on the wait job's exit only where a per-harness probe passes, else falls back to the next-turn manifest check. Inferred (c-093588e7): the design does not need the wake answered before it is built.

## Sites that change or break

All unguarded.

- DELEGATION.md:37, :39: break. A parked agent is silent, so its armed watchdog fires and the on-fire rule stops it; disarm names only normal completion. Outside this ledger: settled S-106 (GRILL-LOG.md:289) disarms the watchdog at park and arms it again on resume.
- CAPABILITIES.md:3: breaks: the wake is a capability branch with no row. S-105 adds one row (GRILL-LOG.md:288).
- CLAUDE.md:201, AGENTS.md:201: break if the script lands in hooks/ (inferred); same-commit update owed (FRESHNESS.md:60).
- docs/afk/agent-team-topology/GRILL-LOG.md:232 (S-58), :145 (S-38): break; S-105 narrows S-58 to no poller (GRILL-LOG.md:288).
- docs/afk/agent-team-topology/PRD.md:74 (AC-012), GRILL-LOG.md:56: break (inferred): the wait job is a background process the run starts. S-105 makes it a manifest process entry killed at cleanup.
- hooks/skill-registry-gate.sh:149 (check C): unchanged under S-128 (GRILL-LOG.md:325). The wait script takes its time as one command-line argument and reads no environment variable, so check C has nothing to flag.
- Unchanged: ADAPTERS.md:66,72; AGENTS.md:31,56; CAPABILITIES.md:5,13,14,15,18,26,41; CHANGELOG.md:560,1177,1178,1273,1342,1343,1345,1349,1350,1587; CLAUDE.md:11,15,31,37,38,56; DELEGATION.md:25,32,34,36,38; FRESHNESS.md:15,17,40,46,60,62; GLOSSARY.md:52; INVESTIGATION.md:108; PROVIDERS.md:18,26,29,39,71; adapters/forge/github/CONTRACT.md:11,31,37; adapters/forge/github/adapter.json:20; adapters/forge/github/forge.sh:8,425,460; adapters/forge/gitlab/CONTRACT.md:12,32,38; adapters/forge/gitlab/adapter.json:20; adapters/forge/gitlab/forge.sh:8,471,473,514; adapters/forge/none/CONTRACT.md:12; adapters/forge/none/adapter.json:20; hooks/README.md:76,97; hooks/genericity-gate.sh:90; hooks/hooks.codex.json:3,25,53; hooks/hooks.json:3,25,53; hooks/native-contract-gate.sh:237,336; hooks/stall-watchdog.sh:2,3,5,7,10,11,14,21,23,25,27,28,36,37,38,40,43,47,48,50,51,54,64; hooks/tests/hook-smoke.sh:13,74,243; hooks/wiring-gate.sh:2,138; providers/CONFORMANCE.md:15,28,36,95,100,301; providers/PARITY.md:58,116; scripts/tests/test_forge_adapters.py:7,109,128,130,140,148,155; scripts/tests/test_skill_frontmatter.py:90; skills/afk/autopilot/SKILL.md:40; skills/afk/bug/FIXER-PROMPT.md:31,33; skills/afk/execute/SKILL.md:135; skills/afk/grill-requirements/ROUND.md:52; skills/afk/grill-requirements/SKILL.md:46,66; skills/afk/grill-requirements/TRIAGE.md:34; skills/afk/grill-solution/GROUNDING-RULE.md:40; skills/afk/grill-solution/SKILL.md:76; skills/afk/mission-control/SKILL.md:88,89; skills/afk/preflight/SKILL.md:194,199,203; skills/afk/setup/MANIFEST.md:217; skills/afk/to-subtasks/JOURNAL-FORMAT.md:37,61; skills/afk/to-subtasks/PLAN-TEMPLATE.md:72; skills/utils/investigate/SKILL.md:44; under docs/afk/agent-team-topology/: GRILL-LOG.md:17,19,21,134,135,139,146,147,148,207,223,269,275,288,324,325,326,338,353,355,356,357; investigations/INV-006-stage-skills/REPORT.md:23; research/CONVERGE.md:46; research/CRITIQUE-claude.md:14; research/CRITIQUE-codex.md:37; research/FACTS-claude.md:40,43,59,61,171; research/FACTS-quota.md:99,113; research/PROPOSAL-claude.md:67,178; research/PROPOSAL-codex.md:73; research/RESPONSE-claude.md:18; research/RESPONSE-codex.md:23; research/VERDICT-claude.md:18,32; research/VERDICT-codex.md:54,84,88.
- Name matches not about the subject stay in COVERAGE.json with disposition `irrelevant`.

## For the design

- skills/afk/execute/SKILL.md:135: a subagent is not reliably notified by its own children. Inferred (c-bd04f7df): a contact agent that is a subagent may miss the wake.
- Inferred (c-d2c2325c): if a job is orphaned and exits, cleanup later kills a gone process entry; confirm the process against the HL-1 started-at (GRILL-LOG.md:269) first.
- Inferred (c-2f5d4bde): a new hooks/ script meets native-contract check I (LF only, hooks/native-contract-gate.sh:336) and the wiring gate (hooks/wiring-gate.sh:7-11).
- GRILL-LOG.md:357 is refuted: adapters/build-gate/maven/maven-lock.sh:47 and forge.sh (github :460, gitlab :514) also sleep (c-d5e8e571).

## Frontier

- B14: installed plugin copies, other repositories and live consumers. Also GRILL-LOG.md:327 (session-end fate), GRILL-LOG.md:358 (whether a harness can wake a new session), research/FACTS-claude.md:157 and research/FACTS-quota.md:86: rest on harness behaviour or external harness docs.

## Unverified

- c-2a4f96e0: the hit set is complete over the name forms searched. Not load-bearing.

## Run notes

- The previous published ledger was partial; the human acknowledged it in round R-31 (ACK-1). Live trials turned its 5 harness-runtime claims into facts (c-413b0ca5, c-563951fc, c-5815db4c, c-51d02507, c-62a7aea9, c-a33e5885).

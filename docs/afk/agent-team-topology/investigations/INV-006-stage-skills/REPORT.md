C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-006-stage-skills/COVERAGE.json

## Answer

With no topology-map entry, one conditional added at each stage skill's work-start step changes nothing: every site is `unchanged`. Every site is also unguarded, because no gate or test reads SKILL.md body prose: registry check D (hooks/skill-registry-gate.sh:183) needs only the `LANGUAGE.md` string, and scripts/tests/test_skill_frontmatter.py:90 and hooks/native-contract-gate.sh:146 read frontmatter only.

## Stage skills and their work-start steps

Paths are skills/{afk,utils}/<name>/SKILL.md unless given.

- Research and design, spawning: grill-requirements :16; grill-solution :14 (also :76, L9-SEAM-GRILL.md:16, :22, GROUNDING-RULE.md:25, :40); grill-verification :55; to-subtasks :48; understand :46, :56, :65; design-system :45, :68 (stage kind inferred).
- Design and planning, inline (a team branch adds a new spawn point): to-prd :20; to-sdd :19; to-verification-plan :38; prototype :25.
- Review and audit, spawning: review :43 (second wave :199); investigate :44; verify-seams :17; retro :36; setup AUDIT.md:5; settle-change :52 (more waves :128); glossary :39; review-qa-tests :19.
- Review and audit, inline: adversary :25; diagnose :16; claude-md AUDIT.md:13; lessons :73; harvest :21.
- Callers, not stages: execute :71, :89; preflight :84, :87, :122, :130; fix :30; autopilot, bug, smoke-test, gc, tdd, mission-control. Digest-only: to-design-brief :21, to-ticket :74, to-meeting-b :36, to-meeting-d :45, :64.

## What a team path must keep (inferred from the cited lines)

- review: its REVIEW line (execute :135, review :172), the information diets (review :195, SETTLEMENT.md:52), the review INDEX.md row format (skills/afk/mission-control/scripts/tests/test_contract.py:99).
- adversary: its ADVERSARY line (:43).
- grill-solution: closed INV ids, which the to-sdd investigation gate reads.
- understand M-1 auto (:28): no prompts.
- every stage: the stall-watchdog wake-up (DELEGATION.md:36).

## Wording constraints

- hooks/native-contract-gate.sh:114-122 rule A bans harness words in plugin markdown; `${AFK_PLUGIN_ROOT}/…` passes.
- The genericity gate bans ticket ids and product names.
- Downstream-blind rule (CLAUDE.md:25): naming the map and the entry script is allowed; naming the calling stage is not.
- Keep the branch inside an existing step: to-subtasks :51 cites to-sdd "Step 7" and grill-solution :68 cites "Step 4".
- ROUND.md:52, TRIAGE.md:33 and GROUNDING-RULE.md:40 are shared by all 3 grills.

## For the design

- Several stages spawn in more than one wave (review :199, settle-change :128, grill-solution per layer); one line at the first step leaves later waves unbranched.
- The settled lock "a spawned agent never spawns" (GRILL-LOG.md:133) conflicts with PRD.md:148 "every agent may always fan out its own native subagents".
- A map entry with no transport still changes behaviour (PRD.md:29, :34); only a missing entry means "run as today".
- "topology map" and "team entry script" are not in GLOSSARY.md.

## Frontier

B14: other repositories or installed plugin copies that pin this prose.

## Unverified

One claim, not load-bearing: the hit set holds every reference over the literal forms searched. The blind counter-search added 241 nodes over other forms.

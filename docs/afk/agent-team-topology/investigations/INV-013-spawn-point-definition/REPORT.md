C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · closed-with-frontier · boundaries 13/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-013-spawn-point-definition/COVERAGE.json

## Answer

DELEGATION.md defines a spawn in six parts. Must-delegate triggers: 5, no size exemption (:7-13). Never-delegate: human conversation, conversation synthesis, single-writer stamps, accumulated-nuance loops (:15-20). Spawn rules (:24-30): independent children in one message; background spawn before yielding in an interactive phase; named types first (afk-reader, afk-runner, afk-runner-lite, afk-implementor, afk-tracer), general-purpose only when none fits; paths and a task, never content; nesting cap of 3 levels, a child spawns helpers only when the spawn states its depth, else runs them inline (:29); blind children where a skill demands it. Stall watchdog: arm hooks/stall-watchdog.sh in the spawn's own message for a child that can run past ~15 min, re-arm or park on fire, disarm on completion (:32-39). Every spawn names its model tier; the implementation tier travels as afk-implementor (:43-50). Return: the skill's structured tail, body ~30 lines, bulk to a file (:63-69).

A stage skill's spawn step (inferred from autopilot SKILL.md:33-40, SUBAGENT-PROMPT.md:3,41, review SKILL.md:31,43,146, SETTLEMENT.md:17,52, bug SKILL.md:30,42,68,87-88, investigate SKILL.md:44): names the type or tier, hands paths plus a filled prompt template, spawns independent children in one message, states depth when the child may spawn, arms the watchdog for long children, keeps single-writer stamps, parses only the child's trailing line. The parent reads each verdict from the spawn call's own result (execute SKILL.md:135).

## Spawn sites

Paths are skills/{afk,utils}/<name>/SKILL.md unless given.

- Spawn steps: autopilot :33; execute :39, :67, :89; bug :55, :68, :87, :88; review :43, :146, :199, SETTLEMENT.md:17; grill-requirements :16, :46, :66, TRIAGE.md:34, ROUND.md:52; grill-solution :14, :76, GROUNDING-RULE.md:40, L9-SEAM-GRILL.md:16, :22, EXTERNAL-SEAM-RULE.md:9; grill-verification :55; smoke-test :43; understand :56 (:59), :65; retro :36; mission-control DIGEST-FORMAT.md:210; design-system :45, :68; lessons CAPTURE.md:68; setup AUDIT.md:5; to-meeting-b :35, :36, :139; to-meeting-d :45, :64; to-sdd :64, :66; to-subtasks :48, :56 (:54); to-prd :16; prototype :31; fix :23; to-design-brief :21; glossary :38; settle-change :52, :83, :128; verify-seams :17; investigate :44.
- Point at a spawning skill, spawn nothing: preflight :85, :87, :122; grill-solution :49; settle-change :94; verify-seams :15.
- Start no subagent: claude-md AUDIT.md:13; to-verification-plan :38; lessons :73; fix :28; to-subtasks :136; preflight :194 and mission-control :89 (background processes); the rest of the 25 sites in claim c-55978751 are in-session steps or unrelated rules.

## For the design

- Watchdog armed only at autopilot :40 and investigate :44. Inferred: execute :67, smoke-test :43 and bug :68 run children DELEGATION.md:34 lists, with no arm; run length not measured.
- No stage-skill spawn states depth; only investigate :44 does (agents/afk-tracer.md:39). Inferred conflict: the executor prompt (SUBAGENT-PROMPT.md:8-38) states no depth, yet execute :67 and review :43 spawn.
- Inferred conflict: GRILL-LOG.md:49 and PRD.md:148 let subagents spawn; DELEGATION.md:29 says helpers do not. PRD.md:129's depth answer at GRILL-LOG.md:133 was withdrawn by :274 but still reads Locked.
- review :43 pastes checklists into prompts, against DELEGATION.md:28. 14 spawn steps name no type or tier, against :43 (review :43, :146, SETTLEMENT.md:17, grill-requirements :66, TRIAGE.md:34, L9-SEAM-GRILL.md:16, :22, understand :65, retro :36, DIGEST-FORMAT.md:210, CAPTURE.md:68, AUDIT.md:5, bug :36-40, execute :89). design-system :45 names Explore, a harness built-in (inferred).
- Rules only at sites: bounded retries (understand :56, DIGEST-FORMAT.md:217, execute :93); autopilot :42 sequential by design; blind diets (bug :42, SETTLEMENT.md:52, review :195, adversary :21, grill-requirements :66, understand :65).
- DELEGATION.md:46 points at a PROVIDERS.md "Pin delivery" section that does not exist; the rule is unheaded at PROVIDERS.md:65.
- Codex name: stub name field is afk-afk-reader (providers/codex/agents/afk-afk-reader.toml:1); trial T5 (Codex 0.157.0, once) refused afk-reader, refuting PROVIDERS.md:23. The gate checks only the stub file (hooks/native-contract-gate.sh:199-203).
- Outside this ledger (not in COVERAGE.json): a later trial, T6 on Codex 0.157.0, showed Codex finds an agent by its file's name field, not its filename. Settled S-127 (GRILL-LOG.md) sets each Codex stub's name field to the skill name.

## Frontier

- B14: other repositories, deployment manifests, live consumers.

## Unverified

- c-d2628e76: the hit set holds every reference over the name forms searched. Not load-bearing.
- c-c2ccf369: no gate ties DELEGATION.md's type list to agents/; providers/PARITY.md:156 overstates the registry gate (hooks/skill-registry-gate.sh:5-6,74-76). Not load-bearing.

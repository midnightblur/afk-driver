## Goal
Change the stage-skill spawn points so each role spawn starts a pane agent (an agent in its own terminal pane) through the contact agent (the agent the human talks to), and helper spawns stay subagents. Each spawn point and wave, and the work start of each inline stage, gains one pointer line to DELEGATION.md's pane-agent rule. This slice changes the spawn steps and the lines outside the steps that the §14 row "Spawn steps that start a role agent (S-208's list)" lists, except: the review gate's and settle-change's lines (owned by 0018-review-gate-pane-workers), the adversary's execute :90, :94 (owned by 0019-adversary-pane-agent), the bug skill's lines (owned by 0022-bug-pane-legs, which ships the bug skill in one commit), and the doctrine lines of DELEGATION.md, CAPABILITIES.md, PROVIDERS.md and autopilot :40 (owned by 0014-delegation-doctrine). It also runs the spawn-site checks and the probes that prove the spawn-rules rows.

## Complexity
complex

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`", "Spawn steps that start a role agent (S-208's list)" and "DELEGATION.md spawn rules (:24-30)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "Named agent definitions and pinned models in a pane agent"
- SDD: SDD.md#§13 Open Questions — V19, V20, V22, V24 and Q33
- ADR: adr/requirements/0013-role-agents-are-pane-agents.md — every spawn step that starts a role agent changes

## Scope
- skills/afk/autopilot/SKILL.md
- skills/afk/autopilot/SUBAGENT-PROMPT.md
- skills/afk/grill-solution/L9-SEAM-GRILL.md
- skills/afk/understand/SKILL.md
- skills/afk/lessons/CAPTURE.md
- skills/utils/investigate/SKILL.md
- skills/utils/verify-seams/SKILL.md
- skills/afk/*/SKILL.md   # only the spawn points and waves the C10 pointer lines go to
- skills/utils/*/SKILL.md   # only the spawn points and waves the C10 pointer lines go to
- skills/afk/AGENTS.md
- agents/afk-tracer.md
- LAVISH.md
- AGENTS.md
- README.md
- GLOSSARY.md   # only the lines that call a role agent a subagent; GLOSSARY.md:319 is 0018's

## Seams
- implement: §14 row "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`" — about 30 pointer lines, one at every spawn point and wave, and at the work start of each inline stage, to the doctrine file owning the topology branch (INV-006)

## Acceptance
- [ ] One pointer line to DELEGATION.md's pane-agent rule sits at every spawn point and each wave, and at the work start of each inline stage, inside an existing step, in downstream-blind wording; about 30 lines in all (SDD §14 row "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`")
- [ ] Seam (plan D-14): §14 row "Spawn steps that start a role agent (S-208's list)", grounded by INV-061 (closed with frontier) — before this subtask merges, §13 V19, V20, V22, V24 are proven at build as listed in ## Verification, and V23 in 0018-review-gate-pane-workers, which states the inline run V23 checks (plan D-12); the change follows the row's Planned change cell (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] In the contact session each role spawn starts a pane agent; in any other agent it sends a start request; a fan-out that started children "all in one message" becomes one start request that lists every agent (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] Helper spawns stay subagents with the named types and model tiers (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The role steps that name the subagent mechanism, an agent type, a same-call return or a vanished subagent change; mechanism-neutral role steps and every helper step stay as they are (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The change-list entries in this slice's Scope change: autopilot :33, :35, :39, SUBAGENT-PROMPT.md:3, :41; understand :65; lessons CAPTURE.md:68; verify-seams :17; investigate :44, with its tracer watchdog arm (plan D-23); and the missed role spawns investigate :53 and L9-SEAM-GRILL.md:14 (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The lines outside the steps in this slice's Scope change: LAVISH.md:327-329, :334; agents/afk-tracer.md:16, :40; skills/afk/AGENTS.md:7; and the skill, AGENTS.md, README.md and GLOSSARY.md lines that call a role agent a subagent, as INV-061's site list names them (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The role steps grill-requirements :46, ROUND.md:52, grill-solution :76 and GROUNDING-RULE.md:40 name no mechanism, so they stay; design-system :68 and to-meeting-b :139 start role agents with no step edit (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] A spawn that runs a check stays a helper that returns a digest, and the skill that owns the gate turns it into the verdict; this places execute :69, smoke-test :43, to-sdd :64, :66, EXTERNAL-SEAM-RULE.md:9 and to-subtasks :56 as unchanged helpers (agent-decided, SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The /afk:investigate runs at review/SKILL.md:38, diagnose :88 and to-prd :12 stay inline runs, not spawns; the /afk:fix hub starts both its reader helpers, :23 and :63; /afk:diagnose gains a helper entry of 1 (agent-decided, SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] Every page writer on the authored path, /afk:prototype's included, is a role agent with lifespan Feature (agent-decided, SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] LAVISH.md:421, the re-starts at autopilot :35, understand :67 and execute :93, and the /afk:investigate runs at execute :51 and execute/CITED-MODE.md:75 are classed by the V19 spawn-site check under S-190's role-work rule, and each role spawn among them changes like the rest (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] LAVISH.md's fresh-spawn recovery for a page writer becomes the resume-first recovery of AC-055, and verify-seams :30 no longer sends a duty after launch; the SDD infers both, so the executor confirms each at its line (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] With no stage map entry each role spawn is an implicit single-role step in a pane agent, with lifespan Turn and the requester as report target, and its start request names the step `solo:` followed by the role (agent-decided, SDD §13 Q33)
- [ ] A pane role runs the model its tier names in PROVIDERS.md: agent-start takes the tier's model cell and the tier's effort cell where the harness has one; no spawn step relies on an agent definition for a pane role's type sizing (autopilot :35, SUBAGENT-PROMPT.md:3) (agent-decided, SDD §9b row "Named agent definitions and pinned models in a pane agent")
- [ ] The changed lines carry no harness word that native rule A refuses (subagent_type, SendMessage, harness names, the mcp__ prefix, PLUGIN_ROOT, CLAUDECODE) (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The configuration reader's refusal of the switch key at afk-config.py:581-582 changes in 0002-config-transport-and-pattern-keys, not here (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The spawn points of research, grounding, design, planning, review and audit work start their role agents as pane agents through the contact agent, so that work can run the debate pattern with 2 or more agents on different models (PRD AC-006)
- [ ] Every agent that writes a plugin artifact, code or a ledger, or returns a gate verdict, is started as a role agent; an agent that only reads and returns text is a helper (PRD AC-040)
- [ ] A role agent that needs another pane agent sends the contact agent a start request naming the pattern step, the requester and the lifespan, and listing each agent with a role and a brief path (PRD AC-042)
- [ ] A helper starts no agent, and a start request past the 3-level nesting limit is refused (PRD AC-043)
- [ ] Conforms to requirement ADR-0013 — every spawn step that starts a role agent changes, and only the contact agent starts pane agents (requirement ADR-0013)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`")
- [ ] Seam-test for the §9b row "Named agent definitions and pinned models in a pane agent" asserts on the harness's real output: probes providers/CONFORMANCE.md:436 and :437 re-run on the shipped version (SDD §9b row "Named agent definitions and pinned models in a pane agent")

## Produces
- skills/afk/autopilot/SKILL.md#pane-agent rule — autopilot's spawn point points at the rule (contract writer: keep this anchor phrase; the executor writes it in the pointer line)

## Consumes
- 0014-delegation-doctrine DELEGATION.md#pane-agent rule — the doctrine every pointer line names
- 0015-team-skill-and-manifests skills/afk/team/SKILL.md#contact agent's run procedure — the start path the contact agent runs
- 0001-glossary-terms GLOSSARY.md#**Pane agent** — the term the changed AGENTS.md, README.md and GLOSSARY.md lines use

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -c 'pane-agent rule' skills/afk/autopilot/SKILL.md` prints 1; `grep -n 'pane-agent rule' DELEGATION.md`; `grep -n "contact agent's run procedure" skills/afk/team/SKILL.md`; `grep -nF '**Pane agent**' GLOSSARY.md` | Produces anchor present once; consumed anchors present |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py scripts/tests/test_skill_registry_gate.py scripts/tests/test_merge_fragments.py -q` | skill frontmatter, agent registration and the investigate :53 merge still valid |
| static | `git diff -U0 main -- skills agents LAVISH.md \| grep -E '^\+[^+]' \| grep -e 'mcp__' -e CLAUDECODE -e SendMessage -e subagent_type -e 'Claude Code' -e Codex -e '[^A-Z_]PLUGIN_ROOT'` prints nothing | no harness word banned by native rule A in the changed lines |
| unit | V19 plan check: a whole-repository search (`git grep -n`) for the spawn-step name forms, among them 'fresh adjudicator', 'Brief a fixer', 'page-writer child' and 'single-message parallel', each hit classed as a role spawn, a helper spawn or none; the tally is taken again at build and recorded in the subtask's evidence | V19 |
| unit | V24 plan check: re-read each PRD.md and INDEX.md line the §14 spawn rows cite, before merge, and record any line that moved or changed | V24 |
| integration | V20, environment-gated on both harnesses with herdr: probe providers/CONFORMANCE.md:436 re-run on the shipped version (a pane agent resolves the plugin's named agent definitions); recorded as a probe row | V20; seam-test of §9b row "Named agent definitions and pinned models in a pane agent" |
| integration | V22, environment-gated on both harnesses with herdr: probe providers/CONFORMANCE.md:437 re-run on the shipped version (a harness started with the pinned identifier runs exactly that model); recorded as a probe row | V22; seam-test of §9b row "Named agent definitions and pinned models in a pane agent" |

## Context excerpts
> (SDD §14 row "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`", Planned change) C10: about 30 pointer lines, one at every spawn point and each wave, and at the work start of each inline stage, to one doctrine file owning the topology branch (S-95)

> (SDD §14 row "Stage-skill `spawn` points and `subagent` waves, per `DELEGATION`", Conventions / landmines) Harness words banned by native rule A; downstream-blind wording; keep the branch inside an existing step. Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version (S-246)

> (SDD §14 row "Spawn steps that start a role agent (S-208's list)", Existing contract) Spawn steps: autopilot :33; execute :39, :69, :90; bug :55, :68, :87, :88; review :43, :148, :202, SETTLEMENT.md:40; grill-requirements :16, :46, :66, TRIAGE.md:34, ROUND.md:52; grill-solution :14, :76, GROUNDING-RULE.md:40, L9-SEAM-GRILL.md:16, :22, EXTERNAL-SEAM-RULE.md:9; grill-verification :55; smoke-test :43; understand :56 (:59), :65; retro :36; mission-control DIGEST-FORMAT.md:210; design-system :45, :68; lessons CAPTURE.md:68; setup AUDIT.md:5; to-meeting-b :35, :36, :139; to-meeting-d :45, :64; to-sdd :64, :66; to-subtasks :48, :56 (:54); to-prd :16; prototype :31; fix :23; to-design-brief :21; glossary :38; settle-change :48, :78, :120; verify-seams :17; investigate :44. [...] At 1210110 the AC-040 test gives 40 role and 42 helper spawn sites, and no pane start exists in the plugin (c-b49f2672, c-11b9942b, c-1b9be445). The list misses the lines written as 'fresh adjudicator', 'Brief a fixer', 'page-writer child' and 'single-message parallel', among them SETTLEMENT.md:39, :40, review :202, settle-change :53, :89, :120, LAVISH.md:167 and to-meeting-b :35, :139 (c-f9a16b1b)

> (SDD §14 row "Spawn steps that start a role agent (S-208's list)", Planned change) In the contact session each role spawn starts a pane agent; in any other agent it sends a start request, and a fan-out 'all in one message' becomes one start request that lists every agent (S-153). Helper spawns stay subagents (S-190). [...] The 17 missed lines add 7 role spawns (bug :54, :78; execute :94; investigate :53; L9-SEAM-GRILL.md:14; settle-change :53, :89) and 10 helper spawns [...]; at 1210110 INV-061 lists 40 role and 42 helper sites (c-b49f2672, c-11b9942b). At 5c9d420 settle-change's afk-reader helper spawns (old :85-87, now :80) and the typed fixer (now :53) are gone, so the tally is taken again at build (§13 V19; GRILL-LOG.md:745 (1)). Agent-decided placements: the /afk:investigate runs at review :38, diagnose :88 and to-prd :12 run inline (D-03, D-04); the /afk:fix hub starts both its reader helpers, :23 and :63 (D-23); /afk:diagnose gains a helper entry of 1 (D-25); a spawn that runs a check stays a helper that returns a digest, and the skill that owns the gate turns it into the verdict (D-12); every page writer on the authored path, /afk:prototype's included, is a role agent with lifespan Feature (D-14); with no stage map entry each role spawn is an implicit single-role step in a pane agent, with lifespan Turn and the requester as report target (D-09; requirement ADR-0013), which its start request names solo: followed by the role (Q33); this row holds that change, so C10 keeps extends (audit L28, agent-decided). No settled row places LAVISH.md:421, the re-starts at autopilot :35, understand :67 and execute :93, or the /afk:investigate runs at execute :51 and execute/CITED-MODE.md:75; the spawn-site check of §13 V19 classes them by S-190's role-work rule

> (SDD §14 row "Spawn steps that start a role agent (S-208's list)", Impacted flows) By INV-061's verdicts, the role steps that name the subagent mechanism, an agent type, a same-call return or a vanished subagent change, and mechanism-neutral role steps and every helper step stay as they are (INV-061 c-96505bde). Change: autopilot :33, :35, :39, :40, SUBAGENT-PROMPT.md:3, :41; bug :30, :36, :42, :54, :68, :76, :98; execute :73, :90, :137; review :43, :110, :148, :202, SETTLEMENT.md:40; understand :65; CAPTURE.md:68; settle-change :48, :120; verify-seams :17; investigate :44 (c-96505bde, c-f9a16b1b; SETTLEMENT.md:40 by its node verdict). The role steps grill-requirements :46, ROUND.md:52, grill-solution :76 and GROUNDING-RULE.md:40 name no mechanism, so they stay (c-b49f2672, c-96505bde; inference). Helpers by D-12, unchanged: execute :69, smoke-test :43, to-sdd :64, :66, EXTERNAL-SEAM-RULE.md:9, to-subtasks :56 (c-11b9942b). design-system :68 and to-meeting-b :139 start role agents with no step edit (c-b49f2672; to-meeting-b :139 only points at LAVISH.md:314, inference). Outside the steps: CAPABILITIES.md:3, :12; DELEGATION.md:24, :26, :27, :29, :34, :36, :37, :39, :43, :46; LAVISH.md:327-329, :334; PROVIDERS.md:131; agents/afk-tracer.md:16, :40; afk-config.py:581-582; skills/afk/AGENTS.md:7; PROVIDERS.md:23 and :126; the skill, AGENTS.md, README.md and GLOSSARY.md lines that call a role agent a subagent (c-96505bde, c-99547c76). These runs change where the plugin is enabled and a pane transport is found (AC-041)

> (SDD §14 row "Spawn steps that start a role agent (S-208's list)", Conventions / landmines) A role agent waits for the contact agent's turn to end (requirement ADR-0013). Harness words stay out of skill prose: native-contract-gate.sh:88, :117, :129 refuse subagent_type, SendMessage and harness names, and DELEGATION.md and the BEHAVIORS.md body may not say 'on Codex' (c-b5de8e90). No test pins a spawn step's mechanism; tests reach only the tier cells and agent files (test_model_tier_gate.py:58), the agent registration (test_skill_registry_gate.py:57), investigate :53 (test_merge_fragments.py:107) and afk-config.py:581-582 (test_afk_config.py:135); check L does not cover a pane role's model (c-990e74f7). [...] A pane role loads no agent definition, so the type sizing at autopilot :35, SUBAGENT-PROMPT.md:3 and bug :68 breaks (c-96505bde), and role rules hold by convention (requirement ADR-0016). A pane role runs the model its tier names in PROVIDERS.md: agent-start takes the tier's model cell and, on Codex, its effort cell from PROVIDERS.md "Model tiers" (D-10, agent-decided; GRILL-LOG.md:745 (4)).

> (SDD §14 row "DELEGATION.md spawn rules (:24-30)", Conventions / landmines) A page writer kept through harness continuation takes later briefs as transport messages, and LAVISH.md:279's fresh-spawn recovery becomes the resume-first recovery of AC-055 (inference, not re-checked at the merge). verify-seams :30 sends a duty after launch, which S-150 forbids (inference, not re-checked at the merge).

> (SDD §9b row "Named agent definitions and pinned models in a pane agent") A pane agent's own spawns resolve the plugin's named definitions. A pinned model name runs that model; a Claude definition's pin is an alias, and a Codex reader stub's read-only sandbox did not apply. Starting the pane agent itself as a definition was not probed | A pane role agent takes its model from the tier name in PROVIDERS.md, and agent-start takes the tier's model cell and, on Codex, its effort cell (D-10, agent-decided; GRILL-LOG.md:745 (4)) | The probes; re-run on the shipped version, because the installed pins differ from this worktree

> (SDD §13 V19) Whether the name forms miss spawn steps outside skills/afk: the counter-search ran over skills/afk only, and the re-run that would close it cannot seed (Q30). [...] Proven at build by: a check the spawn-step subtask carries: a whole-repository search for the name forms, with each hit classed as a role spawn, a helper spawn or none

> (SDD §13 V20) Whether an agent started in a pane resolves the plugin's named agent definitions, such as the Codex agent stubs setup installs. Probe 2026-09-30 (providers/CONFORMANCE.md:436): a pane agent's own spawns resolve them on both harnesses [...] Proven at build by: probe :324, re-run on the shipped version, because the installed pins differ from this worktree (Q30)

> (SDD §13 V22) Whether a harness started with the pinned identifier as its launch model runs exactly that model. [...] Probe 2026-09-30 (providers/CONFORMANCE.md:437): a pinned name ran exactly that model on both harnesses. [...] Proven at build by: probe :325, re-run on the shipped version

> (SDD §13 V24) PRD.md, INDEX.md and requirement ADRs 0015 to 0018 changed after INV-030's seed, so 44 seed nodes are judged on older text, and any cited line may move again. [...] Proven at build by: the spawn-step subtask, which re-reads each cited PRD.md and INDEX.md line before it merges.

> (PRD AC-006) Research, grounding, design, planning, review and audit work runs the debate pattern with two agents or more on different models. For the PRD, the design document and the plan, the contact agent writes the draft, and two agents on different models audit it blind and debate their findings; that audit is the debate.

> (PRD AC-040) An agent that does a role's work — it writes a plugin artifact, code or a ledger, or it returns a gate verdict — starts as a pane agent. An agent that only reads and returns text to its parent is a helper subagent.

> (PRD AC-042) A role agent that needs another pane agent sends the contact agent a start request. The request names the pattern step, the requester and the lifespan, and lists 1 or more agents, each with a role and a brief. [...] A request from a stage with no stage map entry names the step `solo:` followed by the role.

> (PRD AC-043) A pane agent starts helper subagents for bulk reads, repository searches, test runs and large diffs, to keep its own context small. The plugin's named helper types and model tiers apply to helpers. A helper has no run-manifest entry and starts no agent. A start request past the plugin's 3-level nesting limit is refused.

> (requirement ADR-0013) A session with the plugin enabled changes behaviour with no configuration, wherever a pane transport exists. The earlier rule, that with nothing configured the plugin behaves as before, now holds only with the switch set back or no pane transport. Every spawn step that starts a role agent changes, and only the contact agent starts pane agents, so a role agent waits for the contact agent's turn to end.

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0001-glossary-terms, 0014-delegation-doctrine, 0015-team-skill-and-manifests

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

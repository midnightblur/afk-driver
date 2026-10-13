## Goal
State the pane-agent rule once, in full, in DELEGATION.md §Spawn rules: a role agent (an agent that does a role's work) starts as a pane agent (an agent in its own terminal pane) where the plugin is enabled and a pane transport is found, and a helper stays a subagent. The same change adds the pane-agent rule's short form as one BEHAVIORS.md entry, delivered in the setup-installed afk:behaviors block, with its inventory row and inventory id. The same commit adds the model-tier carve-out for patterns the human writes, moves the stall-watchdog arm, fire and disarm lines for role agents to the contact agent, removes the runner arm (a helper gets no watchdog), adds the park and resume watchdog moves and the wait job's arm and disarm, names the agent-start exception to the spawn-model rule, and updates the doctrine lines of CAPABILITIES.md, PROVIDERS.md, AGENTS.md:22 and the watchdog line of /afk:autopilot. The slice ends at the doctrine text and the registry entry: the spawn steps that point at the rule and the team skill are other subtasks.

## Complexity
complex

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules", "DELEGATION.md spawn rules (:24-30)" and "BEHAVIORS.md registry: the pane-agent rule's short form entry" bind the doctrine edits
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Named agent definitions and pinned models in a pane agent" and "SessionStart hook output" (the short form no longer depends on it)
- SDD: SDD.md#§13 Open Questions — Q32 (the runner watchdog arm), V19 to V24 (proofs of the spawn-rules row)
- ADR: adr/requirements/0013-role-agents-are-pane-agents.md — role agents are pane agents by default

## Scope
- DELEGATION.md
- CAPABILITIES.md
- PROVIDERS.md
- AGENTS.md
- skills/afk/autopilot/SKILL.md
- BEHAVIORS.md
- hooks/behavior-dispositions.tsv
- scripts/behavior_registry.py
- CHANGELOG.md

## Seams
- implement: §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules" — the carve-out, the watchdog moves to the contact agent, the removed runner arm, the park and resume moves and the wait job's arm and disarm (INV-055)
- implement: §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry" — one registry entry, scope configured-repos, doctrine DELEGATION.md §Spawn rules, with its inventory row and inventory id (INV-051)

## Acceptance
- [ ] DELEGATION.md gains one carve-out sentence for patterns the human writes over the judge, plugin-work and upward-override rules at :45, :49 and :50; the tier lines :47, :48 and :50 keep their text for a spawned role: an upward override picks a higher tier, and agent-start takes that tier's cell (plan D-22) (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] For a role agent the arm, fire and disarm lines of DELEGATION.md (:34, :36, :37, :39) move to the contact agent's watchdog, which a finished message turns off; a park disarms the stall watchdog and a resume re-arms it, as a kill and a fresh arm, since the watchdog has no park mode; the wait job is armed and disarmed (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] A fire on a live agent with no completion signal leaves it working, and the contact agent tells the human once when the agent's output shows no sign of waiting (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] A helper gets no watchdog: the runner arm of DELEGATION.md:34, which arms the watchdog for suite and build runners, is removed, since runners stay helpers and S-162 gives a helper no watchdog; no skill arms one today (plan D-18) (SDD §13 Q32)
- [ ] hooks/stall-watchdog.sh, DELEGATION.md :26 for helpers, :38, :41, :47-57, the tier table and check L stay unchanged (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] AGENTS.md:22, which restates DELEGATION.md:49 with no exception, updates with the doctrine in the same change (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] DELEGATION.md:46 and PROVIDERS.md:131, which forbid a spawn-model argument, each name the agent-start exception: agent-start takes the tier's model cell (agent-decided, SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] The pin-delivery pointer stays as it is: it already resolves to PROVIDERS.md "Model tiers" on main (DELEGATION.md:46), so change C17 is not made here (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] The tracer arm at skills/utils/investigate/SKILL.md:44, which the doctrine row also changes, moves in 0017-spawn-steps together with that spawn step (plan D-23) (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules")
- [ ] autopilot/SKILL.md:40's stall-watchdog arm moves to the contact agent's watchdog in the same commit as DELEGATION.md:34, :36, :37 and :39 (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] Seam (plan D-14): §14 row "DELEGATION.md spawn rules (:24-30)", grounded by INV-061 (closed with frontier) — §13 V19, V20, V22, V23 and V24 are proven at build by 0017-spawn-steps and 0018-review-gate-pane-workers as listed in their ## Verification, and V21 by 0022-bug-pane-legs; the change follows the row's Planned change cell (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] DELEGATION.md §Spawn rules states the full pane-agent rule exactly once: role agents start as pane agents whenever the plugin is enabled and a pane transport is found; helpers stay subagents that a pane agent starts for its own context, with the named types and model tiers (PRD AC-047)
- [ ] The rule defines role work: an agent that writes a plugin artifact, code or a ledger, or returns a gate verdict, starts as a pane agent; an agent that only reads and returns text to its parent is a helper subagent (PRD AC-040)
- [ ] The rule says nothing needs configuring, one configuration key switches role agents back to subagents, and a session without the plugin enabled is unchanged (PRD AC-041)
- [ ] The rule says a role agent that needs another pane agent sends the contact agent a start request, and only the contact agent starts pane agents (PRD AC-042)
- [ ] The rule says a pane agent starts helper subagents for bulk reads, repository searches, test runs and large diffs; a helper has no run-manifest entry and starts no agent; a start request past the 3-level nesting limit is refused (PRD AC-043)
- [ ] The rule says a helper does no role work and does not go past the nesting limit of 3 levels (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] The doctrine lines outside the steps that the spawn rows list change: DELEGATION.md:24, :26, :27, :29, :34, :36, :37, :39, :43, :46; CAPABILITIES.md:3, :12; PROVIDERS.md:23, :126, :131 (SDD §14 row "Spawn steps that start a role agent (S-208's list)")
- [ ] The type and tier lines DELEGATION.md:26 and :43 narrow to helpers and the subagent fallback: a pane start names a role and a brief path only (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] The rule says a pane role runs the model its tier names in PROVIDERS.md: agent-start takes the tier's model cell and the tier's effort cell where the harness has one; DELEGATION.md words this with no harness name (agent-decided, SDD §14 row "DELEGATION.md spawn rules (:24-30)") (SDD §9b row "Named agent definitions and pinned models in a pane agent")
- [ ] PROVIDERS.md:126's below-cell slice sizing, which matches no tier row, is reworded so it no longer asks agent-start for a model no tier row holds (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] The rule says a helper runs no /afk:investigate: it returns an open code claim as unverified, and its pane-agent starter investigates a load-bearing one (agent-decided, SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] CAPABILITIES.md:12 and the :15 nesting row are updated: a pane role loads no agent definition, and the depth rule (root spawns, children run helpers inline) still holds for helpers (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] BEHAVIORS.md gains one entry, scope configured-repos, doctrine DELEGATION.md §Spawn rules, whose body is the pane-agent rule's short form: fixed text that names the condition and both branches of the rule, then points at `${AFK_PLUGIN_ROOT}/DELEGATION.md`, names no harness, and detects nothing at start (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry")
- [ ] hooks/behavior-dispositions.tsv gains one inventory row of disposition registry mapping to the new entry, and EXPECTED_INVENTORY_IDS in scripts/behavior_registry.py gains that id, in the same change (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry")
- [ ] No SessionStart handler prints the short form; both hooks files, skills/afk/setup/scripts/install_block.py, the setup teardown and the parity rows stay unchanged (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry")
- [ ] The rendered afk:behaviors block stays within the 6,000-byte cap with the new entry (2549 bytes before it) (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry")
- [ ] CHANGELOG.md gains a line for the new behavior entry; a session whose user did not take setup row H7, or a repository with no .afk/config.yaml, does not get the short form; every installed block reports drift until setup renders it again (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry")
- [ ] With no pane transport or the switch set back, a run behaves as it did before this feature, except that a subagent's report file is written by the agent that started it (PRD AC-001)
- [ ] Conforms to requirement ADR-0013 — role agents are pane agents by default, no silent pattern substitution (requirement ADR-0013)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "DELEGATION.md spawn rules (:24-30)")
- [ ] Seam-test for the §9b row "Named agent definitions and pinned models in a pane agent" asserts on the harness's real output: the probes providers/CONFORMANCE.md:436 and :437, re-run on the shipped version (SDD §9b row "Named agent definitions and pinned models in a pane agent")

## Produces
- DELEGATION.md#pane-agent rule — the full rule, stated once: role agents start as pane agents where the plugin is enabled and a pane transport is found; helpers stay subagents
- BEHAVIORS.md#doctrine: DELEGATION.md §Spawn rules — the short form's registry entry, scope configured-repos

## Consumes
- 0008-inbox-wait-script hooks/inbox-wait.sh#park_until_utc — the wait job the doctrine arms and disarms

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -c 'pane-agent rule' DELEGATION.md` prints 1; `grep -c 'doctrine: DELEGATION.md §Spawn rules' BEHAVIORS.md` prints 1; `grep -n 'park_until_utc' hooks/inbox-wait.sh` | the Produces anchors exist once, so the rule is stated once; the consumed wait job exists |
| static | `grep -n 'suite/build runners' DELEGATION.md` prints nothing | the runner arm of DELEGATION.md:34 is removed |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py scripts/tests/test_model_tier_gate.py -q` | skill frontmatter still valid; check L still passes on the tier table |
| static | `git diff -U0 main -- DELEGATION.md BEHAVIORS.md skills/afk/autopilot/SKILL.md \| grep -E '^\+[^+]' \| grep -e 'mcp__' -e CLAUDECODE -e SendMessage -e subagent_type -e 'Claude Code' -e Codex -e '[^A-Z_]PLUGIN_ROOT'` prints nothing | no harness word banned by native rule A or the behavior registry in the changed lines |
| unit | `python -m pytest scripts/tests/test_behavior_registry_gate.py scripts/tests/test_behavior_registry.py -q` and `bash hooks/tests/hook-smoke.sh` | the registry, its dispositions and EXPECTED_INVENTORY_IDS agree with the new entry |
| integration | `python scripts/behavior_registry.py render --output <scratch file>` then grep the rendered block for the new entry's body and check its UTF-8 byte size is at most 6000; `python scripts/behavior_registry.py validate --verbose` passes | seam-test of §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry": the setup-installed block carries the entry within the byte cap |
| integration | environment-gated on both harnesses with herdr: re-run the probes providers/CONFORMANCE.md:436 (a pane agent's spawns resolve the named definitions) and :437 (a pinned name runs that model) on the shipped version; record the result rows | seam-test of §9b row "Named agent definitions and pinned models in a pane agent" |

## Context excerpts
> (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules", Existing contract) Judge, plugin-work and upward-override rules absolute (DELEGATION.md:45, :49, :50); the role decides the model through PROVIDERS.md "Model tiers" (:43), and the implementation model travels as the afk-implementor type (:46). The watchdog section says which spawns to arm, arm, fire, kill and disarm (:34, :36-39), and disarm names only completion; hooks/stall-watchdog.sh exits 3 when stale and 4 at the cap, never 0, and a kill is its disarm (:14-16, :21-31). Only skills/afk/autopilot/SKILL.md:40 and skills/utils/investigate/SKILL.md:44 arm it. No test or gate reads the model or watchdog text, and no test runs stall-watchdog.sh; scripts/behavior_registry.py:383 checks only the heading BEHAVIORS.md names (INV-055)

> (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules", Planned change) C11: carve-out for human-written patterns over :45, :49, :50 (S-99, S-107); park disarms, resume re-arms (S-106); the wait job's arm and disarm (S-105). For a role agent the arm, fire and disarm lines (:34, :36, :37, :39) move to the contact agent's watchdog, which a finished message turns off (S-174, S-188; inferred). A fire on a live agent with no completion signal leaves it working, and the contact agent tells the human once when its output shows no sign of waiting (S-241). A helper gets no watchdog (S-162)

> (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules", Impacted flows) Every spawn sizing and watchdog arm. Changed: DELEGATION.md :34, :36, :37, :39 and :45, :49, :50; the arm at skills/afk/autopilot/SKILL.md:40; the tracer arm at skills/utils/investigate/SKILL.md:44, since a tracer writes a ledger, which is role work (inferred); AGENTS.md:22, which restates :49 with no exception and must update with the doctrine (FRESHNESS.md:43; inferred). Unchanged here: the sizing restatements at autopilot/SKILL.md:35, autopilot/SUBAGENT-PROMPT.md:3 and bug/SKILL.md:68, which change through the pane-role rows, not this one. Unchanged: hooks/stall-watchdog.sh, DELEGATION.md :26, :38, :41, :47-57, the tier table, check L (native-contract-gate.sh:218-266; scripts/tests/test_model_tier_gate.py:58) and every agent model line. Every change is unguarded: no test pins any of these lines (INV-055)

> (SDD §14 row "`DELEGATION` doctrine: `Model tiers` carve-out and `stall-watchdog` rules", Conventions / landmines) The watchdog has no park mode: a park is a kill and a resume is a fresh arm (hooks/stall-watchdog.sh:14-16, :27; INV-055). Inferred, not load-bearing: DELEGATION.md:46 and PROVIDERS.md:131 forbid a spawn-model argument, while agent-start takes the tier's model cell, so both lines name the agent-start exception (INV-055). Agents stay upward-only; the pin-delivery pointer already resolves to PROVIDERS.md "Model tiers" on main (DELEGATION.md:46), so C17 is dropped (GRILL-LOG.md:745 (3)). DELEGATION.md:34 also arms a watchdog for suite and build runners, which stay helpers (§14 row DELEGATION.md spawn rules; §13 Q32); no skill arms one today, since execute/SKILL.md:69 delegates runners without it (inferred, INV-055). Compatibility: a pattern you write may choose models that 3 model rules forbid today; a parked agent's stall watchdog is turned off; a stage with no pattern follows today's rules (S-246). Rollback: revert the commit, or install the previous plugin version; no stored record changes shape (S-246)

> (SDD §14 row "DELEGATION.md spawn rules (:24-30)", Planned change) Role agents start as pane agents whenever the plugin is enabled and a pane transport is found. Helpers stay subagents that a pane agent starts for its own context, with the named types and model tiers. DELEGATION.md holds the full pane-agent rule. A helper does not start agents, does not go past the nesting limit of 3 levels, and does no role work (S-190). PAT1's 'subagents included' means spawned role agents, which may start helpers (D-11, agent-decided). The type and tier lines :26 and :43 narrow to helpers and the fallback: a start names a role and a brief path only (S-231), and no agent definition ships for a role (inference, not re-checked at the merge). A pane role runs the model its tier names in PROVIDERS.md: agent-start takes the tier's model cell and, on Codex, its effort cell from PROVIDERS.md "Model tiers" (D-10, agent-decided; GRILL-LOG.md:745 (4)). DELEGATION.md words it with no harness name, 'and the tier's effort cell where the harness has one', since native check A refuses a harness word there and the behavior registry refuses one in the short form's body (hooks/native-contract-gate.sh:93-99, :131; scripts/behavior_registry.py:43-45, :385-390; INV-061 c-b5de8e90). A helper runs no /afk:investigate; it returns an open code claim as unverified, and its pane-agent starter investigates a load-bearing one (D-16, agent-decided)

> (SDD §14 row "DELEGATION.md spawn rules (:24-30)", Impacted flows) [...] Row C11's watchdog rules do not stand as they are: DELEGATION.md:34, :36, :37, :39 and autopilot :40 move to the contact agent's watchdog, which finished turns off (S-174, S-188); under skills/afk only autopilot :40 arms it (c-6b018f93; inference). DELEGATION.md:34 also arms runner helpers, which S-162 gives no watchdog (inference, not re-checked at the merge; §13 Q32). autopilot :39 and bug :76 key on a vanished subagent, while the contact agent marks a pane agent lost (S-173). The tier lines :47, :48 and :50 stand: an upward override picks a higher tier, and agent-start takes that tier's cell (INV-061, node DELEGATION.md:50); :45 has no model source for a stage with no pattern until D-10 gives one. PROVIDERS.md:126 breaks: its below-cell slice sizing matches no tier row, so it joins :131 in the change list (c-99547c76; inference). CAPABILITIES.md:12 breaks: a pane role loads no definition (requirement ADR-0016). The short form needs one hooks/behavior-dispositions.tsv row and one id in EXPECTED_INVENTORY_IDS (scripts/behavior_registry.py:73), or scripts/tests/test_behavior_registry_gate.py:51 fails; the rendered block is 2549 of 6000 bytes (c-1f2c9b96, c-f97158e0)

> (SDD §14 row "DELEGATION.md spawn rules (:24-30)", Conventions / landmines) CAPABILITIES.md:15 nesting row. The rule is stated once (AC-047), and the short form, one BEHAVIORS.md entry, points at it (D-30; GRILL-LOG.md:744). [...] Rollback: the pane switch set to subagent switches role agents back to subagents (AC-041, S-230).

> (SDD §14 row "Spawn steps that start a role agent (S-208's list)", Impacted flows) [...] Outside the steps: CAPABILITIES.md:3, :12; DELEGATION.md:24, :26, :27, :29, :34, :36, :37, :39, :43, :46; LAVISH.md:327-329, :334; PROVIDERS.md:131; agents/afk-tracer.md:16, :40; afk-config.py:581-582; skills/afk/AGENTS.md:7; PROVIDERS.md:23 and :126; the skill, AGENTS.md, README.md and GLOSSARY.md lines that call a role agent a subagent (c-96505bde, c-99547c76).

> (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry", Planned change) One new BEHAVIORS.md entry, scope configured-repos, doctrine DELEGATION.md §Spawn rules (DELEGATION.md:22), whose body is the pane-agent rule's short form: fixed text that names the condition and both branches of the rule, then points at `${AFK_PLUGIN_ROOT}/DELEGATION.md`, names no harness, and detects nothing at start (GRILL-LOG.md:744, human; D-30, agent-decided). One new inventory row maps to it with disposition registry. No SessionStart handler prints it; the full rule lands in DELEGATION.md §Spawn rules, through the 'DELEGATION.md spawn rules (:24-30)' row, in the same change (GRILL-LOG.md:744)

> (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry", Impacted flows) Sessions whose user instruction file carries the setup-installed block, in repositories with .afk/config.yaml, on both harnesses (adr/0005-managed-behavior-transport.md:20-22). Changed: BEHAVIORS.md; hooks/behavior-dispositions.tsv, one inventory row of disposition registry, without which the gate fails 'active behavior has no registry disposition' (behavior_registry.py:457-459); EXPECTED_INVENTORY_IDS in scripts/behavior_registry.py gains that id, without which the gate fails 'inventory set mismatch' (:450-456; FRESHNESS.md:56); DELEGATION.md §Spawn rules; CHANGELOG.md. Pinned by the gate at Stop (hooks/behavior-registry-gate.sh:22-26; hooks/stop-gates.sh:163) and in CI (.github/workflows/tests.yml:70), and by the tests that read the real registry (scripts/tests/test_behavior_registry_gate.py:51; scripts/tests/test_behavior_registry.py:161-167; hooks/tests/hook-smoke.sh:569, :668). Unchanged: both hooks files, skills/afk/setup/scripts/install_block.py, the setup teardown (skills/afk/setup/SKILL.md:36) and the parity rows (CAPABILITIES.md:27; PROVIDERS.md:34) (INV-051)

> (SDD §14 row "BEHAVIORS.md registry: the pane-agent rule's short form entry", Conventions / landmines) A session without the plugin stays unchanged (AC-041). A session whose user did not take setup row H7, or a repository with no .afk/config.yaml, does not get the short form (adr/0005-managed-behavior-transport.md:20-22; GRILL-LOG.md:744). The block's byte cap binds the new entry: 2549 bytes today, about 2800 with a short form of 1 or 2 lines, against 6,000 (adr/0005-managed-behavior-transport.md:34-37; INV-051). Compatibility: every installed block reports drift at each SessionStart until setup renders it again (behavior-drift.sh:38; CAPABILITIES.md:27). Unverified, not load-bearing: setup row H7 checks the doctrine heading in each provider's installed DELEGATION.md, so a provider still on an older plugin copy may fail the render until it updates (skills/afk/setup/MANIFEST.md:249-253; only a live install on both harnesses settles it). Rollback: revert the commit and run setup again.

> (SDD §13 Q32) Whether a long suite or build runner keeps the stall watchdog that DELEGATION.md:34 arms today. Runners stay helpers (AC-043), and S-162 gives a helper no watchdog, so the settled rows remove that arm; INV-030 flags it (c-612ac654, inference), and the PRD's AC-043 no longer says a helper has no watchdog. The design builds S-162 as settled | L6 | no, scoped to the runner arm of DELEGATION.md:34 | human (confirm) | before slicing the DELEGATION.md work

> (SDD §9b row "Named agent definitions and pinned models in a pane agent") A pane agent's own spawns resolve the plugin's named definitions. A pinned model name runs that model; a Claude definition's pin is an alias, and a Codex reader stub's read-only sandbox did not apply. Starting the pane agent itself as a definition was not probed | A pane role agent takes its model from the tier name in PROVIDERS.md, and agent-start takes the tier's model cell and, on Codex, its effort cell (D-10, agent-decided; GRILL-LOG.md:745 (4)) | The probes; re-run on the shipped version, because the installed pins differ from this worktree

> (PRD AC-001) With no team pattern and no multi-model configured, and with role agents switched back to subagents or no pane transport found, a run behaves as it did before this feature: one agent, one model, no manifest, no knowledge store. One difference: a subagent's report file is written by the agent that started it (AC-044).

> (PRD AC-040) An agent that does a role's work — it writes a plugin artifact, code or a ledger, or it returns a gate verdict — starts as a pane agent. An agent that only reads and returns text to its parent is a helper subagent.

> (PRD AC-041) The pane-agent default applies whenever the plugin is enabled and a pane transport is found; nothing needs configuring. One configuration key switches role agents back to subagents. A session without the plugin enabled is unchanged.

> (PRD AC-042) A role agent that needs another pane agent sends the contact agent a start request. The request names the pattern step, the requester and the lifespan, and lists 1 or more agents, each with a role and a brief.

> (PRD AC-043) A pane agent starts helper subagents for bulk reads, repository searches, test runs and large diffs, to keep its own context small. The plugin's named helper types and model tiers apply to helpers. A helper has no run-manifest entry and starts no agent. A start request past the plugin's 3-level nesting limit is refused.

> (PRD AC-047) The pane-agent rule is stated once, where every session with the plugin enabled reads it; skills point at it.

> (requirement ADR-0013) Whenever the plugin is enabled and a pane transport is found, every agent that does a role's work starts as a pane agent: one that writes a plugin artifact, code or a ledger, or returns a gate verdict. An agent that only reads and returns text to its parent is a helper subagent, started by a pane agent for itself to keep its own context small; the plugin's named helper types and model tiers still apply to it. One configuration key switches role agents back to subagents.

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0008-inbox-wait-script

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

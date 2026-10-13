## Goal
Build the spawn permission check scripts/team/permission.py (file name: plan decision D-3) and the one allow-rule constant in the Claude Code provider file that setup prints and the check reads. Before a run's first transport command, the check confirms, through the provider layer, that the harness will let the contact agent run the team entry script for all six transport verbs, and refuses naming the rule when it will not. The same change adds the opt-in setup register row in skills/afk/setup/MANIFEST.md that prints the rule, waits for the human and confirms it, and updates PROVIDERS.md with the provider behaviour. The slice ends at the check and the setup row: calling the check from agent-start is another subtask.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Spawn permission check" binds the public interface, and the note that the rule covers tab create, pane split and the settings copy
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "Claude Code auto-mode classifier"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "Setup register `MANIFEST`: the spawn allow-rule offer" (change C19)
- SDD: SDD.md#§13 Open Questions — Q11
- ADR: adr/design/0005-human-granted-spawn-rule.md — the human adds one narrow allow rule; setup offers it and never writes it

## Scope
- scripts/team/permission.py
- hooks/lib/providers/claude.sh
- hooks/lib/providers/codex.sh
- skills/afk/setup/MANIFEST.md
- PROVIDERS.md
- hooks/native-contract-allow.txt
- scripts/tests/test_team_permission.py

## Seams
- implement: §9b row "Claude Code auto-mode classifier" via §14 row "Setup register `MANIFEST`: the spawn allow-rule offer" — the opt-in register row that prints the rule constant, and the run check that reads it (INV-057)

## Acceptance
- [ ] One opt-in register row for Claude Code prints the rule constant, which covers every transport verb, waits for the human, then confirms the rule is present; it is skipped with no human present, and setup never writes the rule (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer")
- [ ] The rule constant is a plain assignment in hooks/lib/providers/claude.sh, since a self-default fails check C until an E-table row lands; the register row calls no hooks/lib/providers/claude_*.py helper directly (check K, native-contract-gate.sh:460); a row naming the harness carries a line in hooks/native-contract-allow.txt, or check A fails; no decision id shaped like a ticket id (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer")
- [ ] set_instruction_files.py and every pinning test stay unchanged (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer")
- [ ] Implements the public interface in SDD §8 row "Spawn permission check" unmodified: check() returns ok, or a refusal carrying the rule text (SDD §8 row "Spawn permission check")
- [ ] The check confirms the harness will let the contact agent run the team entry script for all six transport verbs (agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list), and refuses, naming the rule, when it will not (SDD §8 row "Spawn permission check")
- [ ] The rule also covers tab create, pane split and the settings copy, because each runs only inside agent-start (SDD §8)
- [ ] A missing rule, a rule that does not cover every transport verb, or a rule that no longer matches after a plugin update makes the run refuse before its first transport command, naming the rule and /afk:setup; nothing is started (SDD §9b row "Claude Code auto-mode classifier")
- [ ] The rule text lives in one constant in the provider file, which setup prints and the check reads; harness words stay out of skill prose and the Claude Code specifics live in the provider file (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer")
- [ ] A rule matching only the start command is not enough: the constant matches the team entry script's invocation, so it covers a direct tab create as well as the start (SDD §13 Q11)
- [ ] Whether one rule text stays valid across plugin updates is settled against the permission-rule syntax, and the run check catches a stale rule either way (SDD §13 Q11)
- [ ] PROVIDERS.md is updated in the same change to describe the provider files' new rule constant and check behaviour (ADR-0005)
- [ ] Conforms to ADR-0005 — the human adds the one narrow allow rule to their own settings; setup prints it and confirms it, and never writes a settings file; no silent pattern substitution (ADR-0005)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Spawn permission check")
- [ ] The seam-test asserts on the check's real output over real settings files: settings without the rule give a refusal naming it; with it, ok (SDD §9b row "Claude Code auto-mode classifier")

## Produces
- hooks/lib/providers/claude.sh#AFK_SPAWN_ALLOW_RULE — the one rule constant setup prints and the check reads
- scripts/team/permission.py#def check_spawn_permission( — check() → ok, or a refusal naming the rule

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash -n hooks/lib/providers/claude.sh && bash -n hooks/lib/providers/codex.sh && python -m py_compile scripts/team/permission.py && grep -n 'AFK_SPAWN_ALLOW_RULE' hooks/lib/providers/claude.sh && grep -n 'def check_spawn_permission(' scripts/team/permission.py` | code parses; the Produces anchors exist |
| static | `python -m pytest scripts/tests/test_native_contract_events.py scripts/tests/test_set_instruction_files.py -q` | checks A and K pass with the new row and constant; set_instruction_files.py unchanged; seam-test for the row "Setup register `MANIFEST`: the spawn allow-rule offer" |
| unit | `python -m pytest scripts/tests/test_team_permission.py -q`, cases: a settings file with the rule gives ok; without it, a refusal carrying the rule text and naming /afk:setup; the rule text covers all six verbs | the check; seam-test for the row "Claude Code auto-mode classifier" and for the setup register row |

## Context excerpts
> (SDD §8 row "Spawn permission check") | Spawn permission check | Unchanged by the pane close, which runs inside agent-stop: no seventh verb (S-234). Before a run's first transport command, confirm the harness will let the contact agent run the team entry script for all six transport verbs of §3 (agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list); refuse, naming the rule, when it will not (AUTO-1) | check() → ok, or a refusal carrying the rule text | provider layer; the one rule constant (AUTO-2) | Run |
> (SDD §8) The spawn permission check's rule also covers tab create, pane split and the settings copy, because each runs only inside agent-start (S-167, S-191).
> (SDD §9b row "Claude Code auto-mode classifier") | Claude Code auto-mode classifier | Claude Code in auto mode, the built-in starting mode for interactive sessions from v2.1.283 (documentation); observed once on this machine, 2026-09-28 (trial T7) | Refuses the contact agent's start command with or without bypass flags, and refuses the agent's own edit of its settings (T7). A rule matching only the start lets the start run but not the next verb: sending work to a started agent is refused (T7b). An allow rule the human adds resolves before the classifier (documentation, permission modes) | Rule missing, not covering every transport verb, or no longer matching after a plugin update → the run refuses before its first transport command, naming the rule and `/afk:setup`; nothing is started (AUTO-1, AUTO-2) | A check test: settings without the rule → refusal naming it; with it → ok. Live proof: trial T7 repeated with the rule present |
> (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer", Planned change) C19: one opt-in register row for Claude Code prints the rule constant, which covers every transport verb (T7b), waits for the human, then confirms the rule is present; skipped with no human present; setup never writes the rule (AUTO-1, AUTO-2)

> (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer", Impacted flows) Every setup run on Claude Code; the team run's spawn permission check reads the same constant. Unchanged: set_instruction_files.py and every pinning test. Breaks, unless the change lands as designed: a row naming the harness without a line in hooks/native-contract-allow.txt fails native check A at Stop and commit; a row calling a hooks/lib/providers/claude_*.py helper directly fails check K (native-contract-gate.sh:460); the rule constant must be a plain assignment in hooks/lib/providers/claude.sh, since a self-default fails check C until an E-table row lands; a decision id shaped like a ticket id trips the genericity gate (hooks/lib/sensitive-patterns.tsv:8); test_native_contract_events.py:57 pins checks A and K (INV-057)

> (SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer", Conventions / landmines) Harness words stay out of skill prose; the Claude Code specifics live in the provider file. An agent edit of permission settings is refused by the harness itself (T7). Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version; the allow rule stays in the user settings until the human removes it (S-246)
> (SDD §13 Q11) Q11: Trials T7 and T12 covered one transport (herdr) from a Claude Code contact agent: T12 showed that a rule on the start command alone does not cover a direct tab create (S-167). Not tried: headless starts, the desktop tool, a Codex contact agent under its harness's own approval mode. Whether one rule text can stay valid across plugin updates is settled against the permission-rule syntax at implementation, and the run check catches a stale rule either way. On 2026-09-30 the launching session's permission classifier refused a Codex pane launch with the sandbox-bypass flag (providers/CONFORMANCE.md:427); the settled full-access launch (S-136) meets the same refusal wherever that classifier runs (V7)
> (ADR-0005) The human adds one narrow allow rule to their own settings, once per machine. `/afk:setup` offers it: it prints the exact rule, waits for the human, and confirms the rule is present; it never writes a settings file (AUTO-1). The rule matches the team entry script's invocation, and all six transport verbs of §3 (agent-start, agent-send, agent-status, agent-read, agent-stop, agent-list) pass through that script, so one approved command covers them all (T7b). Its text lives in one constant that setup prints and the run check reads. Before a run's first transport command, the spawn permission check, called through the provider layer, confirms the rule; when it is missing or stale, the run refuses and names the rule (AUTO-2). The rule is granted knowingly and never exists to hide spawn flags from the classifier.

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

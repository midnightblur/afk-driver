midnightblur/afk-driver@6b322daf4e1cf9652e5deb6934a45d32b1df1de8 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-086-plugin-path-convention/COVERAGE.json

## Answer
- Hooks: the harness expands `${CLAUDE_PLUGIN_ROOT}` (hooks.json:9) or `${PLUGIN_ROOT}` (hooks.codex.json, held by native-contract-gate.sh:385-386) to start run-hook.py. run-hook.py takes the root from its own file (:89) and exports AFK_PLUGIN_ROOT to every handler (:1021).
- Agent shells carry no root variable (CONFORMANCE.md:437). The agent exports it from its skill folder (setup SKILL.md:41-42, GLOSSARY.md:209); team panes get it from entry.py:319; the MCP (Model Context Protocol) launcher sets it (.mcp.json:7); behavior_registry.py:240 substitutes the absolute root into the managed block.
- Scripts find the root from their own file, AFK_PLUGIN_ROOT as override (config.sh:39, protected_branch_guard.py:35); some ignore the variable (run-hook.py:89, permission.py:24, entry.py:31, python_runtime.py:63).
- Stated in AGENTS.md:202 and GLOSSARY.md:208-210; restated in setup SKILL.md:41, BEHAVIORS.md:4, autopilot SUBAGENT-PROMPT.md:5 (spawn placeholders).
- Enforced by one check only: behavior_registry.py:395-400 refuses a BEHAVIORS.md body with no `${AFK_PLUGIN_ROOT}/<doctrine>` pointer (test_behavior_registry.py:148). No gate refuses an unpinned plugin path or a bare plugin command: native-contract check A (:151) refuses bare `PLUGIN_ROOT` only; check J (:373-399, :420) holds the 2 hook manifests to `afk-python "${ROOT}/hooks/…"`; skill-registry, genericity, behavior-registry, wiring gates and the shell guard hold no path form.
- `afk-team` and `Bash(afk-team *)` pass every gate, while the exception text names no harness and no bare `PLUGIN_ROOT`.
## Sites that break under the afk-team exception
- In plan 0027 Scope: claude.sh:78 rule constant; permission.py:28 INVOCATION; PROVIDERS.md:180, :185, :186; AGENTS.md:202; GLOSSARY.md:209; README.md:350; python_runtime.py:20-21, :266, :500; AUDIT.md:142.
- Tests in Scope: test_team_permission.py:75 (`split()[2]` reads the verb as token 3, now token 2), :270, :271, :275 (deny entries), :285 (refusal text), :304/:306 (first match becomes `Bash(*)`); test_afk_python_entry.py:72 (red in CI too, tests.yml:33-42).
- Missing from 0027 Scope: test_team_entry.py:368 asserts the old prompt that entry.py:237 builds from INVOCATION; scripts/afk-team.py:4 docstring; .claude/wiring-ious.md:35 IOU; MANIFEST.md:403-404 (H15 notes) and plan/DECISIONS.md:526 (D-75) claim the rule survives plugin updates by naming the root variable, while the launcher bakes the versioned folder.
- Inference: ENTRY_NAME "afk-team.py" (permission.py:29, :100) unnamed in 0027; kept, the start-only test (test_team_permission.py:212-219) reads `missing`, not `stale`.
## Conditional (inference)
- 0027 check 3 compares 2 self-relative roots (python_runtime.py:63, permission.py:24). If it compares against permission.py's own folder, a launcher pointing at an older plugin version passes; no test pins it.
- Setup already bakes versioned roots outside the repository with no stated exception: tracker_registration.py:61-63, Codex agent stubs `{{PLUGIN_ROOT}}` (MANIFEST.md:868).
- Deployment order: /afk:setup writes the launcher and puts afk-bin on PATH before any team run; old full-path rules stay in user settings unused.
## Unchanged
- Protected-branch guard passes unknown programs; check J ignores afk-team; the H15 offer prints the rule the adapter returns (permission.py:219-224); every other site: COVERAGE.json nodes table.
## Frontier
- B14: users' allow lists; live PATH resolution of afk-team in Claude Code and through afk-team.cmd in Codex PowerShell; installed plugin copies; forge rationale lookup not run.
- B6: the afk-team launcher is unbuilt (python_runtime.py:266).
## Unverified
- c-b719c272 (not load-bearing): hit set complete over searched name forms; the blind counter-search added 79 read nodes outside those forms.
## New question
- SUBAGENT-PROMPT.md:21 runs `{WORKFLOW_HOOKS_DIR}/app-start-gate.sh`; the only copy is adapters/build-gate/maven/app-start-gate.sh.

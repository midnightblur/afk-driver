nakisainc/core/core-services@fe27ed571348f12ecf5b3ea3633fe50582c26f79 · partial · boundaries 8/14 · unverified 1 (load-bearing 1) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-001-runtime-topology/COVERAGE.json

## Answer
AFK runs inside an enabled agent harness. The harness loads skills, hooks, agent roles, and the tracker Model Context Protocol (MCP) child from the installed plugin.
`/afk:autopilot` reads the local plan and runs subtasks in rank order. It starts one fresh driven `/afk:execute` agent for each runnable subtask.
Each child reads one contract, implements with test-driven development, runs every declared verification tier, settles review, runs the adversary gate, commits, pushes, and updates the Draft change.
The orchestrator keeps one worktree and one app instance for the run. It parks failures and dependent work, then continues independent work.
After all runnable subtasks finish, `/afk:smoke-test` checks the integrated feature. A green stamp starts `/afk:preflight`.
Preflight merges the target branch, validates, reviews, checks consumers, records ship evidence, waits for continuous integration (CI), and changes Draft to Ready. A human performs the merge.

## Facts
- The mandatory execution path is `/afk:autopilot` → driven `/afk:execute` → `/afk:smoke-test` → `/afk:preflight`. [skills/afk/autopilot/SKILL.md:30; skills/afk/autopilot/SKILL.md:33; skills/afk/autopilot/SKILL.md:47]
- The plan files hold subtask state. `/afk:execute` does not write subtask state to the tracker. [README.md:106; README.md:111; README.md:114; skills/afk/execute/SKILL.md:12]
- The run is sequential: one subtask, one worktree, and one app instance. [skills/afk/autopilot/SKILL.md:36; skills/afk/autopilot/SKILL.md:42]
- A subtask failure parks that subtask. Preflight failures park the failing step. Neither path merges the change. [skills/afk/autopilot/SKILL.md:37; skills/afk/execute/SKILL.md:108; skills/afk/preflight/SKILL.md:30]
- Claude and Codex load the same native plugin tree through harness-specific manifests and agent definitions. [PROVIDERS.md:3; PROVIDERS.md:9; PROVIDERS.md:18; PROVIDERS.md:23]

## Inferences
- Inference: this repository defines a harness plugin runtime, not an independently deployed workflow service. The installed plugin, agent processes, worktree, app process, forge adapter, and tracker MCP child form the runtime. [.codex-plugin/plugin.json:54; .codex-plugin/plugin.json:55; PROVIDERS.md:30; PROVIDERS.md:31; mcp-servers/tracker/server.py:16]
- Inference: deployment means plugin installation into each harness. Repository scans found release workflows but no Docker, Kubernetes, Helm, systemd, or service deployment manifest for AFK itself. [README.md:220; README.md:253; command `git ls-files | rg -i '(docker|compose|helm|k8s|kubernetes|deployment|systemd)'`, exit 0]

## Sites
`skills/afk/autopilot/SKILL.md:30`; `skills/afk/execute/SKILL.md:39`; `skills/afk/smoke-test/SKILL.md:12`; `skills/afk/preflight/SKILL.md:34`; `PROVIDERS.md:18`; `.codex-plugin/plugin.json:54`; `.claude-plugin/plugin.json:16`; `mcp-servers/tracker/server.py:16`.

## Unverified
- B3 reflection and scan: no repository-specific enumeration method.
- B5 serialized shape: no repository-specific enumeration method.
- B6 generated code: no generated paths declared.
- B7 build graph: no aggregator manifests declared.
- B10 UI callers: no repository-specific enumeration method.
- The repository has no `investigation:` block. Add one to `.afk/config.yaml` to close these classes.

## Frontier
- B14 external: other repositories, deployment manifests outside this checkout, and live consumers were not crossed.

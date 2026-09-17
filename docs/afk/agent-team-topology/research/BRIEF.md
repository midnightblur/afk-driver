# Research brief — agent team topology + multi-model for the afk plugin

You are a **planner** on a small agent team. The contact agent (herdr pane `w5:p1`, Claude) talks to the human; you do not. You work in the plugin repo worktree `C:\Users\mvu\PersonalProjects\afk-driver-agent-teams` (branch `feat/agent-team-topology`). Read `CLAUDE.md` at the repo root first — it is binding.

## Goal (human's words, condensed)

1. Human talks to ONE agent (single point of contact). Instructions relay to a team whose shape depends on the deployed **team topology**.
2. Team members may be durable or ephemeral: spawned when needed, **terminated** when their job ends (e.g. planners killed once a design is agreed; later audit rounds spawn fresh planners). Goal: token/cost economy — keep a session alive only if later work needs its full history.
3. **Knowledge must not be lost** when an agent is terminated — especially findings from flagship planners. Owners actively compact what they learned into a store; it must be **verifiable**, retrievable, and fed to agents that need it (builders, later planners), so one fact is never discovered twice and can be dug further. Design the produce/consume flow.
4. **Both multi-model and team topology are optional and independent.** Today's behaviour stays the default; nothing breaks for current users. Team topology with one provider must work; multi-model without a team must work.
5. **Auto-detect** the environment: running inside herdr / 1DevTool / plain terminal; which model providers are *actually usable* (installed CLI ≠ active subscription — design a real availability probe).
6. Topology per task: none (single agent), harness-native subagents (e.g. Claude's Agent tool), user-managed agents, or a team. Ship **built-in team patterns** and let users define their own — durable (config) or one-shot.
7. `/afk:setup` offers to install **herdr** optionally.
8. Learn whether **1DevTool** can spawn and kill agents the way herdr can.

Prior agreed design from an earlier session (a starting point you may challenge, not a constraint): `C:\Users\mvu\AppData\Local\Temp\handoff-P1aHuF.md` — agent-transport adapter family (`headless` / `herdr` / `1devtool` kinds; verbs spawn/send/wait/read/close), debate rules at plan + review gates, trigger-gated debate, model cascade tiers, role safety (builder yolo only in own worktree).

## Environment facts already verified by the contact agent

- This session runs inside herdr 0.9.0 (`HERDR_ENV=1`, `HERDR_PANE_ID`). `herdr --skill` prints the control guide. Agent kinds herdr knows: pi, claude, codex, gemini, cursor, devin, agy, cline, omp, opencode, copilot, kimi, kiro, droid, amp, grok, hermes, kilo, qodercli, qwen, maki, muse.
- codex-cli 0.154.0, claude CLI, both on PATH.
- 1DevTool is installed. Its delegation CLI shim: `C:\Users\mvu\.1devtool\bin\1devtool-agent-v9.cmd`. Its user skill `C:\Users\mvu\.claude\skills\1devtool-orchestrator\SKILL.md` documents `run`, `team start`, `swarm start`, `collect`, `send`, `stop --team=<id> --close-terminals`, hierarchy/`report`, links. A second skill `1devtool-tasks` and an MCP server `onedevtool` (tools `orchestration_*`, `tasks_*`) also exist.

## Rules for your work

- **Do not edit plugin source.** Write only your own files under `docs/afk/agent-team-topology/research/`.
- Probes: read-only commands and `--help` freely. Anything that spawns an agent or process must be bounded, trivial prompt, and cleaned up (kill what you start; record the ids). Never touch panes/agents you did not create. No commits, no pushes.
- Delegate bulk reads to subagents if your harness has them; keep your own context for synthesis.
- Follow `LANGUAGE.md` §3 for artifact prose.

## Deliverables (two files, in order)

### 1. `FACTS-<you>.md` — verifiable knowledge ledger

One row per fact. This ledger itself is a prototype of goal 3, so its shape is part of your proposal.

| id | claim | evidence (command + output excerpt, or path:line) | status: verified / inferred / unverified | expires-when |

Cover your **assigned area** (below) deeply; you may add facts outside it.

### 2. `PROPOSAL-<you>.md` — design proposal (independent; do not read the other planner's proposal)

Cover every goal above. Minimum sections: options considered + recommendation for (a) topology model and built-in patterns, (b) agent lifecycle (spawn / reuse / terminate policy), (c) knowledge store: format, producer/consumer flow, verification, retrieval, (d) transport abstraction and env auto-detection, (e) provider availability probe, (f) opt-in + default-preserving guarantee, (g) how it fits existing plugin mechanisms (adapter families, `DELEGATION.md` model tiers, `CONFIG.md`, `CAPABILITIES.md`, `/afk:setup` MANIFEST, autopilot/execute spawn points, review settle loop), (h) debate / cross-model gates, (i) risks + open questions for the human, (j) a phased delivery slice (smallest useful first phase). Mark inferences.

When both files are written, reply in your terminal with exactly one line: `DONE <path-to-proposal>`.

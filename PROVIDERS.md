# Provider mapping

The AFK plugin + harness run on two agent runtimes: **Claude Code** (canonical
plugin under this directory) and **OpenAI Codex CLI** (generated mirror —
`tools/payable/ai-agents/codex-sync/README.md`). This file is the one home for
translating provider-specific constructs. Skill prose stays written in Claude
vocabulary; on Codex, read this once per session and apply the mapping.

| Construct | Claude Code | Codex CLI |
|---|---|---|
| Invoke a workflow skill `/afk:<x>` | `/afk:<x>` slash command | `$afk-<x>` skill mention (or the `/skills` picker); mirrors live in `.agents/skills/` |
| Invoke a project skill | `.claude/skills/<x>` via `/x` | `$<x>` |
| Spawn a subagent | Agent/Task tool with `subagent_type`: `afk-reader` / `afk-runner` / `general-purpose` / `Explore` | spawn agent `afk-reader` / `afk-runner` (defs in `.codex/agents/*.toml`); `general-purpose` → built-in `worker`, `Explore` → built-in `explorer` |
| Parallel spawns "in one message" | parallel Agent calls in one message | parallel agent spawns in one step (`max_threads`, default 6) |
| Nesting cap 3 (`DELEGATION.md`) | native | needs `[agents] max_depth = 3` in `~/.codex/config.toml` (provided by `codex-sync/config-fragment.toml`); at the default depth 1, helper spawns run inline — degraded, not broken |
| Model tiers (see below) | `fable` / `opus` / `sonnet` by tier — table below | `gpt-5.6-sol` / `-terra` by tier — table below |
| Jira MCP tools `mcp__jira__*` | plugin-provided `mcp__jira__<tool>` | same server registered via `config.toml` `[mcp_servers.jira]`; tool prefix differs — match by tool name |
| Agent-runtime env marker | `CLAUDECODE` | `AFK_PROVIDER=codex` (hard-set by generated hook commands; native `CODEX_*` markers unverified) |
| Plugin root / data dirs | `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` | repo-relative paths / `~/.afk/data/<plugin>` (resolved by `hooks/lib/provider.sh`) |
| Job scratch dir | `CLAUDE_JOB_DIR` | unset — skills fall back to a temp/scratch dir |
| Credentials (Jira scripts) | `~/.claude.json` `mcpServers.jira.env` | `~/.codex/config.toml` `[mcp_servers.jira.env]`, or exported env vars (resolution order: env → claude.json → codex toml) |
| Pick up a skill edit | `/reload-plugins` | nothing for prose (pointers re-read canonical files each activation); `python tools/payable/ai-agents/codex-sync/generate.py` when frontmatter/structure changed |

## Model tiers (referenced by `DELEGATION.md` "Model selection")

Tier *roles* are owned by `DELEGATION.md`; this table owns the per-provider
*names*. Within a cell, "best available" degrades left to right — if the
first-listed model is unavailable (plan, region, outage), use the next.

| Tier | Claude Code | Codex CLI |
|---|---|---|
| **frontier** | `fable` (Fable 5); `opus` if Fable is unavailable | `gpt-5.6-sol` at high/xhigh reasoning; `gpt-5.5` if Sol is unavailable |
| **implementation** | `opus` — never `fable`; `sonnet` for simpler slices | `gpt-5.6-terra` — never Sol; drop to medium effort for simpler slices |
| **digest** | `sonnet` (set in the `afk-reader`/`afk-runner` definitions) | `gpt-5.6-terra` at low effort |

## Claude-only capabilities (documented limitations on Codex)

- `claude.ai/design` push (prototype, design-system share mirrors): skip — the
  local-first HTML output is the canonical artifact and is unaffected.
- Picker-style question cards: ask in plain text instead.
- Plugin marketplace / `enabledPlugins`: not applicable — Codex discovery is
  path-based (`.agents/skills`, `.codex/`), provisioned by the generator.

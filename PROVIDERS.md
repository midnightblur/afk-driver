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
| Model tiers (see below) | digest = `sonnet`, verdict = inherit | digest = your configured cheap model / low reasoning effort, verdict = session model |
| Jira MCP tools `mcp__jira__*` | plugin-provided `mcp__jira__<tool>` | same server registered via `config.toml` `[mcp_servers.jira]`; tool prefix differs — match by tool name |
| Agent-runtime env marker | `CLAUDECODE` | `AFK_PROVIDER=codex` (hard-set by generated hook commands; native `CODEX_*` markers unverified) |
| Plugin root / data dirs | `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` | repo-relative paths / `~/.afk/data/<plugin>` (resolved by `hooks/lib/provider.sh`) |
| Job scratch dir | `CLAUDE_JOB_DIR` | unset — skills fall back to a temp/scratch dir |
| Credentials (Jira scripts) | `~/.claude.json` `mcpServers.jira.env` | `~/.codex/config.toml` `[mcp_servers.jira.env]`, or exported env vars (resolution order: env → claude.json → codex toml) |
| Pick up a skill edit | `/reload-plugins` | nothing for prose (pointers re-read canonical files each activation); `python tools/payable/ai-agents/codex-sync/generate.py` when frontmatter/structure changed |

## Model tiers (referenced by `DELEGATION.md` "Model selection")

- **digest tier** — bulk reads, searches, mechanical checks, suite triage:
  returns are advisory and citation-spot-checked. Claude: `sonnet` (set in the
  `afk-reader`/`afk-runner` definitions). Codex: the cheap model / low
  reasoning effort configured in your `config.toml`.
- **verdict tier** — children writing product code, and any verdict acted on
  without re-checking. Both providers: the session's own model. Escalate the
  moment a digest stops being advisory; never judge with a cheaper model than
  the implementor it judges.

## Claude-only capabilities (documented limitations on Codex)

- `claude.ai/design` push (prototype, design-system share mirrors): skip — the
  local-first HTML output is the canonical artifact and is unaffected.
- Picker-style question cards: ask in plain text instead.
- Plugin marketplace / `enabledPlugins`: not applicable — Codex discovery is
  path-based (`.agents/skills`, `.codex/`), provisioned by the generator.

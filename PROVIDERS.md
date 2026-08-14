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
| Spawn a subagent | Agent/Task tool with `subagent_type`: `afk-reader` / `afk-runner` / `afk-implementor` / `general-purpose` / `Explore` | spawn agent `afk-reader` / `afk-runner` / `afk-implementor` (defs in `.codex/agents/*.toml`); `general-purpose` → built-in `worker`, `Explore` → built-in `explorer` |
| Parallel spawns "in one message" | parallel Agent calls in one message | parallel agent spawns in one step (`max_threads`, default 6) |
| Nesting cap 3 (`DELEGATION.md`) | native | needs `[agents] max_depth = 3` in `~/.codex/config.toml` (provided by `codex-sync/config-fragment.toml`); at the default depth 1, helper spawns run inline — degraded, not broken |
| Model tiers (see below) | `fable` / `opus` / `claude-opus-4-8` / `sonnet` by tier — table below | `gpt-5.6-sol` / `-terra` by tier — table below |
| Jira MCP tools `mcp__jira__*` | plugin-provided `mcp__jira__<tool>` | same server registered via `config.toml` `[mcp_servers.jira]`; tool prefix differs — match by tool name |
| Agent-runtime env marker | `CLAUDECODE` | `AFK_PROVIDER=codex` (hard-set by generated hook commands; native `CODEX_*` markers unverified) |
| Plugin root / data dirs | `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PLUGIN_DATA` | repo-relative paths / `~/.afk/data/<plugin>` (resolved by `hooks/lib/provider.sh`) |
| Job scratch dir | `CLAUDE_JOB_DIR` | unset — skills fall back to a temp/scratch dir |
| Credentials (Jira scripts) | `~/.claude.json` `mcpServers.jira.env` | `~/.codex/config.toml` `[mcp_servers.jira.env]`, or exported env vars (resolution order: env → claude.json → codex toml) |
| User-global steering file (every session, all projects) | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| Pick up a skill edit | `/reload-plugins` | nothing for prose (pointers re-read canonical files each activation); `python tools/payable/ai-agents/codex-sync/generate.py` when frontmatter/structure changed |

## Distribution law (binding on every plugin change)

The plugin's blast radius is the opted-in dev, never the monorepo's other
teams. Opt-in: Claude — install the plugin (`enabledPlugins`); Codex — run
`tools/payable/ai-agents/codex-sync/generate.py` (or `/afk:setup`). Three
rules sort every artifact a change ships:

- **Activation surfaces never ride git.** Anything that makes an agent *act*
  — hook wiring, agent defs, skill discovery, first-turn afk context —
  exists only on opted-in machines: Claude via the plugin snapshot, Codex
  via the gitignored root mirror (`.agents/`, `.codex/`, `AGENTS.local.md`).
- **Committed prose is the one shared surface — inert and, at repo root,
  neutral.** Plugin/harness markdown under `tools/payable/ai-agents/` and the
  CLAUDE.md steering tree ride git; a repo-root file every agent auto-reads
  must stay provider-neutral and carry no afk activation content.
- **Provider parity.** What is committed / local / neutral for Claude is
  committed / local / neutral for Codex. Root map: `CLAUDE.md` ↔ `AGENTS.md`
  (committed neutral routers); `CLAUDE.local.md` ↔ `AGENTS.local.md`
  (gitignored per-machine); plugin install ↔ generated mirror.

Exception: generator outputs that are tooling, not activation
(`codex-sync/config-fragment.toml`, the harness `hooks/lib/provider.sh`
byte-copy) ride git. Sort any new artifact class by one test: *can it make an
agent act on a machine whose dev never opted in?* — then it cannot be
committed.

## Model tiers (referenced by `DELEGATION.md` "Model selection")

Tier *roles* are owned by `DELEGATION.md`; this table owns the per-provider
*names*. Within a cell, "best available" degrades left to right — if the
first-listed model is unavailable (plan, region, outage), use the next.

| Tier | Claude Code | Codex CLI |
|---|---|---|
| **frontier** | `fable` (Fable 5); `opus` (alias — always the latest Opus, currently Opus 5) if Fable is unavailable | `gpt-5.6-sol` at high/xhigh reasoning; `gpt-5.5` if Sol is unavailable |
| **implementation** | `claude-opus-4-8` (Opus 4.8) — **pinned**, carried by the `afk-implementor` agent type; one rung below the `opus` alias, never `fable`; `sonnet` for simpler slices | `gpt-5.6-terra` — never Sol; drop to medium effort for simpler slices |
| **digest** | `sonnet` (set in the `afk-reader`/`afk-runner` definitions) | `gpt-5.6-terra` at low effort |

Claude Code: only the **implementation** tier is version-pinned — code-writing
children run Opus 4.8 while every Opus-level *judgment* spawn (frontier tier,
plugin/harness work) rides the floating `opus` alias and follows the latest
Opus.

**Pin delivery.** A pinned tier reaches a child only through an **agent
definition's frontmatter** (`agents/*.md` `model:`), never through a per-spawn
argument — the Agent/Task tool's `model` parameter is an enum
(`sonnet | opus | haiku | fable`) that hard-rejects a pinned id. Both halves
verified 2026-07-31: tool arg `claude-opus-4-8` → `InputValidationError`;
the same id in frontmatter resolved to `claude-opus-4-8[1m]` (a control spawn
at `opus` reported `claude-opus-5` — distinct id *and* cutoff, so the pin is
honored, not silently defaulted). Consequences:

- A spawn that must be pinned names an **agent type**, never a model argument.
- Agent definitions are scanned at **session start** — a new or re-pinned
  definition takes effect on the next session, not mid-run.
- Where no pinned definition exists yet, spawn `opus` and record the
  substitution in the run's journal: unpinned Opus is the sanctioned
  degradation, not a gate failure.

## Claude-only capabilities (documented limitations on Codex)

- `claude.ai/design` push (prototype, design-system share mirrors): skip — the
  local-first HTML output is the canonical artifact and is unaffected.
- Picker-style question cards: ask in plain text instead.
- Plugin marketplace / `enabledPlugins`: not applicable — Codex discovery is
  path-based (`.agents/skills`, `.codex/`), provisioned by the generator.

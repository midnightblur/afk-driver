# Provider mapping

The committed workflow plugin is one native tree. `CAPABILITIES.md` owns capability degradation. `providers/CONFORMANCE.md` owns live proof.

## Supported harnesses

A harness is a CLI, never a model vendor. Add a row here first; the native contract gate holds this table and `hooks/lib/providers/*.sh` to the same list.

| Harness | Native discovery | Adapter | Agent definitions | Conformance | Notes |
|---|---|---|---|---|---|
| `claude` | `.claude-plugin/plugin.json`, enabled by `enabledPlugins` | `hooks/lib/providers/claude.sh` | `agents/*.md`, read in place | pending 2026-09-01 | Reference harness for the shared hook subset |
| `codex` | `.codex-plugin/plugin.json`, enabled through the native marketplace | `hooks/lib/providers/codex.sh` | `providers/codex/agents/*.toml`, copied unchanged to `~/.codex/agents/` | pending 2026-09-01 | Needs `features.hooks` and per-handler trust |

Conformance holds the probe verdict and date per harness. `providers/CONFORMANCE.md` owns the add-a-harness checklist.

## Construct mapping

| Construct | Claude Code | Codex CLI |
|---|---|---|
| Enable plugin | `enabledPlugins` names `afk@nak-marketplace` | Native marketplace plus enabled `afk@nak-marketplace` |
| Skill reference | `/afk:<x>` | Catalog name `afk:<x>`: strip the leading slash; `$afk:<x>` typing is unverified |
| Project skill | Native skill name | Native skill name |
| Spawn AFK role | Plugin agent `afk-reader`, `afk-runner`, `afk-runner-lite`, or `afk-implementor` | Same names from unchanged user TOML stubs |
| Generic role | General-purpose or exploration role | Built-in worker or explorer role |
| Parallel spawn | Parallel calls | Parallel agent spawns |
| Continue child | Native continuation | Continue only where `providers/CONFORMANCE.md` proves same-child context; disk handoff otherwise |
| Plugin root/data | Compatibility root/data variables | `PLUGIN_ROOT`/`PLUGIN_DATA`; compatibility variables also exist |
| Project root | `CLAUDE_PROJECT_DIR` when present | Resolve from `$PWD` through Git |
| Job scratch | Native job directory | Plugin-data scratch directory |
| Jira MCP tools | Plugin-scoped server; call the bare tool name | Plugin-scoped server; call the bare tool name |
| User steering | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| Per-directory steering | `CLAUDE.md` | `AGENTS.md`, then configured `CLAUDE.md` fallback |
| Reload | Reload enabled plugins | Refresh plugin cache and restart; exact proof lives in conformance |

Hook provider detection order is `AFK_PROVIDER` override, `PLUGIN_ROOT` as Codex, compatibility root/runtime markers as Claude, then `unknown`. `CLAUDECODE` can be inherited by another harness and never vetoes `PLUGIN_ROOT`.

## Distribution law

- The committed plugin tree stays inert until the harness enable flag names it.
- Skills, hooks, MCP registration, and agent definitions activate only through that harness.
- Repository-root routers stay provider-neutral.
- Never commit `.agents/`, `.codex/`, or generated local steering blocks.
- Copy Codex agent TOML stubs byte-for-byte into `~/.codex/agents/`; never render a mirror.
- Add provider behavior only in `hooks/lib/providers/<name>.sh` and this file.
- Add harness #N through the checklist in `providers/CONFORMANCE.md`; do not edit skill prose.

## Model tiers

Tier roles are owned by `DELEGATION.md`. A column is harness configuration, not a vendor claim: pick the first available model in the active harness column, else the nearest capability-compatible model that harness can drive.

| Tier | Claude Code | Codex CLI |
|---|---|---|
| Frontier | `fable`; floating `opus` fallback | `gpt-5.6-sol` at high or xhigh effort; `gpt-5.5` fallback |
| Implementation | Pinned `claude-opus-4-8`; `sonnet` for simple slices | `gpt-5.6-terra` at medium effort; lower effort for simple slices |
| Digest | `sonnet` | `gpt-5.6-terra` at low effort |
| Deterministic | `haiku`, carried by the `afk-runner-lite` definition | `gpt-5.6-terra` at low effort; no distinct rung exists, so the split saves nothing here |

The implementation pin travels through the agent definition. Never pass the pinned identifier as a spawn-model argument. Agent definitions load at session start.

## Agent stubs

Claude reads `agents/*.md` from the enabled plugin. Codex reads the unchanged files copied from `providers/codex/agents/` into `~/.codex/agents/`. Each TOML file resolves the enabled plugin cache, then reads the same `LANGUAGE.md` and role Markdown. Parent permissions can override a child sandbox.

Codex has no documented custom-agent tool allowlist or nesting-depth setting. Use sandbox plus role prohibitions. Root agents spawn; children run helper work inline when nesting is unavailable.

## Credentials

Jira reads exported `JIRA_*` variables first, then the supported user-config fallbacks. Never print secret values. The shared plugin `.mcp.json` starts the same server for each harness; tool prefixes vary, so skills use bare tool names.

## Optional capabilities

Question cards and design push are harness capabilities. Follow `CAPABILITIES.md`; do not inline provider branches in skills.

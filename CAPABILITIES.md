# Harness capability contract

Use this table for every capability branch. Missing required capability stops the skill. Missing optional capability uses only the listed degradation.

| Capability | Claude Code | Codex CLI | Required degradation |
|---|---|---|---|
| `skills` | Native plugin catalog; `/afk:<x>` | Native plugin catalog; `afk:<x>` | Unsupported when absent |
| `plugin_hooks` | Native | Native with `features.hooks` and handler trust | Run the named gate explicitly |
| `hook_shell_match` | `Bash` and `PowerShell` | `Bash` covers shell and unified execution | Match the semantic tool class |
| `hook_project_dir` | Optional injected root | No injected project-root contract | Resolve the Git root from `$PWD` |
| `custom_agents` | Plugin Markdown definitions | User TOML stubs | Use a built-in role plus the canonical role prompt |
| `agent_tool_allowlist` | Definition frontmatter | No documented equivalent | Use sandbox plus role prohibitions |
| `parallel_agents` | Native | Native | Serialize when unavailable |
| `continuation` | Native | Use only after conformance proves same-child context | Use disk handoff |
| `nesting` | Native within AFK cap | No depth contract | Root spawns; children run helpers inline |
| `model_tiers` | Provider mapping | Provider mapping | Use nearest capability-compatible model |
| `plugin_mcp` | Native | Native | Use a documented CLI or API fallback; otherwise stop |
| `plugin_job_dir` | Native | No | Use plugin-data scratch space |
| `question_cards` | Native | No | Ask one plain-text question |
| `design_push` | Native | No | Keep local HTML canonical |
| `reload` | Reload the enabled plugin | Re-add the plugin, then start a new session | Report stale cache |

## Shared hook subset

Shared hook events: SessionStart, PreToolUse, Stop

Shared hook matchers: *, Bash, PowerShell, Glob, Grep, mcp__intellij__search_in_files_by_regex, mcp__intellij__search_in_files_by_text, mcp__intellij__search_text, mcp__intellij__search_regex

- Events: `SessionStart`, `PreToolUse`, `Stop`.
- Matchers: `*`, `Bash`, `PowerShell`, `Glob`, `Grep`, `mcp__intellij__search_in_files_by_regex`, `mcp__intellij__search_in_files_by_text`, `mcp__intellij__search_text`, `mcp__intellij__search_regex`.
- Blocking: PreToolUse deny envelope; Stop emits the findings on stderr AND a `{"decision":"block","reason":…}` object on stdout, exiting with the code the adapter names (`afk_<provider>_stop_block_code`). One harness reads the stderr-plus-exit-2 form, another honours only the decision object, and a handler that emits just one of them is recorded as failed rather than as a verdict.
- Every hook command is `python "${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.py" plugin|repo <handler.sh>` — one form both a POSIX shell and PowerShell parse, and the launcher, not the command string, locates the shell and the repository root (`${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}`). Never put shell syntax or a bare `bash` in a command string: `bash` names the WSL stub on many Windows machines.

## Skill requirements

| Skill set | Required | Optional |
|---|---|---|
| Every skill | `skills` | `question_cards` |
| Skills with completion gates | `plugin_hooks` | — |
| Skills that delegate | `custom_agents`, `model_tiers` | `agent_tool_allowlist`, `parallel_agents`, `continuation`, `nesting` |
| `/afk:to-ticket`, `/afk:bug` | `plugin_mcp` | — |
| `/afk:prototype`, `/afk:design-system` | — | `design_push` |

Provider spellings, enable flags, and model names live in `PROVIDERS.md`. Live proofs and unresolved capabilities live in `providers/CONFORMANCE.md`.

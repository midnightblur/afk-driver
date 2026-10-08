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
| `issue_egress` | `gh` CLI, logged in | `gh` CLI, logged in | Queue the draft on disk and print the publish command |
| `protected_branch_guard` | PreToolUse guard; declared reads and one recognized read-only shell command pass; `EnterWorktree` moves the session; `WorktreeCreate`, `WorktreeRemove` and `SessionEnd` handlers | PreToolUse guard; declared reads and one recognized read-only shell command pass; the `/cd` line, typed by a detached helper in a herdr pane or by the human; `SessionEnd` handler | Without hooks the installed git backstop still refuses an agent's commit and branch move in the main checkout, and the behavior line instructs |
| `reload` | Reload the enabled plugin | Re-add the plugin, then start a new session | Report stale cache |
| `nested_steering` | Native nested `AGENTS.md` read with the root `CLAUDE.md` bridge and `instructionFiles=claude-md-and-agents-md` (setup H11) | Loads instruction files once at run start, so nested files never reach it | The plugin `PostToolUse` hook injects the `AGENTS.md` chain below the launch directory (deepest last) and, where the harness has no native path-scoped rules, the matching `.claude/rules` bodies; policy lives in `hooks/lib/providers/<name>.json` (`nested_inject_mode`, `nested_inject_rules`) |
| `agents_md_config_notice` | SessionStart `--soft` notice (`hooks/agents-md-config-check.sh`): warns, never blocks, when the repository tracks an `AGENTS.md` but the `instructionFiles` setting is not `claude-md-and-agents-md` (setup H11) | Not applicable — `instructionFiles` is a Claude-only setting; the hook is present in the twin manifest (twin law), and the launcher exits 0 before any shell here (`instruction_files_setting` is false) | None — advisory only; the notice names the setting and points to `/afk:setup` |
| `change_rationale` | Forge adapter with inline `change-comment`, `commit-changes`, and `git blame`; commit-time comment gate on agent commits | Same | Rationale stays pending under the git directory; the run reports the exact blocker and never claims durable rationale |
| `managed_behavior` | Setup-managed `afk:behaviors` block in `~/.claude/CLAUDE.md`; SessionStart drift notice | Setup-managed `afk:behaviors` block in `~/.codex/AGENTS.md`; SessionStart drift notice | Unavailable until the user opts in through `/afk:setup`; teardown before plugin disable |

## Shared hook subset

Shared hook events: SessionStart, PreToolUse, PostToolUse, PostCompact, Stop

Shared hook matchers: *, Bash, PowerShell, Glob, Grep, startup, clear, mcp__intellij__search_in_files_by_regex, mcp__intellij__search_in_files_by_text, mcp__intellij__search_text, mcp__intellij__search_regex

Provider-specific hook events: claude=WorktreeCreate, claude=WorktreeRemove, claude=SessionEnd, codex=SessionEnd

- Events: `SessionStart`, `PreToolUse`, `PostToolUse`, `PostCompact`, `Stop`. Both harnesses carry `PostToolUse` with an additional-context injection and `PostCompact` as a session reset (`providers/CONFORMANCE.md`).
- Provider-specific events: an event only one harness has lives in that harness's manifest alone, declared by the `Provider-specific hook events` line (`<provider>=<event>`, comma separated). `hooks/native-contract-gate.sh` accepts it there and nowhere else, and the twin test ignores exactly those keys.
- Matchers: `*`, `Bash`, `PowerShell`, `Glob`, `Grep`, `startup`, `clear`, `mcp__intellij__search_in_files_by_regex`, `mcp__intellij__search_in_files_by_text`, `mcp__intellij__search_text`, `mcp__intellij__search_regex`. `startup` and `clear` gate a `SessionStart` reset to a fresh or cleared session, never `resume`/`fork`.
- Injecting: `PostToolUse` returns `hookSpecificOutput.additionalContext` (and a mirrored top-level `additional_context`); the harness folds it into the session. A `PostToolUse`/`PostCompact` handler never blocks — it adds context or resets state and exits 0.
- Blocking: PreToolUse deny envelope (the JSON at exit 0, never exit 2: one harness runs the tool when a PreToolUse hook exits 2); Stop emits the findings on stderr AND a `{"decision":"block","reason":…}` object on stdout, exiting with the code the adapter names (`afk_<provider>_stop_block_code`). One harness reads the stderr-plus-exit-2 form, another honours only the decision object, and a handler that emits just one of them is recorded as failed rather than as a verdict. A user notice on an allowed Stop goes to stderr and to a top-level `systemMessage` at exit 0 (`afk_emit_stop_notice`); both harnesses document that field for Stop.
- The launcher owns the handler's process tree and an inner deadline (`--deadline`, below the manifest `timeout`). Past it the launcher ends the tree and reports verdict unknown. Where the launcher cannot prove cleanup, it says `tree cleanup degraded` on stderr. A handler's leftover processes also end when the handler exits, on both OSes; `DETACHES_HELPERS` in `hooks/run-hook.py` is the plugin-only exemption, and a repository hook that needs a lasting background process detaches it itself, outside the launcher. `hooks/README.md` owns the rule.
- Every hook command is `afk-python "${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.py" plugin|repo <handler.sh>` (one exception: the protected-branch guard, meter and occupancy hooks run under `afk-python` directly, for latency) — one form both a POSIX shell and PowerShell parse, and the launcher, not the command string, locates the shell and the working tree's Git root (`hooks/README.md` owns the root rule). Never put shell syntax or a bare `bash` in a command string: `bash` names the WSL stub on many Windows machines.

## Hook failures

A plugin hook that fails, or a repository handler the launcher runs, names itself with one stderr line:

`[afk] <handler> (<event>) failed: <outcome>: <reason>`

- `outcome` is `exit <n>`, `timed out after <D>s, stopped, verdict unknown` (`verdict unknown` for a repository handler), or `uncaught exception` for a direct Python entry. `reason` is the handler's last non-empty stderr line, the exception, or `no message`. `event` is the envelope's `hook_event_name`, else `unknown event`.
- A deliberate block (exit 2, or a deny/block decision object) is not a failure: no line, and the handler's own message stands. Exit 0 adds nothing.
- stdout stays one document. In a blocking `repo-list` event a crashed handler refuses; its line is the refusal reason inside the one decision object.
- Where stderr reaches the human (`hook_failure_notice: stderr`), the exit code passes through. Where the harness drops stderr on any exit but 0 and 2 (`hook_failure_notice: system_message`), a non-soft failure exits 0 and carries the same line in a top-level `systemMessage`, merged into the document the other handlers printed. The failed handler's stdout is dropped there. Codex 0.161.0 (tag `rust-v0.161.0`): `codex-rs/hooks/src/events/pre_tool_use.rs:278-283` (and the same arm in `session_start.rs:314-319`, `post_tool_use.rs:276-281`, `stop.rs:370-375`) records only `hook exited with code N`; `systemMessage` is read only at exit 0 (`pre_tool_use.rs:218-222`).
- A `--soft` handler and a direct fail-open entry (meter, occupancy) still exit 0. A soft handler's line goes to stderr only. The guard keeps its fail mode: refuse inside a work tree, allow outside.
- A launcher that cannot start at all (`afk-python` not on the hosting process's `PATH`) prints nothing the plugin controls: the harness shows its own failed-hook line. Fix: `/afk:setup` row P1.

## Skill requirements

| Skill set | Required | Optional |
|---|---|---|
| Every skill | `skills` | `question_cards` |
| Skills with completion gates | `plugin_hooks` | — |
| Skills that delegate | `custom_agents`, `model_tiers` | `agent_tool_allowlist`, `parallel_agents`, `continuation`, `nesting` |
| `/afk:to-ticket`, `/afk:bug` | `plugin_mcp` | — |
| `/afk:prototype`, `/afk:design-system` | — | `design_push` |
| `/afk:report-issue` | — | `issue_egress` |
| `/afk:execute`, `/afk:settle-change`, `/afk:diagnose`, `/afk:fix`, `/afk:review` | — | `change_rationale` |

Provider spellings, enable flags, and model names live in `PROVIDERS.md`. Live proofs and unresolved capabilities live in `providers/CONFORMANCE.md`.

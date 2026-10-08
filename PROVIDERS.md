# Provider mapping

The committed workflow plugin is one native tree. `CAPABILITIES.md` owns capability degradation. `providers/CONFORMANCE.md` owns live proof. `providers/HARNESS-MATRIX.md` owns per-harness instruction-file discovery facts (which file each harness reads, walk order, size caps).

## Supported harnesses

A harness is a CLI, never a model vendor. Add a row here first; the native contract gate holds this table and `hooks/lib/providers/*.sh` to the same list.

| Harness | Native discovery | Adapter | Agent definitions | Conformance | Notes |
|---|---|---|---|---|---|
| `claude` | `.claude-plugin/plugin.json`, enabled by `enabledPlugins` | `hooks/lib/providers/claude.sh` | `agents/*.md`, read in place | pending 2026-09-01 | Reference harness for the shared hook subset |
| `codex` | `.codex-plugin/plugin.json`, enabled through the native marketplace | `hooks/lib/providers/codex.sh` | `providers/codex/agents/afk-afk-*.toml`, copied to `~/.codex/agents/` with `{{PLUGIN_ROOT}}` resolved | pending 2026-09-01 | Needs `features.hooks` and per-handler trust |

Conformance holds the probe verdict and date per harness. `providers/CONFORMANCE.md` owns the add-a-harness checklist.

## Construct mapping

| Construct | Claude Code | Codex CLI |
|---|---|---|
| Enable plugin | `enabledPlugins` names `afk@afk-toolkit` | Native marketplace plus enabled `afk@afk-toolkit` |
| Skill reference | `/afk:<x>` | Catalog name `afk:<x>`: strip the leading slash; `$afk:<x>` typing is unverified |
| Project skill | Native skill name | Native skill name |
| Spawn AFK role | Plugin agent `afk-reader`, `afk-runner`, `afk-runner-lite`, `afk-implementor`, or `afk-tracer` | Same names from unchanged user TOML stubs |
| Generic role | General-purpose or exploration role | Built-in worker or explorer role |
| Parallel spawn | Parallel calls | Parallel agent spawns |
| Continue child | Native continuation | Continue only where `providers/CONFORMANCE.md` proves same-child context; disk handoff otherwise |
| Plugin root/data | Compatibility root/data variables | `PLUGIN_ROOT`/`PLUGIN_DATA`; compatibility variables also exist |
| Managed plugin directory | `~/.claude/plugins`, moved by `CLAUDE_CONFIG_DIR` | `~/.codex/plugins`, moved by `CODEX_HOME` |
| Installed root, resolved from a different session | Native env var when set (only when Codex is not the active provider — its `PLUGIN_ROOT` also sets the Claude compatibility variable), else `installed_plugins.json`'s `afk@afk-toolkit` entry's `installPath` | Native env var when set, else the `VERSION` column of `codex plugin list`'s `afk@afk-toolkit` row (located by header column name; no config field names this) → `${CODEX_HOME:-~/.codex}/plugins/cache/afk-toolkit/afk/<VERSION>` |
| Project root | `CLAUDE_PROJECT_DIR` when present | Resolve from `$PWD` through Git |
| Job scratch | Native job directory | Plugin-data scratch directory |
| Jira MCP tools | Plugin-scoped server; call the bare tool name | Plugin-scoped server; call the bare tool name |
| User steering | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| Managed behavior | `afk:behaviors` sentinel in user steering | `afk:behaviors` sentinel in user steering |
| Per-directory steering | `AGENTS.md` (root `CLAUDE.md` bridges `@AGENTS.md`) | `AGENTS.md` |
| Handler process tree | Launcher behavior, harness-neutral: a Job Object on Windows, a process group on POSIX; `--deadline` ends the tree before the hook timeout | Same |
| Reload | Reload enabled plugins | Refresh plugin cache and restart; exact proof lives in conformance |

Hook provider detection order is `AFK_PROVIDER` override, `PLUGIN_ROOT` as Codex, compatibility root/runtime markers as Claude, then `unknown`. `CLAUDECODE` can be inherited by another harness and never vetoes `PLUGIN_ROOT`.

## Protected-branch guard

The rule is `SAFETY.md` "Worktree per session". This section owns the
mechanics. Each provider file
`hooks/lib/providers/<name>.json` declares what the guard needs: the detect
variables, `harness_class`, the tool classes, `move_hint`, `worktree_folder`
and `owner_pid_env`.

The guard judges the resource a call mutates, not the command's shape
(ADR-0010). A shell command is split into segments; each literal path or
repository a mutation names is judged. An opaque target (variable,
substitution, glob) and an unknown program pass. A tool with no path-like key
passes. An exact provider declaration overrides the fallback tool-name
classifier.

Three more hooks serve the guard:

- `protected-branch-meter.py` (`PostToolUse`) compares the checkout with the
  snapshot the guard took before an allowed shell call and holds the session
  when a path changed (ADR-0012). It never blocks.
- `protected-branch-occupancy.py` (`SessionStart`) registers the session in
  its linked worktree and prints one advisory line when another live session
  holds it (ADR-0013).
- `git-backstop.py` consumes the one-shot sync authorization the guard writes
  for `git pull --ff-only` in the main checkout (ADR-0011).

Environment variables: `AFK_WORKTREE_GROUP` names a team that may share one
worktree. Without it, `HERDR_ENV=1` plus `HERDR_TAB_ID` makes one herdr tab a
team. `AFK_WORKTREE_OWNER` overrides the session identity. `AFK_ALLOW_PROTECTED=1`
lifts every worktree-protection refusal and hold; the guard's lavish rule still applies
(`LAVISH.md`). The register is `skills/afk/setup/MANIFEST.md`.

| Class | Harness | How a refused session moves | Cleanup |
|---|---|---|---|
| H-1 | `claude` | The agent calls its own worktree tool. The `WorktreeCreate` handler runs `scripts/create-worktree`. | `WorktreeRemove` and `SessionEnd` handlers run `scripts/remove-worktree.py`; a session ending inside its worktree starts a detached waiter that removes it once the harness exits |
| H-2 | `codex` | The guard names a new worktree and the `/cd <path>` line, then a detached helper cuts it and, in a herdr pane, types the line. `scripts/afk-launch.py` starts a harness in a worktree. | `SessionEnd` handler runs `scripts/remove-worktree.py` |

Typing the `/cd` line needs herdr's session reporting for the H-2 harness: herdr learns a
pane's session id from its own integration hook (`herdr integration install codex`), and the
helper types only into a pane whose reported session is the refused one. Without it the helper
types nothing and logs why; the human types the printed `/cd` line.

The same file declares the launcher's policy, read by `hooks/run-hook.py` before any
shell and by `afk_provider_fact` in bash: `nested_inject_mode` (`never`,
`agent-only` or `always`) and `nested_inject_rules` (`0` or `1`) for the
nested-steering hook, and `instruction_files_setting` (`true` where the
harness has the `instructionFiles` setting). A handler the policy makes a no-op
starts no shell.

`WorktreeCreate` and `WorktreeRemove` ship in the same release. A harness that
creates a worktree through the plugin must also remove it through the plugin.
Every session start prunes worktrees whose owner is gone.

**One-time hook trust for Codex.** Codex runs a new or changed plugin hook only
after you trust it. Trust is positional, so the guard is the last `PreToolUse`
group and the older hooks keep their trust. Five entries are new: the guard,
the `PostToolUse` meter, the `SessionEnd` handler, the session-start prune, and
the session-start occupancy registration. Start `codex` once in
the terminal UI without the full-bypass flag and choose `2. Trust all and
continue` on the "Hooks need review" screen, or type `/hooks` in a session and
press `t`. With the full-bypass flag, or with `codex exec`, the hooks do not
run and Codex prints nothing until you have done this once. A release that
changes hook command strings, such as the move to `afk-python`, asks again.

## Distribution law

- The committed plugin tree stays inert until the harness enable flag names it.
- Skills, hooks, MCP registration, and agent definitions activate only through that harness.
- Repository-root routers stay provider-neutral.
- Never commit `.agents/`, `.codex/`, or generated local steering blocks. One exception:
  `.agents/plugins/marketplace.json` is committed, because `codex plugin marketplace add`
  reads the Codex marketplace manifest from that path. Nothing else under `.agents/`
  may be tracked, and `native-contract-gate.sh` enforces exactly that.
- The comment gate runs only from the `pre-commit` hook that `install-git-hooks.sh` installs for an enabled plugin, on agent-driven commits. Rationale support writes only to the forge change and to two local places: pending entries under the repository's git directory and a cache outside the repository. A developer without the plugin sees neither.
- `install-git-hooks.sh` installs the git backstop in every repository a session opens once the plugin is enabled, with or without `.afk/`. Both hooks act only under an agent-runtime marker, so a human's git is never gated. A repository that sets `core.hooksPath` is skipped with one notice.
- Uninstalling a harness does not remove those per-machine paths; the setup register's stale-activation entry offers their cleanup.
- Run `/afk:setup teardown` before disabling the plugin. It removes the managed
  behavior block from both user instruction files. No shipped provider has a
  proven uninstall callback.
- Copy Codex agent TOML stubs into `~/.codex/agents/` under their own filenames, replacing only the `{{PLUGIN_ROOT}}` placeholder with the installed plugin root that Codex plugin metadata reports; never render a mirror.
- Add provider behavior only in `hooks/lib/providers/<name>.sh`, its facts file
  `hooks/lib/providers/<name>.json` (detection, tool classes, the move hint and the
  `move_ui` block: typed command, outcome patterns, prompt glyphs), this file,
  and — only where the algorithm is naturally table/JSON-shaped, never as a
  default — a `hooks/lib/providers/<name>_*.py` helper that `<name>.sh` alone
  calls. No other file may reference that helper, except a unit test under
  `scripts/tests/` loading the helper module directly to test it.
  `hooks/native-contract-gate.sh` enforces both the naming and the
  single-caller rule.
- Add harness #N through the checklist in `providers/CONFORMANCE.md`; do not edit skill prose.

## Model tiers

Tier roles are owned by `DELEGATION.md`. A column is harness configuration, not a vendor claim: use the model in the active harness column; if that harness cannot drive it, use the nearest capability-compatible model.

| Tier | Claude Code | Codex CLI | Codex effort |
|---|---|---|---|
| Frontier | `opus` | `gpt-6-sol` | `high` |
| Implementation | `opus` | `gpt-6-sol` | `medium` |
| Digest | `sonnet` | `gpt-5.6-terra` | `medium` |
| Deterministic | `haiku` | `gpt-6-luna` | `low` |

| Agent | Tier |
|---|---|
| `afk-tracer` | Frontier |
| `afk-implementor` | Implementation |
| `afk-reader` | Digest |
| `afk-runner` | Digest |
| `afk-runner-lite` | Deterministic |

A model cell is the one home of that tier's model. A cell holds an alias to follow the harness default, or an exact model id to pin. Claude Code accepts both in agent frontmatter `model:` (https://code.claude.com/docs/en/sub-agents).

Each agent file repeats its tier's cell literally, because the harness reads frontmatter and TOML as written. To pin a tier, edit its cell; `hooks/native-contract-gate.sh` check L names every `agents/*.md` and `providers/codex/agents/*.toml` that must follow. Codex users re-run `/afk:setup` afterwards, since setup register entry O5 (`skills/afk/setup/MANIFEST.md`) copies the TOMLs.

A spawn may run a simple slice on `sonnet` (Claude Code) or at lower effort (Codex CLI) instead of the Implementation cell.

A Fable-class or Astra-class model is never a tier. Name one only where a skill
requires that model for one specific usage.

The implementation model travels through the `afk-implementor` definition. Never pass it as a spawn-model argument. Agent definitions load at session start.

## Agent stubs

Claude reads `agents/*.md` from the enabled plugin. Codex reads the files copied from `providers/codex/agents/` into `~/.codex/agents/`. Each TOML file carries the installed plugin root verbatim, then reads the same `LANGUAGE.md` and role Markdown. Parent permissions can override a child sandbox.

Codex has no documented custom-agent tool allowlist or nesting-depth setting. Use sandbox plus role prohibitions. Root agents spawn; children run helper work inline when nesting is unavailable.

Each adapter also names the exit code its harness reads a Stop block from (`afk_<provider>_stop_block_code`, default 2). The findings themselves go out on both channels, so an adapter never has to restate the message shape.

## Credentials

Jira reads exported `JIRA_*` variables first, then the supported user-config fallbacks. Never print secret values. The shared plugin `.mcp.json` starts the same server for each harness; tool prefixes vary, so skills use bare tool names. Its bootstrap does not depend on inherited environment: when a harness starts the MCP child with a filtered environment, it fills the `JIRA_*` values from the same chain the server documents — exported variables first, then the `tracker` server's `env` block (or afk's own pre-rename `jira` entry; another `jira` server is ignored; the test is `is_afk_entry` in `skills/afk/setup/scripts/tracker_registration.py`) in `~/.claude.json`, then `[mcp_servers.tracker.env]` in `~/.codex/config.toml`. It resolves the plugin root in this order: (1) an argument that is not a literal `${…}`; (2) `AFK_PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, `PLUGIN_ROOT`; (3) the newest live install under the user's home, its own harness directory first. The search skips a copy the harness marked orphaned. An argument or variable that names an orphaned copy is tried only after the search. One harness interpolates the argument, another passes it through literally, and both reach the same server. The search sees only harness directories one level under the home directory. A Codex MCP child receives neither a root variable nor `CODEX_HOME`. With `CODEX_HOME` elsewhere, the launcher runs another harness's copy if one is there, else exits not found. A live root passed as the launcher's first argument is tried before the search. Codex passes the arguments of a user-scoped `[mcp_servers.tracker]` entry verbatim, so a root given there is used (live, codex-cli 0.159.0).

## Optional capabilities

Question cards and design push are harness capabilities. Follow `CAPABILITIES.md`; do not inline provider branches in skills.

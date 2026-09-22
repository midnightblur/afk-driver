# Harness instruction-file matrix

The per-harness facts behind the `AGENTS.md` instruction-file standard (steward: `skills/afk/agents-md`, decision record: `adr/0003-agents-md-instruction-standard.md`). This is the one home for how each harness discovers instruction files; skill and doctrine prose points here and never restates a row. `native-contract-gate.sh` excludes this file from its harness-vocabulary scan for exactly that reason.

**Maintaining this file.** Read each row from a primary source before acting on it, and re-verify a row when that harness releases. The facts below were read on 2026-09-22; items still unverified are marked. When you add harness support, fill every subsection for the new harness and cite the source.

## 1. Discovery matrix

| | Claude Code (v2.1.277+; tested 2.1.280) | Codex CLI | Pi | OpenCode |
|---|---|---|---|---|
| Reads `AGENTS.md` | Only when no `CLAUDE.md`, `.claude/CLAUDE.md` or `CLAUDE.local.md` sits in the working directory or above it, unless the user setting says `claude-md-and-agents-md` | Always | Always, first match per directory | Yes, `CLAUDE.md` as fallback |
| Walk | Working directory upward | Project root (marker `.git`) down to the working directory | Working directory up to filesystem root | Working directory up to the worktree root |
| Nested files | Loaded when a file there is read — documented for `AGENTS.md` too (quote in §2) | Start of run only | Start of run only | Loaded when a file there is read (source code, docs silent) |
| User-global file | `~/.claude/CLAUDE.md`, `~/.claude/rules/` | `$CODEX_HOME/AGENTS.override.md`, else `$CODEX_HOME/AGENTS.md` | `~/.pi/agent/…` | `~/.config/opencode/AGENTS.md` |
| Global file additive? | Yes, loads first | Yes — separate `user_instructions`, placed first, joined with `--- project-doc ---` | Yes, first | Yes |
| `@path` imports | Expanded | No | No | No, documented explicitly |
| `AGENTS.override.md` | Ignored | Replaces the same directory's `AGENTS.md`; ancestors still load | Same | None |
| `AGENTS.local.md` | Ignored | Not documented, absent from source | Not documented | Not documented |
| Size cap | None documented | 32 KiB over the *project* chain for the launch directory; the global file is excluded. The straddling file is truncated, then the walk stops | Not documented | Not documented |
| Path-scoped rules | `.claude/rules/*.md` with `paths:` | None | None | Globs in the `instructions` config list |

Sources: code.claude.com/docs/en/memory, /sub-agents, /hooks;
learn.chatgpt.com/docs/agent-configuration/agents-md; openai/codex
`codex-rs/core/src/agents_md.rs`, `codex-rs/codex-home/src/instructions/mod.rs`,
`codex-rs/config/src/config_toml.rs`, `codex-rs/hooks/src/schema.rs`,
`codex-rs/core/src/compact.rs`, `hook_runtime.rs`; earendil-works/pi
`packages/coding-agent/docs/configuration.md`; opencode.ai/docs/rules.

## 2. Claude Code specifics

- "By default, Claude reads `AGENTS.md` only when you have no `CLAUDE.md` in your working
  directory or above it." `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md` count.
  `~/.claude/CLAUDE.md`, managed `CLAUDE.md` and `.claude/rules/` do not.
- Nested, verbatim: "As Claude works in subdirectories: a subdirectory's `AGENTS.md`, when
  Claude opens a file there with the Read tool and that subdirectory has none of the three
  `CLAUDE.md` files of its own." This holds only when the top-level condition above holds.
- **Project instructions** values: `claude-md-or-agents-md` (default), `claude-md-and-agents-md`,
  `claude-md`, `managed-only`. Stored under `pluginConfigs."agents-md@builtin".options.instructionFiles`.
  "Claude Code ignores it in project and local settings files."
- Under `claude-md-and-agents-md`: "each directory's `CLAUDE.md` files first and its `AGENTS.md`
  after them. Claude Code skips an `AGENTS.md` it has already loaded, so one that your
  `CLAUDE.md` imports or symlinks to isn't read twice."
- From v2.1.280, `/memory` lists a natively read `AGENTS.md`: "To check whether Claude
  read your `AGENTS.md`, run `/memory` and look for its path in the list." / "Before v2.1.280,
  `/memory` and `/context` didn't list an `AGENTS.md` that Claude read directly." (The page was
  revised on 2026-09-22; an earlier fetch the same day showed the pre-2.1.280 text.)
  `InstructionsLoaded` hooks still do not fire for it.
- Session start also loads `.claude/AGENTS.md`; inside an `AGENTS.md`, `@path` imports
  are expanded and `claudeMdExcludes` applies. The import ban in the standard is a portability
  policy, not a harness limit.
- Native reading is unavailable on third-party providers, with telemetry off, under
  `disableAllHooks` / `allowManagedHooksOnly`, with the built-in `agents-md` plugin disabled, and
  in "your first session after you install or upgrade to a version with `AGENTS.md` support.
  Claude reads `AGENTS.md` from your next session on." Treat the first-session case as
  recurring on every upgrade until proven otherwise; this is why the standard keeps a root bridge.
- `CLAUDE.local.md` is additive, after that directory's `CLAUDE.md`.

## 3. Codex specifics

- Per directory: `AGENTS.override.md`, `AGENTS.md`, then `project_doc_fallback_filenames`;
  at most one file per directory.
- No per-repo additive instruction file. `experimental_instructions_file` is gone.
- A trusted repo's `.codex/config.toml` may set `instructions` / `developer_instructions` — not on
  `PROJECT_LOCAL_CONFIG_DENYLIST`. **Inferred, untested.** Not used by the standard.
- Hook events (`schema.rs:102`): `PreToolUse`, `PermissionRequest`, `PostToolUse`,
  `PreCompact`, `PostCompact`, `SessionStart`, `UserPromptSubmit`, `SubagentStart`,
  `SubagentStop`, `Stop`, `Interrupt`, `SessionEnd`. `additional_context` exists on
  SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart. Input carries
  `agent_id: Option<String>`.
- "Hooks running within subagents use the parent session ID" (`hook_runtime.rs`).
- Compaction keeps only user messages (`compact.rs:561-584`); hook `additional_context`
  is recorded as a developer message and is dropped by compaction.
- Codex re-prompts hook trust when `hooks.codex.json` changes
  (`providers/CONFORMANCE.md`). A dismissed prompt means no hook, silently.

## 4. Subagents

- Claude: a non-fork subagent loads "`CLAUDE.md` files — the full hierarchy including …
  `AGENTS.md` files loaded as project instructions". Explore, Plan, and `omitClaudeMd: true`
  agents skip them. No afk agent sets `omitClaudeMd`.
- Claude hooks that fire inside subagents: `PreToolUse`, `PostToolUse`, `SubagentStart`,
  `SubagentStop`. `PostToolUse` injects through `hookSpecificOutput.additionalContext`.
- **Unverified**: whether a Claude subagent's read triggers the nested lazy load.
- **Unverified**: whether hook-injected context survives Claude compaction.

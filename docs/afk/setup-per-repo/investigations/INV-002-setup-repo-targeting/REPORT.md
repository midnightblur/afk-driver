midnightblur/afk-driver@17ec3223985388dab50ffdc5d04b1b1f27dc99ce · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-002-setup-repo-targeting/COVERAGE.json

## Answer

Only the H6 fix can configure a repository other than the current directory (`--repo PATH`). Every other `/afk:setup` step uses the current directory's git root, or user or machine scope. The plugin keeps no durable list of the developer's repositories at HEAD 17ec322. Run 3 confirms the SessionStart H5 install is bound to the current directory too. No answer changed from run 2.

## Sites

- Step 0 / H0 `init` — current directory: `scripts/afk-config.py:1236` (`git_root()` `:315`), writes `:1152,1168`, usage `:7-12` has no repo flag.
- H6 probe — current directory: `skills/afk/setup/MANIFEST.md:140,150-170`; test `scripts/tests/test_setup_h6_probe.py:156-164`.
- H6 fix — any repository: `MANIFEST.md:180-187,202`; `skills/afk/setup/scripts/developer_values.py:189-224`; test `scripts/tests/test_setup_developer_values.py:93-115`. `--machine` writes `~/.afk/config.yaml` (`:191`).
- H2, S1, C3, C3b, W5 git half via `skills/afk/setup/scripts/setup_secrets.py` — no args; reads the current directory for kinds (`:54,112-128,150,154-155`); writes user-scope `~/.claude.json` `mcpServers.tracker` (`:243-252`) and `git config --global` (`:288`); refuses under the `claude` session marker (`:147-148`).
- `skills/afk/setup/scripts/tracker_registration.py:13-14,26-78` — plugin root only; registration names `tracker`, `jira` carry no repository.
- Tracker MCP server — the `claude` project-folder variable, else launch directory, per call: `mcp-servers/tracker/server.py:69`, `scripts/afk-config.py:324-329`.
- H5 `hooks/install-git-hooks.sh:44,53,101-102` resolves `git rev-parse --show-toplevel` in its working directory and reads no event field. At SessionStart (`hooks/hooks.json:9`, `hooks/hooks.codex.json:9`) the launcher starts it with no `cwd` and never changes directory (`hooks/run-hook.py:267,1035`). Both harnesses start hooks in the session's current directory (`claude` hooks docs: "Handlers run in the current directory"; `codex` hooks docs: "Commands run with the session `cwd`").
- H13, H14 probes pass no repository (`MANIFEST.md:341,358`).
- C4, C5, N3, O8, S3, `setup.extra`, every `sh:` probe — current directory.
- Machine or user scope: H1, H4, H7, H9, H11, H12, C1-C2b, C6-C16, P1, N1, N2, N4, O1-O7, W1, W2, teardown.
- No environment variable points a setup step at another repository; `AFK_CONFIG` adds one value layer only (`MANIFEST.md:142`, `developer_values.py:142`).
- `scripts/create-worktree` `--repo` (`:107,143,188,197,273`) — not a setup step.
- No repository list: schema `scripts/afk-config.py:53-59,73`; `CONFIG.md:4-5`; `hooks/lib/occupancy.py:51` is per repository. The harness's `~/.claude.json` has a `projects` map (19 entries here). The plugin reads it only inside the Jira credential walk (`adapters/tracker/jira/api.py:74-87,116-119`). The uncommitted `GLOSSARY.md:328-329` "Repository list" term is design text, not code.
- Inference: the overlay path `<git common dir>/afk/config.yaml` is spelled out, not taken from `shared_overlay`, at `hooks/precommit-gates.sh:191`, `scripts/protected-lookup.py:110`, `MANIFEST.md:143`; moving it changes all three.
- Inference, not run: `GIT_DIR` or `GIT_WORK_TREE` set in the harness environment would redirect H5, H13, H14 (`hooks/run-hook.py:421` copies the environment).

## Frontier

- B14, outside this repository: `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`, `~/.claude/settings.json`, `$CODEX_HOME/config.toml`, `~/.codex/agents/`, `%LOCALAPPDATA%/afk`, `~/.afk/config.yaml`, each target's `<git common dir>/afk/config.yaml`, the plugin cache, and the tracker env blocks in the harness configs (`PROVIDERS.md:176`).

## Unverified

- None.

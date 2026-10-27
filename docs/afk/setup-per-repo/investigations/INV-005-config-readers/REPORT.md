midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-005-config-readers/COVERAGE.json

## Answer
`load()` (`scripts/afk-config.py:388-397`) merges, lowest first: built-in defaults, `~/.afk/config.yaml`, `.afk/config.yaml`, `shared_overlay()` (`<git common dir>/afk/config.yaml`), `.afk/config.local.yaml`, `$AFK_CONFIG` (`layers()` :363-385). Most readers go through it: `hooks/lib/config.sh` export-shell plus 20 sourcing scripts, by-path imports (`hooks/run-hook.py:664`, `mcp-servers/tracker/server.py:62`, `adapters/tracker/github-issues/api.py:71`, `scripts/tracker_api.py:32`, `setup_secrets.py:51`), and the CLI `get`/`resolve`/`effective`/`validate`. Twelve sites read or locate a layer file themselves:

## Sites that skip load()
- `hooks/precommit-gates.sh:186-199`: no afk-python, so it lists 5 layers by hand and greps each for `repo-hooks`. Shared path from `git rev-parse --git-common-dir`.
- `hooks/precommit-gates.sh:59`: no code gates unless `<root>/.afk` dir exists. Inferred: home/shared/env-only config skips gates.
- `hooks/release-gate.sh:81-83`: awk reads `toolkit-version` from the repo file only. No test.
- `scripts/protected-lookup.py:107-112` `_configured`: 4 hand-listed paths + `$AFK_CONFIG` existence gate; none → `{}`, not defaults; else load().
- `scripts/afk-config.py:937-942` `_machine_layer`: parses home file alone (init → scaffold :985).
- `scripts/afk-config.py:1129-1145` `committed_elsewhere`: repo file on base refs + main worktree (init :1158).
- `scripts/afk-config.py:1148-1168` `init`: checks, writes repo file.
- `scripts/afk-config.py:1260-1279` `validate FILE`: parses one named file over defaults.
- `skills/afk/setup/scripts/developer_values.py:45-53,141-145,164`: `read_block` parses env/local/shared/home one by one for source labels; repo file left out.
- `developer_values.py:85,191,202`: writes shared or home file; `:177` `is_file` on repo file.
- `skills/afk/setup/scripts/setup_secrets.py:157`: `is_file` on repo file, warning only.
- `skills/utils/investigate/scripts/seed_map.py:286` (`.yml` too, label only), `:290-295` (`--config PATH`, one file; callers pass `auto`).

## Agent-facing instructions that touch layers directly
`skills/afk/setup/MANIFEST.md:42,45,142-147` (H0 `test -f`, H6 `says_none` greps 5 layers), `skills/afk/setup/SKILL.md:49-51,62`, `adapters/notes/notion/NOTES.md:12` (inferred), `scripts/behavior_registry.py:227` guard text.

## Documents the code refutes
`AGENTS.md:223`, `CONFIG.md:7,22`, `hooks/lib/config.sh:4-6`: "no gate parses the file" — `release-gate.sh:81`, `precommit-gates.sh:194` do.

## Tests
Pinned: precommit fallback (local/repo only), protected-lookup (repo only), init helpers, developer_values, setup_secrets, H6 probe, seed_map `--config`. Unguarded: `release-gate.sh:81-83`; env/shared/home branches of the precommit fallback and protected-lookup.

## Frontier
B14: consuming repositories and installed plugin cache copies hold their own copies of these readers.

## Unverified
- Same directory from protected-lookup's git path and `shared_overlay()` (inferred, untested).
- `forge_ledger.py:2101` `AFK_CFG_FORGE`: which parent exports it.

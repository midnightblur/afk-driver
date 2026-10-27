midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-011-setup-rerun-failure/COVERAGE.json

## Answer

- Walk: a failed fix is recorded and the walk goes on (`SKILL.md:128-129`); every touched entry is re-probed (`:130`); no stop rule in steps 0-6 (inferred from a full read). The final table has one status per entry: ok, fixed, deferred, three `skipped (...)` forms, `needs-human` (`:133-138`). There is no `failed` status, so a failed fix ends `needs-human` (inferred, `:140-142`). Rows classify `n/a`, which the status set lacks (`MANIFEST.md:418,453,572,797`).
- Rerun: no progress record; every probe reruns (`SKILL.md:80`; progress-word search over `skills/afk/setup`: 0 lines). Only P1 keeps a stamp (`python_runtime.py:300-315`).
- Stops inside one step: the H7 recipe stops at the first failing target after earlier targets are written (`MANIFEST.md:251-256`). `setup_secrets.py` `die()` or any uncaught error skips every later leg (`:75-77`). P1 install stops at the first failing step and rolls nothing back (`python_runtime.py:342-349`).
- Byte-identical on a second run (lab): `install-git-hooks.sh`, `install_block.py install`, `developer_values.py set`, `tracker_registration`, `set_instruction_files.py`, `codex_marketplace_ref.py`. `afk-config.py init` refuses an existing file (exit 2).
- Rerun leftovers: a new `~/.claude.json.bak-<ts>` every `setup_secrets.py` run, never pruned, inferred to hold the Jira token (`setup_secrets.py:243-246`). `.<name>.afk.lock` beside each instruction file, never removed (`install_block.py:160`). One `settings.json.bak-<second>` per changing H11 run (`set_instruction_files.py:121-124`).
- Part-way failure residue (lab, read-only target): `install_block.py` leaves `.<name>.<rand>.tmp` (exit 2). `developer_values.py` leaves `config.yaml.tmp` (exit 1, traceback). `set_instruction_files.py` leaves a backup (exit 1). `codex_marketplace_ref.py` on Windows leaves the backup and a temp file (exit 2).
- Silent passes: `install-git-hooks.sh:88` does not check the hook write; it prints "installed", exits 0, and the stale hook stays. The H5 probe checks only `reference-transaction` (`MANIFEST.md:112`), so a kept foreign `pre-commit` reads ok. When `core.hooksPath` is set, the installer exits 0 and installs nothing (`install-git-hooks.sh:47-50`); only the re-probe catches it. H13 exits 0 outside a repository (`background_git_hooks.py:40-54`).
- `setup_secrets.py` refuses only when the `claude` session marker is set; it does not check for a terminal (`:147-148`). It ran to exit 0 with input on a pipe, which contradicts `SKILL.md:124`. It writes `Path.home()/.claude.json` and ignores `CLAUDE_CONFIG_DIR` (`:38`).
- H11 rewrites the whole settings file: tab indent becomes spaces and non-ASCII becomes `\u` escapes, which contradicts `MANIFEST.md:308`.

## Changes outside the repository and their undo

| Step | Writes | Undo |
|---|---|---|
| H5 (+ every session start, `hooks.json:9`, `hooks.codex.json:9`) | `reference-transaction`, `pre-commit` in the common hooks dir | delete by hand (`branch-name-gate.sh:5`); the next session reinstalls them while the plugin is enabled |
| H2/S1 `setup_secrets.py` | `~/.claude.json` tracker entry + token, backups | restore a backup by hand; no command |
| C3/C3b | gh/glab credential store | `auth logout` (inferred; none named) |
| W5 + `setup_secrets.py:288` | `git config --global core.longpaths`; HKLM registry (human) | `--unset` (inferred; none named) |
| H6 | `<common dir>/afk/config.yaml`, `~/.afk/config.yaml` | `developer_values.py set KEY=` |
| H7 | `CLAUDE.md`, `AGENTS.md` in user config dirs | `/afk:setup teardown`; not byte-exact, lock files stay |
| H11 | `~/.claude/settings.json` | copy a `.bak-*` back by hand |
| O3/O5 | `~/.codex/config.toml`, plugin state, `~/.codex/agents/*.toml` | restore backup; `codex plugin remove`; delete stubs |
| O8 | deletes untracked worktree files | none |
| P1 | `%LOCALAPPDATA%\afk` or XDG dir; user PATH | delete dir + PATH entry (`MANIFEST.md:680-682`); POSIX startup-file lines not named |
| N2, N4, C2/C9 base, C12, W1, C15, C16 | global npm, winget, herdr binary, herdr hook in `codex` | none named |
| H12/O4 trust, H13, H14, H9 | human only; the scripts never write | harness UI |

No entry writes IDE settings. No script sets `core.hooksPath`, `git maintenance` or `fsmonitor` (query q-c7e2b21d).

## Sites
`skills/afk/setup/SKILL.md:45-142`; `skills/afk/setup/MANIFEST.md:38-939`; `hooks/install-git-hooks.sh:43-112`; `hooks/hooks.json:9`; `hooks/hooks.codex.json:9`; `skills/afk/setup/scripts/setup_secrets.py:38,75-77,147,185-291`; `install_block.py:111-299`; `developer_values.py:57-86,189-237`; `set_instruction_files.py:42-126`; `codex_marketplace_ref.py:63-140`; `background_git_hooks.py:40-110`; `ancestor_instruction_files.py:48-127`; `check_hook_trust.py:15-91`; `python_runtime.py:230-365`; `bootstrap.sh:3-47`; `bootstrap.ps1:3-56`; `scripts/afk-config.py:1148-1258`.

## Frontier
- B14: what uv, npm, winget, herdr and the gh/glab login write and how they undo; when the harness picks up PATH and asks for trust; the HKLM flag; what `codex plugin marketplace add|upgrade` and `codex plugin add|remove` write and whether a rerun is a no-op (`MANIFEST.md:786-792` runs them unwrapped; the repo decides only `codex_marketplace_ref.py`). Past live record, inferred to still hold: `marketplace add` twice answers "already added" (`providers/CONFORMANCE.md:74-77,233-237`).

## Unverified
- Not load-bearing: whether the harness reads `.claude.json` from `CLAUDE_CONFIG_DIR`; H11 truncation on a crash mid-write. No test covers the residue or silent-pass paths above.

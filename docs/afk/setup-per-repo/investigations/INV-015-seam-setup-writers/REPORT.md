midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-015-seam-setup-writers/COVERAGE.json

## Answer

| Seam | Existing contract | Verdict | Behaviour changes someone depends on |
|---|---|---|---|
| (a) safe writer | `install_block.py:101-234`: 40×50 ms lock wait, refuses "target is locked"; compare before and after temp write, refuses "changed during update"; keeps file mode (:203); temp `.{name}.*.tmp` deleted; lock `.{name}.afk.lock` kept | extends | none, if `install_block` keeps `InstallError`, `write_if_unchanged`, `_target_lock` and the error stays `InstallError` (or subclass) |
| (b) settings writer | `developer_values.py:57-86` rewrites only the `developer:` block; `record` :189-209 takes the 5 `ORDER` keys, several `KEY=VALUE` per call | reworked | `write_block(path, dict)` signature; `ORDER == DEVELOPER_KEYS`; `--machine` refusal of `worktreeBasePath`; `inherited` flag for machine values |
| (c) secret step | `setup_secrets.py` runs at import; one refusal (the `claude` session marker, :147); start copy :185 written back :252 via fixed `.afk-tmp`, no lock, default mode; dated `.bak-` per run | reworked | no-terminal refusal stops the 4 preflight tests; per-field Jira merge test; bare-run Fix lines |

- (a) Landmines: `install_block.main` catches only `(OSError, InstallError)` (:334, :359); a new error class gives a traceback. The Windows retry must re-raise an injected `OSError("interrupted")` unchanged and leave no temp (`test_install_block.py:168-181`). Owner-only must default off (mode test :159). Moved comments over 2 lines fail the comment gate (`hooks/lib/comment_gate.py:22`). `behavior_registry.py:64-68` needs 3 tests kept in `test_install_block.py`.
- (b) Landmines: `developer:  # note` header keeps the old block, so a second block makes `load()` fail on a duplicate key (`afk-config.py:254`). Values starting `{ [ & * | >` are not quoted (:77-79), and the parser refuses them (`afk-config.py:186-196`). `jira.site` must be written as a nested map. The shared overlay may not set `schema` (:394). A new key unknown to `validate` (`afk-config.py:73,109,633`) blocks the seed map (`seed_map.py:297`) and `resolve` (:1309). A machine-owned key always reads `inherited` (:183-184), so the H6 probe (`MANIFEST.md:165`) keeps failing.
- (c) Landmines: `test_setup_secrets_repo_root.py:44-57` runs with stdin closed and output captured, and keeps the `codex` session marker. `gh/glab auth status` with no `--hostname` skips login (:268). The re-probe checks only the legacy trio (:304). `register` replaces the whole `tracker` entry (`tracker_registration.py:71-78`). The harness does not take the afk lock, so the change refusal can fire on its writes. `resolve_creds_env` merges per field (`api.py:123-126`), pinned by `test_tracker_jira.py:199`; `afk-config.py:955` and `developer_values.py:116` read the legacy trio only.
- Conventions: FRESHNESS.md rule 2 (:16-18) needs a row for the new `scripts/` module; rows :67 and :69 name the touched scripts. Markdown naming the `claude` session marker/the `codex` session marker needs `hooks/native-contract-allow.txt` (`native-contract-gate.sh:127-128`). Schema changes move `CONFIG.md:119,136` with `test_afk_config.py:356`.
- Baseline: 105 tests pass in the 6 touched test files (Windows).

## Sites

`skills/afk/setup/scripts/install_block.py:101-234,334,359` · `developer_values.py:53-86,163-209,233` · `setup_secrets.py:105-109,145-148,185-252,268,304` · `tracker_registration.py:52-78` · `adapters/tracker/jira/api.py:107-136` · `scripts/afk-config.py:73,109,254,394,633,955,1309` · tests `test_install_block.py`, `test_setup_developer_values.py`, `test_setup_secrets_repo_root.py`, `test_tracker_jira.py:199`, `test_afk_config.py:356`, `test_afk_config_init.py:359-487` · docs `MANIFEST.md:76,149-214,422,441,746,938`, `setup/SKILL.md:122-127`, `FRESHNESS.md:67,69`, `CONFIG.md:119,136,294`, `PROVIDERS.md:176`, `jira/CONTRACT.md:25-36`.

## Frontier

- B14: the harness writing `~/.claude.json`; gh/glab account stores; other repositories.

## Unverified

- Bare `setup_secrets.py` run and the W5 long-path step (`MANIFEST.md:938` breaks: the line must name `longpaths`): design gap, answered by the solution grill: L9.10.
- Several `KEY=VALUE` pairs per `set` (`test_setup_developer_values.py:56` unchanged): design gap, answered by the solution grill: L9.11.
- Safe writer's error class (`developer_values.py:233` breaks: the catch does not name the new error): design gap, answered by the solution grill: A-3.
- `load_creds` signature (`api.py:136` unchanged: same name, no argument, 3 values): design gap, answered by the solution grill: L9.12.
- Harness use of `CLAUDE_CONFIG_DIR` for `~/.claude.json` (not load-bearing).

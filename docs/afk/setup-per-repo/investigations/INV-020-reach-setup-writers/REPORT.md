midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-020-reach-setup-writers/COVERAGE.json

## Answer

| Subject | Callers (site) | What the caller relies on |
|---|---|---|
| `install_block.py` CLI | MANIFEST.md H7 Fix :254-256 (`install "$rendered" "$target" \|\| exit 1`, run from SKILL.md:106); SKILL.md teardown loop :26-35 (checks no exit; judged by AUDIT.md:131-136); `hooks/tests/hook-smoke.sh` :208-275 (lifts the H7 recipe), :573-672 (CI `tests.yml:67`) | exit 0 + stdout `<action>: <target>; removed=N` (:362, read by nobody); exit 2 + stderr `install_block: <exc>` on OSError/InstallError (:334-336, :359-361); legacy form exit 1/2 (:303-312); default sentinel `behaviors` + `LEGACY_SENTINELS` (:31) |
| `install` / `teardown` / `InstallError` / `write_if_unchanged` (Python) | only `scripts/tests/test_install_block.py`, loaded by file path (:16, :231, :253) | `Result.action`/`removed`; `write_if_unchanged(target, expected, updated)`; `InstallError` texts "managed sentinel marker", "changed during update"; unwrapped OSError (:177); private `_target_lock`; `.<name>.afk.lock`, `.<name>.*.tmp` names. No other code catches `InstallError`/`ValueError` |
| `_atomic_write_locked` | 4 callers, all in `install_block.py`: :234, :269, :298, :316. No register row or skill step names it or `write_if_unchanged`; only GRILL-LOG.md:124,141-143 and design ADR 0005 | private |
| test file as contract | `scripts/behavior_registry.py:536-539` requires 3 test names in `test_install_block.py` (:64-68); gate chain `behavior-registry-gate.sh:22` → `plugin-source-gates.sh:97,271` → `precommit-gates.sh:153` + CI `tests.yml:99`. `behavior_registry.py:63` copies `LEGACY_SENTINELS`; `hooks/behavior-drift.sh:24` greps the sentinels | renaming a pinned test blocks commit and CI |
| `developer_values.py` | MANIFEST.md H6 Probe :165-167 (`status`, no `--repo`, parses `inherited`, `keys.<k>.need`; run by `test_setup_h6_probe.py:40`); H6 Fix :179-207 (`status --repo`, `set KEY=VALUE --repo [--machine]`), SKILL.md:80,111; `test_setup_developer_values.py` (import `dv` via sys.path :14-16, CLI :50) | status JSON keys; exit 0 `developer_values: wrote <file>`; exit 2 texts "not a git checkout", "KEY=VALUE", `worktreeBasePath` refusal; `KEY=` deletes |
| `write_block(path, dict)` | non-test: `record()` at developer_values.py:208 only; tests :76,128,142,174,184 | signature, `ORDER == DEVELOPER_KEYS` (:167), `read_block` |
| `setup_secrets.py` | `human:` Fix of H2 :76, S1 :746, C3 :422, C3b :441, W5 :938; SKILL.md:122-127 prints it; 4 `adapter.json` rows (checked by `adapter_registry_check.py:36`); `test_setup_secrets_repo_root.py:56` (no args, stdout only, no exit check); `test_tracker_registration.py:327-331` reads its source | no arguments; cwd in the target checkout; the `claude` session marker unset; `afk-python` entry; every abort exit 1, success 0; runs on import |
| `install-git-hooks.sh` | SessionStart `hooks.json:9`, `hooks.codex.json:9` via `run-hook.py --soft ... plugin install-git-hooks.sh --quiet` (:1029, :1035, :636); MANIFEST.md H5 Fix :113 (SKILL.md:116); tests `test_git_backstop.py:59-61`, `test_main_sync.py:71`, `test_protected_branch_acceptance.py:958`, `bench-hooks.py:212` (CI `tests.yml:105`) | `--quiet` as `$1`; exit 1 only on foreign hook without `--quiet`; `--soft` makes it always 0; a missing file returns 0 silently (`run-hook.py:1030-1032`) |
| stub it writes (name-free readers) | `precommit-gates.sh:50-53` (`gate="..."` line :93, marker `afk-branch-name-gate`, exec bit); H5 probe MANIFEST.md:112; `background_git_hooks.py:26,81` (MANIFEST.md:343); `test_git_backstop.py:298-316`; `test_background_git_hooks.py:64` | marker text and `gate=` grammar |

- Documents the code refutes: SKILL.md:124 "no tty" refusal (only the `claude` session marker, setup_secrets.py:147-148); MANIFEST.md C3 `--hostname` (script runs `auth login` with no host, :272); MANIFEST.md:968 says install-git-hooks.sh reads `AFK_PLUGIN_ROOT` (comment only, :13); CHANGELOG.md:479-480 (not load-bearing).
- Inference: design.round.json:510 "no Python importer" holds for production code only; moving the writer moves `test_install_block.py` and its `_target_lock` use.
- Inference: `claude` loads `hooks/hooks.json` by default discovery (`.claude-plugin/plugin.json` names no hooks file).
- `teardown` on a missing target exits 0 but creates the parent folder and a `.afk.lock` file (`install_block.py:148-160`).

## Sites

Full list per subject: claims c-68981be2, c-8f7b8052, c-5138281c, c-186a1331 in COVERAGE.json (574 terminal + 16 traced nodes).

## Frontier

- B14: harness hook loading and live sessions, other repositories, the gh/glab CLIs.

## Unverified

- Seed universe: the untracked ledgers `docs/afk/setup-per-repo/investigations/INV-005..022` were excluded (they pushed B1 past the 20000 ceiling); inferred to be recorded data, not callers. Not load-bearing.
- Seed claim c-52b8bc70 (hit set complete over searched forms): not load-bearing.

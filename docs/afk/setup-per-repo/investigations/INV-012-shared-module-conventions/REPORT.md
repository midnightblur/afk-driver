midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-012-shared-module-conventions/COVERAGE.json

## Answer

- No plugin module is an installed package (`runtime/pyproject.toml:22` `package = false`). Nothing sets `PYTHONPATH`; `hooks/plugin-source-gates.sh:229-235` unsets it. No cross-tree relative import. Relative imports stay inside `scripts/lavish/` and `skills/afk/mission-control/scripts/mc/`.
- Python to Python across trees: mostly `importlib.util.spec_from_file_location` by path, registered as `afk_<stem>`. Three cross-tree `sys.path.insert` + plain import sites: `scripts/afk-launch.py:26` (hooks/lib), `skills/afk/bug/scripts/publish_bug.py:54`, `skills/afk/to-ticket/scripts/publish_prd.py:65` (scripts/tracker_api). Two subprocess sites: `hooks/lib/h2_move.py:96` (afk-move.py), `skills/afk/review/scripts/forge_ledger.py:1143` (`afk-config.py effective`, JSON).
- No shared loader helper: five private ones (`run-hook.py:458`, `mcp-servers/tracker/server.py:54`, `protected-lookup.py:44`, `tracker_api.py:23`, `developer_values.py:34`). The rest write importlib inline. Only `server.py:57` and `tracker_api.py:26` register in `sys.modules`.

| Shared module | Loaded from |
|---|---|
| `scripts/afk-config.py` | `hooks/run-hook.py:664`, `mcp-servers/tracker/server.py:62`, `adapters/tracker/github-issues/api.py:70`, `skills/afk/setup/scripts/{developer_values.py:41,setup_secrets.py:51}`, `skills/utils/investigate/scripts/{contract.py:195,seed_map.py:277}`, `scripts/{tracker_api.py:32,protected-lookup.py:114}`; shell via `hooks/lib/config.sh`, `scripts/create-worktree` |
| `scripts/worktree_owner.py` | `hooks/lib/occupancy.py:26`, `hooks/lib/h2_move.py:28,41`, `hooks/run-hook.py:955`, `scripts/{afk-launch.py:37,remove-worktree.py:76}`, shell `create-worktree:348` |
| `hooks/run-hook.py` | `scripts/afk-launch.py:45`, `scripts/afk-move.py:96`, `skills/afk/setup/scripts/python_runtime.py:401` |
| `hooks/lib/protected_branch_guard.py` | `hooks/*.py`, `scripts/afk-launch.py:26`, `scripts/remove-worktree.py:450` |
| `adapters/tracker/jira/api.py` | `scripts/afk-config.py:949`, `developer_values.py:114`, kind dispatch `tracker_api.py:43`, `server.py:76` |
| `skills/afk/setup/scripts/tracker_registration.py` | `adapters/tracker/jira/api.py:48`, `setup_secrets.py:40` |

- Conventions: hyphenated stems load only by path; underscore stems both ways. `#!/usr/bin/env afk-python` plus a usage docstring on CLI modules; missing on `afk-config.py`, `run-hook.py`, `protected_branch_guard.py`, `h2_move.py`, `occupancy.py`. Stdlib-only except `jira/api.py:36` (`markdown_it`). Plugin root: `Path(__file__)` parents, or `AFK_PLUGIN_ROOT` then a fixed parent, or `AFK_PLUGIN_ROOT` then a marker walk (`contract.py:186`).
- Bash to Python: always `${AFK_PYTHON:-afk-python}`, inline or in a local variable. Exception: `bootstrap.sh:45-47` uses `uv run`. `hooks/lib/config.sh:29-31` evals `afk-config.py export-shell` once per process. `afk_config_get` runs `get` (:40). `afk_config_list` reads the export.
- Forge adapters: source config.sh, then `afk_config_load` (`github/forge.sh:25-26`, `gitlab/forge.sh:27-28`). Read `AFK_CFG_{GITHUB,GITLAB}_REMOTE`. Subprocess `adapters/forge/project_from_remote.py` (:139/:147). Inline `"$PY" -c` for JSON.
- `afk-config.py resolve` from code: only `scripts/create-worktree:188`. Skill prose: `skills/afk/bug/CONFIG.md:11`, `skills/afk/execute/SKILL.md:17`.
- Guard: reaches `scripts/` (`protected_branch_guard.py:269` protected-lookup.py, and from there `afk-config.py` load, `adapters/forge/{project_from_remote,branch_protection}.py`; `occupancy.py`/`h2_move.py` worktree_owner.py; detached `afk-move.py`). Never reaches `skills/`: the `afk-config.py` paths into skills sit under `scaffold()`, which only `init` reaches (:1167).
- Tests: CI runs `afk-python -m pytest scripts/tests -q`, `bash hooks/tests/hook-smoke.sh`, `bench-hooks.py` (`.github/workflows/tests.yml:64,67,105`). There is no conftest or pytest config. `scripts/tests` covers every tree, loading each module by path or after a `sys.path` insert. These run nowhere: skill smoke scripts under `skills/*/scripts/tests/`, `validate_plan_smoke.py`, the mission-control unittest package.
- Documents: one interpreter (`README.md:349-353`). One config reader (`CONFIG.md:7-13`). Provider helpers single-caller (`AGENTS.md:41-46`, gate K). No markdown outside docs/ states a cross-tree import rule. Drift: `AGENTS.md:44` omits the scripts/tests exemption in `PROVIDERS.md:130-131`.

## Sites
See the table above. Also: `hooks/lib/config.sh:17-57`; `hooks/lib/adapter.sh:17-144`; `adapters/forge/{github,gitlab}/forge.sh`; `hooks/native-contract-gate.sh:573-576`; `scripts/protected-lookup.py:44-226`; `scripts/afk-config.py:928-953,1204-1321`; `.mcp.json:7`.

## Frontier
- B14: other repositories, installed plugin copies, and live harness consumers. Not crossed.

## Unverified
- Not load-bearing: by-path loads that skip `sys.modules` likely give each caller its own copy. Modules no test names: `hook_failure.py`, `main_sync.py`, `adapters/tracker/payload.py`, `publish_prd.py`.

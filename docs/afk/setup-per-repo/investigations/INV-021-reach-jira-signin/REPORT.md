midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-021-reach-jira-signin/COVERAGE.json

## Answer

Neither function takes an argument. `resolve_creds_env` (`adapters/tracker/jira/api.py:110-127`) returns a dict of only the `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` fields it resolved, per field: exported variable, then the first `tracker` (or afk legacy `jira`) env block at any depth in `~/.claude.json`, then `~/.codex/config.toml`. It swallows read errors and never exits. `load_creds` (`:130-136`) exits through `sys.exit(<message>)` when fewer than 3 fields resolve, else returns `(base.rstrip("/"), email, token)`. The Jira site address is read today only as `JIRA_BASE_URL`: inside `resolve_creds_env`, and separately by `setup_secrets.py`. No config key holds it.

## Sites

- `load_creds` callers: `client()` `api.py:464` (only caller `_json` `:481`; every operation through `_DISPATCH` and `call()`; `call()` reached from `mcp-servers/tracker/server.py:101` behind 9 `@mcp.tool()` tools and from the CLI `api.py:664`); `--check-creds` `api.py:646-650`; `publish_prd.py:267`; `publish_meeting.py:128` (imports it from publish_prd, `:52`); `publish_bug.py:299` `_connect` (used `:317,:329,:339,:348`). Publishers bind it through `scripts/tracker_api.py` `load((... "load_creds" ...))` (`publish_prd.py:69`, `publish_bug.py:58`) and unpack the 3 values by position into `Jira(base, email, token)`.
- `resolve_creds_env` callers: `api.py:131`; `scripts/afk-config.py:955` `_jira_env_present` (reads `JIRA_BASE_URL` presence only, for the init hint; catches only `ImportError` `:953`; called from scaffold only when the tracker is none, `:1016-1020`); `skills/afk/setup/scripts/developer_values.py:116` (reads `JIRA_EMAIL` only, as the `trackerAssignee` suggestion; every Exception becomes None, `:117`).
- Exit behaviour: tool and CLI path — `SystemExit` passes `_json`'s `except Exception` (`api.py:484`) and `call()` turns it into an error answer (`:639-642`); the server stays alive and adds `config_root`. `--check-creds` and all 3 publishers — nothing catches it; process ends with exit 1 (publish_bug main catches only `BugPublishError`/`OSError`, `:393`). `publish_prd`/`publish_meeting` read credentials even with `--dry-run`; publish_bug dry runs return before `_connect`.
- Site address reads outside the two functions: `setup_secrets.py:185-208,296-305` takes defaults from the top-level `~/.claude.json` entry via `tracker_registration.prior_env` (`:52-56`), ignores exported variables, the `codex` file and project blocks, requires `https://`, checks `GET <base>/rest/api/3/myself` (`:224`), writes the 3 keys back. No code writes the `codex` env block. No Jira host is hard-coded.
- `jira.credentials-env`: validated (`afk-config.py:109,656-659`), never read for its value.
- Tests: direct `test_tracker_jira.py:130-265`; via the server `test_tracker_registration.py:134-221` (error prefix `could not resolve Jira creds` at `:143`); via init `test_afk_config_init.py:354-397,455-495`; `test_publish_bug.py:378-384` (dry run never calls `load_creds`). Load api.py but never reach the sign-in: `test_tracker_create_assignee.py`, `test_tracker_surface.py`, `test_tracker_server.py:260-267`.
- Unguarded: the 3 publisher call sites, `--check-creds`, `developer_values.jira_email` with tracker jira, the Jira branch of `setup_secrets.py`, the full exit message, `~/.claude.json` outranking the `codex` file.
- Documents the code refutes: `CONFIG.md:294`, `adapters/tracker/jira/CONTRACT.md:23-34` (`credentials-env` read; a harness credential store). `MANIFEST.md:737-742` omits the `developer_values.py:116` reader.
- Prior investigation records under `docs/afk/setup-per-repo/investigations/` (4369 hits) only quote the names: irrelevant.
- Inference: `.mcp.json`/`.mcp.codex.json` carry no env block, so the server sees only the user-scope entry setup writes or exported variables. Inference: agents reach `--check-creds` and `tracker_get` through skill prose (`MANIFEST.md:68,744`, `fix/SKILL.md:23`, `to-ticket/SKILL.md:14,96`).

## Frontier

- B14: live values in exported variables, `~/.claude.json`, `~/.codex/config.toml`; what the harness passes the tracker server; consumers outside this repository.

## Unverified

- Seed claim that the name set reaches every reference (not load-bearing): refuted by the counter-search, whose new sites (server-spawned tests, `setup_secrets` read) are in the ledger.

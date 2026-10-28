midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-016-seam-jira-signin/COVERAGE.json

## Answer

Proposed verdict: `reworked`. Existing callers see changed behaviour: a mixed-source sign-in that works today is refused, and the email that setup suggests as assignee no longer matches a repository on another site. The call shape holds if `load_creds()` keeps its name, takes no argument, returns `(base, email, token)` and exits with `SystemExit`. `api.py` reads no repository config, and `call(operation, payload)` receives none, so `load_creds` has to read `jira.site` itself on each call through afk-config `project_root()`. The github-issues adapter already does this.

## Sites

- `adapters/tracker/jira/api.py:107-136`: per-field fill over env, `~/.claude.json`, `~/.codex/config.toml`. One exit message, which names no source.
- `api.py:456-467` `client()` rebuilds when the 3-tuple changes, so a site change rebuilds the client. `:636-642` `call()` catches only `SystemExit`. Inference: a `ConfigError` from a config read inside `load_creds` would escape `call()` and `server._call`.
- `api.py:136,145`: the base has its trailing slash removed and is joined to relative paths. A `jira.site` value must arrive as scheme plus host. Every REST call, attachments included, follows the base. The media UUID host is fixed.
- `mcp-servers/tracker/server.py:54-77,101`: loads `afk_tracker_api_{kind}` by path and re-reads `tracker:` on every call. The tool arguments carry no site. `adapters/tracker/github-issues/api.py:66-74` is the per-call config precedent (test `test_tracker_server.py:140-158`).
- Unchanged callers of `load_creds`: `publish_prd.py:267`, `publish_meeting.py:128`, `publish_bug.py:299`, `main --check-creds` (`api.py:649`, no test).
- `resolve_creds_env` callers: `scripts/afk-config.py:945-955` (init hint; catches only `ImportError`) and `developer_values.py:114-117` (the legacy `JIRA_EMAIL` as assignee; swallows every error; ignores `--repo`). Both break.
- Config: `afk-config.py:109` `CHILD_KEYS['jira']` and `:633-636` refuse an unknown key with exit 2. Adding `site` requires `CONFIG.md:119` in the same commit (`test_afk_config.py:356-379`). Removing `credentials-env` without a warning channel turns `test_afk_config.py:119-122` red, because the sample at `monorepo-config.yaml:21-24` carries it. validate has no warning path today.
- `adapters/tracker/jira/adapter.json:25` goes stale silently: `adapter_registry_check.py:107-110` accepts any `jira.*` key.
- Env block: adding `JIRA_SITE_<KEY>_*` breaks neither the readers (`api.py:74-104`) nor the writer (`setup_secrets.py:193`, `tracker_registration.py:71-78`). `setup_secrets.py:199-239` asks for one base address and writes only the trio. Nothing writes the per-site names.
- Tests that go red: `test_tracker_jira.py:199-210` (field-wise mixing). Inference: the four init-hint tests `test_afk_config_init.py:354-360,376-383,455-464,478-487`, which supply a base-only source.
- Tests that hold only if the wording stays: `test_tracker_registration.py:143,156,160` pin the prefix `could not resolve Jira creds` in the no-source case.
- Unguarded: `jira.site`, `JIRA_SITE_`, the per-site key derivation, the partial-source error, the refusal to mix fields, `--check-creds`. The search returned 0 lines.
- Documents the design makes false: `CONFIG.md:119,294`, `adapters/tracker/jira/CONTRACT.md:23-32`, `PROVIDERS.md:176`, `skills/afk/setup/MANIFEST.md:90,749-750,941`, the `api.py:14-19` docstring. Inference: `CONFIG.md:56` and `server.py:16-19` go stale. `GLOSSARY.md:333` holds. `MANIFEST.md:977` is the the `claude` session marker row and not part of this seam.
- Same-commit rules: `FRESHNESS.md:13-15` (new env names, MANIFEST), `:40` (CHANGELOG), `:67` (setup_secrets env block, MANIFEST Fix rows), `:72` (PROVIDERS), `:86` (publishers). Inference: `:86` leaves out `publish_meeting.py` and `_jira_env_present`.
- Inference: the KEY rule maps `a-b.example.net` and `a.b.example.net` to one key, and the design does not say how that collision is handled.
- Inference: a team file setting `jira.site` fails validate until the plugin release that admits it lands, so the code ships first.

## Frontier

- B14: whether the harness passes the `claude` project-folder variable and the env block to the MCP server; consumers outside this repository.

## Unverified

- Seed name-form completeness (not load-bearing): refuted by the counter-search; the new sites are in the ledger.

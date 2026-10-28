midnightblur/afk-driver@17ec3223985388dab50ffdc5d04b1b1f27dc99ce · partial · boundaries 13/14 · unverified 2 (load-bearing 2) · ledger: docs/afk/setup-per-repo/investigations/INV-003-credential-resolution/COVERAGE.json

## Answer

Two repositories on one machine cannot use different Jira sites or accounts, or different accounts on one GitHub or GitLab host. Jira credentials resolve per machine. Forge credentials resolve per host through the gh or glab login. Only the protected-branch read chooses the host per repository. `jira.credentials-env` is validated but never read.

## Sites

- `adapters/tracker/jira/api.py:107-127`: fixed `CRED_KEYS`; process environment, then `~/.claude.json`, then `~/.codex/config.toml`; each field may come from a different source.
- `adapters/tracker/jira/api.py:74-87`: the first `tracker` env block in `~/.claude.json`, at any depth, wins. It is not keyed to the repository (test `scripts/tests/test_tracker_jira.py:238-243`).
- `adapters/tracker/jira/api.py:93,116`: fixed home paths. `CODEX_HOME` and `CLAUDE_CONFIG_DIR` are not read, so a separate harness config folder gives no second Jira account.
- No import alias: `api.py` loads by file path as `afk_jira_api` (`scripts/afk-config.py:949-955`), `afk_tracker_api` (`scripts/tracker_api.py:39-43`), `afk_tracker_api_jira` (`mcp-servers/tracker/server.py:71-76`), and in `developer_values.py:114-116`.
- `scripts/afk-config.py:109,656-659,1033-1036`, `adapters/tracker/jira/adapter.json:25`: `jira.credentials-env` is declared, type-checked and scaffolded. No code reads its value.
- `skills/afk/setup/scripts/setup_secrets.py:185-253`: writes one user-scope `mcpServers.tracker.env`; a second repository overwrites it. `:258-279` runs `auth login` with no host.
- `skills/afk/setup/scripts/developer_values.py:111-117`: the assignee suggestion comes from the machine-wide `JIRA_EMAIL`.
- `.mcp.json:7`, `.mcp.codex.json:7`: the plugin registrations carry no env block, so the tracker server inherits the harness environment.
- `adapters/forge/github/forge.sh:15`, `adapters/forge/gitlab/forge.sh:16`, `adapters/forge/project_from_remote.py:20-33`: CLI login. The host is dropped from `<kind>.remote` before `--repo`/`-R`. No `--hostname`.
- `adapters/forge/github/forge.sh:365-371`, `gitlab/forge.sh:378-384`, `skills/afk/review/scripts/forge_ledger.py:829-834,1793-1800,2169-2178`: identity is the CLI's active login (`api user`, no host flag).
- `adapters/forge/branch_protection.py:160-174`: the protection read takes the host from the repository's remote and passes `--hostname` only for a host the CLI is logged in to. An SSH alias that resolves to github.com uses the one github.com login (test `scripts/tests/test_protected_lookup.py:761-764`).
- The protection read has four entry points, each reading `GH_TOKEN`/`GITHUB_TOKEN`/`GITLAB_TOKEN` from its own process: `hooks/hooks.json:73`, `hooks/git-backstop.py:33-36,71-81`, `scripts/afk-launch.py:32`.
- `adapters/tracker/github-issues/api.py:77-79,147`: `--repo` from `github-issues.repo`, else `GH_REPO`, with the inherited CLI login.
- Untested hops: `<kind>.remote` to `--repo`/`-R`, `auth-status`, `forge_user`, the setup login step, the payload `repo` override.
- Documents the code contradicts: `CONFIG.md:294`, `adapters/tracker/jira/CONTRACT.md:23-31`, `CHANGELOG.md:593`, `mcp-servers/tracker/server.py:16-19`.
- Inference: on a non-default host with `<kind>.remote` set, forge verbs likely reach the CLI's default host, not the checkout's host.

## Frontier

- B14 (outside this repository): gh/glab host and account choice, git credential helpers, how the harness passes the environment to MCP servers. 12 nodes.

## Unverified

- Harness (load-bearing): the harness must pass a tracker registration's env block into the server process and pick one `tracker` entry when plugin, user and project scope each define one. The repository only writes the user-scope entry and ships registrations with no env, so the code cannot show which env the server receives.
- gh/glab (load-bearing): the CLIs must pick the host, and so the login, for a host-less `--repo`/`-R owner/name`, a plain `gh api` or `glab api` call and an unflagged `auth status`, and decide whether a host-prefixed `github-issues.repo` reaches another host. The repository passes no host on these calls, so the code cannot show which host or account is used.

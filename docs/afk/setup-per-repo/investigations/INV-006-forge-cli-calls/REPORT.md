midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 11/14 · unverified 2 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-006-forge-cli-calls/COVERAGE.json

## Answer

No plugin code sets or removes GH_TOKEN, GITHUB_TOKEN, GH_HOST, GITLAB_TOKEN, GITLAB_HOST, GH_CONFIG_DIR or GLAB_CONFIG_DIR before it starts gh or glab. Each call passes on the caller's whole environment. Only `adapters/forge/branch_protection.py` gives a host (`--hostname`), and only for a host it finds in the CLI's own login file. Every other call relies on the CLI default host and the stored login. Where code sends `--repo`/`-R`, the value is `OWNER/NAME` with the host removed.

## Sites

| Site · function | CLI / verb | Host | Account |
|---|---|---|---|
| `adapters/forge/github/forge.sh:88` `gh()`, `gitlab/forge.sh:95` `glab()` (verb `case` at :279 / :276) | `gh pr`, `gh api`, `glab mr`, `glab api`; `auth-status` = `auth status` + `api user` (github :366-367, gitlab :379-380) | `--repo`/`-R` only from the payload `repo` or `github.remote`/`gitlab.remote` through `project_from_remote.py:20-33`, which drops the host (github :131-144, gitlab :139-156). `api` calls take neither flag | stored login (comment at github :15, gitlab :16); environment inherited |
| `hooks/lib/adapter.sh:112` `afk_adapter` ← `skills/afk/review/scripts/forge_ledger.py:760` `Adapter.call` (env copy :750; `AFK_LEDGER_ADAPTER_CMD` override :749), `skills/afk/gc/scripts/gc-check.sh:136` | forge verbs | none; the payload never carries `repo` | `auth-status` user trusted at `forge_ledger.py:829-834, 1793-1800, 2169-2178` |
| `adapters/forge/branch_protection.py:212` `_github`, `:279` `_gitlab`, `:183` `_login_token` ← `scripts/protected-lookup.py:226` ← `hooks/lib/protected_branch_guard.py:299` (PreToolUse, `git-backstop.py:35`, `scripts/afk-launch.py:32`) | `gh api`, `glab api --paginate`, `gh auth token --hostname github.com` | host from the remote URL (`protected-lookup.py:129`); `--hostname` only when the host is listed in hosts.yml/config.yml under GH_CONFIG_DIR/GLAB_CONFIG_DIR and similar folders (`:131-174`); public host gets no flag | GH_TOKEN, then GITHUB_TOKEN, or GITLAB_TOKEN over HTTPS (`:189`, `:260`); else the github.com login token; else the CLI |
| `adapters/tracker/github-issues/api.py:91` `_gh` ← `mcp-servers/tracker/server.py:101` | `gh issue …` (:168-332), `gh api …/timeline` (:239) | `--repo` = `github-issues.repo`, else GH_REPO (`:77-79`, `:147`); no `--hostname` | stored login; environment inherited (`.mcp.json` has no env block) |
| `skills/afk/setup/scripts/setup_secrets.py:268,272` | `<cli> auth status`, `<cli> auth login` (`FORGE_CLI` at :260) | no `--hostname` | the login the human makes |
| `skills/afk/setup/scripts/developer_values.py:96` `forge_user` | `gh api user`, `glab api user` | none | stored login |
| `skills/utils/report-issue/scripts/publish.sh:206-287` | `gh auth status`, `gh issue`, `gh label` | `-R OWNER/NAME`; github.com is removed at :133 | stored login |
| `.github/workflows/release.yml:71-81` | `gh release view/create` | checkout remote | `GH_TOKEN: ${{ github.token }}` |
| `skills/utils/report-issue/scripts/collect_env.sh:41` | `gh --version` | — | — |
| Prose: `skills/afk/setup/MANIFEST.md:417,420-421,435,440` | `glab auth status`, `glab auth login --hostname <host>`, `gh auth status`, `gh auth login` | `--hostname` only at :420-421 | login |
| Prose that runs the wrapper (execute, preflight, settle-change, SETTLEMENT, FIXER-PROMPT, understand) | `afk_adapter forge`, `forge_ledger.py` | none | via forge.sh |

Where documents and code disagree: `MANIFEST.md:420-423` says setup runs `glab auth login --hostname`, but `setup_secrets.py:272` passes no host. `ADAPTERS.md:100` says every call has a timeout, but it applies only where GNU `timeout` exists (`github/forge.sh:87`).

Tests: only `branch_protection.py` has tests for its host and account choice (`scripts/tests/test_protected_lookup.py:654-769`). The `-R` and host choices in forge.sh, publish.sh and github-issues have no tests. `scripts/tests/test_setup_developer_values.py:71-149` runs the real gh or glab with the developer's login (inferred).

## Frontier

- Handlers that a consuming repository declares in `.afk/hooks.json` and that run through `hooks/run-hook.py:193-197`, `hooks/precommit-gates.sh:185` and `scripts/create-worktree:513`: their commands are outside this repository.
- The value of `AFK_LEDGER_ADAPTER_CMD` and the configured worktree command.
- `hooks/lib/adapter.sh:111`: the entry is named in `adapter.json`; the `:112` run is traced.
- B14: other repositories and live consumers.

## Unverified

- unverified: how gh and glab pick a host and a token when no `--hostname` is given (GH_HOST/GITLAB_HOST, then the default host; an environment token over the stored login). Neither CLI's documentation was read.
- unverified: what `auth status` checks when no host is given.

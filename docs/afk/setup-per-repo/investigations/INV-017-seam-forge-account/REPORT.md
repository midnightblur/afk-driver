midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-017-seam-forge-account/COVERAGE.json

## Answer

| Seam | Existing contract | Impacted flows, landmines | Proposed verdict |
|---|---|---|---|
| Account helper (new, `scripts/`) | `project_from_remote.project()` returns owner/name only, never a host (`adapters/forge/project_from_remote.py:20-33`). A host is derived only in `protected-lookup.py:119-141` and `branch_protection.py:160-174` (SSH alias through `ssh -G`). `forgeAccount` is not in `DEVELOPER_KEYS` (`afk-config.py:73`, `:126`) | Unknown key today: `validate` fails (`afk-config.py:626-637`), `resolve` exits 2 (`:1309`), `developer_values.py set` refuses (`:197`), `publish.sh:121` queues `config-invalid`. `load()` merges home, repo, personal, local and `AFK_CONFIG` (`afk-config.py:363-398`), so the helper must read `shared_overlay()` (`:342-360`) alone. Key-list tests: `test_afk_config.py:357`, `test_setup_developer_values.py:167` | extends; the host source must change and the key must be registered |
| (a) `gh()` `github/forge.sh:88` | Time limit only; inherited environment; every gh call goes through the function | With an account set, `auth-status` (`:366-367`) answers the account. The review ledger trusts that user (`forge_ledger.py:829-835`, `:1793-1800`, `:2169-2182`). An open change carrying markers from the old login stops with `unclassified_authors` (`:843`) until `--trust`. `identity.json` has no account in its key (`:2085-2104`). The token fetch must call the binary (the function would recurse), run under `_forge_limit`, and fail closed (`:77-82`). `GH_TOKEN` does not serve a GitHub Enterprise Server host (`GH_ENTERPRISE_TOKEN`). With `github.remote` unset, gh picks the project and the helper picks the host (`:131-144`). Stubs answer `auth token` with `{}` (`test_forge_adapters.py:103-116`) | reworked when an account is set |
| (b) `glab()` `gitlab/forge.sh:95` | Same wrapper; `-R owner/name` without a host (`:139-156`) | `GITLAB_HOST` chooses only the host; the account part cannot choose a glab login (inferred). Effect on `-R`, `projects/:id` (`:225`) and `auth status` (`:379`) is unverified | extends |
| (c) `branch_protection.py` | `gh auth token --hostname github.com` without `--user` (`:183`); test pins the argv (`test_protected_lookup.py:654`); runs inside the guard deadline (`protected-lookup.py:201-232`) | Add `--user` to the one token spawn (`:190`) and reuse `_configured()`. Keep the public-API-only token (`:177-182`), the 0.3 s budget, and the `_hostname` None refusal (`:160-174`). A 401/403 answer falls back to the active login (`:203-204`); an inherited `GH_TOKEN` wins (`:189`) | reworked (test-pinned argv) |
| (c) `github-issues/api.py` `_gh:91` | No environment; identity "whatever gh auth login established" (`CONTRACT.md:31`, `:5`) | Tracker writes change identity. Tests patch `subprocess.run` (`test_tracker_server.py:225-238`, `test_tracker_surface.py:88-112`) | reworked |
| (c) `developer_values.py` `forge_user:89` | Default login, 30 s, no host; suggests `mrAssignee`/`trackerAssignee` (`:153-157`); unguarded | Suggestion becomes the account (AC-032). Adding the key to `ORDER` without `need`/`suggest` raises KeyError (`:146-169`) | reworked |
| (c) `setup_secrets.py:268-272`, `MANIFEST.md:417-440` | `auth status`/`auth login` without host or account; `MANIFEST.md:420` claims `--hostname`, which the code does not pass | Probes pass for any login | reworked |
| (c) `report-issue/publish.sh:206-287` | Default login, `-R` with no host | Unsets neither `GH_HOST` nor `GH_TOKEN`. Unchanged while wrappers set them per call and never export them | fits |
| (d) Setup account check | No check exists. `AFK_FORGE_TIMEOUT` (60) applies per call inside forge.sh only | Through `auth-status`: 2 calls plus 2 token fetches, each up to 60 s, against a 20 s cap, so run it outside forge.sh (inferred) | extends |

Same commit: `MANIFEST.md` rows for `GH_HOST`, `GH_TOKEN`, `GITLAB_HOST` (only `:1002` names `GH_TOKEN`); `CONFIG.md:136`; `ADAPTERS.md:87-101`; `github/CONTRACT.md:27-28`; `github/forge.sh:15`; `hooks/README.md:109`. Comment gate: 2 lines (`comment_gate.py:22`). The `auth-status` shape stays, so the review-ledger lockstep is not triggered; its meaning changes.

## Frontier

- B14: the CLIs' own behaviour, outside this repository: `gh auth token --user` by version; GH_HOST with `--repo owner/name` (`github/forge.sh:144`, `:425`); GH_TOKEN against GH_ENTERPRISE_TOKEN; glab GITLAB_HOST with `-R` (`gitlab/forge.sh:156`), `projects/:id` (`:225`) and `auth status` (`:379-381`). Five nodes are frontier, each marked `breaks` because the change reaches it. Only local help text was read (gh 2.92.0, glab 1.89.0).
- B14: live forges, consuming repositories, CI.

## Unverified

- None load-bearing. Inherited GH_TOKEN precedence is decided in this repository: `branch_protection.py:189` prefers the inherited token. A per-call assignment in forge.sh would replace it for that call (inferred from shell semantics).
- B1 name-form slots for private names are recorded not applicable, each with its reason in `run.aliases`.

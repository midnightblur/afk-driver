midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-022-review-ledger-login/COVERAGE.json

## Answer

Every reference is in `skills/afk/review/scripts/forge_ledger.py` unless a path is given.

- **Trusted set:** the `--trust` values plus the live login from the forge verb `auth-status` (`user`, else `username`, else `login`: `:790-793`). Each call rebuilds it: `reconstruct_state` `:829-835`, `_trusted_set` `:1793-1800`, `RationaleReader._identity` `:2169-2183`. `--reject` authors are dropped; an author in both lists exits 3 (`:597-600`). The flags exist on 9 subcommands (`:2394-2411`). The `afk:settle:trust` marker is written (`:1454-1457`) and never read back.
- **Review commands** (`reconstruct`, `post`, `reply`, `resolve`, `summary`, `gate`): an unedited marker note by an author in neither list, or an edited marker, raises `unclassified_authors` or `edited_markers` and exits 2 before any write (`:611-637`, `:843-844`, `:2449-2451`).
- **Rationale scope:** `rationale-post` and `rationale-verify` count only trusted, unedited notes; other authors go to `excluded.untrusted` (`:1660-1662`, `:1921`, `:2005`). `rationale-read` counts every author except rejected ones and labels each self, trusted or other (`:1642-1678`, `:2248-2257`).
- **Cached identity `identity.json`:** base `AFK_RATIONALE_CACHE`, else `XDG_CACHE_HOME`, else `~/.cache`; key = hash of git dir, `AFK_CFG_FORGE`, origin URL, no account (`:2085-2102`). Only `rationale-read` writes it, after a live non-empty login (`:2175`). It is read only on `--offline` or a failed live call, and the answer is then `unverified` (`:2178-2181`). Review commands never read it.
- **Login path:** `AFK_LEDGER_ADAPTER_CMD` test seam (`:749-753`), else `hooks/lib/adapter.sh:32,37,108` runs `forge.sh auth-status`: github `gh auth status` + `gh api user --jq .login` (`adapters/forge/github/forge.sh:365-368`); gitlab `glab auth status` + `glab api user` (`adapters/forge/gitlab/forge.sh:378-381`); `none` exits 3. Call limit `AFK_LEDGER_ADAPTER_TIMEOUT` 120 s (`:755-771`).
- **Failure paths:** no code reads `authenticated`; `{authenticated:false}` gives an empty login, so only `--trust` authors stay trusted. Neither adapter checks the exit status of `api user`. On GitHub a failing call writes the HTTP error body to stdout (probe, gh 2.92.0), so parsing raises `adapter wrote extra stdout` (`:691-694`): review commands exit 2, rationale-post/verify block, rationale-read uses the cache.
- **`forge_user` does not reach trust:** `skills/afk/setup/scripts/developer_values.py:89` only suggests `mrAssignee`/`trackerAssignee` (`:155`, `:157`); its one alias `dv` is test-only (`scripts/tests/test_setup_developer_values.py:16`). `setup_secrets.py:268-273`, `report-issue/publish.sh:206`, `branch_protection.py:183` do not reach it either.

## Sites

- Callers (markdown instructions only; no hook, workflow or agent runs the script; CI runs it only through pytest, `.github/workflows/tests.yml:64`): `/afk:execute` `SKILL.md:53,61,63,73,106`; `/afk:preflight` `SKILL.md:88,96,108,161`; `/afk:settle-change` `SKILL.md:34,55,98`; `skills/afk/review/SETTLEMENT.md:17,19`; `RATIONALE.md:46`; rationale-read in `/afk:fix:36`, `/afk:diagnose:91`, `/afk:review:198`, `INVESTIGATION.md:47`. No caller passes a concrete `--trust` value; `SETTLEMENT.md:19` asks for the logged-in user, which the code already adds.
- Tests: `scripts/tests/test_forge_ledger.py:61-62,378,429,1041,1172,267`; `test_rationale_ledger.py:347,480,811,816,828,848,895,909`; `test_forge_adapters.py:164,941`. Unguarded: `username`/`login` fallbacks, empty login, `auth-status` failure on review and rationale-post/verify, rejected-author branch, trust marker, command-line `--trust`/`--reject`, `--no-cache`, the adapters' `auth-status` shell path.
- Documents the code refutes (design targets, not built): `docs/afk/setup-per-repo/GRILL-LOG.md:159`, `adr/design/0003-forge-account-per-call.md:14`, `design.round.json:924,933` say the ledger trusts every account on the host and keys the cache by account. `design.round.json:765` and `INV-017 REPORT.md:17` are likely stale (inferred).
- Findings: `classify_author` (`:603`) has no caller outside tests. Inferred: a null note author (github `forge.sh:620`, gitlab `:665`) raises an uncaught TypeError; trust match is case-sensitive (`:604`, `:2255`); `/afk:settle-change:17` names no verb for its own user lookup.

## Frontier

- B14: gh/glab session store and forge server answers (which login `api user` returns); live notes on changes; other repositories.

## Unverified

- Whether gh can list every account on one host (the design's trust-every-account rule depends on it): outside this repository.
- Whether GitHub ever sends a null review-comment author, and whether `gh auth status` passes while `gh api user` fails in practice: CLI and server behaviour.

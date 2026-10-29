midnightblur/afk-driver@251484b5e25af332054e10df9181ead8859cbff3 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-027-forge-account-at-head/COVERAGE.json

## Answer
- Shell adapters: every gh call goes through `gh()` (adapters/forge/github/forge.sh:88-90) and every glab call through `glab()` (adapters/forge/gitlab/forge.sh:95-97). Only the wrapper bodies (:89, :96) run the binary, so the per-call account environment fits in one place in each file.
- These break or must change:
  - auth-status checks any signed-in account, then `api user` (github forge.sh:386-393, gitlab :378-385). Nothing tests it.
  - branch_protection.py `_run` (:59-78) passes no env; the CLI token fetch (:183) has no `--user`; an inherited GH_TOKEN wins (:189). test_protected_lookup.py:654 pins the argv `auth token --hostname github.com`.
  - github-issues/api.py `_gh` (:91-113) calls `subprocess.run` (:101) with no env and no host.
  - developer_values.py forge_user (:90-109) suggests assignees from the default login.
- forge_ledger.py trusts one login, read from the auth-status `user` field at :831, :1804 and :2217. The identity cache key (:2144) holds no account.
- A non-zero auth-status raises LedgerError (:770-771):
  - reconstruct, post, reply, resolve, summary and gate exit 2;
  - rationale-post and rationale-verify are blocked and exit 2;
  - rationale-read falls back to the cache.
- Contracts that break:
  - ADAPTERS.md:112 says ci-wait is the only verb with an exit-code contract;
  - skills/afk/understand/SKILL.md:87 handles only `authenticated:false` or `unavailable`;
  - the forge.sh:15 header text no longer holds.
- At HEAD no code reads GH_ENTERPRISE_TOKEN or AFK_CFG_DEVELOPER_FORGEACCOUNT (tracer query q-f4581b87).

## Sites (full list in COVERAGE.json)
- forge_ledger trusted set: :829-835, :1801-1808, :2196-2225. Callers: :1925, :2042.
- auth-status consumers:
  - code: forge_ledger.py :830, :1803, :2216;
  - skill: understand SKILL.md:87;
  - tests: test_forge_ledger.py:61, :672; test_rationale_ledger.py:78-80, :635, :875.
- Dynamic loads:
  - protected-lookup.py:140 and :226;
  - the guard: protected_branch_guard.py:313 and :342;
  - tracker_api.py:43.

## Frontier
- B14 (gh 2.92.0 and glab 1.89.0, read from --help only):
  - whether `gh auth token --user` returns a token for an account that is not active;
  - whether GH_HOST overrides the host gh reads from the git remote of the clone;
  - the order in which glab weighs GITLAB_HOST against the git remote.

## Unverified
- Inferred from code, not run:
  - the github-issues tracker host can differ from the forge remote host;
  - test_existing_worktree_outside_root.py:788 breaks only if the account becomes a cache subfolder;
  - the auth-status fakes in the tests stay valid only if the ledger keeps the `user` field.

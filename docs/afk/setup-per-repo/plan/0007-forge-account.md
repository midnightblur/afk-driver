# 0007-forge-account — every forge call acts as the repository's forge account

## Goal
Add the forge account helper (host and account name for a repository, never a token) and make every forge call use it: the GitHub wrapper fetches that account's token right before each call and passes it in the variable gh documents for the host kind; the GitLab wrapper sets the host; the `auth-status` verb of both forge adapters fails with `account not available` and never falls back to the default login; branch protection and the GitHub Issues tracker use the account; the review ledger trusts every account the forge tool holds on the host plus `--trust` and keys its cache by account. Add setup's forge account check script, which saves nothing unless the host accepts the account. The plugin-issue reporter keeps the default login.

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "forge account helper (new)"
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — row "Δ forge sign-in check (`auth-status` verb of both forge adapters)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "gh token per account", "gh host and token variables", "glab host", "glab accounts per host"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ rows "save a forge account or an assignee" and "Δ trust a comment author in the review ledger"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "forge wrappers …" and "review ledger `forge_ledger` …"
- ADR: adr/design/0003-forge-account-per-call.md — forge account chosen per call

## Scope
- scripts/forge_account.py
- adapters/forge/github/forge.sh
- adapters/forge/gitlab/forge.sh
- adapters/forge/github/CONTRACT.md
- adapters/forge/gitlab/CONTRACT.md
- adapters/forge/branch_protection.py
- adapters/forge/project_from_remote.py
- adapters/tracker/github-issues/api.py
- skills/afk/review/scripts/forge_ledger.py
- skills/afk/review/SETTLEMENT.md
- skills/afk/setup/scripts/developer_values.py
- skills/afk/setup/scripts/forge_account_check.py
- scripts/tests/test_forge_account*.py
- scripts/tests/test_forge_ledger.py

## Seams
- implement: forge wrappers `_gh`, `forge_user`, `project_from_remote`, `auth-status`, branch protection, GitHub Issues tracker; `GH_TOKEN` per call — §9b "gh token per account": `gh auth token --hostname <h> --user <a>` per call (INV-017)
- implement: forge wrappers `_gh`, `forge_user`, `project_from_remote`, `auth-status`, branch protection, GitHub Issues tracker; `GH_TOKEN` per call — §9b "gh host and token variables": `GH_TOKEN` for `github.com`/`ghe.com`, `GH_ENTERPRISE_TOKEN` for an Enterprise Server host (INV-017)
- implement: forge wrappers `_gh`, `forge_user`, `project_from_remote`, `auth-status`, branch protection, GitHub Issues tracker; `GH_TOKEN` per call — §9b "glab host" and "glab accounts per host": `GITLAB_HOST` per call, account check by `glab api --hostname <h> user` (INV-017)
- implement: review ledger `forge_ledger` trusted `forge_user` login and cache — trusted set and cache keyed by account (INV-022)

## Acceptance
- [ ] The forge account helper returns the host (from the forge remote through the guard's host lookup) and the account name (`developer.forgeAccount`) for a repository, never a token (SDD §8 row "forge account helper (new)"; ADR-0003)
- [ ] With an account set, every GitHub wrapper call fetches that account's token with `gh auth token --hostname <host> --user <account>` right before the call and passes it only to that call, in `GH_TOKEN` for a `github.com` or `ghe.com` host and in `GH_ENTERPRISE_TOKEN` for an Enterprise Server host (SDD §9b rows "gh token per account", "gh host and token variables"; PRD §Accounts AC-033)
- [ ] The GitLab wrapper sets `GITLAB_HOST` per call (SDD §9b row "glab host")
- [ ] With an account set and its token not available, `auth-status` of both forge adapters prints `account not available`, exits non-zero, and no call falls back to the default login; with no account set, behaviour is unchanged (SDD §3 row "Δ forge sign-in check (`auth-status` verb of both forge adapters)")
- [ ] Branch protection passes the account and keys its cache by it; the GitHub Issues tracker acts as the account (SDD §14 row "forge wrappers …")
- [ ] The plugin-issue reporter keeps the default login (ADR-0003)
- [ ] The review ledger trusts a comment author who is any account the forge tool holds on the host, plus `--trust`; its cache and rationale scope include the account; a failing login lookup makes the review commands exit 2, with a test (SDD §5 row "Δ trust a comment author in the review ledger"; SDD §14 row "review ledger `forge_ledger` …")
- [ ] The setup forge account check asks the host who the account is (gh: `gh api user` with that account's token; glab: `glab api --hostname <host> user`), one try with a 20000 ms timeout; it saves the account only when the host accepts it; a refused or unreachable host saves nothing and names the cause; a glab login that differs from the account is refused, naming the signed-in account (PRD §Accounts AC-030, AC-031; SDD §5 row "save a forge account or an assignee"; SDD §9b row "glab accounts per host")
- [ ] When the repository's push sign-in or commit email does not match its forge account, the check warns and names both values (PRD §Accounts AC-034)
- [ ] With one remote, `github.remote`/`gitlab.remote` stays empty and the wrappers still derive the correct project from that remote (PRD §Setting owners AC-026)
- [ ] An unset or `none` change assignee opens the change with no assignee; the change assignee, reviewer and work item assignee come from the repository's own settings (PRD §Accounts AC-033)
- [ ] No token is ever printed, logged or written to a file (SDD §5 Secrets)
- [ ] Implements the public interface in SDD §8 row "forge account helper (new)" unmodified (SDD §8)
- [ ] Conforms to ADR-0003 — no silent pattern substitution: one adapter per forge kind sharing the one account helper (ADR-0003)

## Produces
- scripts/forge_account.py#def host_and_account( — the host and account name for a repository; never a token
- adapters/forge/github/forge.sh#GH_ENTERPRISE_TOKEN — the token variable for an Enterprise Server host
- adapters/forge/github/forge.sh#account not available — the sign-in check failure with an account set
- skills/afk/setup/scripts/forge_account_check.py#def check_forge_account( — host accepts the account, or the cause; saves nothing on refusal

## Consumes
- 0002-settings-reader scripts/afk-config.py#OWNER_TABLE = — `developer.forgeAccount` as a personal key

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | seam test: a stub `gh` on PATH holding two accounts on one host, the default differing from the repository's account; run each GitHub verb, branch protection and the GitHub Issues adapter; assert the stub received `auth token --hostname <h> --user <account>` and the call's environment carried that token in `GH_TOKEN` (github.com host) and `GH_ENTERPRISE_TOKEN` (Enterprise Server host) | the real gh invocation per account and host kind |
| unit | seam test: a stub `glab`; assert `GITLAB_HOST` per call and that the account check runs `glab api --hostname <h> user` and refuses a differing login | the real glab invocation |
| unit | `auth-status` with the account's token missing: `account not available`, non-zero, the stub sees no default-login call; unset account unchanged | the sign-in check contract |
| unit | `scripts/tests/test_forge_ledger.py`: trusted set holds every account on the host plus `--trust`; cache keyed by account; failing login lookup exits 2 | review ledger trust |
| unit | account check: accepted, refused, unreachable (timeout), push sign-in / commit email mismatch warning; nothing saved on failure | setup forge account check |
| smoke | `smoke` tier | hooks end to end |

## Context excerpts
> (ADR-0003) A forge account helper returns the host and account name for a repository, never a token. The host comes from the forge remote through the guard's existing host lookup. Each forge wrapper fetches the token itself right before a GitHub call and passes it, with the host, to that one call in the variable gh documents for the host kind. The GitLab wrapper sets the host only; setup's account check refuses a glab login that differs from the account. Branch protection and the GitHub Issues tracker use the account. With an account set, the sign-in check fails with `account not available` and never falls back to the default login. The review ledger trusts every account the forge tool holds on the host, plus `--trust`, and keys its cache by the account. The plugin-issue reporter keeps the default login.

> (SDD §8 row "forge account helper (new)") host and account per repository | host and account name for a repository; never a token | settings reader, the guard's host lookup | personal settings

> (SDD §3 row "Δ forge sign-in check (`auth-status` verb of both forge adapters)") setup, adapters | the repository's forge account when set | exit 0 when that account's token is available | `account not available`, non-zero; never falls back to the default login | new failure shape when an account is set; unset: unchanged

> (SDD §9b) gh token per account | gh 2.92.0, installed tool, not a pinned dependency | `gh auth token --hostname <h> --user <a>` prints that account's token ("The account to output the token for", `gh auth token --help`) | non-zero exit → `account not available` | forge wrapper test with a stub gh holding two accounts on one host, the default differing from the account
> gh host and token variables | gh 2.92.0 | `GH_TOKEN` applies to `github.com` and `ghe.com` hosts; a GitHub Enterprise Server host reads `GH_ENTERPRISE_TOKEN` (`gh help environment`); the wrapper passes the token in the variable gh documents for the host kind | wrong variable → call acts as the stored login | wrapper test asserting the variable set for a `github.com` host and for an Enterprise Server host
> glab host | glab 1.89.0, installed tool | `GITLAB_HOST` selects the host (docs.gitlab.com/cli); `glab auth status` ignores it (gitlab-org/cli issue 8065), so the account check calls `glab api --hostname <h> user` | login differs → setup saves nothing, names the signed-in account | setup account check test with a stub glab
> glab accounts per host | glab 1.89.0 | one account per host (unverified-external, acknowledged in the requirements grill) | mismatch refused at setup | as above

> (SDD §14 row "forge wrappers …") every gh or glab call uses the default login; branch protection caches without an account (INV-006, INV-008, INV-017) | per-call host and account; `account not available` when its token is missing; branch protection passes the account and keys its cache by it | every forge verb; branch-protection lookup; GitHub Issues adapter (INV-006, INV-017) | the plugin-issue reporter keeps the default login; the host comes from the remote the wrapper already uses | reworked (ADR-0003)

> (SDD §14 row "review ledger `forge_ledger` …") trusts only the current login; cache key has no account (INV-017, INV-022) | trusts every account the forge tool holds on the host, plus `--trust`; cache and rationale scope include the account | changes already in review (INV-017, INV-022) | a failing login lookup on GitHub fails every ledger command, review commands exit 2, with no test today; add one with the account check (INV-022) | reworked (ADR-0003)

> (SDD §5 AuthZ) save a forge account or an assignee | developer; an agent recording the answer | an agent on its own initiative; teammate | setup asks, then checks with the host | saved only after the host accepts it
> Δ trust a comment author in the review ledger | every account the forge tool holds on that host, plus `--trust` | any other author | — | review ledger trusted set

> (SDD §5 Retry + timeout) setup account check (forge host or Jira site) | 1 | — | 20000

> (PRD §Accounts) AC-030 Setup saves a forge account for a repository only when the forge host accepts it. A refused or unreachable host saves nothing, names the cause and leaves the other repositories to continue (unverified premise: gh can hold several accounts per host and select one per command; glab holds one account per host). AC-031 Recovery after AC-030: a later setup run for that repository alone saves the account once the host accepts it. AC-033 Agents in a repository act as that repository's forge account, and set its change assignee, reviewer and work item assignee. An unset or `none` change assignee opens the change with no assignee. AC-034 When the repository's push sign-in or commit email does not match its forge account, setup warns and names both values.

> (PRD §Setting owners) AC-026 The forge remote is asked only when the clone has more than 1 remote. With 1 remote it stays empty, and agents still open changes on the correct project.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0002-settings-reader

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

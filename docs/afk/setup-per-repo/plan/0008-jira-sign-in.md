# 0008-jira-sign-in — one Jira sign-in per site, written only from the developer's terminal

## Goal
Make the Jira sign-in load take the first complete sign-in for the repository's `jira.site` (existing three names for their own site; `JIRA_SITE_<KEY>_EMAIL` / `JIRA_SITE_<KEY>_API_TOKEN` for further sites), skipping and naming a partial source, with the same function names and the same three values. Rework the secret step into subcommands `jira --site <address>`, `forge --host <host> --account <name>` and `longpaths`, refused without a terminal on input and output or inside an agent session, writing through the safe writer with a fresh read under the lock, owner-only access and one backup. Add setup's Jira account check against the site.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — rows "`setup_secrets.py jira --site <address>`, `forge --host <host> --account <name>`, `longpaths`" and "tracker server tools"
- SDD: SDD.md#§4 L3 — Data Architecture — "Jira sign-ins (harness settings block)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "harness settings file" and "Jira REST"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "secret step `setup_secrets`" and "Jira sign-in load `load_creds`, `resolve_creds_env`"
- ADR: adr/design/0004-jira-sign-in-per-site.md — one sign-in per site, per-site names
- ADR: adr/design/0005-shared-safe-writer.md — the secret step writes through the safe writer

## Scope
- adapters/tracker/jira/api.py
- adapters/tracker/jira/CONTRACT.md
- skills/afk/setup/scripts/setup_secrets.py
- skills/afk/setup/scripts/tracker_registration.py
- skills/afk/setup/scripts/jira_account_check.py
- scripts/tests/test_jira_sign_in*.py
- scripts/tests/test_setup_secrets*.py

## Seams
- implement: Jira sign-in load `load_creds`, `resolve_creds_env` — first complete sign-in for `jira.site`; §9b "Jira REST" account check (INV-016)
- implement: secret step `setup_secrets` — subcommands, terminal and agent-session refusal; §9b "harness settings file": fresh read under the lock (INV-015)
- use: safe writer `_atomic_write_locked` from `install_block` — the secret step's harness-file write (INV-010)

## Acceptance
- [ ] The sign-in load tries each source in its existing order (environment, Claude settings file, `codex` settings file) and takes the first holding a complete sign-in for `jira.site`; a partial source is skipped and named in the error; `load_creds` and `resolve_creds_env` keep their names, take no argument, return the same three values and find the repository themselves (ADR-0004; SDD §14 row "Jira sign-in load `load_creds`, `resolve_creds_env`")
- [ ] Every repository on one Jira site uses that site's one sign-in; two sites can use two accounts; `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` stay the sign-in for their own site (PRD §Accounts AC-035; SDD §4 "Jira sign-ins")
- [ ] `KEY` is the site host in capitals with every character other than a letter or digit replaced by an underscore; a second site whose key collides with another site's is refused naming both (SDD §4; SDD §3 row "`setup_secrets.py` …")
- [ ] With `jira.site` absent, the one existing sign-in and its address are used (SDD §4 committed file row `jira.site`)
- [ ] Tracker server tool refusals name the site and the folder read; tool schemas are unchanged (SDD §3 row "tracker server tools")
- [ ] `setup_secrets.py jira --site <address>`, `forge --host <host> --account <name>` and `longpaths` run only when input and output are a terminal and the agent detector reports no agent session; every other run is refused with the reason; a bare run prints the three commands and exits (SDD §3 row "`setup_secrets.py` …"; PRD §Setup walk AC-013)
- [ ] The secret step re-reads the harness file under the lock and changes only its own keys; a harness rewrite while it waits is refused with nothing changed; the file is owner-only on Linux and macOS; one backup is kept and replaced each run; a rerun replaces the value (SDD §9b row "harness settings file"; SDD §6 row "Jira sign-in per site")
- [ ] No secret is ever printed, echoed or written to a repository file (SDD §5 Secrets; PRD §Access & validation policy row "Store a secret")
- [ ] The Jira account check asks the site who the sign-in belongs to, one try within 20000 ms; a 401 records a failed row and saves nothing (SDD §9b row "Jira REST"; SDD §5 Retry + timeout)
- [ ] The bare-run exit status is decided here and recorded in `plan/DECISIONS.md` (VERIFICATION-PLAN.md Gaps surfaced)
- [ ] The secret step's target under `CLAUDE_CONFIG_DIR` stays `Path.home()/.claude.json` as today; the open question is recorded in `plan/DECISIONS.md` and not changed here (SDD §11; VERIFICATION-PLAN.md Gaps surfaced)
- [ ] The mixed-source test is rewritten for the whole-sign-in rule (SDD §14 row "Jira sign-in load `load_creds`, `resolve_creds_env`")
- [ ] Conforms to ADR-0004 and ADR-0005 — no silent pattern substitution (ADR-0004, ADR-0005)

## Produces
- adapters/tracker/jira/api.py#def site_key( — the site host in capitals, every other character an underscore; names `JIRA_SITE_<KEY>_EMAIL` and `JIRA_SITE_<KEY>_API_TOKEN`
- skills/afk/setup/scripts/setup_secrets.py#add_parser("jira" — the `jira --site` subcommand
- skills/afk/setup/scripts/setup_secrets.py#add_parser("longpaths" — the `longpaths` subcommand named by the setup register
- skills/afk/setup/scripts/jira_account_check.py#def check_jira_account( — the site accepts the sign-in, or the failed row

## Consumes
- 0001-safe-writer scripts/safe_write.py#def update_locked( — locked write with change refusal and owner-only option
- 0002-settings-reader scripts/afk-config.py#OWNER_TABLE = — `jira.site` as a team key

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | seam test: a stub Jira site per sign-in source (environment, Claude file, `codex` file) on a local port; assert the sign-in the site receives per `jira.site`, a partial source skipped and named, a 401 giving a failed row | the real request the Jira site sees |
| unit | seam test: run the real secret step on a pseudo-terminal while a second writer rewrites the sandbox `~/.claude.json`; assert refusal and the second writer's bytes intact; assert owner-only mode and one backup | the harness settings file seam |
| unit | `unit` tier; refusal per run shape: piped input, piped output, agent detector on, under `codex`; key collision refused naming both; nothing printed matching the token | terminal and agent-session refusal |
| smoke | `smoke` tier | hooks end to end |

## Context excerpts
> (ADR-0004) The team setting `jira.site` names the site. Sign-ins for further sites live in the existing tracker block as `JIRA_SITE_<KEY>_EMAIL` and `JIRA_SITE_<KEY>_API_TOKEN`; `KEY` is the site host in capitals with every other character an underscore. The existing three names stay the sign-in for their own site. The sign-in load tries each source in its existing order and takes the first one holding a complete sign-in for the site; a partial source is skipped and named in the error. The secret step writes sign-ins only from the developer's terminal with `jira --site <address>`, refuses a site whose key collides with another site's, re-reads the harness file under the lock, sets owner-only access and keeps one backup.

> (SDD §3 row "`setup_secrets.py jira --site <address>`, `forge --host <host> --account <name>`, `longpaths`") developer, own terminal | developer / every agent shell, piped input | input and output are a terminal; no agent session by the agent detector | writes the sign-in; bare run prints the three commands and exits | refused with the reason; a second site whose name key matches a different site's is refused naming both | rerun replaces the value; one backup kept | breaking for a bare run that signed in once, and for runs under `codex` or with piped input

> (SDD §3 row "tracker server tools") agents | unchanged | unchanged | unchanged | refusals name the site and the folder read | unchanged | compatible: the account choice happens inside the adapter

> (SDD §4 Jira sign-ins) `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | strings | the sign-in for the site in `JIRA_BASE_URL` | unchanged · `JIRA_SITE_<KEY>_EMAIL`, `JIRA_SITE_<KEY>_API_TOKEN` | strings | `KEY` is the site host in capitals, every character other than a letter or digit an underscore; one sign-in comes whole from one source | unique key per site; a key collision between two sites is refused | new

> (SDD §14 row "secret step `setup_secrets`") bare run signs in once and fixes long paths; no terminal check (INV-008, INV-015) | subcommands `jira --site`, `forge --host --account`, `longpaths`; terminal and agent-session refusal; fresh read under the lock; owner-only file; one backup | setup prints its commands; the W5 long-path register line names `longpaths` (INV-015, INV-020) | the agent detector, not two variable names | reworked (ADR-0004)

> (SDD §14 row "Jira sign-in load `load_creds`, `resolve_creds_env`") fills each field from the first source that has it (INV-008, INV-016) | takes the first complete sign-in for `jira.site`; same name, no argument, same three values; finds the repository itself | tracker server, publishers, init hint, assignee suggestion; the mixed-source test is rewritten (INV-016, INV-021) | refusals name the site and the folder read | reworked (ADR-0004)

> (SDD §9b) harness settings file | `~/.claude.json` | the harness may rewrite it while the secret step waits; the step re-reads under the lock | changed file → refuse, nothing changed | secret step test with a concurrent writer
> Jira REST | Jira Cloud | a token belongs to one Atlassian account (unverified-external, AC-035) | 401 at the account check → failed row | Jira adapter test with a stub site per sign-in source

> (SDD §11) Moving `~/.claude.json` under `CLAUDE_CONFIG_DIR`: not checked (INV-015).

> (PRD §Accounts) AC-035 Every repository on one Jira site uses that site's one Jira account. Two sites can use two accounts (unverified premise: a Jira API token belongs to one Atlassian account; the harness passes the tracker server its stored sign-in and picks one tracker entry across scopes).

> (PRD §Setup walk) AC-013 The secret step runs in the developer's own terminal, never in an agent shell.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer, 0002-settings-reader

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

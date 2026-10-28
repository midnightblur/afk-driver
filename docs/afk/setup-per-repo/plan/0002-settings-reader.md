# 0002-settings-reader — owner rule in the settings reader

## Goal
Apply the catalog S owner rule inside the one settings reader: an owner table beside the key and default tables filters every file during the merge, ignored values are recorded and listed by `validate`, a repository counts as set up with a committed file or a repository personal file, and the new keys `jira.site`, `developer.worktreeRoot` and `developer.forgeAccount` exist. `load()` keeps returning a plain dictionary. The commit gates and every plugin check that today needs the committed file accept a set-up repository without one, and every notes kind keeps agent working files in the spec folder.

## Complexity
complex

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "settings reader (changed)"
- SDD: SDD.md#§4 L3 — Data Architecture — entity tables for the machine file, the repository personal file and the committed file; Migration & backfill
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — rows "`afk-config.py validate`" and "`afk-config.py get`, `effective`, `export-shell`, `resolve`"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "`afk-config.py` merge in `afk_config`" and "commit gates `config.yaml` test"
- ADR: adr/design/0001-owner-rule-in-the-reader.md — owner table applied as a filter in the merge
- ADR: adr/design/0007-ignore-misplaced-values-at-once.md — no fallback reads an ignored value
- ADR: adr/requirements/0002-setting-ownership.md — team, personal, machine
- ADR: adr/requirements/0003-notes-per-machine.md — agent working files stay in the repository

## Scope
- scripts/afk-config.py
- scripts/tests/test_afk_config*.py
- hooks/precommit-gates.sh
- scripts/tests/test_precommit_config_gate.py
- scripts/behavior_registry.py
- scripts/tests/test_behavior_registry*.py
- adapters/notes/*/adapter.json
- adapters/notes/common.sh
- CONFIG.md
- scripts/tests/create-worktree-smoke.sh — fixtures only
- scripts/tests/test_create_worktree_name.py — fixtures only
- scripts/tests/test_protected_branch_acceptance.py — fixtures only
- skills/afk/setup/scripts/developer_values.py — key order, plus the status reporting D-22 and D-24 record
- scripts/tests/test_setup_developer_values.py
- scripts/tests/test_precommit_order.py
- adapters/notes/notion/NOTES.md
- adapters/notes/obsidian/notes.sh
- adapters/notes/obsidian/CONTRACT.md
- adapters/notes/repo-files/notes.sh
- adapters/notes/repo-files/CONTRACT.md
- providers/CONFORMANCE.md
- ADAPTERS.md
- adapters/tracker/jira/adapter.json
- .afk/config.yaml

## Seams
- implement: `afk-config.py` merge in `afk_config` (`load`, `validate`, `get`, `resolve`) — owner table, ignored values, is-set-up, new keys (INV-013)
- implement: commit gates `config.yaml` test — runs when the reader says set up or the `.afk` folder exists (INV-004)

## Acceptance
- [ ] For every team setting in catalog S, a repository with a committed AFK file reads the committed value; a personal-file value for it is absent from `get`/`effective`/`export-shell`/`resolve` and listed by `validate` as ignored, naming the setting (PRD §Setting owners AC-020)
- [ ] For every team setting, a repository with no committed AFK file reads the value from the repository personal file (PRD §Setting owners AC-021)
- [ ] For every personal setting, a committed value is ignored and `validate` warns naming the setting (PRD §Setting owners AC-022)
- [ ] For every machine setting (the worktree root, `notes`, `obsidian.vault`, `notion.parent-page-id`), a value in any repository file is ignored and `validate` warns naming the setting (PRD §Setting owners AC-023, AC-044)
- [ ] `afk-config.py validate` prints `configuration is valid`, then one warning line per ignored value naming setting, file and rule, and exits 0; unknown keys are still refused (SDD §3 row "`afk-config.py validate`")
- [ ] `jira.credentials-env` is removed from the schema: a set value is ignored and `validate` prints `jira.credentials-env was removed; delete this key` (PRD §Setting owners AC-027)
- [ ] `jira.site` (team), `developer.worktreeRoot` (machine) and `developer.forgeAccount` (personal) are accepted keys with the owners SDD §4 gives them (SDD §4)
- [ ] The reader refuses a `schema` key in the repository personal file (SDD §4)
- [ ] `load()` keeps returning a plain dictionary; the reader also answers the ignored-value list, whether a repository is set up (committed file or personal file), and a single-file parse (SDD §8 row "settings reader (changed)")
- [ ] An unreadable `.git` file or common directory is reported as a reader error, not an uncaught crash (PRD §Implementation Decisions)
- [ ] The commit gates run their configuration test when the reader says the repository is set up or the `.afk` folder exists, with no Python on the commit path; one test pins both answers (SDD §14 row "commit gates `config.yaml` test")
- [ ] A repository with no committed AFK file passes the commit gates and the behavior registry; `init` and the developer-values step are covered by 0009-settings-writer, the setup check for the AFK file by 0010-setup-walk (PRD §Setting owners AC-025)
- [ ] Every notes kind resolves the spec folder from `repo-files.spec-dir`; choosing a note-taking app moves no agent working file out of the repository (PRD §Agent working files AC-070, AC-071)
- [ ] The owner table is pinned by a test against the setting list in `CONFIG.md`; the top-level key list stays a literal (SDD §14 row "`afk-config.py` merge in `afk_config`")
- [ ] The owner rule adds at most 10 ms per load, measured and reported by the informational bench; the test itself asserts counts (no new file read), not times (SDD §10; GRILL-LOG Verification grill C-23)
- [ ] Conforms to ADR-0001 and ADR-0007: no fallback code reads an ignored value (ADR-0001, ADR-0007)
- [ ] Implements the public interface in SDD §8 row "settings reader (changed)" unmodified (SDD §8)
- [ ] `CONFIG.md` documents the owner of every setting, the three new keys and the removed key (SDD §14 row "`afk-config.py` merge in `afk_config`")
- [ ] Tests outside the reader that put personal worktree settings (`worktree.*`) in the committed file write them to the repository personal file instead, and the developer-values key order covers `worktreeRoot` and `forgeAccount`, so every test that passed before this slice still passes (human re-slice 2026-10-27, after the 0002 park)
- [ ] No file in this slice's Scope still reads, lists or documents a setting at a file its owner does not read: the notes adapters and their docs take the machine-owned notes settings from the machine file, the Jira adapter's setting list names `jira.site` and drops `jira.credentials-env`, the plugin's own `.afk/config.yaml` holds no personal or machine value, and the no-Python commit check keeps every repository that has hooks gated (round-1 review findings f002 f004 f005 f006 f013; human re-slice 2026-10-27, after the second 0002 park)

## Produces
- scripts/afk-config.py#OWNER_TABLE = — every setting's owner: team, personal or machine
- scripts/afk-config.py#def ignored_values( — (setting, file, rule) for each value the owner rule dropped
- scripts/afk-config.py#def is_set_up( — true for a committed file or a repository personal file
- scripts/afk-config.py#def parse_single_file( — one file parsed without the merge
- scripts/afk-config.py#jira.credentials-env was removed; delete this key — the removed-key warning text

## Consumes
- 0001-safe-writer .afk/config.yaml#verification: — the `unit`, `smoke` and `static` tier keys this subtask's Verification names

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; one test per catalog S owner class plus the no-committed-file path in `scripts/tests/test_afk_config_owner.py`; owner-table drift test against `CONFIG.md`; `validate` warning lines and exit status | owner rule and validate contract |
| unit | `unit` tier; `scripts/tests/test_precommit_config_gate.py` runs the real `hooks/precommit-gates.sh` in a temp repository with only a personal file and with only `.afk`, asserting the configuration test runs in both | the commit-gate seam on the real script |
| smoke | `smoke` tier | hooks still run end to end |

## Context excerpts
> (ADR-0001) The settings reader applies the owner rule while it merges the files. One owner table sits beside the reader's key and default tables and gives every setting its owner. The merge passes each file through the table: a value at a file its owner does not read is dropped and recorded as ignored. `validate` and the setup walk list the ignored values; every other read stays silent. `load()` keeps returning a plain dictionary. A test pins the table against `CONFIG.md`.

> (ADR-0007) Values the owner rule ignores stop counting in this release. `validate` and the setup walk warn about each one, and setup offers to copy each value to the file its owner reads. No fallback code reads them.

> (PRD §Catalog S) team: read from the committed AFK file when the repository has one, and not overridable there. With no committed file, setup keeps it in the repository personal file (the developer's own settings for one repository, never committed). personal: lives only in the developer's own files. A committed value is ignored with a warning. machine: lives only in the developer's machine file (`~/.afk/config.yaml`). A value in any repository file is ignored with a warning.

> (PRD §Catalog S) S-01 forge kind team · S-02 forge remote personal · S-03 tracker kind team · S-04 Jira site address team · S-05 Jira project, work item types, status names team · S-06 GitHub issues repository and status labels team · S-07 git base branch, branch pattern, branch template team · S-08 spec folder team · S-09 build gates and their settings, verification tiers, service map, investigation boundaries, review paths, repository hooks, setup extras, plugin-issue repository team · S-10 files a new worktree copies from the main checkout personal · S-11 forge account for the repository personal · S-12 Jira account personal · S-13 change assignee, reviewer, work item assignee personal · S-14 commit email, IDE personal · S-15 worktree root machine · S-16 note-taking app, Notion parent page, Obsidian vault machine

> (SDD §4 committed file) `jira.site` | URL | team | new · `jira.credentials-env` | removed: ignored; validate warns to delete it · `developer.*`, `github.remote`, `gitlab.remote`, `worktree.copy` keys | personal: ignored with a warning naming the setting · `notes`, `obsidian.vault`, `notion.parent-page-id` | machine: ignored with a warning naming the setting · Δ `schema`, `toolkit-version` | team · Δ `report-issue.auto-publish` | stays ignored everywhere, as today · every other key | team

> (SDD §4 repository personal file) every team key | read only when the repository has no committed file; ignored with a warning when it has one · `developer.forgeAccount` | saved only after the host accepts it | new; the host is derived from the forge remote on every read · `github.remote`, `gitlab.remote` | personal | was team · `worktree.copy`, `copy-personal`, `copy-ignored-claude-md` | personal; Δ a committed value of the two switches is ignored with a warning · `developer.worktreeBasePath` | ignored with a warning · Δ `schema` | never written here; the reader refuses it

> (SDD §4 machine file) `developer.worktreeRoot` | absolute path | absent: not confirmed, the suggestion `~/repo-worktrees` applies | catalog R on write and on every read | new, machine-owned · `developer.worktreeBasePath` | read as the root only while `worktreeRoot` is absent and the value passes catalog R

> (SDD §3 row "`afk-config.py validate`") setup, developer, plugin-issue reporter | the merged files | `configuration is valid`, then one warning line per ignored value (setting, file, rule), exit 0 | unknown keys refused as today; `jira.credentials-env` warns `jira.credentials-env was removed; delete this key` | compatible: ignored values do not change the exit status

> (SDD §3 row "`afk-config.py get`, `effective`, `export-shell`, `resolve`") an ignored value is absent from the answer | the answer changes only where a value sat at a file its owner does not read

> (SDD §14 row "`afk-config.py` merge in `afk_config`") owner table filters each file; ignored list and is-set-up calls; new keys `jira.site`, `developer.worktreeRoot`, `developer.forgeAccount`; `jira.credentials-env` warns; `load()` keeps returning a plain dictionary | nine importers of `load()`; sites that skip it move onto it where the owner rule changes their value; the creator's IDE lookup no longer sees a committed `developer.ideBinary`; the redactor reads the top-level key list (INV-005, INV-013) | keep the top-level key list a literal; never write `schema` in the personal file; owner drift test against `CONFIG.md`

> (SDD §14 row "commit gates `config.yaml` test") tests the `.afk` folder (INV-004) | runs when the reader says set up, or the `.afk` folder exists | repositories with only repository hooks keep their gates (INV-004, INV-005) | no Python on the commit path; one test pins both answers | extends

> (PRD §Implementation Decisions) An unreadable `.git` file or common directory crashes the config reader and the tracker server today (INV-004). M2 must report it instead.

> (ADR-0003 requirements) Agents write every working file for a work item into the repository's spec folder, whatever app is chosen.

## Parent PRD
docs/afk/setup-per-repo/PRD.md

## Parent SDD
docs/afk/setup-per-repo/SDD.md

## Blocked by
0001-safe-writer

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

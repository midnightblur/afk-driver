# 0009-settings-writer — one key to its owner's file, init from the personal file, copy deletion

## Goal
Rework the settings writer so it writes any key, one key at a time, to the file its owner reads (repository personal file for team values without a committed file and for personal values; machine file for machine values), through the safe writer. Make `init` fill a new committed file from the personal file's team values. Add the copy-deletion step that, once a committed file holds a real value, deletes each personal-file copy of that team setting and reports what it deleted and what it kept, and the migration steps setup offers for misplaced values.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "settings writer `write_block` in `developer_values`" and "`afk-config.py init` in `afk_config`"
- SDD: SDD.md#§4 L3 — Data Architecture — Migration & backfill
- SDD: SDD.md#§7 L6 — Process & Coordination — use cases "set a value", "copy deletion", "root migration"; side-effect rows "delete personal copies of team settings" and "delete the old worktree base value"
- ADR: adr/design/0005-shared-safe-writer.md — the settings writer uses the safe writer
- ADR: adr/design/0007-ignore-misplaced-values-at-once.md — setup offers to copy each ignored value to its owner's file

## Scope
- skills/afk/setup/scripts/developer_values.py
- skills/afk/setup/scripts/copy_deletion.py
- scripts/afk-config.py
- scripts/tests/test_setup_developer_values.py
- scripts/tests/test_afk_config_init.py
- scripts/tests/test_copy_deletion.py

## Seams
- implement: settings writer `write_block` in `developer_values` — one key to its owner's file (INV-015)
- implement: `afk-config.py init` in `afk_config` — fills the committed file from the personal file's team values (INV-013)
- use: safe writer `_atomic_write_locked` from `install_block` — every settings write (INV-010)

## Acceptance
- [ ] The settings writer writes one key per call to its owner's file, chosen by the owner table; a key sent to a file its owner does not read is refused; machine refusal follows the owner table (SDD §14 row "settings writer `write_block` in `developer_values`")
- [ ] A value starting with a special character is quoted; an existing heading carrying a note is recognised and reused; the writer never writes a `schema` line into the repository personal file (SDD §14 row "settings writer `write_block` in `developer_values`"; SDD §4)
- [ ] Setting a value twice changes nothing (SDD §5 Idempotency row "settings write")
- [ ] The writer's error handling names the safe writer's own error, not only the installer's (SDD §14 row "settings writer `write_block` in `developer_values`")
- [ ] A value the writer writes lands in the repository personal file under the git common folder and is read by the main checkout and every worktree of that repository (PRD §Setup walk AC-015)
- [ ] The writer never writes a per-worktree value; when `.afk/config.local.yaml` overrides a value setup manages, the writer's caller gets a warning naming both (PRD §Setup walk AC-014)
- [ ] For a repository with no committed AFK file, team values are written to the repository personal file (PRD §Setting owners AC-021)
- [ ] A repository with no committed AFK file passes `init` and the developer-values step (PRD §Setting owners AC-025)
- [ ] `init` fills a new committed file from the repository personal file's team values and never writes the personal file (SDD §14 row "`afk-config.py init` in `afk_config`"; PRD §Setting owners AC-024)
- [ ] Copy deletion: when the committed file holds a real value for a team setting, the personal-file copy is deleted without asking; every copy is kept while a worktree of the repository is on a branch without the committed file; the result lists each deleted setting, file and value and each kept copy with its reason (PRD §Setting owners AC-024; SDD §7 side effect "delete personal copies of team settings")
- [ ] Migration helpers: a team value in the machine file is copied, on yes, into a listed repository's personal file; machine-wide assignee and reviewer values are written, on confirmation, to that repository's personal file; the old `developer.worktreeBasePath` is deleted only after `worktreeRoot` is written and reads back, and only on yes (SDD §4 Migration & backfill; SDD §7 "root migration"; PRD §Accounts AC-037; PRD §Worktree root AC-043)
- [ ] Conforms to ADR-0005 and ADR-0007: every write through the safe writer; no fallback reads an ignored value (ADR-0005, ADR-0007)

## Produces
- skills/afk/setup/scripts/developer_values.py#def write_setting( — one key to its owner's file through the safe writer
- skills/afk/setup/scripts/copy_deletion.py#def delete_team_copies( — deleted and kept copies with reasons
- scripts/afk-config.py#def init_from_personal( — the committed file filled from the personal file's team values

## Consumes
- 0001-safe-writer scripts/safe_write.py#def update_locked( — locked read-modify-write
- 0002-settings-reader scripts/afk-config.py#OWNER_TABLE = — the owner of every key
- 0002-settings-reader scripts/afk-config.py#def is_set_up( — committed file or personal file

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `static` tier + grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `unit` tier; `scripts/tests/test_setup_developer_values.py`: one key per owner class to the right file, wrong-file key refused, special first characters quoted, heading with a note reused, no `schema` line, second write changes nothing, `config.local.yaml` override warning; read back from the main checkout and from a worktree | writer contract on a real repository with a worktree |
| unit | `scripts/tests/test_copy_deletion.py`: committed real value deletes the copy; a worktree on a branch without the committed file keeps it; result lists setting, file, value and reasons | copy deletion |
| unit | `scripts/tests/test_afk_config_init.py`: init fills from personal team values; personal file unchanged | init |
| smoke | `smoke` tier | hooks end to end |

## Context excerpts
> (SDD §14 row "settings writer `write_block` in `developer_values`") rewrites only the `developer:` block; 5 keys; several `KEY=VALUE` per call (INV-010, INV-015) | any key to its owner's file, one key at a time; special first characters quoted; a heading with a note recognised; machine refusal follows the owner table | setup steps writing values (INV-015, INV-020) | no `schema` line in the personal file; the writer's catch names the safe writer's own error, not only the installer's (INV-015) | reworked

> (SDD §14 row "`afk-config.py init` in `afk_config`") writes the committed file from a template (INV-004, INV-013) | fills the new committed file from the personal file's team values | setup's copy deletion waits for a real committed value (INV-005, INV-013) | setup, not `init`, writes the personal file | reworked

> (SDD §4 Migration & backfill) machine `developer.worktreeBasePath` | the root while no root is confirmed, if it passes catalog R; setup offers to write `worktreeRoot` and delete the old key · `developer.worktreeBasePath` in a repository personal file | ignored with a warning; setup offers to delete it; the root is asked fresh · the one Jira sign-in | kept; setup asks which listed repositories use its site and writes `jira.site` to the personal file of each one without a committed file · a personal value in a committed file | ignored with a warning; setup asks for the developer's own value · a team value in the machine file | ignored with a warning; setup offers to copy it into each listed repository's personal file · personal copies of team values once a committed file holds a real value | deleted without asking, listed in the report (§7) · existing worktrees | untouched

> (SDD §7 side effects) delete personal copies of team settings | setup, once the committed file holds a real value for that setting and no worktree of the repository is on a branch without the committed file | deleted without asking; each deleted setting, file and value listed in the report; kept otherwise, with the reason | type the value again from the report
> delete the old worktree base value | setup, after the new root reads back; Δ per repository, on yes | offered, not automatic | set it again

> (SDD §7 use cases) set a value | setup answer | one key per safe write | read-after-write | file lock, re-read, compare · copy deletion | setup run | per key safe write | file lock · root migration | developer answers the root question | write `worktreeRoot`, read back, then offer deletion | new key wins while both exist | safe writer

> (PRD §Setup walk) AC-014 Setup never writes a per-worktree value. When a value in `.afk/config.local.yaml` overrides a value setup manages, setup warns and names both. AC-015 A value setup writes is read by the main checkout and every worktree of that repository.

> (PRD §Setting owners) AC-024 When a repository gains a committed AFK file, the next setup run deletes, without asking, each personal-file copy of a team setting the committed file holds a real value for. It keeps every copy while a worktree of the repository is on a branch without the committed file. The report lists each deleted setting, file and value, and each kept copy with its reason.

> (PRD §Accounts) AC-037 Existing machine-wide assignee and reviewer values are shown for each repository to confirm. The answers go to that repository's personal file.

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

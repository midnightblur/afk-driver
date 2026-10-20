## Goal
Remove `/afk:bug` in one commit — skill, manifests, its test, every reference and its eight glossary headings — and add a commit check that fails while a mention survives outside `CHANGELOG.md` and spec folders. Rewrite the tracker-boundary rule to one writer with a plugin-root ADR superseding ADR-0001, update the registries, and prepare the major release: changelog section with a Migration line, agreeing versions, and the two deprecated aliases removed.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "`/afk:bug`"
- SDD: SDD.md#§10 NFRs — row "`/afk:bug` mentions outside `CHANGELOG.md` and spec folders"
- SDD: SDD.md#§12 Reversed Decisions — plugin ADR-0001 superseded
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows for the removal, the writer rule, the registries, the commit check and the release gate
- ADR: adr/design/0011-bug-skill-removal-enforced-by-a-commit-check.md — removal enforced by a commit check
- ADR: adr/requirements/0003-to-ticket-sole-tracker-writer.md — one tracker writer, no alias

## Scope
- skills/afk/bug/*.md
- skills/afk/bug/scripts/*.py
- skills/afk/to-demo-plan/SKILL.md
- skills/utils/settle-mr/SKILL.md
- .claude-plugin/plugin.json
- .claude-plugin/marketplace.json
- .codex-plugin/plugin.json
- .afk/config.yaml
- GLOSSARY.md
- AGENTS.md
- README.md
- CAPABILITIES.md
- FRESHNESS.md
- CHANGELOG.md
- adr/0008-one-tracker-writer.md
- skills/afk/setup/MANIFEST.md
- skills/afk/gc/SKILL.md
- adapters/tracker/jira/adapter.json
- hooks/plugin-source-gates.sh
- hooks/lib/removed_skill_check.py
- hooks/README.md
- hooks/tests/*.sh
- scripts/glossary_usage.py
- scripts/tests/test_*.py
- SPINOFF-TICKET.md
- skills/afk/to-meeting-d/SKILL.md
- adapters/tracker/jira/CONTRACT.md

## Seams
- implement: `/afk:bug` skill removed — skill, manifests, test, references and glossary headings in one commit (INV-026)
- implement: tracker-writer rule after `afk:bug` — one writer, plugin-root ADR supersedes ADR-0001 (INV-026)
- implement: registries, FRESHNESS, MANIFEST rows for `afk:bug` — rows deleted or edited (INV-026)
- implement: new commit check for `afk:bug` mentions — the plugin-source gate entry and its fixtures (INV-026)
- implement: release gate for `afk:bug` removal — major release, Migration line, aliases removed (INV-026)

## Acceptance
- [ ] The bug skill folder, both manifest entries, `test_publish_bug.py`, every reference, and the eight bug-pipeline glossary headings (One-live-fixer among them) are gone in one commit (SDD §14 row "`/afk:bug` skill removed")
- [ ] The slice's report names each live check for the developer to run before the release merges — GitLab branch lookup with several changes, `glab --ready` on a non-Draft change, Jira formatting, unknown-fix-version answers, Jira upload type, GitHub Issues attach with gh ≥ 2.99.0; the slice runs none of them and does not wait (SDD §13)
- [ ] Invoking `/afk:bug` finds no skill and no alias (PRD AC-039)
- [ ] A new plugin-source commit check fails while `/afk:bug` or `/afk-toolkit:bug` appears outside `CHANGELOG.md` and spec folders, scans through `hooks/lib/bounded_scan.py`, and has passing and failing fixtures plus a hooks README row (SDD §14 row "new commit check for `afk:bug` mentions")
- [ ] After the change, the count of `/afk:bug` mentions outside `CHANGELOG.md` and spec folders is 0, and `/afk:setup audit` passes (PRD AC-038)
- [ ] The tracker-boundary text in `AGENTS.md`, `README.md`, `MANIFEST.md`, `CAPABILITIES.md` and `GLOSSARY.md` says one writer, `/afk:to-ticket`, with `/afk:report-issue` a separate egress; a plugin-root ADR supersedes ADR-0001; `FRESHNESS.md` changes in the same commit (PRD AC-035)
- [ ] Registry rows for the bug skill are deleted or edited: MANIFEST H2 and S1 edited, not deleted, because the Jira adapter still uses them; the H6 probe test and the gate E register ids still pass (SDD §14 row "registries, FRESHNESS, MANIFEST rows for `afk:bug`")
- [ ] The glossary usage check and its tests, and the tracker-create test header, no longer expect the removed headings or name the removed skill (SDD §14 row "new commit check for `afk:bug` mentions")
- [ ] `CHANGELOG.md` opens a section for the next major version stating that `/afk:bug` is gone and `/afk:diagnose` no longer fixes, with a `Migration:` line giving clean-up steps for `.claude/bugs` folders and old fixer worktrees (PRD AC-041)
- [ ] Both plugin manifests, the marketplace entry, `.afk/config.yaml` `toolkit-version` and the changelog heading agree on that major version, so the release gate passes (SDD §14 row "release gate for `afk:bug` removal")
- [ ] The deprecated `/afk:to-demo-plan` and `/afk:settle-mr` aliases are removed with their catalog rows (SDD §14 row "release gate for `afk:bug` removal")
- [ ] Conforms to ADR-0011 design — no silent pattern substitution (design ADR-0011)

## Produces
- hooks/lib/removed_skill_check.py#def find_removed_skill_mentions( — the commit check's scan, excluding `CHANGELOG.md` and spec folders
- adr/0008-one-tracker-writer.md#Supersedes: ADR-0001 — the plugin-root record of the one-writer rule

## Consumes
- 0005-bug-mode skills/afk/to-ticket/scripts/publish_bug_mode.py#def run_bug_mode( — the replacement ticket writer the boundary text names
- 0008-standalone-fix skills/afk/fix/SHIPPING.md#Standalone write order — the replacement fix path the release notes name
- 0002-developer-settings CONFIG.md#Developer settings (K1–K5) — the new home of the settings the removed page documented

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged` (incl. the new check, skill registry, native contract); grep each ## Produces anchor | no `/afk:bug` mention survives; manifests and catalog agree |
| unit | `afk-python -m pytest scripts/tests/test_plugin_source_gates.py scripts/tests/test_glossary_usage.py scripts/tests/test_behavior_registry_gate.py scripts/tests/test_setup_h6_probe.py scripts/tests/test_removed_skill_check.py -q` | the new check's fixtures fail and pass as designed; gate lists and probes still match |
| integration | `bash hooks/release-gate.sh v<next major>` exits 0; `/afk:setup audit` reports no drift | release agreement; no registry drift (PRD AC-038) |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §3) | `/afk:bug` | nobody | everybody | — | — | the harness finds no such skill | — | breaking for humans; no alias (ADR-0011) |
> (SDD §10) | `/afk:bug` mentions outside `CHANGELOG.md` and spec folders (count) | 0 | new commit check | plugin-source gates |
> (SDD §12) | Plugin ADR-0001 (two tracker writers; cited, no file) | requirement ADR-0003 of this feature; plugin-root `adr/0008` written by the build | `/afk:bug` is removed; `/afk:to-ticket` is the only tracker writer; `/afk:report-issue` stays a separate egress (ADR-0002/0007 of the plugin) |
> (SDD §14 row "`/afk:bug` skill removed") INV-026: manifests `.claude-plugin/plugin.json:19`, `.codex-plugin/plugin.json:9`; gates; `test_publish_bug.py` imports the skill script | remove skill, manifests, test, every reference and 8 glossary headings (One-live-fixer among them) in one commit | INV-026: text reference list; glossary usage test | `mrReviewer` and `change-reviewers` land with fix's ready step; glossary commit with `PRD.md`; bug-mode script test covers `tracker_api.load` (its only test goes, `test_publish_bug.py:43`)
> (SDD §14 row "tracker-writer rule after `afk:bug`") INV-026: "exactly two" (`AGENTS.md:9,193-195`, `README.md`, `MANIFEST.md`, `GLOSSARY.md:262`); no code enforces it | one writer; `adr/0008` supersedes ADR-0001; `/afk:report-issue` a separate egress | INV-026: report-issue writes this repository's tracker; rule statements also at `MANIFEST.md:858`, `CAPABILITIES.md:65`, `README.md:108,117` | `FRESHNESS.md:94` in the same commit
> (SDD §14 row "registries, FRESHNESS, MANIFEST rows for `afk:bug`") INV-026: FRESHNESS `:77-80,86`; MANIFEST H2, H6, S1, W2 | delete or edit rows (H2 and S1 edited, not deleted: `jira/adapter.json:27-30`); gh ≥ 2.99.0 floor row; `tracker_attach` at every home | INV-026: gate E register ids; `test_setup_h6_probe.py:22-25`; FRESHNESS row 79 also owns `scripts/create-worktree`, row 78 names K1-K4 | same-commit rule
> (SDD §14 row "new commit check for `afk:bug` mentions") INV-026: audit checks miss a bare `/afk:bug` in prose | gates entry, fixtures, hooks README row; excludes `CHANGELOG.md` and spec folders; also `/afk-toolkit:bug` | INV-026: `plugin-source-gates.sh:97,186-188`; the gate list is pinned at `test_plugin_source_gates.py:33,313-314`, `test_behavior_registry_gate.py:70` | gate cost rules (check M requires `hooks/lib/bounded_scan.py`); exclude or edit `glossary_usage.py:28-31`, `test_glossary_usage.py:96,132`, `test_tracker_create_assignee.py:3`
> (SDD §14 row "release gate for `afk:bug` removal") INV-026: `release-gate.sh:91-95` checks agreement; the major bump is the human's call (`CHANGELOG.md:23-27`) | major release; Migration line; remove `to-demo-plan` and `settle-mr` aliases | INV-026: `update-notice.sh:124` surfaces `Migration:` (untested, `:123-150`) | the Migration line gives clean-up steps for `.claude/bugs` and fixer worktrees, which lose their purge owner (`gc/SKILL.md:89-90`)

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0001-diagnosis-format, 0002-developer-settings, 0003-tracker-attach, 0004-diagnose-rewrite, 0005-bug-mode, 0006-fix-procedure, 0007-ship-script, 0008-standalone-fix, 0009-in-place-callers, 0010-out-of-slice

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

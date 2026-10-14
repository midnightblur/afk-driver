## Goal
Give mission control a read-only team section that parses the run manifest and tells a parked agent from a hung one, showing the park-until time as an absolute time. The section joins the section registry, the nav order, the titles and the renderer, and watch mode also watches the main checkout's manifest (file name skills/afk/mission-control/scripts/mc/sections/team.py: plan decision D-3). Separately, the progress section also reads the feature outcomes files that /afk:preflight writes and shows the count of feature review rounds once for the feature. The slice ends at mission control; the manifest module it reads is another subtask.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Dashboard section"
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`" and "Mission control progress.py never counts feature review rounds"
- ADR: adr/design/0015-a-change-that-only-adds-keeps-the-contract.md — both rows are extends: the existing contract holds and only gains

## Scope
- skills/afk/mission-control/scripts/mc/**
- skills/afk/mission-control/scripts/tests/test_contract.py
- skills/afk/mission-control/SKILL.md

## Seams
- implement: §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`" — the team section parser, nav order, titles, renderer entry; watch scope widened to the main checkout's manifest; Absent in the one-time render; park-until absolute (INV-008)

## Acceptance
- [ ] The dashboard section implements the §8 public interface unmodified: a mission-control section, a read-only parser over the manifest file (SDD §8 row "Dashboard section")
- [ ] A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time (PRD AC-029)
- [ ] The team section gets its parser, its nav-order entry, its title and its renderer entry; watch scope widens to the main checkout's manifest; the section is Absent in the one-time render; the park-until time is absolute (SDD §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`")
- [ ] The team section's id is present in `NAV_ORDER`, since an id missing from it is dropped silently (SDD §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`")
- [ ] A re-render of the same inputs stays byte-identical: the team section shows no relative time (SDD §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`")
- [ ] progress.py also reads the feature outcomes files that /afk:preflight writes under plan/review/ and shows the count of feature review rounds once for the feature; the counts per subtask stay as they are (SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] The feature count is one feature-level key beside subtasks, counts and the ladder, never a feature row in data.subtasks or data.counts; the renderer edit in shell.html ships in the same commit as progress.py (SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] test_contract.py gains one test fixture with a feature outcomes file (SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] Seam (plan D-14): §14 row "Mission control progress.py never counts feature review rounds", grounded by INV-063 (closed with frontier) — progress.py also reads the feature outcomes files and shows the feature review-round count once; progress.py and shell.html in one commit with a test fixture (SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] The feature count comes from calling _rounds with the id feature (progress.py:26, :141-144), with no rollup passed, so a rollup row keyed feature feeds no cycle note into it (SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] At build, the executor checks that the outcomes files give the same number as the forge feature round that reconstruct returns, which the PF-3 Cycle cell shows; a lag is recorded, since outcomes files are optional telemetry and a clean round writes only a summary (agent-decided, SDD §14 row "Mission control progress.py never counts feature review rounds")
- [ ] Conforms to ADR-0015 — both changes only add, and every existing caller keeps the contract it has today (ADR-0015)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Dashboard section")

## Produces
- skills/afk/mission-control/scripts/mc/sections/team.py#def parse_team_section( — read-only team section over the run manifest

## Consumes
- 0003-manifest-module scripts/team/manifest.py#def read_manifest( — the manifest format the section parses

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'def parse_team_section(' skills/afk/mission-control/scripts/mc/sections/team.py`; `grep -n 'def read_manifest(' scripts/team/manifest.py`; `afk-python -m py_compile skills/afk/mission-control/scripts/mc/sections/team.py skills/afk/mission-control/scripts/mc/sections/progress.py` | Produces and consumed anchors present; the changed modules compile |
| unit | `afk-python -m pytest skills/afk/mission-control/scripts/tests/test_contract.py -q`, with new cases: the team section is present in `NAV_ORDER`; a parked agent shows an absolute park-until time; a re-render is byte-identical; the feature round count comes from a PF-3 outcomes fixture; test A10 stays green | the team section and the feature round count, per both §14 rows |
| static | compare the feature count from a PF-3 outcomes fixture with the round `afk-python skills/afk/review/scripts/forge_ledger.py reconstruct` returns on a test change with feature rounds; a difference is recorded in plan/DECISIONS.md | the feature count and the Cycle cell follow the same forge feature round, or the lag is on the record |

## Context excerpts
> (SDD §8 row "Dashboard section") | Dashboard section | Read-only parser over the manifest | a mission-control section | manifest file | — |

> (SDD §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`", Planned change) C16: team section parser, nav order, titles, renderer entry; watch scope widened to the main checkout's manifest; Absent in the one-time render; park-until absolute (S-97, S-102)

> (SDD §14 row "Mission control `SECTION_PARSERS`, `NAV_ORDER`, `SECTION_META`", Conventions / landmines) An id missing from `NAV_ORDER` is dropped silently; relative times break byte-identical re-render. Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version (S-246)

> (SDD §14 row "Mission control progress.py never counts feature review rounds", Existing contract) _rounds (progress.py:136-149) counts settle rounds per subtask only: it runs once per tracker row (:59), globs plan/review/ for that subtask's outcomes files (:141) and keeps the highest round number (:142-144); a cycle note in the rollup raises it (:145-148). [...] The PF-3 Cycle cell is refreshed from the reconstruct round, the highest summary round on the change, which never restarts (forge_ledger.py:650, :961-986; preflight/SKILL.md:107-108), and mission control already shows it on the gates page (gates.py:37; shell.html:1035-1037) (c-c5463331, c-e2f834b3)

> (SDD §14 row "Mission control progress.py never counts feature review rounds", Planned change) progress.py also reads the feature outcomes files that /afk:preflight writes under plan/review/, and shows the count of feature review rounds once for the feature; the counts per subtask stay as they are (S-206). The executor picks where the section shows the number; test_contract.py gains one test fixture with a feature outcomes file (S-206). progress.py keeps S-206's feature count, its source checked at build; the PF-3 Cycle cell shows the forge feature round that reconstruct returns (preflight/SKILL.md:106-108; D-05, agent-decided; GRILL-LOG.md:745 (5))

> (SDD §14 row "Mission control progress.py never counts feature review rounds", Impacted flows) The dashboard's progress section. One feature-level key beside subtasks, counts and the ladder (progress.py:85) breaks nothing: the suite stays green, and a re-render is byte-identical (test_contract.py:435). A feature row in data.subtasks or data.counts would break A1 (test_contract.py:286, :303), progress.py:85, overview.py:47-48 and shell.html:342, :892, :1141, which S-206 rules out. Showing the number needs a renderer edit in shell.html (:896, :900-913) in the same commit, and reaches the one-time, PF-5 and watch launches, the watch loop re-rendering on any file change under the spec folder (server.py:53, :105; test_contract.py:439). Calling _rounds with the id feature already gives the count (progress.py:26, :141-144) (INV-063 c-1e41e3eb, c-511b4f65, c-a550259c)

> (SDD §14 row "Mission control progress.py never counts feature review rounds", Conventions / landmines) Only test A10 (test_contract.py:511-522) pins rounds, and no CI job runs the mission-control tests (.github/workflows/tests.yml:64; c-f247f876). The Cycle cell and the feature count both follow the forge feature round, so whether the outcomes files still give the same number is checked at build (GRILL-LOG.md:745 (5)). Not load-bearing: outcomes files are optional telemetry and a clean round writes only a summary, so the outcomes count can lag the forge round (SETTLEMENT.md:41-44; c-c6a440a0, c-3b56fe3a); a rollup row keyed feature could feed a cycle note into the count unless the call passes no rollup (c-5c300f19). Compatibility: the counts per subtask do not change; there is one new number, with no migration or ship order (S-206).

> (PRD AC-029) A dashboard reading the manifest distinguishes a parked agent from a hung one, showing the park-until time.

> (ADR-0015) A change takes extends when every existing caller keeps the contract it has today and the change only adds: a key, a row, a field, a line, a step or a count (S-199).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0003-manifest-module

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

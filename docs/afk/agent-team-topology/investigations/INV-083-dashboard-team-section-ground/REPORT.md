midnightblur/afk-driver@3bccf52847af2527b0e9166c52a28e24d47c0a0d · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/agent-team-topology/investigations/INV-083-dashboard-team-section-ground/COVERAGE.json

## Answer
- `SECTION_PARSERS` (skills/afk/mission-control/scripts/mission_control.py:39-51) is the one parser list. `compose.build` (mc/compose.py:44-67) calls each parser with `spec_dir` only, puts overview first, and keeps only the ids `NAV_ORDER` lists. An id missing from `NAV_ORDER` is dropped with no error. `SECTION_META` gives a title and kind only to an Absent result. shell.html draws a section through `RENDER[sec.id]` (:494, :1179); a populated section with no entry shows "failed to render".
- No try surrounds a parser call (compose.py:46-48): a raising parser stops `--once` and watch start-up. `read_manifest` (scripts/team/manifest.py:169) raises ManifestError for bad files and lets RecursionError through, so a team parser must catch more than ManifestError.
- Watch mode snapshots only files under `spec_dir` (mc/server.py:50-63). A manifest in the main checkout's `.claude/afk-team/<run>/` triggers nothing today, and mission control resolves no main checkout. A worktree made by create-worktree carries a copy of `.claude/`, so the manifest must be read from the main checkout (inference).
- Both entry points pass the same list (mission_control.py:112, :115), so an Absent team section in `--once` needs its own list or a mode. PF-5 commits the `--once` page as `plan/SHIP-SNAPSHOT.html` (preflight/SKILL.md:171-180).
- `_rounds(review_dir, "feature", None)` returns the highest n over `plan/review/feature-*-r{n}.outcomes.json`, else None; with no rollup no cycle note raises it. A fourth top-level progress key breaks no reader (progress.py:85; overview.py:47-48; shell.html:342, :534, :896).
- Tests: A1 checks 12 ids by membership; A3 runs every parser; A4 and A5 refuse an external reference, a form or a second `fetch(`; A6 needs the team section Absent in `--once` or stored times only; A10 pins only per-subtask rounds. Every fixture is its own git repository. No CI job runs this suite.
- No code maps a spec folder to a team run name; the run root is `AFK_TEAM_ROOT`, else `<main checkout>/.claude/afk-team` (scripts/team/entry.py:85). Reading the variable would break the renderer's no-environment rule (compose.py:2-3).
## Sites
- breaks: mc/compose.py:14 (`NAV_ORDER`); mission_control.py:39, :112; mc/server.py:50; mc/assets/shell.html:494, :1152 (12 number keys), :1167 (footer); SKILL.md:13, :33; GLOSSARY.md:273
- wrong today: SKILL.md:31-33 (watch mode watches no git refs); mc/__init__.py:6 (names `panels/`); shell.html:1160 (a live section's dot is green whatever its state); `plan/mission-control/` has no ignore rule although SKILL.md:70, :87 call it ignored
- unchanged, load-bearing: progress.py:136-149 (`_rounds`); overview.py:28-48; template.py; manifest.py:146-171
- every other site: COVERAGE.json nodes table
## Frontier
- B14: open browser tabs on a served page, committed ship snapshots, and run folders in other repositories.
## Unverified
- c-3f313d8b (not load-bearing): the hit set is complete over the name forms searched.

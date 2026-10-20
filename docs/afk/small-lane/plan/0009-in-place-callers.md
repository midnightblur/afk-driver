## Goal
Point every agent caller that fixes in place at the shared fix procedure: `/afk:execute` Steps 8, 10 and 10.5, `/afk:preflight` PF-3 and PF-4, and a fix helper `/afk:autopilot` runs between smoke-gate runs. Map the procedure's results onto each caller's existing statuses, count `flaky` as passed with one journal line, and widen "only execute commits" to the autopilot and preflight fix helpers.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "shared fix procedure, read in place"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — AuthZ row "Commit an in-place fix on the feature branch"; Observability row "one `flaky` journal line"
- SDD: SDD.md#§7 L6 — Process & Coordination — "Red smoke gate"
- SDD: SDD.md#§10 NFRs — rows "Re-runs of a failure before diagnosing", "Smoke-gate re-runs after in-place fixes"
- ADR: adr/design/0001-in-place-fix-is-a-shared-procedure-file.md — callers read the procedure; result mapping; `flaky`
- ADR: adr/design/0007-red-smoke-gate-fixed-by-autopilot-between-runs.md — autopilot fixes between gate runs; one re-run

## Scope
- skills/afk/execute/SKILL.md
- skills/afk/preflight/SKILL.md
- skills/afk/autopilot/SKILL.md
- skills/afk/smoke-test/SKILL.md
- skills/afk/to-subtasks/JOURNAL-FORMAT.md
- skills/afk/mission-control/scripts/mc/**/*.py
- skills/afk/mission-control/scripts/tests/*.py
- scripts/tests/test_execute_step_pointers.py
- CHANGELOG.md

## Seams
- implement: `/afk:execute` fix points and limits — Steps 8, 10, 10.5 read the procedure; status mapping; commit rule widened (INV-023)
- implement: `/afk:preflight` PF-3/PF-4 and the `afk:subtasks` block — PF-3 and PF-4 read the procedure and map its results to park reasons (INV-023)
- implement: `/afk:smoke-test` red gate with `/afk:autopilot` — autopilot's fix helper between gate runs (INV-023)
- implement: `JOURNAL-FORMAT` events and `/afk:autopilot` report — the `flaky` line only (INV-023)

## Acceptance
- [ ] `/afk:execute` Steps 8, 10 and 10.5 point at the shared fix procedure; step numbers and caps stay as they are (SDD §14 row "`/afk:execute` fix points and limits")
- [ ] Each caller maps the six non-`flaky` results onto its existing statuses or park reasons; no new executor status appears (SDD §3)
- [ ] On `flaky`, the caller counts the check as passed for that run and appends one journal line naming the check and both runs, in a form `JOURNAL-FORMAT.md` defines (SDD §5)
- [ ] `/afk:preflight` PF-3 and PF-4 point at the procedure and map its results to PF park reasons (SDD §14 row "`/afk:preflight` PF-3/PF-4 and the `afk:subtasks` block")
- [ ] "Only execute commits" widens to the fix helpers `/afk:autopilot` runs between smoke-gate runs and `/afk:preflight` runs in its final review; every other skill still may not commit (SDD §5)
- [ ] On a red smoke gate, `/afk:autopilot` runs the procedure once per failing scenario through a fix helper that commits on the feature branch, rebuilds the app, then re-runs the full gate once; a second red ends the run red; `/afk:smoke-test` stays report-only (SDD §7)
- [ ] The fix commits keep the comment gate and rationale, and no caller uses `--no-verify` (SDD §14 row "`/afk:execute` fix points and limits")
- [ ] Rows B-2 to B-7 of catalog B hold: B-2 one targeted retry inside the build loop; B-3 to B-6 an in-place fix approved by the agent caller under `DECISIONS.md`, with a wrong finding disputed in the settle loop and an adversary finding's reproduction kept as the permanent test; B-7 no product-code change (PRD AC-025)
- [ ] The step-pointer test, the mission-control insights patterns and the `test_fail` text still match the edited skill text (SDD §14 row "`/afk:execute` fix points and limits")
- [ ] Conforms to ADR-0001 and ADR-0007 design — no silent pattern substitution (design ADR-0007)

## Produces
- skills/afk/to-subtasks/JOURNAL-FORMAT.md#Flaky check line — grammar of the one `flaky` journal line
- skills/afk/autopilot/SKILL.md#smoke-gate fix helper — the helper that commits in-place fixes between gate runs

## Consumes
- 0006-fix-procedure skills/afk/fix/IN-PLACE-FIX.md#In-place fix results — the seven results each caller maps

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep each ## Produces anchor | prose gates pass; declared anchors present |
| unit | `afk-python -m pytest scripts/tests/test_execute_step_pointers.py skills/afk/mission-control/scripts/tests -q` — every in-place caller step names the procedure file; insights still parse the status text | callers reach the procedure; dashboards still read the journal |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §3) `flaky` is new: every caller counts the check as passed for that run and writes one journal line naming it and both runs; no new executor status
> (SDD §5) | Commit an in-place fix on the feature branch | the executor; the fix helpers `/afk:autopilot` runs between smoke-gate runs and `/afk:preflight` runs in its final review | every other skill | `/afk:execute`, `/afk:autopilot`, `/afk:preflight` text |
> (SDD §7) **Red smoke gate** (B-6; ADR-0007): gate run reports red → `/afk:autopilot` runs the shared fix procedure once per failing scenario through a fix helper that commits on the feature branch, rebuilds the app → one full gate re-run → second red ends the run red.
> (SDD §10) | Re-runs of a failure before diagnosing (count) | 1 | procedure-caller tests | shared fix procedure |
> (SDD §10) | Smoke-gate re-runs after in-place fixes (count) | 1 | autopilot plan test | `/afk:autopilot` |
> (SDD §14 row "`/afk:execute` fix points and limits") INV-023: Step 8 red → retry → fix, Step 10 by class, 10.5; statuses `execute/SKILL.md:120-133`; out-of-Scope → `blocked`; no tracker `:12`; this branch `:30`; "only execute commits" `:142` | steps point at the procedure; step numbers and caps kept; "only execute commits" widens to autopilot's and preflight's fix helpers; V-4 out of slice → `design_conflict` cited, `needs_decision` uncited; out-of-slice sibling file | INV-023: `test_execute_step_pointers.py:44`; mission-control insights regexes `insights.py:23-24`; `test_fail` text | cherry-pick carries the bug work id, not the slice prefix (`review/SKILL.md:23`); re-run from Step 8; never `--no-verify`
> (SDD §14 row "`/afk:preflight` PF-3/PF-4 …") INV-023: PF-3/PF-4 route to fix (`preflight/SKILL.md:99,125`) | procedure results map to PF park reasons
> (SDD §14 row "`/afk:smoke-test` red gate with `/afk:autopilot`") INV-023: never patches a red run (`smoke-test/SKILL.md:53,80`); autopilot `:67` | autopilot runs the procedure once per failing scenario between gate runs; gate report-only; one re-run; second red ends red | INV-023: app rebuild after a code change (autopilot `:36`); scoped runs never stamp (`:29`) | full re-run before stamping; comment gate and rationale on the fix commits
> (SDD §14 row "`JOURNAL-FORMAT` events and `/afk:autopilot` report") … a `flaky` line … | new token = same-commit edit to `JOURNAL-FORMAT.md`

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0006-fix-procedure

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

## Goal
Rewrite `/afk:diagnose` so it never changes product code: it reproduces the bug with a failing test, compares it with the specs, finds the root cause and writes `DIAGNOSIS.md` with a verdict and a fix proposal. Teach both grills to take a diagnosis and end with a size call (G-1), recorded as a row in their own grill-log section, through a size-call file beside the requirements grill.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 L2 — Service Boundaries & Integration — API contract row "`/afk:diagnose` with a ticket key or a quoted description"
- SDD: SDD.md#§4 L3 — Data Architecture — rows "Diagnosis branch", "Diagnosis worktree"
- SDD: SDD.md#§7 L6 — Process & Coordination — "Size call"
- SDD: SDD.md#§8 L7 — Module Decomposition — rows "diagnose skill", "size-call file"
- ADR: adr/design/0002-diagnosis-file-is-the-hand-off-and-the-state.md — the file is the hand-off; grills accept it; size-call row

## Scope
- skills/utils/diagnose/SKILL.md
- skills/utils/diagnose/scripts/hitl-loop.template.sh
- skills/afk/grill-requirements/SIZE-CALL.md
- skills/afk/grill-requirements/SKILL.md
- skills/afk/grill-requirements/GRILL-LOG-FORMAT.md
- skills/afk/grill-solution/SKILL.md
- BEHAVIORS.md
- scripts/tests/test_behavior_registry_gate.py
- hooks/tests/hook-smoke.sh
- skills/afk/fix/SKILL.md
- CHANGELOG.md

## Seams
- implement: `/afk:diagnose` never fixes — the fix and regression-test phases leave the skill (INV-022)
- implement: grills: `/afk:grill-requirements`, `/afk:grill-solution` — accept a diagnosis and end with the size call (INV-022)

## Acceptance
- [ ] A diagnose run leaves product code unchanged; the only code it adds is the failing test that reproduces the bug (PRD AC-001)
- [ ] Diagnose takes exactly one of a ticket key the tracker returns or a non-empty description; with neither it asks when a person is present, else ends `blocked`, and writes nothing (SDD §3)
- [ ] `DIAGNOSIS.md` is written per the diagnosis format file into the bug's spec folder before any tracker or forge call (PRD AC-008)
- [ ] Diagnose runs the diagnosis check script at its end and prints `DIAGNOSIS: <verdict> <path>` plus the plain-terms sentence; run alone, it offers the fix and writes no ticket (PRD AC-010)
- [ ] A full diagnosis reproduces the bug on a clean copy of the base branch before it names a root cause; a light diagnosis names the reproduction it reused and still records spec comparison, root cause and verdict (PRD AC-005, AC-006)
- [ ] A standalone run works in its own worktree off the base branch, made in owned mode, and keeps the failing test on a local lower-cased branch from the branch template; diagnose never pushes it (SDD §4 row "Diagnosis branch")
- [ ] Run on a branch other than the base branch, diagnose asks once whether to start from that branch's tip or the base branch and records the answer as Base (SDD §3)
- [ ] A re-run rewrites verdict, root cause and proposal, empties Approval, and keeps ticket key, Outside writes and Base (SDD §3)
- [ ] The "§Phase 2.5 — Trace the path" heading stays word for word, as do the investigate and rationale-read steps, the name, the language pointer and the hitl template; the description no longer promises a fix or a regression test, and Phase 2.5's cross-references no longer point at removed phases (SDD §14 row "`/afk:diagnose` never fixes")
- [ ] `/afk:fix` works at this commit: its diagnose phase takes the diagnosis's fix proposal and applies it test-first until the diagnosis's failing test passes, so no caller relies on diagnose fixing (PRD AC-017)
- [ ] Both grills accept a `DIAGNOSIS.md` as input; a grill handed one records its size call as a size-call row in its own grill-log section (SDD §7)
- [ ] The size-call file names `/afk:fix` only as a bounce target and never names a caller (SDD §14 row "grills: `/afk:grill-requirements`, `/afk:grill-solution`")
- [ ] A solution grill run without a PRD ends at the size call and never hands on to `/afk:to-sdd` (SDD §7)
- [ ] The grill-solution description stays valid unquoted YAML (SDD §14 row "grills: `/afk:grill-requirements`, `/afk:grill-solution`")
- [ ] Implements SDD §8 rows "diagnose skill" and "size-call file" unmodified (SDD §8)

## Produces
- skills/utils/diagnose/SKILL.md#DIAGNOSIS: <verdict> <path> — the run's final status line
- skills/afk/grill-requirements/SIZE-CALL.md#Size call (G-1) — the size-call procedure both grills point at
- skills/afk/grill-requirements/GRILL-LOG-FORMAT.md#Size-call row — the row grammar `/afk:fix` reads before changing code

## Consumes
- 0001-diagnosis-format skills/utils/diagnose/DIAGNOSIS-FORMAT.md#Required parts per verdict — the fields diagnose writes
- 0001-diagnosis-format skills/utils/diagnose/scripts/check_diagnosis.py#def check_diagnosis( — run at diagnose's end

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged` (skill registry, genericity, behaviour registry); grep each ## Produces anchor | prose gates pass; the Phase 2.5 doctrine heading still resolves |
| unit | `afk-python -m pytest scripts/tests/test_behavior_registry_gate.py scripts/tests/test_behavior_registry.py scripts/tests/test_skill_frontmatter.py -q` | doctrine home and frontmatter pins hold |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §3) | `/afk:diagnose` with a ticket key or a quoted description; a light diagnosis adds the reproduction it reuses (a check name with its output file, or a finding id) | a developer; an agent caller for B-8, B-9, B-10 | no role; a product-code change is refused to every caller | exactly one of: a ticket key the tracker returns, or a non-empty description; neither → asks when a person is present, else `blocked`. Run on a branch other than the base branch → asks once: that branch's tip or the base branch; records the answer | `DIAGNOSIS.md` in the spec folder, then `DIAGNOSIS: <verdict> <path>` and the plain-terms sentence; run alone, it offers the fix | `blocked` (input missing, ticket unreadable, spec folder unresolved). Cannot reproduce is a verdict, not a failure | rewrites verdict, root cause, proposal; empties approval; keeps ticket key, outside writes and the recorded starting branch | breaking: callers that relied on diagnose fixing move to `/afk:fix` (§14) |
> (SDD §4) | Diagnosis branch | local git branch from the branch template, made from the Base tip | one per diagnosis | pushed only by `/afk:fix` | until a fix ships it or the developer deletes it; the plugin deletes none |
> (SDD §4) | Diagnosis worktree | a linked worktree off the Base branch, made in the owned mode (name and base given) | one per diagnosis | none | retired by `/afk:fix` at its end, from outside it, through the plugin's remove script … a stopped diagnosis keeps its worktree and names it |
> (SDD §7) **Size call** (B-7; ADR-0002): a grill handed a diagnosis records its size call in its own grill-log section; "still small" sends the bug back to `/afk:fix`, which reads that row before changing code; "too big" goes to the requirements grill. A solution grill run without a PRD ends at the size call and never hands on to `/afk:to-sdd`.
> (SDD §14 row "`/afk:diagnose` never fixes") writes `DIAGNOSIS.md` only; asks the starting branch off the base branch; drops the hand-off to an unshipped skill | … | keep the "§Phase 2.5 — Trace the path" heading word for word, the investigate and rationale-read steps, name, language pointer, hitl template; rewrite the description (`:3` says "→ fix → regression-test") and the Phase 2.5 cross-references to Phases 3 and 6 (`:91`)
> (SDD §14 row "grills: …") accept `DIAGNOSIS.md`; grill-solution runs without a PRD and then ends at the size call, never handing on to `/afk:to-sdd`; the size call is a new row shape in `GRILL-LOG-FORMAT.md`, written in the grill's own section; size-call file names fix only as a bounce target | … | gap-routing may name the owner, never the caller; fix and grill-solution descriptions are unquoted YAML (`test_skill_frontmatter.py:86`)
> (PRD G-1) the size call: a bug that is still small goes back to `/afk:fix`. A larger bug goes into the full chain until a medium lane exists (#108).

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0001-diagnosis-format

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

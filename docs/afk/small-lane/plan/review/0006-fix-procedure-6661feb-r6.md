# Review — 0006-fix-procedure round 6

- policy: lean · delta round 6 (6661feb..2cfd96b before the rebase onto main; 1bda3b7..0021bc3 after it), scope-escalated (copies again in round 5) · activated: delta-sweep, consistency-sweep (scope escalation, 65 fixed keys), test-veracity (delta edits test code), logic-correctness (delta touches 5 files) · skipped: fix-owner specialists (round 5 had no critical or high finding), scope-and-impact (every path is in Scope or added by D-41 or D-44), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 6 upheld / 0 downgraded / 0 dropped (10 raw findings, 4 merged as duplicates)
- verdict: advisory — 0 high, 2 medium, 4 low
- shape: two callers of a round 5 fix left stale (the fix skill ran the lesson step twice after a step 7 design conflict; its exit gate and verdict bullet still stopped the two-way-door path); two unrestored or unrouted branches in the procedure; one untested table half
- Gate outcome: 5 fixed in place (f066-f070); f071 (low smell) deferred to the feature gate under the lean policy
- head: 1b51818f12cc43e0e6908b286c19700137aa5401
- counts: crit=0 high=0 med=2 low=4

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:56`
The delta made procedure step 7 run step 8 itself before it returns `design_conflict`. Its caller, fix Phase 3, still runs Phase 3.5 (step 8 again) after that return, so a fix-skill design conflict appends the workflow lesson twice under two lesson ids.

- Why: skills/afk/review/checklists/delta-sweep.md:9 "the change edits a shared symbol, signature, or util without updating all direct callers"; skills/afk/lessons/LEDGER-FORMAT.md:27-28 "writers add lines at the end via the appender; **nobody edits or deletes a prior line**", so the duplicate lesson cannot be removed.
- Fix: In skills/afk/fix/SKILL.md:56 drop "run Phase 3.5," from the `design_conflict` branch (step 7 has already run step 8), e.g. "Its `design_conflict` → keep the fix in the tree (skip the procedure's revert) and report `design_conflict`, naming the kept fix and the lesson id step 7 recorded".
- Concern: delta-sweep,logic-correctness,consistency-sweep
- Key: 0006-fix-procedure/f066 — fixed

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:37`
The delta added a two-way-door branch that sends a non-small V-2, V-3 or V-4 diagnosis to step 3, but the bullet still opens with "stop with no code change", and the Phase 1 Exit gate still admits only V-1 or a `still small` V-2/V-3. An agent on the new path either stops at the bullet head or fails the Exit gate after applying the fix.

- Why: skills/afk/review/checklists/delta-sweep.md:8 "a fix applied at one site while a sibling path keeps the old behaviour"; the slice brief treats a contradiction or an instruction an agent cannot carry out as a defect.
- Fix: Restructure SKILL.md:37 so "stop with no code change" covers only the non-door cases (e.g. lead with the binding-decision classification, then "Otherwise stop with no code change and report `blocked`..."), and widen the Exit gate at SKILL.md:44 to "verdict V-1, a V-2/V-3 whose latest size-call row is `still small`, or a two-way-door decision recorded per `DECISIONS.md`".
- Concern: delta-sweep,logic-correctness,consistency-sweep
- Key: 0006-fix-procedure/f067 — fixed

## r-003 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:117`
The new step 4 `blocked` exit fires on the run with the step 3 fix reverted ("passes with the fix reverted"), and nothing says to restore the fix before returning. The step 6 red-then-green exit has the same gap. The procedure then returns `blocked` with the fix missing from the tree, while the Record says `blocked` leaves the edits made so far and lists them under Edits.

- Why: skills/afk/fix/IN-PLACE-FIX.md:216-217 "`fail`, `adversary_fail` and `blocked` leave the edits made so far, listed under Edits." The caller's retry loop (SDD §3 "the caller's loop decides retries") then works from a tree whose Edits field names a fix that is no longer there. Failing input: a seam unit test that step 4 adds which passes on the reverted tree.
- Fix: In step 4 write: "... → restore the step 3 fix, then return `blocked`, naming it." Give the step 6 sentence the same restore.
- Concern: logic-correctness
- Key: 0006-fix-procedure/f068 — fixed

## r-004 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:175`
Possible missing branch: a one-way-door change to a binding SDD decision now records a workflow lesson when step 7 finds it, but not when step 3 finds it. Step 3 returns `design_conflict` directly. Step 8 would skip anyway, because at step 3 no miss class has been named and no stale artifact recorded. The same wrong frozen decision leaves a lesson or none, depending on which step finds it.

- Why: The reason the delta gave step 7 its step 8 run is PRD AC-023 "A fix keeps escape analysis, spec reconciliation and the workflow lesson in both modes" (fixed key f059). skills/afk/fix/WORKFLOW-FEEDBACK.md:33 maps "A frozen SDD decision was wrong or infeasible" to a stage, and this case reaches that row only through step 7.
- Fix: In step 3, for a one-way door or a tie on a binding SDD or ADR decision: record the SDD as a stale artifact, run step 8, then return `design_conflict`. Or state that a design conflict found at step 3 records no lesson.
- Concern: logic-correctness
- Key: 0006-fix-procedure/f069 — fixed

## r-005 · low · test · `scripts/tests/test_fix_procedure.py:42`
Possible gap: the trace test pins only the miss-class half of the workflow-feedback table. The stale-artifact half that fixed key f065 added (three rows matching procedure step 7's table) has no check, so the defect f065 fixed can come back with the suite green. Mutation probe on a scratch copy: all three new rows deleted from WORKFLOW-FEEDBACK.md, and the 21 non-shell tests still passed.

- Why: D-44 restates a contract 0006 acceptance bullet as "The procedure keeps escape analysis and the workflow lesson, and records each stale artifact for its caller to reconcile (PRD AC-023)" (docs/afk/small-lane/plan/DECISIONS.md:308); WORKFLOW-FEEDBACK.md:20-21 maps "the stale artifact from procedure step 7" to a stage, so each step 7 row needs a trace row, the way each miss class does.
- Fix: Add a test that reads the 'Stale artifact' column of IN-PLACE-FIX.md step 7's table and asserts each artifact has a row in WORKFLOW-FEEDBACK.md's trace table, for example by a map of artifact to its expected trace phrase ({'PRD.md': 'PRD asserted', 'SDD.md': 'frozen SDD decision', 'VERIFICATION-PLAN.md': 'No verification scenario', 'plan/NNNN-slug.md': 'subtask contract shifted'}) checked against both tables. Optionally also run lesson-append.sh opened with --class wrong-design and no --miss, the stale-artifact-alone append LEDGER-FORMAT.md:91-92 defines.
- Concern: test-veracity
- Key: 0006-fix-procedure/f070 — fixed

## r-006 · low · smell · `skills/afk/fix/WORKFLOW-FEEDBACK.md:34`
Possible drifted twin: the new stale-artifact row "No verification scenario would catch the bug" repeats the `no-scenario` row (same gap, same stage, same skills), but the two take different lesson classes: `no-scenario` maps to `missing-instruction`, while a stale artifact alone takes `wrong-design`. The same verification-design gap is then classified two ways in the ledger, depending on whether escape analysis ran.

- Why: LANGUAGE.md:21 "One term, one meaning — and one meaning, one term."; skills/afk/lessons/LEDGER-FORMAT.md:75 defines `wrong-design` as "A grill/design stage accepted a wrong premise a later stage disproved", not a missing scenario.
- Fix: Pick one class per gap: either give the stale-artifact rows their own class mapping in LEDGER-FORMAT.md (e.g. the `no verification scenario` row takes `missing-instruction`, like `no-scenario`), or fold the new row into the `no-scenario` row as "`no-scenario`, or no verification scenario would catch the bug".
- Concern: delta-sweep
- Key: 0006-fix-procedure/f071 — deferred gate=feature

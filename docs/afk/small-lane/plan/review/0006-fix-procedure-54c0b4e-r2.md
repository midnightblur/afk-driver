# Review — 0006-fix-procedure round 2

- policy: lean · delta round 2 (54c0b4e..5693ac2) · activated: delta-sweep, spec-fidelity, scope-and-impact, refactor-safety, logic-correctness (each owned the round 1 high finding), test-veracity (delta adds test code) · skipped: api-contract, domain-alignment (no trigger), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level concern ran)
- verdict: advisory — 0 high, 6 medium, 7 low
- Gate outcome: all 13 fixed in place (f023-f035); D-42 records the catalog-scenario and workflow-lesson decisions
- head: 5693ac291666a70d55466a733c6cffdb252d9301
- counts: crit=0 high=0 med=6 low=7

## r-001 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:102`
Step 3 now lets a failing build or lint command be the red check with no test written, but step 4 still treats the step 3 test as always existing.

- Why: The delta edited step 3 (IN-PLACE-FIX.md:86-89) without updating its dependent in step 4; no seam regression test exists to anchor the watch-it-fail-with-the-fix-reverted check for a build or lint failure.
- Fix: In step 4 say: the step 3 test, when step 3 wrote or ran one, is the seam regression test; for a build or lint red check the red check itself is.
- Concern: delta-sweep

## r-002 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:170`
The closing sentence says a stale artifact never changes the result, but the paragraph 8 lines above returns design_conflict for a stale frozen SDD decision.

- Why: Two instructions in step 7 give opposite answers for the same case; the results table (IN-PLACE-FIX.md:214) lists step 7 as a design_conflict source.
- Fix: Reword to: a stale artifact changes the result only through the design_conflict rule above.
- Concern: delta-sweep

## r-003 · medium · spec · `skills/afk/fix/IN-PLACE-FIX.md:27`
The Caller paths rule now lets an in-place fix change catalog scenarios outside the caller paths. D-41 (b) allows it, but its Supersedes line names neither the SDD row nor the execute Scope rule that say work outside Scope is blocked.

- Why: docs/afk/small-lane/SDD.md:647 lists out-of-Scope = blocked as an execute fix limit, and skills/afk/execute/SKILL.md:79 stops with blocked for work outside Scope; a Supersedes line overrides only the exact passage it quotes, and D-41 quotes only the 0006 Scope list and D-40.
- Fix: Add the SDD 14 row out-of-Scope = blocked and the execute Scope hard rule to the Supersedes line of D-41, or limit the catalog exemption to callers whose own paths include the catalog.
- Concern: spec-fidelity

## r-004 · medium · test · `scripts/tests/test_fix_procedure.py:91`
Possible tautology: the test feeds each miss class to lesson-append.sh and asserts the same strings come back, so it passes for any string and never reads the procedure. Its name promises a finding id, but it asserts source 0001-slice.

- Why: Meszaros mock echo: assert real output, not the input echoed back. hooks/lesson-append.sh:85-86 copies --miss verbatim with no enum check (only --class is checked, :60).
- Fix: Rename it to say it tests hook pass-through, or assert something the procedure owns: pass the class the LEDGER-FORMAT mapping gives for each miss, and check step 8 of IN-PLACE-FIX.md names --miss and the finding id.
- Concern: test-veracity

## r-005 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:105`
Step 4 tells the agent to watch each added test fail with the fix reverted, but the only instruction to restart the running instance is in step 5. A live-tier (api or e2e) test run after the revert hits an instance still running the fixed or older code, so the red-then-green proof is false.

- Why: skills/afk/fix/IN-PLACE-FIX.md:131 ties a live tier to an instance restarted on the working tree; step 4 has no such restart, so the proof it demands cannot be carried out for the tiers step 4 itself names (api, e2e/browser, lines 112-113).
- Fix: In step 4, say: for a live-tier test, restart the handed-over instance after the revert and again after the restore, or limit the revert proof to tests that need no running instance.
- Concern: logic-correctness

## r-006 · medium · correctness · `skills/afk/fix/SKILL.md:55`
On a procedure design_conflict from step 7 the skill now keeps the fix in the tree, though the procedure defines that result as No fix and reverts. The fix was applied against a binding decision that is a one-way door or a tie, so an uncommitted fix that contradicts it stays for whoever commits, and the skill states no rule that stops that commit.

- Why: skills/afk/fix/IN-PLACE-FIX.md:201-203 says design_conflict, needs_decision and flaky leave no edit of the fix in the working tree; :214 says No fix. SKILL.md:87 says the Uncommitted rule binds, but no line keeps the human from committing the kept fix.
- Fix: Either revert on design_conflict as the procedure does and run Phase 3.5 from the record, or state in Phase 3 that the kept fix stays uncommitted until the superseding ADR lands and the report names it.
- Concern: logic-correctness

## r-007 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:131`
Step 5 orders the agent to restart the caller running instance, but the intake gives no restart command or permission, so the agent cannot carry out the restart.

- Why: An instruction the agent cannot carry out is a defect. Intake line 17 hands over only the running instance, when there is one; no restart means is named.
- Fix: Add to intake the command that restarts the instance on the working tree; in step 5 restart with it, and when the caller hands over none, return blocked naming the live tier.
- Concern: delta-sweep,logic-correctness

## r-008 · low · compliance · `skills/afk/fix/SKILL.md:14`
The rewritten pointer paragraph is one long sentence chain of about 70 words with a fragment: Which of its hard rules bind: Hard rules.

- Why: LANGUAGE.md:19 Short sentences, one point each (aim <= 20 words); one instruction per sentence.
- Fix: Split into one sentence per handed-over item and end with: The Hard rules section lists which procedure rules bind.
- Concern: delta-sweep

## r-009 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:55`
Step 1 files a passing re-run under miss class disabled/flaky, whose owning definition means a guard skipped, quarantined or green on a swallowed error; a check that merely passed on re-run is not covered, so the lesson routes to the wrong stage.

- Why: ESCAPE-ANALYSIS.md:29 defines the class and WORKFLOW-FEEDBACK.md:30 maps it to a built guard left skipped/quarantined; the new use matches neither.
- Fix: Add a flaky-check clause to the disabled/flaky row in ESCAPE-ANALYSIS.md (the set single owner) and to the WORKFLOW-FEEDBACK.md:30 row.
- Concern: delta-sweep,scope-and-impact

## r-010 · low · spec · `skills/afk/fix/WORKFLOW-FEEDBACK.md:6`
The delta replaced the pointer to the Unreleased feature signals with a two-signal restatement (branch pattern, PLAN.md present). The fix skill session-type step still uses three signals, so a shipped feature, or a failure from outside the feature verification, now gets a lesson.

- Why: skills/afk/fix/SKILL.md:25 uses the signals in IN-PLACE-FIX.md Unreleased feature (three signals incl. Feature line not yet shipped); AGENTS.md DRY: one fact, one home.
- Fix: Point the applicability sentence back at IN-PLACE-FIX.md Unreleased feature and keep only the no-miss-class-and-no-stale-artifact skip addition.
- Concern: spec-fidelity

## r-011 · low · test · `scripts/tests/test_fix_procedure.py:60`
Possible false green: the stale-pointer scan matches only the shape fix/SKILL.md Phase N; a pointer worded fix skill Phase 2 passes unseen. The pointer test at line 56 checks only the substring IN-PLACE-FIX.md, not that the cited step exists.

- Why: Meszaros happy-path-only: the guard covers one phrasing of the defect that D-41 (a) fixed in ROUND.md.
- Fix: Widen the regex to other fix ... Phase N phrasings, or assert each pointer step N resolves to a heading N. in the procedure.
- Concern: test-veracity

## r-012 · low · test · `scripts/tests/test_fix_procedure.py:70`
Possible fragile pin: the test asserts one prose sentence verbatim, so a rewording that keeps the rule breaks it, while a logic change to step 1 can leave it green.

- Why: Meszaros fragile test: assert behaviour, not incidental wording.
- Fix: Assert structure (step 1 heading, a bullet returning flaky, no step before it) and drop the exact-sentence match.
- Concern: test-veracity

## r-013 · low · correctness · `skills/afk/fix/SKILL.md:25`
Possible behaviour change: an ad-hoc run of /afk:fix no longer skips the workflow-lesson phase at intake; the skip moved to WORKFLOW-FEEDBACK.md, whose gate drops the old unreleased-feature signals.

- Why: Delta changed Ad-hoc skip Phases 3 and 3.5 to skip Phase 3; the earlier WORKFLOW-FEEDBACK gate was an unreleased feature built with AFK assistance (signals in IN-PLACE-FIX.md Unreleased feature). A refactor must preserve behaviour (checklist refactor-safety).
- Fix: Restore skip Phases 3 and 3.5 in fix/SKILL.md step 2, or keep the WORKFLOW-FEEDBACK gate on the Unreleased feature signals and record the narrowing as a decision.
- Concern: refactor-safety

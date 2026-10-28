# Review — 0006-fix-procedure round 5

- policy: lean · delta round 5 (63c4b00..6661feb), scope-escalated (copies again in round 4) · activated: delta-sweep, consistency-sweep (scope escalation, 54 fixed keys), test-veracity (delta edits test code), logic-correctness (delta touches 6 files) · skipped: fix-owner specialists (round 4 had no critical or high finding), scope-and-impact (inline Scope grep: every path is in Scope or added by D-41), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 11 upheld / 0 downgraded / 0 dropped (14 raw findings, 3 merged as duplicates)
- verdict: advisory — 0 high, 6 medium, 5 low
- shape: branches the procedure and the fix skill left unrouted (blocked from steps 4 to 6, restart on the diagnosis worktree, lesson on a step 7 conflict); two copies outside Scope (capture trigger, glossary)
- tooling: the forge adapter's thread-list passes the review graph as one argument and hit the Windows argument limit; the gate and later calls ran with a scratch copy of the plugin that reads it from a file
- Gate outcome: all 11 fixed in place (f055-f065); D-44 records the Scope additions and the contract bullet
- head: 6661febf4518c523c3c5bfded1cb0de8afbe991d
- counts: crit=0 high=0 med=6 low=5

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:28`
Phase 0 step 5 takes the restart command before Phase 1 decides where the fix lives, and diagnose usually cuts a new worktree for it. The command the invoker named restarts the instance from the invoker's checkout, so the live checks in steps 4 and 5 run against code without the fix. The skill never names the diagnosis worktree as the procedure's working tree, or the tree the restart must serve.

- Why: IN-PLACE-FIX.md:43-45 lets a live check run 'only after the caller's restart command has restarted that instance on the current working tree'. Failing input: a human in checkout A runs `/afk:fix KEY` and names instance :8080 with restart `./run.sh`. Diagnose Phase 0 step 4 cuts worktree B (`create-worktree --name ...`) and the fix lands in B (SKILL.md:40). `./run.sh` serves A, so step 5's api check stays red → Phase 2 reports `blocked`, or the step 4 revert proof runs against A and proves nothing.
- Fix: Line 14: 'The procedure's working tree is the diagnosis worktree Phase 1 step 3 picks.' Phase 0 step 5, or a new Phase 1 step after step 3: ask for or derive a restart command that serves that worktree, and ask again when Phase 1 moved the fix to a worktree the named command does not serve.
- Concern: logic-correctness,delta-sweep

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:40`
Fixed keys f027, f036 and f040 established that a live-tier test proves nothing after a code change unless the instance is first restarted on the current tree. The procedure's Live tiers rule now states this. Fix Phase 1 step 3 still watches the diagnosis's failing test fail, applies the fix and watches it pass with no restart. Line 33 steers that test toward an api or e2e/browser loop, and line 14 applies the Phase 0 step 5 restart command only to the procedure's steps.

- Why: IN-PLACE-FIX.md:43-46 "A check that runs against the running instance runs, in any step, only after the caller's restart command has restarted that instance on the current working tree."; SKILL.md:14 "Its running instance and restart command are the ones Phase 0 step 5 takes; with none, a live tier ends the procedure `blocked`."
- Fix: In Phase 1 step 3 add: a failing test that runs against the running instance runs only after the Phase 0 step 5 restart command restarts the instance on the working tree, both before the red run and after the fix is applied. With no instance or restart command, stop `blocked`, naming the test. Alternatively, extend line 14 so the procedure's "Live tiers" rule binds Phase 1 too.
- Concern: consistency-sweep

## r-003 · medium · test · `scripts/tests/test_fix_procedure.py:58`
Possible false green and false red: the delta widened CITED_STEP from 'then its' to a bare '\bits', which now also matches 'its step 4' in AGENTS.md, where 'its' means autopilot, not the procedure. That match satisfies the non-empty guard for AGENTS.md, so deleting AGENTS.md's only real procedure citation ('IN-PLACE-FIX.md` step 8') leaves the suite green, while a legitimate renumbering of autopilot's step fails it.

- Why: The test's own contract: scripts/tests/test_fix_procedure.py:55-56 "A cited procedure step: ... "its step N" ... every cited number must be a procedure step." and :85 "assert cited and cited <= _procedure_steps()" (the non-empty guard added for fixed key f039, whose fix asked to "assert a non-empty cited set per file"). Checklist skills/afk/review/checklists/test-veracity.md:9-10 (assert real output; no weaker proxy) and :16 (fragile test breaks on an unrelated change, not on the bug).
- Fix: Drop the bare '\bits' alternative and reword skills/afk/fix/SKILL.md:48 to 'then procedure step 5 ... as the procedure's step 1 failure', or replace the regex check with a per-file expected-citation map (for example {'AGENTS.md': {'8'}, 'skills/afk/lessons/LEDGER-FORMAT.md': {'1', '6', '7'}, ...}) and assert the cited set per file equals it.
- Concern: test-veracity

## r-004 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:115`
Step 4 and step 6 each demand a red-then-green proof but give no branch when it fails: a test step 4 adds that still passes with the fix reverted, or a scenario step 6 strengthens in place that never goes red (or never goes green). Step 3 has that branch ('a test that does not → return blocked'), steps 4 and 6 do not, and the results table maps `fail` only to step 5.

- Why: Every path an agent can reach must end in one of the seven results (contract 0006 Acceptance: 'returns exactly one of `fixed`, `fail`, `blocked`, ...'). Failing input: a logic bug where the seam unit test step 4 adds passes on the reverted tree — the agent has no instruction, and a guard that cannot fail is recorded as proof.
- Fix: In step 4 add: 'An added test that passes with the fix reverted, or fails with it restored → return `blocked`, naming it.' Give step 6 the same sentence for the scenario it fixes in place (or point step 6 at the step 4 rule).
- Concern: logic-correctness

## r-005 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:173`
A step 7 `design_conflict` returns before step 8, so an in-place caller records no workflow lesson for a frozen SDD decision proved wrong, even when step 6 named a miss class. The fix skill does the opposite for the same return: it runs Phase 3.5 (step 8) after step 7's `design_conflict`. The flaky branch shows the procedure states 'run step 8, and return' when it means it; step 7 does not.

- Why: PRD AC-023: 'A fix keeps escape analysis, spec reconciliation and the workflow lesson in both modes.' The Lesson hard rule (IN-PLACE-FIX.md:35-36) binds 'when step 8 applies', and WORKFLOW-FEEDBACK.md:6-11 makes it apply whenever a miss class or stale artifact exists on an unreleased feature; LEDGER-FORMAT.md:91-92 gives a stale-artifact lesson the class `wrong-design`, exactly this case.
- Fix: In step 7 write: 'a one-way door or a tie → run step 8, then return `design_conflict`', and keep the revert rule as is.
- Concern: logic-correctness

## r-006 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:52`
The Unreleased feature test cannot be evaluated as written. It lists three signals without saying whether all or any must hold, and 'a `Feature:` line ... not yet shipped' names a state the line never takes: the line holds `in-progress`, `smoke-failing` or `complete (...)`. A preflight fix on a plan stamped `Feature: complete (smoke green ...)` is unreleased, but an agent reading 'complete' as shipped skips step 7 and the lesson. In the fix skill the test also reads 'the spec folder', which Phase 0 step 3 locates only after step 2 has decided the session is a feature session.

- Why: D-42 (b) makes this test the one gate for step 7 and the lesson: 'the fix skill's session type and the procedure's step 7 use the same three signals, so one test decides both steps; a shipped feature or a failure from outside the feature's own verification records no lesson' (DECISIONS.md D-42). A gate whose value is undefined for a reachable input decides those steps at random.
- Fix: Say 'all three hold', and replace 'is not yet shipped' with a test the line supports, e.g. 'the branch's change is not merged' or 'the line is `in-progress`, `smoke-failing` or `complete (...)` and the change is open'. In the fix skill, locate the spec folder before the session-type decision, or let step 2 read `plan/PLAN.md` from the spec folder the notes adapter resolves.
- Concern: logic-correctness

## r-007 · low · correctness · `skills/afk/fix/SKILL.md:48`
The delta gave Phase 2.5 a route for a `blocked` return from procedure step 6, but left its sibling Phase 2 without one. Phase 2 runs steps 4 and 5, and both can return `blocked` under the Live tiers rule (no instance or no restart command). Phase 2 routes only a check that is "still red", and a `blocked` return is not a red check.

- Why: Delta-sweep item: "a fix applied at one site while a sibling path keeps the old behaviour". skills/afk/fix/IN-PLACE-FIX.md:43-46 "A check that runs against the running instance runs, in any step, only after the caller's restart command has restarted that instance ... A live check with no instance or no restart command handed over → return `blocked`, naming the check." skills/afk/fix/IN-PLACE-FIX.md:116-117 puts step 4's live-tier runs under that rule, and :141-142 puts step 5's live tiers under it.
- Fix: Append to Phase 2 the same line Phase 2.5 got: "A `blocked` return → report `blocked`, naming it." Alternatively, state the route once for every phase that runs a procedure step.
- Concern: delta-sweep,logic-correctness

## r-008 · low · correctness · `skills/afk/fix/SKILL.md:37`
Fixed keys f007 and f048 narrowed `design_conflict` to a binding-decision change that is a one-way door or a tie, where a two-way door is decided and recorded. Phase 1 still reports `design_conflict` for any wrong binding SDD/ADR decision, with no door classification. So a two-way-door case at Phase 1 gets a status that the skill's own Phase 4 table does not define for it.

- Why: SKILL.md:76 "The fix needs a frozen SDD/ADR decision changed, and that change is a one-way door or a tie"; IN-PLACE-FIX.md:102-105 "Classify each fork by `DECISIONS.md` (plugin root). A two-way door is decided, recorded, and the fix goes on. A one-way door or a tie → return `design_conflict`"; IN-PLACE-FIX.md:172-173 "Classify a change to a frozen SDD decision by `DECISIONS.md` as in step 3: a one-way door or a tie → return `design_conflict`"
- Fix: In Phase 1 step 2, classify the wrong decision by `DECISIONS.md`: a one-way door or a tie → report `design_conflict`, naming the decision. A two-way door → record it in `plan/DECISIONS.md` and go on to step 3 with the recorded decision. Or, if Phase 1 must stop on every wrong decision, widen the Phase 4 `design_conflict` row to cover the diagnose-time case.
- Concern: consistency-sweep

## r-009 · low · spec · `skills/afk/fix/IN-PLACE-FIX.md:159`
Fixed keys f010 and f053, recorded as D-43 (b), made the procedure only record stale artifacts: it runs no owning skill and the caller reconciles. Contract 0006's Acceptance still says the procedure itself keeps spec reconciliation. D-43's Supersedes line quotes D-40 (c) but not this bullet, so a fidelity check against the contract can still demand reconciliation from the procedure.

- Why: DECISIONS.md:300 "(b) record: the Ownership rule forbids an edit across an ownership boundary, and the fix skill routes from the record in its Phase 3. Every stale artifact goes to the caller; no artifact is one the procedure \"cannot reconcile\"."
- Fix: Add a ledger entry, or extend the next one, whose Supersedes line quotes contract 0006 "The procedure keeps escape analysis, spec reconciliation and the workflow lesson (PRD AC-023)". Make it read: the procedure keeps escape analysis, records stale artifacts for the caller to reconcile, and keeps the workflow lesson.
- Concern: consistency-sweep

## r-010 · low · correctness · `skills/afk/lessons/LEDGER-FORMAT.md:79`
Possible uncorrected copy. Fixed key f049 corrected the idea that a fix lesson comes only from escape analysis: procedure step 1 also names `disabled/flaky`, and a stale artifact alone also yields a lesson. The capture protocol's qualification list still names only "escape analysis names a miss class" as the fix-side trigger. That list ends with "When unsure, don't capture", so a reader who checks it can skip the step 1 flaky lesson or the stale-artifact lesson. The glossary's Lesson entry repeats the same narrow wording.

- Why: LEDGER-FORMAT.md:79-80 "The shared fix procedure (`skills/afk/fix/IN-PLACE-FIX.md` steps 1 and 6) names a **miss class**"; LEDGER-FORMAT.md:91-92 "A lesson from a stale artifact alone (procedure step 7) names no miss class and takes the lesson `class` `wrong-design`."; IN-PLACE-FIX.md:64-65 "The re-run passes → put the miss class `disabled/flaky` into the record, run step 8, and return `flaky`."
- Fix: Reword skills/afk/lessons/CAPTURE.md:18 to "the shared fix procedure names a miss class (`skills/afk/fix/IN-PLACE-FIX.md` steps 1 and 6) or records a stale artifact (step 7)", or point it at `skills/afk/fix/WORKFLOW-FEEDBACK.md`'s gate. Align GLOSSARY.md:344's parenthesis the same way. Record the out-of-Scope edit in the decision ledger.
- Concern: consistency-sweep

## r-011 · low · correctness · `skills/afk/fix/WORKFLOW-FEEDBACK.md:20`
Possible missing branch. After fixed keys f008 and f049, a stale artifact alone triggers a workflow lesson. Step 7 can record four kinds of stale artifact, but the step 1 stage table maps only a wrong PRD. A lesson from a stale SDD, `VERIFICATION-PLAN.md` or subtask contract with no miss class therefore has no implicated stage, and so no `--target` for the append.

- Why: WORKFLOW-FEEDBACK.md:9-11 runs the step unless "procedure steps 1 and 6 named no miss class and procedure step 7 recorded no stale artifact"; WORKFLOW-FEEDBACK.md:40 "**Implicated stage + skill** — from the table."; LEDGER-FORMAT.md:91-92 "A lesson from a stale artifact alone (procedure step 7) names no miss class and takes the lesson `class` `wrong-design`."
- Fix: Add stage rows for the other three stale artifacts in IN-PLACE-FIX.md step 7's table. For example: SDD decision wrong → architecture, `/afk:grill-solution` → `/afk:to-sdd`. No verification scenario → verification design. Subtask contract shifted → slicing, `/afk:to-subtasks`. Alternatively, say a stale artifact with no table row records no lesson.
- Concern: consistency-sweep

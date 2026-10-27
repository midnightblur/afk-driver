# Review — 0006-fix-procedure round 1

- policy: lean · full-unit round 1 (554b28a..54c0b4e) · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (modified lines), logic-correctness (downstream consumers 0008, 0009) · skipped: api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level concern ran)
- verdict: blocking — 1 high, 15 medium, 6 low
- relocated: r-011 (from `skills/afk/grill-requirements/ROUND.md:162`), r-015, r-016, r-022 (from `docs/afk/small-lane/plan/0006-fix-procedure.md:44, 11, 43`) sat outside the diff; each is posted on the changed line it concerns
- Gate outcome: all 22 fixed in place (f001-f022); D-41 records the Scope addition, the catalog clause, the flaky lesson and D-40's corrected ground fact
- head: 54c0b4e4d0fe755f497cc94e53b36cdfdb3f1565
- counts: crit=0 high=1 med=15 low=6

## r-001 · high · correctness · `skills/afk/fix/SKILL.md:87`
The fix skill binds every IN-PLACE-FIX.md hard rule to every run, but those rules forbid what the skill's own phases do: run diagnose (writes DIAGNOSIS.md) and report statuses outside the seven results.

- Why: The skill is left with contradictory binding rules: Phase 1 makes a DIAGNOSIS.md that 'ships with the fix' and Phase 4 reports `cannot_reproduce`, `fixed_no_test` and `needs_artifact_sync`, yet the bound rules say 'Write no DIAGNOSIS.md' and 'Return one result from "In-place fix results"'; also 'paths the caller's work may change' has no caller for a standalone run.
- Fix: Name only the hard rules that bind the fix skill (no-commit, AGENTS.md chain, routing, lesson, tier match, debug cleanup) instead of 'the hard rules ... bind every run'.
- Concern: logic-correctness,refactor-safety,spec-fidelity,scope-and-impact

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:47`
Phases 2 to 3.5 run procedure steps 4 to 8 without supplying the caller inputs those steps read: the tiers the caller's work declares, the paths it may change, its spec folder and a running instance.

- Why: For a standalone fix, step 5's 'every tier the caller's work declares' resolves to nothing, so the tier set it runs is undefined. The old text ran 'every tier you added/touched'. The path rule has no path list to check against.
- Fix: Have Phase 2 state what plays each caller input for a standalone run (for example the tiers the repository declares for the touched paths, and the spec folder from Phase 0 step 3).
- Concern: logic-correctness,scope-and-impact

## r-003 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:82`
A failing build or lint check, which the procedure accepts as input, can only end `blocked` at step 3: only a test check counts as its own red test, and no test can fail 'for the recorded reason' of a compile or lint error.

- Why: Execute Step 8 routes static and compile failures here ('or `build_fail` for a static/compile failure'). Every such input then ends `blocked` and never `fixed`, although step 4's cosmetic row accepts a 'static check' as the guard.
- Fix: In step 3, let a failing build or lint command serve as the red check, in the same way a failing test does.
- Concern: logic-correctness,spec-fidelity,test-veracity

## r-004 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:129`
The step 5 results do not cover every case and can overlap. If a non-tier check stays red for a non-adversary input, no result applies (the step 1 reproduction, the un-minimised scenario, or the running-UI confirmation). If a tier and an adversary reproduction are both red, two results apply.

- Why: Example: a review finding whose reproduction still fails while every tier is green matches neither '→ step 6' nor '`fail`' (which needs a tier) nor '`adversary_fail`'. A red tier together with a red adversary reproduction matches both `fail` and `adversary_fail`, and no order is given.
- Fix: Make `fail` cover any check in step 5 that stays red, and state that `adversary_fail` takes precedence when the input was an adversary finding.
- Concern: logic-correctness

## r-005 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:124`
Live tiers in step 5 run against 'the running instance the caller provides' after the fix. The procedure never rebuilds or restarts that instance, and the inputs the caller hands over do not include it.

- Why: An instance started before the fix still runs the old code. The live api, e2e and adversary reproductions then stay red after a correct fix and return `fail` or `adversary_fail` falsely. The SDD's red-smoke-gate flow rebuilds the app after a code change (SDD.md:367).
- Fix: Add the running instance to the inputs the caller hands over, and have step 5 rebuild or restart it before running a live tier.
- Concern: logic-correctness

## r-006 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:25`
The hard rule 'Change only the paths the caller's work may change' clashes with mandatory writes outside the slice: step 4 always adds a catalog scenario for an adversary finding, and step 6 says to fix an existing scenario in place.

- Why: A slice whose Scope does not list the api or ui-e2e catalog can never fix an adversary finding (step 4 needs another path → `blocked`). The procedure never says whether the corpus ratchet or the path rule wins.
- Fix: State which rule wins: either exempt the step 4 and step 6 catalog writes from the path rule, or say that an adversary finding outside the slice's paths returns `blocked`.
- Concern: logic-correctness

## r-007 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:152`
Step 7 returns `design_conflict` for any frozen SDD decision that is wrong or infeasible. Step 3 and the results table return it only for a one-way door or a tie, and a two-way door is decided and recorded.

- Why: The same fork gets two different results depending on the step that finds it: a two-way-door correction found in step 7 reverts a fix that already passed every tier, and parks the caller.
- Fix: In the step 7 row, classify the fork by `DECISIONS.md` as step 3 does, and return `design_conflict` only for a one-way door or a tie.
- Concern: logic-correctness

## r-008 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:166`
Step 8 records a lesson on every fix of an unreleased feature, but there is no miss class when step 6 skips a unit or logic bug. The lesson append then has no `--class` to map, and the mapping table covers no lesson that comes from a stale artifact.

- Why: Every in-slice unit-tier fix now reaches step 8 without a miss class. The agent must then either make up a class or stop, because `lesson-append.sh` requires `--class` and WORKFLOW-FEEDBACK maps it only from a miss class.
- Fix: Have step 8 skip when step 6 produced no miss class and step 7 no stale artifact, or give a class for a lesson that comes from a stale artifact.
- Concern: logic-correctness

## r-009 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:191`
On `design_conflict`, `needs_decision` or `flaky`, the procedure reverts product edits but keeps the pending `rationale-add` entries it recorded for those edits. The record still lists them, and nothing says to drop them.

- Why: Pending entries sit under the git directory and the caller's later `rationale-post` posts them. They would point at lines the revert removed, and RATIONALE.md's drop rule covers only lines that a later commit rewrote.
- Fix: On a revert, run `rationale-drop` for each pending operation the fix recorded, and list them as dropped in the record.
- Concern: logic-correctness,refactor-safety,test-veracity

## r-010 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:151`
Step 7 tells the procedure to route a stale PRD to `/afk:to-prd` then `/afk:to-ticket` (republish), a ticket write, while the hard rule at line 20-21 forbids any ticket write.

- Why: An agent caller following step 7 ('route it to the owning skill', line 142; 'An artifact this run cannot reconcile goes into the record', line 161 implies the run does reconcile what it can) would republish to the tracker, breaking AC-022's no-ticket-write guarantee.
- Fix: State that the in-place procedure never runs an owning skill itself: it names each stale artifact and its owning skill in the record (as the plan/NNNN-slug.md row already does) and the caller routes it.
- Concern: spec-fidelity

## r-011 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:100`
ROUND.md still says fix Phase 2 states the proportionality doctrine, but this slice moved that text into IN-PLACE-FIX.md step 4.

- Why: Fix Phase 2 is now a one-line pointer. A reader sent there for the doctrine must take a second hop, and the claim 'states it' is now false.
- Fix: Repoint ROUND.md:162 at `../fix/IN-PLACE-FIX.md` step 4 (it is outside this slice's Scope, so record it in the decision ledger or the Scope list).
- Concern: refactor-safety,spec-fidelity

## r-012 · medium · correctness · `skills/afk/fix/SKILL.md:25`
Possible silent narrowing: an ad-hoc session now skips Phase 3.5 as well as Phase 3, and workflow feedback now gates on all the 'Unreleased feature' signals rather than an AFK branch plus `plan/PLAN.md`.

- Why: Before, Phase 0 skipped only Phase 3, and WORKFLOW-FEEDBACK ran whenever the AFK branch and `plan/PLAN.md` signals held. A human-found bug on an AFK-built branch, which is not 'from that feature's own verification', now records no workflow lesson. Neither D-40 nor the contract records this change.
- Fix: Restore 'skip Phase 3' alone and keep WORKFLOW-FEEDBACK's own AFK-built test, or record the narrowing as a decision.
- Concern: refactor-safety

## r-013 · medium · test · `skills/afk/fix/IN-PLACE-FIX.md:123`
Tests that step 4 adds (incl. permanent api/e2e corpus scenarios) are only ever run green after the fix; nothing requires seeing them red against the unfixed code.

- Why: A regression scenario that was never observed failing can pass on the bug too, yet the corpus ratchet marks it permanent as the guard for that ticket or finding.
- Fix: In step 4, require each added test to be watched failing with the step 3 product edit temporarily reverted, then green with it; record both runs.
- Concern: test-veracity

## r-014 · medium · test · `skills/afk/fix/IN-PLACE-FIX.md:52`
One passing re-run returns `flaky` and the caller counts the check as passed, skipping escape analysis and the workflow lesson, so an intermittent guard or an intermittent defect (e.g. a race an adversary reproduced) leaves only a journal line.

- Why: A failure that passes once is proven intermittent, not absent; the plugin's own escape analysis classes this as `disabled/flaky` ("Re-enable + de-flake"), and PRD AC-023 keeps escape analysis and the lesson in every fix.
- Fix: On `flaky`, still change no code but record the `disabled/flaky` miss class and a step 8 lesson (or name a follow-up), so the erratic guard reaches the ledger.
- Concern: test-veracity

## r-015 · medium · test · `skills/afk/lessons/LEDGER-FORMAT.md:79`
The integration tier claims to prove the lesson lockstep via hook-smoke.sh 'lesson append and digest', but hook-smoke.sh never touches the lesson scripts and no test reads the miss-class pair this slice edits.

- Why: The declared check passes whether or not ESCAPE-ANALYSIS.md and the LEDGER-FORMAT.md mapping stay in step, so 'lesson lockstep ... unchanged' is asserted, not proven.
- Fix: Correct the Proves cell, or add a check that compares the ESCAPE-ANALYSIS.md miss-class column with the LEDGER-FORMAT.md 'Miss-class mapping' rows and runs lesson-append.sh opened with --miss/--source.
- Concern: test-veracity

## r-016 · medium · test · `skills/afk/fix/IN-PLACE-FIX.md:58`
The contract cites the SDD §10 NFR 're-runs before diagnosing = 1, measured by procedure-caller tests', but no declared tier here (or in 0009, which also cites it) runs a procedure-caller test.

- Why: The NFR's named measurement never runs, so the one-re-run bound the procedure states is unverified.
- Fix: Add the procedure-caller test the SDD names (here or in 0009's unit tier), or record an IOU anchored to the slice that will own it.
- Concern: test-veracity

## r-017 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:186`
The Stale artifacts field holds 'each stale artifact with its owning skill', with no split between reconciled and unreconciled artifacts. Fix Phase 3 reports `needs_artifact_sync` for any stale artifact in the record.

- Why: An artifact that step 7 routed and reconciled still ends in `needs_artifact_sync`. The prose (:161) puts only an artifact 'this run cannot reconcile' into the record, but the field definition does not say so.
- Fix: Define the field as only the artifacts left unreconciled, or add a reconciled or unreconciled marker to each entry.
- Concern: logic-correctness

## r-018 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:56`
Step 1 gives no branch for a finding with nothing to run whose defect does show at the current head. The only path to step 2 is 'The re-run fails', which also expects failing output that such a finding does not have.

- Why: The main case of this input kind is handled only by inference, and step 2 starts from 'its failing output', which does not exist here.
- Fix: Add a bullet: a finding with nothing to run whose defect shows → step 2, with the cited lines as the failure.
- Concern: logic-correctness

## r-019 · low · spec · `docs/afk/small-lane/plan/DECISIONS.md:279`
D-40 says `git diff d346cfb..HEAD` changes WORKFLOW-FEEDBACK.md only through 0004, but that diff also carries d555ebb5's non-0004 change to its step 3 (lesson append from the session's linked worktree instead of the main checkout).

- Why: The ledger entry is the recorded proof the ground held; a false enumeration in it misleads the next reader even though the extra change does not touch this slice's seams.
- Fix: Amend D-40 (a) to name the d555ebb5 step 3 change and state it leaves the seam unaffected.
- Concern: spec-fidelity

## r-020 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:154`
Possible widening of `needs_artifact_sync`: the fix skill now reports it for any stale artifact step 7 records, including an in-flight subtask whose contract shifted. That case used to be surfaced to the execute run, and no status was set for it.

- Why: The old skill reported `needs_artifact_sync` only when it could not reach the truth this session. The Record field now holds 'each stale artifact', so a routed artifact or a shifted subtask can turn an otherwise `fixed` run into `needs_artifact_sync`.
- Fix: Make the Record field hold only artifacts left unreconciled, and say what the fix skill reports for the shifted-subtask row.
- Concern: refactor-safety

## r-021 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:21`
The 'never merge' prohibition from the old fix hard rules did not survive the move; the new no-commit rule names commit, push, opening a change and writing a ticket, but not merge.

- Why: The fix skill runs inside execute or preflight on a branch that already has an open Draft change. That change could still be merged, and merging is outside the agent's lane per AGENTS.md's CR/Merge split.
- Fix: Add 'or merges' to the IN-PLACE-FIX.md hard rule, or keep 'never merge' in the fix skill's Hard rules.
- Concern: refactor-safety

## r-022 · low · test · `AGENTS.md:119`
The static tier says the wiring gate proves 'the procedure is reachable from its pointers', but the gate passes on any single file naming the token, not on each pointer the slice adds.

- Why: ESCAPE-ANALYSIS.md, WORKFLOW-FEEDBACK.md, LEDGER-FORMAT.md or AGENTS.md could drop its pointer and the gate would still pass on fix/SKILL.md alone.
- Fix: Grep each of the five pointing files for `IN-PLACE-FIX.md` as the static check, or narrow the Proves cell to 'the file has a referrer'.
- Concern: test-veracity

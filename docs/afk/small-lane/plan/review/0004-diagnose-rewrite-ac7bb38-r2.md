# Review — 0004-diagnose-rewrite-ac7bb38-r2

- policy: lean · delta round 2 (ac7bb38..d22496e) · activated: delta-sweep, spec-fidelity, logic-correctness, refactor-safety, scope-and-impact (fix owners of round 1's high findings), api-contract (public surface changed), test-veracity (test code changed) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 5 medium, 5 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: d22496e5c36db9686cc0ae5e57dfe58e79f46543
- counts: crit=0 high=0 med=5 low=5

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:35`
Fix selects any `still small` row but never says the latest row across both grill sections wins, so a later `too big` row does not stop the fix.

- Why: The latest-row-wins rule lives only in GRILL-LOG-FORMAT.md and D-14; fix would apply a superseded call.
- Fix: State in step 2 that the row with the latest time across both grill sections decides; a latest `too big` row stops.
- Concern: refactor-safety,logic-correctness,spec-fidelity (behaviour-preservation: changed rule with a second reader)

## r-002 · medium · correctness · `skills/utils/diagnose/SKILL.md:36`
A re-run in a handed worktree gets contradictory instructions: step 2 makes the handed branch and its tip the Diagnosis branch and Base, while step 5 keeps the recorded Base and Diagnosis branch from an existing DIAGNOSIS.md.

- Why: Both rules fire on a second in-place call for the same bug.
- Fix: In step 5, say a handed worktree's branch and tip replace the recorded Base and Diagnosis branch.
- Concern: refactor-safety (behaviour-preservation: reworked control flow in an existing procedure)

## r-003 · medium · correctness · `skills/afk/fix/SKILL.md:39`
With a DIAGNOSIS.md path input no worktree was handed over, so 'the worktree fix handed over' has no referent and fix falls to the Diagnosis-branch worktree (a second worktree); the delta also dropped 'git checkout <Diagnosis branch> -- <test path>', so a caller's worktree lacks the failing test.

- Why: A path input from a caller in its own linked worktree recreates the second-worktree problem D-14 removed, and the failing test cannot be watched failing.
- Fix: Fix in the linked worktree fix runs in (outside one, the Diagnosis-branch worktree) and bring the failing test in from the Diagnosis branch when it is not there.
- Concern: refactor-safety,api-contract,logic-correctness,delta-sweep,spec-fidelity (behaviour-preservation: dropped step / path input location)

## r-004 · low · scope · `skills/afk/fix/WORKFLOW-FEEDBACK.md:31`
Delta edits WORKFLOW-FEEDBACK.md, which is not in contract 0004 ## Scope; D-16 records it but supersedes no Scope passage.

- Why: A decision entry waives only the spec passage it quotes (D-16 'Supersedes: none').
- Fix: Record a decision superseding the Scope list for this file, or revert the edit.
- Concern: scope-and-impact (changed paths match ## Scope)

## r-005 · medium · correctness · `skills/utils/diagnose/SKILL.md:33`
A handed-over worktree makes the invoker's own branch the Diagnosis branch with only its tip commit as Base: no Base branch is named (DIAGNOSIS-FORMAT requires the branch and its commit id), the SDD §4 rows for the diagnosis branch and worktree no longer hold, and fix's 'gone -> create-worktree --branch <Diagnosis branch>' could target an invoker branch.

- Why: The consumed format and SDD §4 disagree with the skill about the handed case.
- Fix: Name the Base branch for a handed worktree, record a decision narrowing SDD §4 for that case, and keep fix from cutting onto an invoker branch.
- Concern: scope-and-impact,delta-sweep (caller whose contract the diff changed but did not update)

## r-006 · medium · correctness · `skills/afk/fix/SKILL.md:31`
Fix hands diagnose its own linked worktree, where diagnose leaves DIAGNOSIS.md and the failing test uncommitted; nothing says what the caller's commit does with them.

- Why: The caller set changed from 'separate diagnosis worktree' to 'uncommitted files in the caller's worktree' with no instruction to include or exclude them.
- Fix: State in fix what happens to the uncommitted DIAGNOSIS.md and failing test in a handed worktree.
- Concern: scope-and-impact (caller whose contract the diff changed but did not update)

## r-007 · low · scope · `skills/afk/fix/SKILL.md:37`
Fix reports `blocked` for V-2/V-3 without a still-small row and for V-4; D-16(b) defers caller routing to slice 0009.

- Why: Callers still expect fix to fix.
- Fix: Confirm slice 0009 names execute and preflight as its own consumers; otherwise add an IOU.
- Concern: scope-and-impact (caller routing of fix's new outcome)

## r-008 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
Re-run detection derives the branch from `git.branch-template` and the work id, which prose cannot do for a template with {user} or other placeholders, and a stale same-name branch silently becomes the Diagnosis branch.

- Why: A re-run is missed or unrelated work is reused.
- Fix: Detect a re-run by the owner record (which names the branch) and leave branch derivation to create-worktree.
- Concern: logic-correctness,delta-sweep (boundary values / re-run detection)

## r-009 · low · compliance · `docs/afk/small-lane/plan/DECISIONS.md:98`
D-14 'Supersedes' quotes D-11 text that does not appear in D-11; the quoted sentence is from the old diagnose step 5.

- Why: An entry supersedes exactly the passage it quotes, so D-11's real wording stays un-superseded.
- Fix: Quote D-11's Chosen text exactly.
- Concern: delta-sweep (Documented-rule breach in changed lines)

## r-010 · low · correctness · `skills/afk/grill-solution/SKILL.md:14`
grill-solution says the no-PRD grill 'ends at that call whatever it is', but SIZE-CALL.md now stops with no size call for a verdict other than V-2/V-3.

- Why: Two homes give a different end for a V-1, V-4 or V-5 diagnosis.
- Fix: Point the end condition at SIZE-CALL.md, covering the no-open-question stop.
- Concern: delta-sweep (Propagation gap)

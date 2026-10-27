# Review — 0004-diagnose-rewrite round 6

- policy: lean · delta round 6 (fc15fc0..9fab050) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: fix-owner specialists (no critical or high in round 5), scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above); both high findings re-checked by the orchestrator against scripts/create-worktree:267-269 and hooks/worktree-create.sh:26
- verdict: blocking — 2 high, 1 medium, 0 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: 9fab050aad3b988a62a15422a16354294623d5b4
- counts: crit=0 high=2 med=1 low=0

## r-001 · high · correctness · `skills/afk/fix/SKILL.md:39`
The new rule 'the one in `git worktree list` whose folder holds the `DIAGNOSIS.md` path' matches two worktrees on the default layout: diagnose's `--name` cut lands under `<main checkout>/.claude/worktrees/<name>`, so the main checkout (listed first) also holds that path.

- Why: The replaced `git -C <folder> rev-parse --show-toplevel` returned the innermost worktree; the list rule names no tie-break, so fix can pick the main checkout and either stop `blocked` on the guard or edit the wrong tree, on every in-repository diagnosis.
- Fix: Pick the listed worktree with the longest folder that holds the path (or keep `rev-parse --show-toplevel` and require its result to appear in `git worktree list`); mirror the wording in D-21.
- Concern: refactor-safety,delta-sweep (reworked control flow in an existing method (behaviour-preservation risk))

## r-002 · high · correctness · `skills/utils/diagnose/SKILL.md:34`
A record-only re-run takes HEAD as the Base commit on the premise that only diagnose's --name cut writes an owner record, but the harness WorktreeCreate hook writes one for every session worktree, so a person's session worktree named for the ticket key is taken as a re-run, its HEAD becomes Base, and Phase 7 commits on that person's branch. The Base it records also mixes sources: the old HEAD with today's starting-branch answer, so the branch need not hold the commit.

- Why: D-20 rejected folder-name detection because diagnose 'would then commit onto a branch it does not own'; the owner record carries the same risk because hooks/worktree-create.sh calls create-worktree --name and the record is written for every --name cut.
- Fix: Require the record-only re-run's spec folder to hold this Work id's DIAGNOSIS.md, or make the record mark its creator (diagnose) and accept only that; correct D-20's premise.
- Concern: delta-sweep,refactor-safety (New defect in the change)

## r-003 · medium · correctness · `skills/utils/diagnose/SKILL.md:35`
The delta gives a re-run with no DIAGNOSIS.md a Base (HEAD plus the answer) at step 3, but the sibling path at step 4 (branch exists, worktree gone) still discards the answer because 'step 5 keeps the recorded Base', which does not exist when no DIAGNOSIS.md was committed; it also treats a bare existing branch name as diagnose's own, which D-20 rejected for a bare folder name.

- Why: A first run that cut its worktree and ended before Phase 7's commit leaves a branch with no diagnosis on it, so after the worktree is removed the re-run reaches step 5 with no Base, and a person's same-named branch gets diagnose's commit.
- Fix: In step 4's branch-exists case, apply step 3's rule: with no DIAGNOSIS.md on the branch, Base commit = the branch tip and Base branch = the answer; and treat the branch as a re-run only when it holds this Work id's DIAGNOSIS.md or the failing test.
- Concern: delta-sweep (New defect in the change)

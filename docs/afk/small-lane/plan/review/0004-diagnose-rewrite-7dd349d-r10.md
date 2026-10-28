# Review — 0004-diagnose-rewrite round 10

- policy: lean · delta round 10 (7dd349d..01ecbc2) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 2 medium, 0 low
- Gate outcome: stalemate; round 10 is the settle loop's hard cap, so both findings stay open and the slice stops with review_fail for a human to look at
- head: 01ecbc2d10dba5c248809d626c0b77caf45bfafc
- counts: crit=0 high=0 med=2 low=0

## r-001 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The blocked reason names only the worktree path, yet the new clearing recipe ends with `git branch -D <branch>` run after the worktree and its owner record are gone, so the person has no named source for <branch> at that point.

- Why: remove-worktree.py deletes the record that holds the branch name (drop_record) and keeps the branch when it has commits of its own (drop_branch requires own_commits == 0), and `git worktree remove` drops the folder, so once the clearing steps run in the stated order the branch name can no longer be found from the record or the worktree, and the retry dead-ends at step 4 `blocked` (branch exists).
- Fix: Have the blocked reason name the worktree's branch (from `git worktree list`) next to its path, or have the person read the branch before clearing.
- Concern: delta-sweep (New defect in the change)

## r-002 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The rewrite replaces the script's safe branch drop (only when the branch holds no commit of its own) with an unconditional `git branch -D <branch>` of the worktree's own branch, and claims a retry needs that branch gone. For a worktree with no owner record (the 'someone else's work' case), that branch can be any branch; the retry only needs the branch `create-worktree --name` would fill.

- Why: create-worktree refuses only on `refs/heads/$BRANCH` where BRANCH=branch_for_name(NAME), so the blocked reason sends the person to force-delete a branch the retry never checks, and it may hold unpushed commits, while a leftover template-filled branch under another name would still end the retry `blocked` (branch exists).
- Fix: In the no-record case, name the branch step 4 would create (git.branch-template filled with the work id) as the one to delete, and only when it exists. Keep `git branch -D` of the worktree's branch for the record case, where the record's branch is that same template-filled branch.
- Concern: refactor-safety (behaviour-preservation risk (changed defaults in pre-existing step text))

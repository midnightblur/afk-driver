# Review — 0004-diagnose-rewrite round 7

- policy: lean · delta round 7 (9fab050..4442db8) · activated: delta-sweep, refactor-safety (fix owner of round 6's high findings; pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 2 medium, 0 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: 4442db8af6d63975faf9aa6c29c00a4fd4361bee
- counts: crit=0 high=0 med=2 low=0

## r-001 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
A diagnose run that stopped after its own --name cut but before Phase 7 (e.g. step 5 'spec folder unresolved', or any blocked end, which prints only a status line) leaves its worktree, owner record and branch with no DIAGNOSIS.md; every retry now skips step 3 and step 4's --name cut is always refused 'worktree name ... is already taken', so the work id can never be diagnosed again without manual worktree removal.

- Why: D-22 says such a worktree 'goes on to a fresh cut', but create-worktree refuses the cut whenever the folder or record for that name exists (create-worktree:296 and :473, checked before the branch), and SDD §4 keeps a stopped diagnosis's worktree, so the retry case the previous step 3 handled is now a dead end that the blocked reason does not explain.
- Fix: When step 4's cut is refused as 'name already taken' for a worktree whose owner record diagnose's own cut wrote and that holds no DIAGNOSIS.md, end blocked naming that worktree path and the remove-worktree step (or cut under a distinct name), and correct D-22's 'goes on to a fresh cut'.
- Concern: delta-sweep,refactor-safety (New defect in the change)

## r-002 · medium · correctness · `skills/utils/diagnose/SKILL.md:35`
The new branch-exists test in step 4 needs `<spec folder path>` and whether the spec folder is outside the repository, but the spec folder is only resolved in step 5, 'from inside the diagnosis worktree', which does not exist when step 4's refusal fires

- Why: Step order leaves the re-run check with no defined way to get the path it reads, so the agent improvises the resolve location or ends `blocked (branch exists)` on a real re-run.
- Fix: Say where step 4 resolves the spec folder for this check (e.g. `afk_adapter notes resolve <work id>` from the current checkout, taking its repository-relative path for `git show`).
- Concern: refactor-safety,delta-sweep (open-question)

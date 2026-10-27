# Review — 0004-diagnose-rewrite round 12

- policy: lean · delta round 12 (8c6ffa2..982b259) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean; only plan files outside Scope), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- verdict: advisory — 0 high, 0 medium, 3 low
- Gate outcome: r-001 and r-003 fixed; r-002 deferred to the feature gate (low compliance, lean policy)
- head: 982b25934a36212663560c35acc0c5a58b8a0319
- counts: crit=0 high=0 med=0 low=3

## r-001 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
Step 3 now takes the branch rule from `branch_for_name`, but step 4 still says the Diagnosis branch is "filled from `git.branch-template`", so the two steps give different rules for one branch.

- Why: with a template whose only placeholder is `{user}`, the script makes `worktree-<work id>`, so a hand fill records a branch that does not exist and the later re-run test fails.
- Fix: step 4 reads the Diagnosis branch from the new worktree.
- Concern: refactor-safety, delta-sweep (open question; New defect in the change)

## r-002 · low · compliance · `skills/utils/diagnose/SKILL.md:34`
The pointer to `branch_for_name` makes the agent work out the branch name by reading a shell function.

- Why: AGENTS.md "Deterministic-first" puts mechanical work in a script the skill runs; no script command prints the branch.
- Fix: a command that prints the branch `--name` would make; it belongs in `scripts/create-worktree`, outside this slice's Scope.
- Concern: delta-sweep (Documented-rule breach in changed lines)

## r-003 · low · compliance · `skills/utils/diagnose/SKILL.md:34`
The change narrows the human's D-36 rule and replaces its branch rule, with no new decision ledger entry.

- Why: root `DECISIONS.md` says a new fork on the same ground gets a new entry.
- Fix: record the choice as a new entry.
- Concern: delta-sweep (open question)

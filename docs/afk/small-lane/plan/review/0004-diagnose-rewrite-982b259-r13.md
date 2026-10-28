# Review — 0004-diagnose-rewrite round 13

- policy: lean · delta round 13 (982b259..365a6a1) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean; only plan files outside Scope), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- verdict: advisory — 0 high, 0 medium, 2 low
- Gate outcome: r-001 and r-002 fixed by the human's decision D-38
- head: 365a6a1b4aad0fd3f2470d63e1960676446b3e85
- counts: crit=0 high=0 med=0 low=2

## r-001 · low · spec · `skills/utils/diagnose/SKILL.md:35`
Step 4 records the Diagnosis branch as the branch the new worktree is on, but DIAGNOSIS-FORMAT.md:17, SDD §4 (lines 117 and 133) and the contract 0004 acceptance bullet still say "from the branch template", and no decision supersedes them.

- Why: with no `git.branch-template`, or one whose only placeholder is `{user}`, `create-worktree --name` makes `worktree-<work id>`, so the format row the Phase 7 writer follows disagrees with step 4.
- Fix: a decision entry that supersedes those passages in favour of step 4's rule.
- Concern: refactor-safety, delta-sweep (open question; Propagation gap)

## r-002 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:260`
D-37's "To reverse" line says to restore "the D-36 wording" in step 4, but D-36 holds no step 4 wording.

- Why: a person who reverses D-37 (c) from the ledger cannot tell which step 4 text to restore.
- Fix: quote the step 4 sentence that D-37 (c) replaced.
- Concern: delta-sweep (New defect in the change)

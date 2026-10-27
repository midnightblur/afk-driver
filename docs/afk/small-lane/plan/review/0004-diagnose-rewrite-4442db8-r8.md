# Review — 0004-diagnose-rewrite round 8

- policy: lean · delta round 8 (4442db8..2309c3c) · activated: delta-sweep, refactor-safety (fix owner of round 7 findings; pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 1 medium, 0 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: 2309c3cb8dee57f71bb2658f9a0eff34069147a6
- counts: crit=0 high=0 med=1 low=0

## r-001 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The new 'worktree without a diagnosis' block tells the person only to 'remove' the worktree, but a stopped run also leaves its owner record and its branch, and a plain removal (`git worktree remove`) clears neither, so the retry still dead-ends at step 4.

- Why: create-worktree refuses `--name` while the record exists (scripts/create-worktree:473 'worktree name ... is already taken') and while the branch exists (:474). The session-start prune drops a record whose folder is gone without deleting its branch (scripts/remove-worktree.py prune: `if not path.is_dir(): drop_record(record_file)`). After a plain removal the next run therefore ends `blocked` (branch exists): no DIAGNOSIS.md was ever committed on that branch, because Phase 7 commits only after writing the file.
- Fix: Name the removal that clears all three in the blocked reason, e.g. `${AFK_PLUGIN_ROOT}/scripts/remove-worktree.py --path <path> --force` (it drops the record and the branch when the branch holds no commit of its own), and add it to D-23's Chosen.
- Concern: delta-sweep,refactor-safety (New defect in the change)

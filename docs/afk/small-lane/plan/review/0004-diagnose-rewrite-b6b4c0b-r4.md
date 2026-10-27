# Review — 0004-diagnose-rewrite round 4

- policy: lean · delta round 4 (b6b4c0b..1e91f66) · activated: delta-sweep, refactor-safety (fix owner of round 3's high finding; pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 2 medium, 2 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: 1e91f66d6b89bf898b7f3cb5f63429f144bae1f3
- counts: crit=0 high=0 med=2 low=2

## r-001 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
Widened re-run trigger (any linked worktree whose folder is named for the work id) skips step 4, yet Base and Diagnosis branch on a re-run come only from a prior DIAGNOSIS.md; a matched worktree holding none (a stopped earlier run, or an unrelated worktree a person named for the ticket with --dir) leaves both required parts unset, and diagnose then commits its failing test onto that foreign branch.

- Why: Step 5 keeps Base and Diagnosis branch only from an existing DIAGNOSIS.md, and every verdict row of DIAGNOSIS-FORMAT.md requires both, so the folder-name path has no defined source for them and no guard that the matched worktree is a diagnosis worktree.
- Fix: On a re-run with no DIAGNOSIS.md, set Diagnosis branch to the matched worktree's branch and Base from the record or merge-base, or treat a folder match without a record or DIAGNOSIS.md as not a re-run (fall through to step 4).
- Concern: refactor-safety (reworked control flow in an existing method (behaviour-preservation risk))

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:39`
Fix step 3 now leaves the linked worktree it runs in whenever that branch lacks the Base commit and works in (or cuts) the Diagnosis-branch worktree, reversing D-14 (a)/D-17's rule with no ledger entry; for a handed diagnosis given by path, the Diagnosis-branch worktree is the invoker's own worktree, so fix would edit another session's worktree. If that worktree is gone, fix cuts one onto the invoker's branch before it finds the files missing.

- Why: D-17 chose that fix cuts or moves to the Diagnosis worktree only when it runs outside any linked worktree, and D-18 supersedes nothing about fix, so the changed condition is an unrecorded behaviour change whose new path reaches a worktree fix does not own.
- Fix: Record a ledger entry superseding D-17's fix-worktree clause, and for a handed diagnosis (Diagnosis branch not from the template) stop `blocked` naming the invoker's worktree instead of working in it.
- Concern: refactor-safety,delta-sweep (reworked control flow in an existing method (behaviour-preservation risk))

## r-003 · low · correctness · `skills/afk/fix/SKILL.md:39`
The two new `blocked` exits (test not on the Diagnosis branch; test passes or does not build) do not exempt a diagnosis that has no failing test because no correct seam exists. The exit gate accepts that case, but step 3 now reads as stopping it.

- Why: DIAGNOSIS-FORMAT.md lets a full diagnosis record a missing seam in Root cause, with no failing test. Read literally, the added 'not on that branch either → stop blocked' then fires for a legitimate diagnosis.
- Fix: Add '(a diagnosis that records a seam absence in Root cause has no test to bring in: skip to the Fix proposal)' beside the light-diagnosis sentence.
- Concern: delta-sweep (New defect in the change)

## r-004 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
The new folder-name check reads `git worktree list`, which still lists a worktree whose folder was deleted (marked prunable). Step 3 then treats it as a live re-run and says to work in a folder that does not exist, so step 4's recut for a gone worktree is never reached.

- Why: create-worktree runs `git worktree prune` only after its own checks, and step 3 runs before any prune. The recut path the delta relies on for a gone worktree is therefore bypassed when the folder was removed by hand.
- Fix: Count only entries whose folder exists (skip `prunable` entries in `git worktree list --porcelain`), or run `git worktree prune` before step 3.
- Concern: delta-sweep (New defect in the change)

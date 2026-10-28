# Review — 0004-diagnose-rewrite round 15

- policy: lean · delta round 15 (a6d78da..5781d42) · activated: delta-sweep, refactor-safety (delta edits existing lines), scope-and-impact (delta edits `docs/afk/small-lane/SDD.md`, outside Scope) · skipped: test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract and domain-alignment (no trigger), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- verdict: advisory — 0 high, 2 medium, 3 low
- Gate outcome: all 5 open (f074-f078); the human allowed no round after this one, so the slice stops with review_fail for the human
- head: 5781d42b35f5213cc4daaf70ca93dd0e1a1bbdac
- counts: crit=0 high=0 med=2 low=3

## r-001 · medium · scope · `docs/afk/small-lane/SDD.md:117`
The delta edits SDD.md rows 117 and 133, but no Scope entry covers SDD.md; D-39 adds only DIAGNOSIS-FORMAT.md to Scope.

- Why: `/afk:execute` hard rule "Stay inside Scope globs"; every earlier out-of-Scope edit in this plan has its own Scope line in a Supersedes line (D-2, D-3, D-17, D-28, D-30).
- Fix: a new ledger entry adds SDD.md to Scope (human decision), or revert the two SDD rows.
- Concern: scope-and-impact

## r-002 · medium · correctness · `skills/utils/diagnose/DIAGNOSIS-FORMAT.md:17`
The edited row still says "made from the Base tip", but D-39 says the row also holds for a worktree that step 2 receives, where diagnose makes no branch.

- Why: the handed-worktree exception stays only in D-18 in the ledger, which D-39 itself rejects as a home that outlives the feature.
- Fix: put the handed case in the row ("made from the Base tip when diagnose cuts the worktree, the handed branch itself otherwise") and lift D-18's narrowing in a Supersedes line.
- Concern: delta-sweep (New defect in the change)

## r-003 · low · scope · `docs/afk/small-lane/plan/0004-diagnose-rewrite.md:26`
The delta adds DIAGNOSIS-FORMAT.md to the `## Scope` list in place, while D-17's Scope addition (`skills/afk/fix/WORKFLOW-FEEDBACK.md`) stays only in the ledger.

- Why: the Scope now has two homes with different contents; a reader of `## Scope` alone counts WORKFLOW-FEEDBACK.md as out of Scope.
- Fix: keep one home — revert line 26, or also list WORKFLOW-FEEDBACK.md (human decision).
- Concern: scope-and-impact

## r-004 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:272`
D-39 retargets D-17's and D-18's quotes in its Chosen line, not in its Supersedes line; the passages they quote no longer exist.

- Why: root `DECISIONS.md`: "A `Supersedes:` line overrides the exact spec passage it quotes"; Chosen prose has no override effect.
- Fix: list D-17's and D-18's Supersedes lines in a Supersedes line with their new quotes, or drop the retarget once the row carries the handed case.
- Concern: delta-sweep (New defect in the change)

## r-005 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:274`
D-39's undo line restores the "from the branch template" clauses but not the D-38 lines that D-39 supersedes.

- Why: after the undo, the text again says "from the branch template" while step 4 reads the branch from `git worktree list`, and no ledger line settles the conflict.
- Fix: add "D-38's Supersedes and To reverse lines then govern again" to the undo line.
- Concern: delta-sweep (New defect in the change)

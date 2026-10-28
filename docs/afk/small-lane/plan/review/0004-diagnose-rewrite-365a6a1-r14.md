# Review — 0004-diagnose-rewrite round 14

- policy: lean · delta round 14 (365a6a1..560dec7) · activated: delta-sweep · skipped: refactor-safety (delta only adds lines), scope-and-impact (Scope grep clean; only plan files outside Scope), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- verdict: advisory — 0 high, 1 medium, 3 low
- Gate outcome: all 4 open; no further round allowed, so the slice stops with review_fail for the human
- head: 560dec786e2c3db34b2cd91fff75fbdf95bae455
- counts: crit=0 high=0 med=1 low=3

## r-001 · medium · spec · `docs/afk/small-lane/plan/DECISIONS.md:266`
D-38 overrides the shipped DIAGNOSIS-FORMAT.md:17 row and the SDD §4 rows only through the plan ledger, which is deleted with `plan/` after merge.

- Why: root `DECISIONS.md` says "A decision worth outliving the feature routes through the normal channels"; readers of DIAGNOSIS-FORMAT.md never see this ledger, so the format row and step 4 disagree after merge.
- Fix: edit DIAGNOSIS-FORMAT.md:17 and SDD §4 rows 117 and 133 to step 4's rule (DIAGNOSIS-FORMAT.md is outside this slice's Scope), or record a wiring IOU naming the owner.
- Concern: delta-sweep (open question)

## r-002 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:266`
Each quoted passage is replaced whole, and the quotes are wider than the "from the branch template" clause.

- Why: read literally, the contract bullet loses "keeps the failing test" and "lower-cased", and SDD row 133 loses its other cells.
- Fix: quote only the clause being replaced, or state each full rewritten passage.
- Concern: delta-sweep (New defect in the change)

## r-003 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:266`
Two supersessions run together with no separator: `D-18.D-37 "To reverse`.

- Why: a reader cannot tell where the first override ends and the D-37 undo-line override starts.
- Fix: put `; ` between `D-18` and `D-37`.
- Concern: delta-sweep (New defect in the change)

## r-004 · low · correctness · `docs/afk/small-lane/plan/DECISIONS.md:267`
D-38's "To reverse" points at the whole corrected D-37 line, which also restores the step 3 wording.

- Why: following it reverts D-37 (a) and (b), which D-38 does not touch.
- Fix: say "restore the step 4 sentence quoted in (b)".
- Concern: delta-sweep (New defect in the change)

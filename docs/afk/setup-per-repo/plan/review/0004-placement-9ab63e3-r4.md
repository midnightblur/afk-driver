# Review — 0004-placement, round 4

- Verdict: **advisory** — crit=0 high=0 med=1 low=2
- Diff: the round 3 fix, 9ab63e3 to a74bfa1; the whole slice from the PR base was context only.
- policy: lean · activated: delta-sweep, test-veracity (the fix touches tests) · skipped: logic-correctness, code-quality (delta under 150 lines), design-quality, api-contract, refactor-safety (no delta trigger), scope-and-impact (the delta stays inside the Scope globs) · deferred: agents-md-compliance, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design finding at medium or above)
- Mutation probe: does not apply (no Java; delta round).

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | test | test-veracity | scripts/placement.py:263 | No test reaches a check with a refused root, so removing the refused-root arm leaves every test green |
| r-002 | low | correctness | delta-sweep | scripts/placement.py:264 | A check resolves the root but not the short-name folder, so a linked short-name folder is shown unresolved beside a resolved target |
| r-003 | low | test | test-veracity | scripts/tests/test_placement.py:476 | The new-target linked-root test passes against the code before the change: it is a guard, not a test of the change |

The full text of each finding is in `0004-placement-9ab63e3-r4.findings.json`.

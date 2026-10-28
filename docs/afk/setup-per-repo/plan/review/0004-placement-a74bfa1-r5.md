# Review — 0004-placement, round 5

- Verdict: **advisory** — crit=0 high=0 med=1 low=1
- Diff: the round 4 fixes, a74bfa1 to a900962; the whole slice from the PR base was context only.
- policy: lean · activated: delta-sweep, test-veracity (the fixes touch tests) · skipped: logic-correctness, code-quality (delta under 150 lines), design-quality, api-contract, refactor-safety (no delta trigger), scope-and-impact (the delta stays inside the Scope globs) · deferred: agents-md-compliance, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design finding at medium or above)
- Mutation probe: does not apply (no Java; delta round).

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | delta-sweep | scripts/placement.py:269 | A check answers inside for a dangling link at the short name, which a new target refuses |
| r-002 | low | smell | delta-sweep | scripts/placement.py:162 | The folder fallback in the short-name folder rule can never run |

The full text of each finding is in `0004-placement-a74bfa1-r5.findings.json`. test-veracity found nothing: six mutations of the changed lines tried, five killed, one equivalent.

# Review — 0004-placement, round 3

- Verdict: **advisory** — crit=0 high=0 med=0 low=1
- Diff: the round 2 fixes, 02a274f to 9ab63e3; the whole slice from the PR base was context only.
- policy: lean · activated: delta-sweep, test-veracity (the fixes touch tests) · skipped: logic-correctness, code-quality (delta under 150 lines), design-quality, api-contract, refactor-safety (no delta trigger), scope-and-impact (the delta stays inside the Scope globs) · deferred: agents-md-compliance, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design finding at medium or above)
- Mutation probe: does not apply (no Java; delta round).

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | low | correctness | delta-sweep | scripts/placement.py:266 | A checked target's folder is resolved while its short-name reasons keep the root as written, so one refusal can show two spellings |

The full text of the finding is in `0004-placement-02a274f-r3.findings.json`. test-veracity found nothing: the linked-root test fails without the round 2 fix.

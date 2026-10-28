# Review — 0004-placement, round 2

- Verdict: **advisory** — crit=0 high=0 med=0 low=3
- Diff: the round 1 fixes, 540a7d9 to 02a274f; the whole slice from cc6bff8 was context only.
- policy: lean, opt-in design-quality · activated: delta-sweep, test-veracity (the fixes touch tests), logic-correctness (complex slice), refactor-safety (the fixes rework lines of this slice) · skipped: design-quality, api-contract, scope-and-impact (no delta trigger) · deferred: code-quality, agents-md-compliance, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design finding at medium or above)
- Mutation probe: does not apply (no Java; delta round).

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | low | correctness | delta-sweep | scripts/placement.py:247 | A checked target is shown resolved while its folder is shown as configured, so one message can spell one tree two ways |
| r-002 | low | test | test-veracity | scripts/tests/test_placement.py:442 | The link-then-`..` test takes its expectation from where the folder lands, so on Windows it cannot fail |
| r-003 | low | test | test-veracity | scripts/tests/test_placement.py:356 | One case of the broken-machine-file test builds a worktree it never uses |

The full text of each finding is in `0004-placement-540a7d9-r2.findings.json`.

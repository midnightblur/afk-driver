# Review — 0002-settings-reader, round 5

- Verdict: **advisory** — crit=0 high=0 med=1 low=2
- Diff: the delta from eb22541 to c12a0ab (round-4 fix); the full slice from 09444b0 was context only.
- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests), refactor-safety (pre-existing lines changed) · skipped: scope-and-impact (inline Scope check clean), logic-correctness, code-quality (delta under 150 lines), domain-alignment, api-contract (no delta trigger), no fix owner (round 4 had no critical or high finding) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding, no verify pass
- Caller set: C:/t/p2c/rv/callers-r5.md.
- Ledger keys: r-001 → f033, r-002 → f034, r-003 → f035 on PR #145. refactor-safety returned no finding.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | test | test-veracity | scripts/tests/test_afk_config_owner.py:420 | The home-checkout test pins only top-level settings, so the nested branch has no test. |
| r-002 | low | correctness | delta-sweep | scripts/afk-config.py:535 | A removed-key note for a home-checkout file prints twice under validate with no argument. |
| r-003 | low | smell | delta-sweep | scripts/afk-config.py:512 | `_settings` repeats the key and child walk of `_owner_filter`. |

Details per finding: `0002-settings-reader-eb22541-r5.findings.json`.

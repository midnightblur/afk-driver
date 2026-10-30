# Review of 0002-core-behaviors, round 1

Telemetry only. The review record is pull request 155.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (trigger: the slice replaces seed lines) · skipped: api-contract, domain-alignment (no trigger) · deferred: agents-md-compliance, code-quality, design-quality, resilience, logic-correctness (→ feature gate)
verified: no design-level finding, so no verify pass ran. Caller set: no pre-existing public symbol changed, so no coverage ledger exists.

Diff d9446023..3fb21005.

## Commit 3fb21005: 0/0/3/3 (critical/high/medium/low)

Verdict: advisory. Under owner ruling R-2 the 6 findings stay on the pull request with no fix and no dispute round.

| Id | Key | Severity | Class | Where | Outcome | Finding |
|---|---|---|---|---|---|---|
| r-001 | 0002-core-behaviors/f001 | medium | spec | afkv2/scripts/search_bench.py:62 | carried (R-2) | "Same hits" leaves out binary-file notices; git grep printed 1, rg printed 0 |
| r-002 | 0002-core-behaviors/f002 | medium | test | afkv2/tests/test_core_behaviors.py:247 | carried (R-2) | The marker test gets its expected hash from the production function |
| r-003 | 0002-core-behaviors/f003 | medium | test | afkv2/tests/test_core_behaviors.py:80 | carried (R-2) | 3 benchmark verdict branches have no test |
| r-004 | 0002-core-behaviors/f004 | low | spec | afkv2/core/CORE-BEHAVIORS.md:15 | carried (R-2) | The text implies the 2 interim bans on a local full suite and on a CI wait, and does not state them |
| r-005 | 0002-core-behaviors/f005 | low | test | afkv2/tests/test_core_behaviors.py:111 | carried (R-2) | Tests that use the real tools skip when a tool is missing |
| r-006 | 0002-core-behaviors/f006 | low | test | afkv2/tests/test_core_behaviors.py:225 | carried (R-2) | The interim-rule test checks for a substring only |

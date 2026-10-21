# Review — 0009-spawn-permission-check (base b2babf7, round tag r15)

policy: lean · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: fix-owner specialists (round 14's high finding was fixed and is re-checked by delta-sweep), scope-and-impact (the delta stays inside Scope), logic-correctness and code-quality (delta under 150 changed lines and 6 files), consistency-sweep (no scope escalation) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 295607a · delta diff: b2babf7..295607a · forge ledger: pull request 112, keys 0009-spawn-permission-check/f072 to f076

Verdict: blocking — crit=0 high=0 med=1 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| DS-1 | f072 | low | correctness | scripts/team/permission.py:137 | One bad byte in the listing loses the printed rule, and the refusal says "did not answer" | deferred to the feature gate (human decision 2026-10-20: nitpicks slip); the refusal stays safe |
| DS-2 | f073 | low | smell | scripts/team/permission.py:56 | The CR strip in the matcher script no longer has a reason now that stdin is bytes | deferred to the feature gate (nitpicks slip) |
| TV-1 | f074 | medium | test | scripts/team/permission.py:183 | No test feeds stderr that is not UTF-8, so `_text`'s replace handler is unpinned | fixed in 6be1a04: adapter and matcher stderr tests |
| TV-2 | f075 | low | test | scripts/team/permission.py:168 | No test passes an entry that strict UTF-8 cannot encode | fixed in 6be1a04: lone-surrogate deny entry test |
| TV-3 | f076 | low | test | scripts/tests/test_team_permission.py:348 | `_new_harness` hides the fixture the tests rely on | deferred to the feature gate (nitpicks slip) |

62 tests pass and 6 skip on Windows; 67 pass and 1 skips on WSL Linux.

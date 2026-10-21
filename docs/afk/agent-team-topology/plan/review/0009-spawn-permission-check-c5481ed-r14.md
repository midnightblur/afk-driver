# Review — 0009-spawn-permission-check (base c5481ed, round tag r14)

policy: lean · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: fix-owner specialists (round 13 had no critical or high finding), scope-and-impact (the delta stays inside Scope), logic-correctness and code-quality (delta under 150 changed lines and 6 files), consistency-sweep (no scope escalation) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: b2babf7 · delta diff: c5481ed..b2babf7 · forge ledger: pull request 112, keys 0009-spawn-permission-check/f070 and f071

Verdict: blocking — crit=0 high=1 med=1 low=0

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| delta-sweep-1 | f070 | high | correctness | scripts/team/permission.py:137 | On Windows the decode error is raised in a reader thread, so the check crashed with AttributeError instead of refusing | fixed in 295607a: bytes in, decode in the check |
| TV-1 | f071 | medium | test | scripts/tests/test_team_permission.py:432 | The non-UTF-8 test faked the error, so it pinned only the except clause | fixed in 295607a: a real scratch adapter prints byte 0xe9 |

59 tests pass and 6 skip on Windows; 64 pass and 1 skips on WSL Linux. Against b2babf7 the new test fails on Windows with the AttributeError.

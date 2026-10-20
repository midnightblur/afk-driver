# Review — 0009-spawn-permission-check (base 6a58db7, round tag r6)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 5 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: eaab05b · delta diff: 6a58db7..eaab05b without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..eaab05b plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f037 to f041

Verdict: advisory — crit=0 high=0 med=1 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| tv-r6-001 | f037 | medium | test | scripts/tests/test_team_permission.py:172 | The root and git-dir ownership checks are testable through a stub git | fixed in b4d0a81: parametrized over all three entries |
| tv-r6-002 | f038 | low | test | scripts/tests/test_team_permission.py:108 | No test puts the current rule beside an old entry; the setup note misdescribed it | fixed in b4d0a81 |
| cs-r6-001 | f039 | low | correctness | scripts/team/permission.py:2 | The docstrings state the promises earlier fixes narrowed | fixed in b4d0a81 |
| cs-r6-002 | f040 | low | spec | PROVIDERS.md:186 | D-86 does not cover the 0009 contract's rows or the SDD §8 interface column | fixed in b4d0a81 (D-87; the contract text is the human's) |
| cs-r6-003 | f041 | low | spec | PROVIDERS.md:186 | Contract 0015 still says every refusal names the rule | fixed in b4d0a81 (D-87; the 0015 bullet is the human's) |

35 tests pass and 1 skips on WSL Linux; 30 pass and 6 skip on Windows. Each of the three ownership entries and the allowed-before-stale order has a mutant that fails a test.

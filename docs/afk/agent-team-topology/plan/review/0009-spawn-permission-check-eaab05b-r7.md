# Review — 0009-spawn-permission-check (base eaab05b, round tag r7)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 6 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: b4d0a81 · delta diff: eaab05b..b4d0a81 without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..b4d0a81 plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f042 to f045

Verdict: advisory — crit=0 high=0 med=0 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| tv-r7-001 | f042 | low | test | scripts/tests/test_team_permission.py:177 | One parametrized test body held three different setups | fixed in 5ef23e8: split into two tests |
| tv-r7-002 | f043 | low | test | scripts/tests/test_team_permission.py:212 | The old-entry test did not prove the old entry's file was read | fixed in 5ef23e8 |
| cs-r7-001 | f044 | low | spec | PROVIDERS.md:186 | The stale refusal read as firing beside the current rule | fixed in 5ef23e8 |
| cs-r7-002 | f045 | low | spec | PROVIDERS.md:189 | ADR-0005 still promised an ok covers every source of asking | fixed in 5ef23e8 (D-88; the ADR is unchanged) |

35 tests pass and 1 skips on WSL Linux; 30 pass and 6 skip on Windows; the static tier passes (49). Each ownership entry and the allowed-before-stale order still has a failing mutant.

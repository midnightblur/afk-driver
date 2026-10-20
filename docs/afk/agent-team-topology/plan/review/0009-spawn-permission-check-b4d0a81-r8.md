# Review — 0009-spawn-permission-check (base b4d0a81, round tag r8)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 7 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 5ef23e8 · delta diff: b4d0a81..5ef23e8 without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..5ef23e8 plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f046 to f049

Verdict: advisory — crit=0 high=0 med=1 low=3

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| tv-r8-001 | f047 | medium | test | scripts/tests/test_team_permission.py:254 | No test pins that a block list outranks an old entry or an empty allow list | fixed in b397b3d |
| delta-sweep-1 | f046 | low | correctness | PROVIDERS.md:186 | The stale condition still overlapped blocked; no order was stated | fixed in b397b3d |
| cs-r8-001 | f048 | low | spec | PROVIDERS.md:176 | The section's opening still promised a refusal whenever the harness would ask | fixed in b397b3d |
| cs-r8-002 | f049 | low | spec | PROVIDERS.md:189 | The 0009 Goal still promised the managed-settings case | fixed in b397b3d (D-89; the contract text is the human's) |

39 tests pass and 1 skips on WSL Linux; 34 pass and 6 skip on Windows. Moving the stale branch above blocked fails two of the new cases.

# Review — 0009-spawn-permission-check (base ed074e6, round tag r12)

policy: lean · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: fix-owner specialists (the round 11 summary closed with no open finding), scope-and-impact (the delta stays inside Scope), logic-correctness and code-quality (delta under 150 changed lines and 6 files), consistency-sweep (no scope escalation) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 2643b80 · delta diff: ed074e6..2643b80, the fix for adversary finding F1 (D-94) · forge ledger: pull request 112, keys 0009-spawn-permission-check/f062 to f066

Verdict: blocking — crit=0 high=1 med=2 low=2

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| ds-1 | f062 | high | correctness | scripts/team/permission.py:162 | Block entries went to the bash child in the Windows locale encoding; a character outside it stalled the check for 30 s, then refused | fixed in c5481ed: UTF-8 both ways |
| ds-2 | f063 | low | correctness | scripts/team/permission.py:57 | A matcher exit other than 1 read as no match, so the check could answer ok | fixed in c5481ed: any other exit refuses |
| tv-r12-1 | f064 | medium | test | scripts/tests/test_team_permission.py:279 | No test had more than one block entry, so the named entry was unpinned | fixed in c5481ed |
| tv-r12-2 | f065 | medium | test | scripts/team/permission.py:166 | No test reached the matcher's failure paths | fixed in c5481ed |
| tv-r12-3 | f066 | low | test | scripts/tests/test_team_permission.py:270 | The space the `:*` rewrite inserts was unpinned | fixed in c5481ed |

57 tests pass and 6 skip on Windows; 62 pass and 1 skips on WSL Linux. The old code hangs on the new non-ASCII block entry test.

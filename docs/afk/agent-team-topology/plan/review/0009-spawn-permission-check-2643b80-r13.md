# Review — 0009-spawn-permission-check (base 2643b80, round tag r13)

policy: lean · activated: delta-sweep (also the owner of the round 12 high finding), test-veracity (the delta touches tests) · skipped: scope-and-impact (the delta stays inside Scope), logic-correctness and code-quality (delta under 150 changed lines and 6 files), consistency-sweep (no scope escalation) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: c5481ed · delta diff: 2643b80..c5481ed · forge ledger: pull request 112, keys 0009-spawn-permission-check/f067 to f069

Verdict: advisory — crit=0 high=0 med=2 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| TV-1 | f068 | medium | test | scripts/tests/test_team_permission.py:299 | The first-match test had only one matching entry | fixed in b2babf7: a later `Bash(*)` also matches |
| TV-2 | f069 | medium | test | scripts/team/permission.py:136 | No test covered the UTF-8 decoding of the adapter listing | fixed in b2babf7: a settings folder with a non-ASCII name; red without the decoding on Windows |
| ds-01 | f067 | low | correctness | scripts/team/permission.py:136 | Lenient decoding turned a non-UTF-8 path into a silent skip | fixed in b2babf7: strict decoding, a refusal on bad bytes |

59 tests pass and 6 skip on Windows; 64 pass and 1 skips on WSL Linux.

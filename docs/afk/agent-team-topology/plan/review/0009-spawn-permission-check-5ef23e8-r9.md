# Review — 0009-spawn-permission-check (base 5ef23e8, round tag r9)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 8 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: b397b3d · delta diff: 5ef23e8..b397b3d without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..b397b3d plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f050 to f054

Verdict: advisory — crit=0 high=0 med=1 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| tv-r9-001 | f050 | medium | test | scripts/tests/test_team_permission.py:216 | No test checked that a stale refusal says nothing was started | fixed in d824640: one helper for every refusal |
| tv-r9-002 | f051 | low | test | scripts/tests/test_team_permission.py:259 | The block-list test did not check the rule or /afk:setup in the refusal | fixed in d824640 |
| cs-r9-001 | f052 | low | correctness | scripts/team/permission.py:97 | The missing refusal claimed the harness will ask | fixed in d824640 |
| cs-r9-002 | f053 | low | spec | PROVIDERS.md:186 | Row H15 and ADR-0005 read as ok whenever the rule is present | fixed in d824640 (D-90; the ADR is unchanged) |
| cs-r9-003 | f054 | low | correctness | hooks/lib/providers/codex.sh:76 | The Codex comment stated an untried premise as fact | fixed in d824640 |

39 tests pass and 1 skips on WSL Linux; 34 pass and 6 skip on Windows; the static tier passed at b397b3d (49). Dropping "nothing was started" from any refusal fails a test.

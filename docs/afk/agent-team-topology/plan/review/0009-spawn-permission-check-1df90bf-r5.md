# Review — 0009-spawn-permission-check (base 1df90bf, round tag r5)

policy: lean · scope escalated · activated: delta-sweep, test-veracity (the delta touches tests), consistency-sweep (scope escalation) · skipped: fix-owner specialists (round 4 had no critical or high finding), scope-and-impact (the delta stays inside Scope; plan records excluded), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 6a58db7 · delta diff: 1df90bf..6a58db7 without docs/afk/agent-team-topology/plan/ · surface: every file in 53d1586..6a58db7 plus the specs and setup files that state the same facts · forge ledger: pull request 112, keys 0009-spawn-permission-check/f031 to f036

Verdict: advisory — crit=0 high=0 med=1 low=5

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| cs-r5-001 | f034 | medium | spec | skills/afk/setup/MANIFEST.md:391 | SDD §14 C19 and the contract still say row H15 is always skipped with no human present | fixed in eaab05b (D-84) |
| DS-1 | f031 | low | smell | skills/afk/setup/MANIFEST.md:391 | The no-human rule for a provider-layer refusal is stated in three places in one file | deferred to the feature review gate (lean policy) |
| tv-r5-001 | f032 | low | test | scripts/tests/test_team_permission.py:171 | The ownership test drives only the `.claude` entry | fixed in eaab05b: named after it, limit stated |
| tv-r5-002 | f033 | low | test | scripts/tests/test_team_permission.py:342 | No test pinned the row's provider-layer handling | fixed in eaab05b |
| cs-r5-002 | f035 | low | spec | PROVIDERS.md:189 | SDD §8 still promised the check covers every source of harness asking | fixed in eaab05b (D-85) |
| cs-r5-003 | f036 | low | spec | PROVIDERS.md:186 | SDD §8 and §9b and contract 0015 say every refusal names the rule | fixed in eaab05b (D-86; the 0015 bullet is the human's) |

32 tests pass and 1 skips on WSL Linux; 29 pass and 4 skip on Windows.

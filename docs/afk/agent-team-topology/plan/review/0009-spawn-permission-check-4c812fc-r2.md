# Review — 0009-spawn-permission-check (base 4c812fc, round tag r2)

policy: lean · activated: delta-sweep, logic-correctness (lean trigger: 0010 consumes this slice), test-veracity (the delta touches tests), scope-and-impact (the delta touches CHANGELOG.md and .claude/wiring-ious.md, outside Scope) · skipped: fix-owner specialists beyond those (r1's only high finding was logic-correctness's) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: cf432e0 · delta diff: 4c812fc..cf432e0 · full diff (context): 53d1586..cf432e0 · forge ledger: pull request 112, keys 0009-spawn-permission-check/f014 to f020

Verdict: advisory — crit=0 high=0 med=1 low=6

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| tv-r2-001 | f014 | medium | test | hooks/lib/providers/claude.sh:93 | No test drove the home-directory and git-dir guards on the main-checkout read | fixed in 384f2f0; the ownership guard cannot be faked without root and stays untested |
| lc-r2-001 | f015 | low | correctness | PROVIDERS.md:188 | The text said the adapter refuses when both other functions are missing; the code refuses when either is | fixed in 384f2f0 |
| ds-002 | f016 | low | compliance | PROVIDERS.md:187 | The main-checkout read conditions are stated twice in one section | deferred to the feature review gate (lean policy) |
| s-001 | f017 | low | scope | scripts/team/permission.py:59 | Setup row H15 did not say what to do on a provider-layer refusal | fixed in 384f2f0 |
| s-002 | f018 | low | scope | PROVIDERS.md:188 | The add-harness checklist did not name the spawn functions | fixed in 384f2f0 (D-82) |
| tv-r2-002 | f019 | low | test | scripts/tests/test_team_permission.py:120 | One test chose its expected answer by platform | fixed in 384f2f0: one test per platform |
| tv-r2-003 | f020 | low | test | scripts/tests/test_team_permission.py:190 | The missing-function test skipped the third function and the kept rule | fixed in 384f2f0 |

The new guard tests failed when each guard was reverted in a scratch copy on WSL Linux. 29 tests pass and 3 skip on Windows; 31 pass and 1 skips on WSL.

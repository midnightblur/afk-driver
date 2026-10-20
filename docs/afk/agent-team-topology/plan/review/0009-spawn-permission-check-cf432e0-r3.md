# Review — 0009-spawn-permission-check (base cf432e0, round tag r3)

policy: lean · activated: delta-sweep, test-veracity (the delta touches tests), scope-and-impact (the delta touches providers/CONFORMANCE.md, outside Scope; D-82) · skipped: fix-owner specialists (round 2 had no critical or high finding), logic-correctness and code-quality (delta under 150 changed lines and 6 files) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 384f2f0 · delta diff: cf432e0..384f2f0 · full diff (context): 53d1586..384f2f0 · forge ledger: pull request 112, keys 0009-spawn-permission-check/f021 to f024

Verdict: advisory — crit=0 high=0 med=2 low=2

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| ds-001 | f021 | medium | correctness | skills/afk/setup/MANIFEST.md:386 | Row H15 called every provider-layer refusal a plugin defect and named no final status for it | fixed in 1df90bf: report `needs-human: <says>` |
| tv-r3-001 | f023 | medium | test | scripts/tests/test_team_permission.py:162 | The git-dir guard test passed with the guard deleted, because it checked loaded files, not listed files | fixed in 1df90bf: the tests assert the adapter lists 3 files |
| ds-002 | f022 | low | spec | PROVIDERS.md:187 | PROVIDERS.md omitted the tested git-dir skip | fixed in 1df90bf |
| sai-r3-01 | f024 | low | scope | skills/afk/setup/MANIFEST.md:387 | The opt-in election would still offer the row on a provider-layer refusal | fixed in 1df90bf |

On WSL Linux, deleting the git-dir guard and deleting the home-directory guard each fail their test; 31 tests pass and 1 skips there, and 34 pass and 3 skip on Windows.
f021 and f024 repeat round 2's shape (a changed rule whose sibling text was not updated), so round 4 runs scope-escalated.

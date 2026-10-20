# Review — 0005-pattern-resolver-and-builtin-records (base 2454924, round tag r3)

policy: lean · delta round · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: scope-and-impact (the delta stays inside the Scope globs), logic-correctness and code-quality (delta under 150 lines and 6 files), the design-level concerns (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level findings, so no verify pass · mutation probe: 3 survivors became r-001 to r-003
reviewed head: af57533 · delta: commit af57533 · forge ledger: pull request 112, keys 0005-pattern-resolver-and-builtin-records/f019 to f021

Verdict: advisory — crit=0 high=0 med=0 low=3

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | low | test | scripts/tests/test_team_resolver.py:434 | No case with a moderator role equal in value to the added one | fixed in 824fd86 |
| r-002 | low | test | scripts/tests/test_team_resolver.py:434 | One test body checked two clash shapes | fixed in 824fd86 |
| r-003 | low | test | scripts/tests/test_team_resolver.py:434 | Nothing pinned that the first debate step is named | fixed in 824fd86 |

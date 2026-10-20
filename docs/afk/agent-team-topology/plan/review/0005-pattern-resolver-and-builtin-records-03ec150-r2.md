# Review — 0005-pattern-resolver-and-builtin-records (base 03ec150, round tag r2)

policy: lean · delta round · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: scope-and-impact (the delta stays inside the Scope globs), logic-correctness and code-quality (delta under 150 lines and 6 files), the design-level concerns (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level findings, so no verify pass · mutation probe: run by test-veracity on a scratch copy; 3 survivors became r-002 to r-004
reviewed head: 2454924 · delta: commit 2454924 · forge ledger: pull request 112, keys 0005-pattern-resolver-and-builtin-records/f015 to f018

Verdict: advisory — crit=0 high=0 med=3 low=1

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | correctness | scripts/team/resolver.py:130 | The loop walk could reach a later role's undefined target and crash with exit 1 | fixed in af57533 |
| r-002 | medium | test | scripts/tests/test_team_resolver.py:428 | No three-role ring in the report-loop test | fixed in af57533 |
| r-003 | medium | test | scripts/tests/test_team_resolver.py:440 | A missing moderator part had no test | fixed in af57533 |
| r-004 | low | test | scripts/tests/test_team_resolver.py:432 | The moderator-name clash test used one pattern for both sides | fixed in af57533 |

# Review — 0025-dashboard-team-section (base 3bccf52, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity (always), refactor-safety (the diff edits existing lines) · skipped: api-contract, domain-alignment (no trigger), logic-correctness (Complexity: standard, no lean trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 70fef27 · diff: 3bccf52..70fef27 · forge ledger: pull request 112, keys 0025-dashboard-team-section/f001 to f006

Verdict: blocking — crit=0 high=0 med=2 low=4 (7 reviewer findings merged by file, line and issue into 6)

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f001 | medium | test | skills/afk/mission-control/scripts/tests/test_contract.py:604 | Only one parked agent was tested, so the earliest park time was never chosen among several | fixed in e2a87a0: a test with three parked agents and a resumed one |
| r-002 | f002 | medium | test | skills/afk/mission-control/scripts/mc/assets/shell.html:969 | No test checked that the shell's team and progress renderers read keys the section data holds | fixed in e2a87a0: a test checks every key the two renderers read |
| r-003 | f003 | low | scope | skills/afk/mission-control/scripts/mc/assets/shell.html:1188 | The grey dot and the tip change every live section, not only the team section | fixed in e2a87a0: plan D-132 records it as intended, and a reason is posted on the line |
| r-004 | f004 | low | scope | skills/afk/mission-control/SKILL.md:15 | GLOSSARY.md:273 still said live sections come only from the plan's artifacts | fixed in e2a87a0: the glossary names the team run manifest (plan D-131) |
| r-005 | f005 | low | test | skills/afk/mission-control/scripts/tests/test_contract.py:663 | One test loops over three bad manifests | deferred to the feature gate (low test style) |
| r-006 | f006 | low | test | skills/afk/mission-control/scripts/tests/test_contract.py:683 | The watch test waits on fixed sleeps and a 5 s deadline | deferred to the feature gate (low test style) |

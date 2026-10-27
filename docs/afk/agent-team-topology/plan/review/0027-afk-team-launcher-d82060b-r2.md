# Review — 0027-afk-team-launcher (base d82060b, round tag r2)

policy: lean · delta round · activated: delta-sweep (always), test-veracity (delta touches tests), refactor-safety (pre-existing lines changed), logic-correctness (delta over 150 lines; complexity complex) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: e3c5e93 · diff: d82060b..e3c5e93 · verified: no design-level finding at medium or above · forge ledger: pull request 112, round 2

Verdict: advisory — crit=0 high=0 med=2 low=5

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f013 | medium | test | delta-sweep, test-veracity | scripts/tests/test_team_permission.py:611 | The host-afk-bin test strips the host afk-bin before the check runs, so it covers the missing case again | fixed 2ec37d3: split into an isolation test and a test with another afk-team later on PATH |
| r-002 | f014 | medium | correctness | logic-correctness | skills/afk/setup/scripts/python_runtime.py:326 | ps_quote doubles only the ASCII apostrophe; PowerShell also ends a literal at U+2018 to U+201B | fixed 2ec37d3; a live pwsh run showed the ParserError before the fix |
| r-003 | f015 | low | spec | delta-sweep | adr/design/0017…md:23 | The ADR Decision sentence still names afk-team.cmd only | deferred to the feature gate (wording, outside Scope) |
| r-004 | f016 | low | correctness | delta-sweep | scripts/team/permission.py:135 | Any entry containing afk-team.py reads as an old team entry | fixed 2ec37d3 |
| r-005 | f017 | low | correctness | logic-correctness | skills/afk/setup/scripts/python_runtime.py:319 | A start that fails exits with the session's last native code | fixed 2ec37d3; both PowerShells exited 0 before the fix |
| r-006 | f018 | low | smell | delta-sweep | skills/afk/setup/scripts/python_runtime.py:365 | The rename-away block copies place_entry's | deferred to the feature gate (lean policy) |
| r-007 | f019 | low | correctness | refactor-safety | skills/afk/setup/scripts/python_runtime.py:369 | The rename-away branch also runs when the target does not exist | fixed 2ec37d3 |

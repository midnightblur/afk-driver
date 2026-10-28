# Review — 0011-job-supervisor (base f3bddc15, round tag r3)

policy: lean · delta round · reviewers: delta-sweep, test-veracity, scope-and-impact · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: 695f71f · forge ledger: pull request 112, round 3

Verdict: advisory — crit=0 high=0 med=1 low=2

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f019 | medium | correctness | delta-sweep | scripts/team/supervisor.py:37 | The new `limit reached ... (resets\|try again)` alternative reads a non-provider error that says `try again` as a provider limit. | fixed 666f14f |
| r-002 | f020 | low | test | test-veracity | scripts/tests/test_team_supervisor.py:278 | No limit_line test reaches the 'try again' branch of the new 'limit reached' alternative | fixed 666f14f |
| r-003 | f021 | low | test | test-veracity | scripts/tests/test_team_supervisor.py:267 | The local-time oracle is bound to the machine's zone, so on a UTC machine it cannot tell local time from UTC | fixed 666f14f |

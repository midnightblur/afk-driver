# Review — 0011-job-supervisor (base f3bddc15, round tag r2)

policy: lean · delta round · reviewers: delta-sweep, test-veracity, scope-and-impact · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: bc5c5cf · forge ledger: pull request 112, round 2

Verdict: advisory — crit=0 high=0 med=2 low=3

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f014 | medium | correctness | delta-sweep | scripts/team/supervisor.py:39 | Possible wrong reset time: ISO now matches a bare date-time, so a timestamp prefix on a limit line wins over the line's own reset text. | fixed 695f71f |
| r-002 | f015 | low | correctness | delta-sweep | scripts/team/supervisor.py:36 | Possible missed provider limit: LIMIT now needs 'usage limit', 'hit your limit', 'N-hour limit' or 'weekly limit', so a plain 'limit reached' line reads as exited (inferred; wording of every provider not verified). | fixed 695f71f |
| r-003 | f016 | low | test | test-veracity | scripts/tests/test_team_supervisor.py:289 | Possible untested LIMIT alternatives: no limit_line test uses '<n>-hour limit' or 'weekly limit'. | fixed 695f71f |
| r-004 | f017 | low | test | test-veracity | scripts/tests/test_team_supervisor.py:264 | Possible weak oracle: the no-offset ISO test computes its expectation with the same call the code uses. | fixed 695f71f |
| r-005 | f018 | medium | scope | scope-and-impact | .claude/wiring-ious.md:40 | The supervisors-folder IOU names a consumer (0012 step 2) whose contract does not list the folder, so possibly nothing will delete it. | fixed 695f71f |

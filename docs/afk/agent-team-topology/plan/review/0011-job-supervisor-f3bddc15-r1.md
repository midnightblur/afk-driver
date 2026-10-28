# Review — 0011-job-supervisor (base f3bddc15, round tag r1)

policy: lean · full round · reviewers: spec-fidelity, scope-and-impact, test-veracity, logic-correctness · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: 3040a20 · forge ledger: pull request 112, round 1

Verdict: advisory — crit=0 high=0 med=7 low=6

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f001 | medium | correctness | logic-correctness | scripts/team/supervisor.py:34 | The provider-limit pattern matches lines that are not a provider limit, so a crashed headless run gets parked instead of exited. | fixed bc5c5cf |
| r-002 | f002 | medium | correctness | logic-correctness | scripts/team/supervisor.py:36 | An ISO 8601 reset time with no zone offset gives a wrong reset time, not none: the clock fallback reads the minutes and seconds as the hour and minute, or drops the date. | fixed bc5c5cf |
| r-003 | f003 | medium | correctness | logic-correctness | scripts/team/supervisor.py:42 | A reset date with no year, or with a day word such as `tomorrow`, is dropped, and the clock time alone gives a reset time on the wrong day. | fixed bc5c5cf |
| r-004 | f004 | medium | test | test-veracity | scripts/team/supervisor.py:62 | The counter test proves only the processed folder; ids in inbox and bodies are not shown to raise the counter (D-151) | fixed bc5c5cf |
| r-005 | f005 | medium | test | test-veracity | scripts/team/supervisor.py:92 | No test holds a claim whose holder state is 'unknown', so narrowing the refusal to 'same' survives | fixed bc5c5cf |
| r-006 | f006 | medium | test | test-veracity | scripts/team/supervisor.py:218 | The handle-only watch path has no test where agent-status answers alive, so dropping the alive check survives | fixed bc5c5cf |
| r-007 | f007 | medium | test | test-veracity | scripts/tests/test_team_supervisor.py:75 | ended() hands out a finished process id with no started_at, so a reused id makes the supervise loop wait for ever | fixed bc5c5cf |
| r-008 | f008 | low | scope | scope-and-impact | .claude/wiring-ious.md:38 | The wiring IOU for the supervisor's start argument stays open, although this slice lands supervisor.py and the end-to-end test of agent-start starting it. | fixed bc5c5cf |
| r-009 | f009 | low | scope | scope-and-impact | scripts/team/supervisor.py:84 | The slice adds a new run-directory folder `<run>/supervisors/<agent-id>/` (claim files that are never deleted, plus each parked body's source .txt at line 259), but the cleanup contract that deletes run files does not list it. | fixed bc5c5cf |
| r-010 | f010 | low | spec | spec-fidelity | scripts/team/supervisor.py:93 | In the window D-150 names, the second supervisor's exit 2 reaches no caller: agent-start already answered 0 with its process id. | fixed bc5c5cf |
| r-011 | f011 | low | test | test-veracity | scripts/team/supervisor.py:145 | No 12 am or 12 pm reset time is tested, so dropping `% 12` survives | fixed bc5c5cf |
| r-012 | f012 | low | correctness | logic-correctness | scripts/team/supervisor.py:203 | A poll that lands between the headless agent's exit and the job owner's status write reads exit_code as unknown, so an exit-0 run whose log names a limit gets parked. | fixed bc5c5cf |
| r-013 | f013 | low | test | test-veracity | scripts/team/supervisor.py:209 | No test pins that a relative reset time counts from the log's last write | fixed bc5c5cf |

# Review — 0006-transport-family-and-herdr (base cedb959, round tag r4)

policy: lean · round 4 delta roster: delta-sweep (always); no critical or high finding was remediated in round 3 · delta 2dbb316..1212097
reviewed head: 1212097 · diff: cedb959..1212097 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=1 low=0

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f039 | medium | test | scripts/tests/test_team_transport.py:680 | No test covers the other side of the new `pid is None` guard: a stop given a pid whose pane close fails must still answer stopped true. If the guard were dropped, every test would still pass. | fixed in 3ce1a42 |

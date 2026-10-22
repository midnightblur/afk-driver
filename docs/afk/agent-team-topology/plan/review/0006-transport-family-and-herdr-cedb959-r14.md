# Review — 0006-transport-family-and-herdr (base cedb959, round tag r14)

policy: lean · round 14 delta roster: delta-sweep (always), test-veracity · delta 3ef51e1..5fb3964
reviewed head: 5fb3964 · diff: cedb959..5fb3964 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=2 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f078 | medium | correctness | adapters/transport/process.py:295 | Possible: the sweep's skip set follows Windows parents only, so an orphan that is the MSYS parent of the caller is not skipped and gets killed, and the walk returns the caller's own descendants. | fixed in 421c9a9 |
| r-002 | f079 | medium | test | scripts/tests/test_team_transport.py:834 | Possible gap: the snapshot-walk test pins killing the caller's own MSYS parent and never covers the caller's or a member's other descendants. | fixed in 421c9a9 |
| r-003 | f080 | low | smell | docs/afk/agent-team-topology/plan/DECISIONS.md:653 | D-92's 'To reverse' line names `_msys_children`, which this delta deletes. | deferred gate=feature |

# Review — 0006-transport-family-and-herdr (base cedb959, round tag r8)

policy: lean · round 8 delta roster: delta-sweep (always); no critical or high finding was remediated in round 7 · delta 9850cc0..c3a30da
reviewed head: c3a30da · diff: cedb959..c3a30da · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=1 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f043 | medium | correctness | adapters/transport/multiplexer/herdr.md:71 | Busy-pane trap row opens with 'holds messages until its turn and Stop handlers end' and then says claude/codex take them earlier, so the row contradicts itself. | fixed in 87d3a63 |
| r-002 | f044 | low | smell | adapters/transport/multiplexer/herdr.md:45 | The edited delivery paragraph now has 'either way' twice in consecutive sentences, and the second says nothing new. | deferred to the feature review gate (low wording) |

# Review — 0006-transport-family-and-herdr (base cedb959, round tag r6)

policy: lean · round 6 delta roster: delta-sweep (always); no critical or high finding was remediated in round 5 · delta 8e4565f..c335776 (the live re-run record and the herdr recipe sentence)
reviewed head: c335776 · diff: cedb959..c335776 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=1 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f040 | medium | test | providers/CONFORMANCE.md:469 | The Codex V35 re-run cell claims 'both times' all 3 messages were held until the 90 s command ended and 'none went into the running turn', but the first run does not show that. | fixed in 9850cc0 |
| r-002 | f041 | low | correctness | adapters/transport/multiplexer/herdr.md:45 | The recipe says a busy codex pane 'answers them in that turn', but the evidence in the same commit shows it answered only the last message. | fixed in 9850cc0 |

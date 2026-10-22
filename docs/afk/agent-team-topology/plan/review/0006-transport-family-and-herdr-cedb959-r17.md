# Review — 0006-transport-family-and-herdr (base cedb959, round tag r17)

policy: lean · round 17 delta roster: delta-sweep (always); no critical or high finding was remediated in round 16 · delta 3aa4bf3..89c5eac
reviewed head: 89c5eac · diff: cedb959..89c5eac · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=1 low=1

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f083 | medium | correctness | BEHAVIORS.md:16 | Possible stale short form: the managed pane-agent-rule still says role agents stay subagents unless a pane tool is found, but the doctrine now lets a forced transport.kind (e.g. headless) decide. | fixed in aa2c9bf |
| r-002 | f084 | low | correctness | GLOSSARY.md:76 | The Role agent definition still gives only two outcomes (pane agent or subagent) and omits the forced-kind case the delta adds to DELEGATION.md. | deferred gate=feature |

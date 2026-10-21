# Review — 0006-transport-family-and-herdr (base cedb959, round tag r3)

policy: lean · round 3 delta roster: delta-sweep (always), logic-correctness (owner of a round 2 high finding) · delta 04c45c4..2dbb316
reviewed head: 2dbb316 · diff: cedb959..2dbb316 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=2 low=2

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f035 | medium | correctness | adapters/transport/headless/headless.py:89 | On Windows the prompt file is written in text mode, so every line break in the prompt reaches the harness as CRLF, not as the prompt's own LF; the new test cannot see it because the stub reads stdin with universal newlines. | fixed in 1212097 |
| r-002 | f036 | medium | correctness | adapters/transport/multiplexer/herdr.py:310 | The r-010 fix covers only the no-tool path: with herdr usable, a handle-only stop whose pane close fails still answers stopped true, method 'pane close', though nothing was killed and the agent runs on in its open pane. | fixed in 1212097 |
| r-003 | f037 | low | correctness | adapters/transport/headless/headless.py:138 | agent-read reads the status after the log chunk, so a run that finishes its cut character and exits between the two reads gets that cut lead byte decoded as U+FFFD and the marker moved past it, losing the character. | fixed in 1212097 |
| r-004 | f038 | low | smell | adapters/transport/process.py:247 | process.stop takes over the shared kill-and-answer block for herdr and the no-tool path, but Headless.agent_stop keeps its own copy of the same survivors answer, so the consolidation left a drifted third twin. | fixed in 1212097 |

# Review — 0006-transport-family-and-herdr (base cedb959, round tag r2)

policy: lean · round 2 delta roster: delta-sweep (always), logic-correctness (owner of round 1 high findings) · delta 4ebc258..04c45c4
reviewed head: 04c45c4 · diff: cedb959..04c45c4 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=2 med=6 low=2

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f025 | high | spec | adapters/transport/headless/headless.py:87 | A headless start through a .cmd/.bat harness shim now refuses any prompt holding a line break, a double quote, %, ^, &, /, <, > or !, instead of keeping cmd.exe out of the prompt's path. | fixed in 2dbb316 |
| r-002 | f026 | high | correctness | adapters/transport/multiplexer/herdr.py:414 | When the marker's body lines are no longer on screen, the footer-only splits still match the unchanged TUI footer, so agent-read returns no text with complete true and every new line is lost. | fixed in 2dbb316 |
| r-003 | f027 | medium | smell | adapters/transport/multiplexer/multiplexer.py:56 | _stop_without_tool is a near-copy of Herdr.agent_stop's kill block, and the copy has already drifted on its wait budget. | fixed in 2dbb316 |
| r-004 | f028 | medium | correctness | adapters/transport/process.py:188 | Possible: on macOS `ps -o sid=` is not a keyword, so session_members answers [] and the orphan sweep silently does nothing while agent-stop answers stopped true. | fixed in 2dbb316 |
| r-005 | f029 | medium | correctness | adapters/transport/process.py:220 | Likely: the creation-time filter also drops MSYS children, so a background child of an MSYS process that later exec'd is left out of the tree and survives agent-stop. | fixed in 2dbb316 |
| r-006 | f030 | medium | correctness | scripts/team/probe.py:46 | A configuration file that cannot be read or is not UTF-8 still reads as no configuration, because afk-config.py crashes with exit 1, the same code as an absent key. | fixed in 2dbb316 |
| r-007 | f031 | medium | correctness | scripts/team/probe.py:137 | The dispatch timeout kills only the outer bash, so the verb's Python process keeps running (POSIX) or the timeout does not return until the verb exits (Windows), yet the answer says the verb 'was stopped'. | fixed in 2dbb316 |
| r-008 | f032 | medium | test | scripts/tests/test_team_transport.py:715 | No test covers the second half of the tab fix: a successor numbered from the highest number in use, not from the count of the step's tabs. | fixed in 2dbb316 |
| r-009 | f033 | low | correctness | adapters/transport/headless/headless.py:60 | A log that ends for good in a cut UTF-8 lead byte (an agent killed mid-character) never reads complete true; the marker stays one byte short forever. | fixed in 2dbb316 |
| r-010 | f034 | low | correctness | adapters/transport/multiplexer/multiplexer.py:59 | With no usable tool and a handle but no pid, agent-stop answers stopped true 'nothing to kill' though the agent still runs in its unclosed pane. | fixed in 2dbb316 |

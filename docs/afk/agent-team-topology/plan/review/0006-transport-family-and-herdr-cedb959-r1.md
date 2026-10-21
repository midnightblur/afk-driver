# Review — 0006-transport-family-and-herdr (base cedb959, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity (always), logic-correctness (complex slice), refactor-safety (the slice edits existing lines in ADAPTERS.md, MANIFEST.md, CONFORMANCE.md, .claude/wiring-ious.md) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
reviewed head: 4ebc258 · diff: cedb959..4ebc258 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=3 med=13 low=8

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f001 | high | correctness | adapters/transport/multiplexer/herdr.py:196 | A Codex resume that never reaches idle spends the whole start budget, so the cleanup that follows gets no time and leaves the pane open. | fixed in 04c45c4 |
| r-002 | f002 | high | correctness | adapters/transport/multiplexer/herdr.py:301 | agent-read with since_marker likely returns empty text on a TUI pane: new output appears above an unchanged input-box footer, and the marker matches that footer at the end. | fixed in 04c45c4 |
| r-003 | f003 | high | correctness | adapters/transport/process.py:185 | On Windows the process tree adopts unrelated processes whose dead parent's id was reused by a member of the agent's tree, and kill_tree force-kills them. | fixed in 04c45c4 |
| r-004 | f004 | medium | spec | adapters/transport/contract.py:137 | The multiplexer's herdr detection runs before the verb's Deadline starts and can take up to 20 s, outside the 10000 ms budgets of agent-status and agent-list. | fixed in 04c45c4 |
| r-005 | f005 | medium | spec | adapters/transport/contract.py:138 | contract.run catches only Answer, so any OSError or subprocess timeout inside a verb exits 1 with a Python traceback, which is none of the house answer shapes. | fixed in 04c45c4 |
| r-006 | f006 | medium | correctness | adapters/transport/headless/headless.py:61 | Possible: on Windows a harness installed as a .cmd shim (npm install) runs through cmd.exe, which cuts a multi-line prompt at the first line break and expands %VAR% and & inside it. | fixed in 04c45c4 |
| r-007 | f007 | medium | correctness | adapters/transport/headless/headless.py:76 | A start whose job owner reports no pid within 15 s answers unavailable, but the owner keeps running and starts the agent, leaving an untracked headless run. | fixed in 04c45c4 |
| r-008 | f008 | medium | correctness | adapters/transport/headless/job.py:80 | Likely: on Windows each headless agent opens a visible console window, since the owner runs DETACHED_PROCESS and starts the console harness with no CREATE_NO_WINDOW. | fixed in 04c45c4 |
| r-009 | f009 | medium | spec | adapters/transport/multiplexer/multiplexer.py:37 | The multiplexer agent-stop refuses with exit 4 whenever herdr detection fails, so it neither kills the tree by process id nor answers stopped false. | fixed in 04c45c4 |
| r-010 | f010 | medium | correctness | adapters/transport/process.py:202 | On POSIX agent-stop never uses the session job.py leads, so a descendant reparented to init before the stop survives while stop answers stopped true. | fixed in 04c45c4 |
| r-011 | f011 | medium | correctness | scripts/team/probe.py:41 | The probe reads an unreadable configuration as no configuration and accepts an invalid forced kind with no conflict. | fixed in 04c45c4 |
| r-012 | f012 | medium | spec | scripts/team/probe.py:120 | A verb that runs past its budget makes dispatch raise TimeoutExpired, so probe.py crashes instead of giving SDD §3's after-timeout answer. | fixed in 04c45c4 |
| r-013 | f013 | medium | test | scripts/tests/test_team_transport.py:64 | The time-budget test only compares the BUDGET_MS constant table. No test shows that a verb stops at its budget, or that agent-start and agent-send make exactly one attempt. | fixed in 04c45c4 |
| r-014 | f014 | medium | test | scripts/tests/test_team_transport.py:173 | No test proves the headless run is held by an operating-system job; the stop path kills by kill_tree, which works without any job. | fixed in 04c45c4 |
| r-015 | f015 | medium | test | scripts/tests/test_team_transport.py:327 | FakeHerdr replaces Herdr.call entirely, so no test covers how real herdr output is parsed into answers and error codes. The gone-pane, receiver_gone and idempotent-close branches all rest on herdr answer shapes the author wrote into the fake. | fixed in 04c45c4 |
| r-016 | f016 | medium | test | scripts/tests/test_team_transport.py:556 | The V31 seam test passes whatever the partial installer does: no herdr binary exists anywhere on the probe's PATH, and there is no positive control. | fixed in 04c45c4 |
| r-017 | f017 | low | spec | ADAPTERS.md:209 | ADAPTERS.md says configuration never sets AFK_CFG_TRANSPORT, which contradicts D-63 and the slice's own MANIFEST env row. | fixed in 04c45c4 |
| r-018 | f018 | low | correctness | ADAPTERS.md:228 | Reworded gate-coverage sentence leaves the gate's own pointer text calling "Adding a kind" the list of the four checked places. | deferred(feature: low wording or test style) |
| r-019 | f019 | low | correctness | adapters/transport/headless/headless.py:113 | A read that stops at the 1 MiB cap or at the live end can split a UTF-8 character, giving replacement characters on both sides of the marker. | fixed in 04c45c4 |
| r-020 | f020 | low | correctness | adapters/transport/headless/job.py:26 | On Windows the final status write can fail while agent-status is reading the file, losing the exit code. | fixed in 04c45c4 |
| r-021 | f021 | low | correctness | adapters/transport/multiplexer/herdr.py:358 | A tab name whose last word is a number never matches its own tab, so every start opens a new tab; a successor label can also repeat. | fixed in 04c45c4 |
| r-022 | f022 | low | test | scripts/tests/test_team_probe.py:35 | Every resolve_kind test fakes the configuration reader. No test of the forced-kind or pane-switch path runs the real `afk-config.py get transport.kind` against a real .afk/config.yaml. | fixed in 04c45c4 |
| r-023 | f023 | low | test | scripts/tests/test_team_transport.py:185 | One headless test covers start, status, read, read-since-marker, stop, status after the stop, and a repeat stop (an eager test). | deferred(feature: low wording or test style) |
| r-024 | f024 | low | test | scripts/tests/test_team_transport.py:558 | The V31 proof of setup's 'not fixed' rule matches a prose line together with its exact line wrap and indent. | deferred(feature: low wording or test style) |

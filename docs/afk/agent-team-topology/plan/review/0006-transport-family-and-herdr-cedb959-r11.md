# Review — 0006-transport-family-and-herdr (base cedb959, round tag r11)

policy: lean · round 11 delta roster: delta-sweep (always), logic-correctness, code-quality, test-veracity · delta 81b06fc..4ec66f9
reviewed head: 4ec66f9 · diff: cedb959..4ec66f9 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=8 low=5

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f046 | medium | test | adapters/transport/multiplexer/herdr.py:311 | The herdr tool's agent_stop gained with_kin=True, but no test fails if it is dropped. | fixed in 747014a |
| r-002 | f047 | medium | correctness | adapters/transport/process.py:155 | A failed or partial kin sweep is silent, so agent-stop can still answer stopped true while an orphan runs. | fixed in 747014a |
| r-003 | f048 | medium | test | adapters/transport/process.py:255 | Nothing tests the safety clause that spares the caller and its ancestors. | fixed in 747014a |
| r-004 | f049 | medium | correctness | adapters/transport/process.py:257 | kin kills any newer process in a shared console or session whose parent is alive, not only ones whose parent ended; the caller's own siblings and children are not spared | fixed in 747014a |
| r-005 | f050 | medium | smell | adapters/transport/process.py:258 | Possible blurred failure: a console or session member whose creation time cannot be read is dropped from kin without a trace. | fixed in 747014a |
| r-006 | f051 | medium | smell | adapters/transport/process.py:259 | Possible over-kill on POSIX: _born is whole-second ISO text, so a neighbour in the same session born earlier within the root's second passes 'born no earlier than the root'. | fixed in 747014a |
| r-007 | f052 | medium | test | scripts/tests/test_team_transport.py:778 | Two of the new tests do not wait for the orphan to leave the process tree, so they can pass without the fix. | fixed in 747014a |
| r-008 | f053 | low | smell | adapters/transport/process.py:6 | Module docstring says kin is 'a newer process in the root's console', but the code reads the console or session of every tree member. | fixed in 747014a |
| r-009 | f054 | low | smell | adapters/transport/process.py:152 | Unnamed constants: 0x00000008 (DETACHED_PROCESS) and the 4096 process-list cap in the helper. | fixed in 747014a |
| r-010 | f055 | low | smell | adapters/transport/process.py:237 | Possible mysterious names: _born aliases creation_time or _created; _containers returns processes, not containers. | fixed in 747014a |
| r-011 | f056 | low | test | scripts/tests/test_team_transport.py:759 | The own-pane variant's 'older neighbour survives' assertion cannot fail. | fixed in 747014a |
| r-012 | f057 | low | test | scripts/tests/test_team_transport.py:761 | The first new test's cleanup raises ValueError on an empty pid file and then leaks its 300 s processes. | fixed in 747014a |
| r-013 | f058 | medium | correctness | adapters/transport/multiplexer/CONTRACT.md:27 | agent-stop can still answer stopped true while an orphan survives, when the orphan's console holds no tree member (inferred, not live-tested) | fixed in 747014a |

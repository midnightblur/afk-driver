# Review — 0006-transport-family-and-herdr (base cedb959, round tag r12)

policy: lean · round 12 delta roster: delta-sweep (always), logic-correctness, code-quality, test-veracity · delta 4ec66f9..4b909e9
reviewed head: 4b909e9 · diff: cedb959..4b909e9 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=1 med=7 low=4

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f059 | high | correctness | adapters/transport/process.py:350 | A live child of an orphan is neither swept nor killed, yet agent-stop answers stopped true. | fixed in e6f2584 |
| r-002 | f060 | medium | correctness | adapters/transport/process.py:123 | When Git's `ps` is missing or fails, the sweep treats every MSYS process with a gone Windows parent as an orphan, without reporting a gap. | fixed in e6f2584 |
| r-003 | f061 | medium | test | adapters/transport/process.py:168 | No test reads the console helper's second output line or its access-denied and failure branches, so the 'could not be read' honesty path on Windows is unproven end to end. | fixed in e6f2584 |
| r-004 | f062 | medium | correctness | adapters/transport/process.py:179 | A pool member whose creation time cannot be read, with a live Windows parent id, is dropped from the sweep with no gap reported. | fixed in e6f2584 |
| r-005 | f063 | medium | correctness | adapters/transport/process.py:288 | A process missing from the process listing, or an empty listing, counts as 'parent ended' instead of 'unknown' | fixed in e6f2584 |
| r-006 | f064 | medium | test | scripts/tests/test_team_transport.py:795 | Unit test named 'never the caller or an ancestor' never puts an ancestor of the caller or of the root in the swept pool. | fixed in e6f2584 |
| r-007 | f065 | medium | test | scripts/tests/test_team_transport.py:796 | The Windows `_parent_ended` rule that a parent id held by a newer process counts as ended is never exercised. | fixed in e6f2584 |
| r-008 | f066 | medium | test | scripts/tests/test_team_transport.py:804 | No test covers an orphan that has its own live child. | fixed in e6f2584 |
| r-009 | f067 | low | smell | adapters/transport/process.py:174 | The Windows `_parent_ended` takes a `peers` parameter it never uses. | deferred gate=feature |
| r-010 | f068 | low | smell | adapters/transport/process.py:272 | Three start-time helpers with overlapping names (`creation_time`, `_created`, `_started`), and POSIX `_started` re-parses the /proc stat field that `creation_time` already parses | deferred gate=feature |
| r-011 | f069 | low | smell | adapters/transport/process.py:347 | `extra: list[int] = ()` annotates a list but defaults to a tuple | deferred gate=feature |
| r-012 | f070 | low | test | scripts/tests/test_team_transport.py:802 | `alive` is patched to always True, so the 'unreadable start time of a dead process raises no gap' branch is untested. | fixed in e6f2584 |

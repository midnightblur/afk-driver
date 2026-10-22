# Review — 0006-transport-family-and-herdr (base cedb959, round tag r13)

policy: lean · round 13 delta roster: delta-sweep (always), logic-correctness, code-quality, test-veracity · delta 4b909e9..3ef51e1
reviewed head: 3ef51e1 · diff: cedb959..3ef51e1 · forge ledger: pull request 112

Verdict: advisory — crit=0 high=0 med=5 low=2

| Id | Key | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|---|
| r-001 | f071 | medium | correctness | adapters/transport/process.py:130 | A Git `ps` failure at the second read is swallowed, so kin's descendant walk can miss a Git Bash descendant of an orphan and agent-stop still answers `stopped: true`. | fixed in a02ad0b |
| r-002 | f072 | medium | test | adapters/transport/process.py:320 | No test fails if the `m not in skip` filter on an orphan's descendants is removed. | fixed in a02ad0b |
| r-003 | f073 | medium | correctness | providers/CONFORMANCE.md:489 | The third re-run records V28 and Q20 as passed, but its own Codex evidence shows an orphan descendant (`cat.exe` 30548) still alive after `stopped` true, explained only by an unverified inference. | fixed in 5fb3964 |
| r-004 | f074 | medium | test | scripts/tests/test_team_transport.py:820 | No test runs the new `_msys_parents` failure branches (non-zero exit, OSError) or the `_msys_children` fallback; the Windows kin test patches `_msys_parents` to return None directly. | fixed in a02ad0b |
| r-005 | f075 | medium | test | scripts/tests/test_team_transport.py:943 | The delta's own motivating case, a Git Bash orphan that has MSYS children, has no automated test; the MSYS test still uses an orphan with no child. | fixed in a02ad0b |
| r-006 | f076 | low | smell | adapters/transport/process.py:312 | Possible variable double-duty: `ended` is a tri-state (True, False, None) and line 312 relies on truthiness to tell True from None. | deferred gate=feature |
| r-007 | f077 | low | test | scripts/tests/test_team_transport.py:812 | The no-process-list test leaves `_msys_parents` unpatched, so on Windows it runs Git's real `ps -e`. | fixed in a02ad0b |

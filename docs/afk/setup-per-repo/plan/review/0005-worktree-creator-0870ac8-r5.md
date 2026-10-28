# Review — 0005-worktree-creator, round 5

- Verdict: **blocking** — crit=0 high=1 med=1 low=4
- Diff: the whole slice 55b4098..0870ac8 (scope stays escalated: round 4 found two copies a fix had missed); the round-4 delta d1fd0ba..0870ac8 for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 34 fixed keys) · no fix-owner specialists (round 4 had no critical or high finding) · skipped: scope-and-impact (the orchestrator's Scope grep over the delta found only Scope files and plan records), logic-correctness and code-quality (code delta 101 lines in 4 files) · deferred: agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design findings); r-001 raised from medium to high after the referee ran test_setup_h6_probe.py (8 of 12 fail at 0870ac8, 12 of 12 pass at 55b4098).
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | test | consistency-sweep | scripts/tests/test_setup_h6_probe.py:115 | Setup's H6 probe still resolves the removed worktreeBasePath key, so 8 of its 12 tests fail (raised to high after the referee ran them) |
| r-002 | medium | spec | consistency-sweep | docs/afk/setup-per-repo/SDD.md:80 | SDD still says setup is the only writer of short-name markers; the creator now writes them too |
| r-003 | low | correctness | delta-sweep | scripts/create-worktree:278 | The creator refuses an unusable harness folder even for a listed repository, which never uses it |
| r-004 | low | test | test-veracity | scripts/tests/test_create_worktree_name.py:61 | The creator and guard tests read the developer's real ~/.afk |
| r-005 | low | test | consistency-sweep | scripts/tests/test_create_worktree_placement.py:332 | A test name still says every climbing --dir is refused; only an agent's is |
| r-006 | low | test | test-veracity | scripts/tests/test_h2_move.py:612 | The move helper's unreadable, stale and raced marker branches have no test |

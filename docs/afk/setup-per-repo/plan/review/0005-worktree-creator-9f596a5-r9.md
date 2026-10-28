# Review — 0005-worktree-creator, round 9

- Verdict: **advisory** — crit=0 high=0 med=4 low=17
- Diff: the whole slice 55b4098..9f596a5 (scope stays escalated); the round-8 delta 304657f..9f596a5 for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 93 fixed keys), logic-correctness and code-quality (code delta 198/160 lines) · not activated: scope-and-impact (the delta touches only Scope files) · deferred: agents-md-compliance, design-quality, resilience, and the smell findings r-014, r-018, r-019 (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped; r-012, r-013 share r-011's cause; r-016 duplicates r-015; r-021 duplicates r-004.
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | smell | code-quality | hooks/lib/h2_move.py:123 | settle passes its results back through a closure dict, and its clear() is dead |
| r-002 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:138 | A created worktree removed later is restarted under its spent name |
| r-003 | medium | test | test-veracity | scripts/tests/test_h2_move.py:762 | No test for a marker without `started`, or one that names no path |
| r-004 | medium | test | test-veracity | scripts/tests/test_h2_move.py:805 | The spawn-failure test does not count spawns on the second call |
| r-005 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/0005-worktree-creator.md:38 | The contract's exit-code bullets and the SDD §14 row keep the claim D-59 and D-64 corrected |
| r-006 | low | smell | consistency-sweep | hooks/lib/h2_move.py:5 | The module docstring says the marker is keyed by the pane id first |
| r-007 | low | correctness | consistency-sweep | hooks/lib/h2_move.py:9 | The docstring says every marker access is locked; remove-worktree's is not |
| r-008 | low | smell | code-quality | hooks/lib/h2_move.py:96 | `failed` and `fresh` do not say what they build |
| r-009 | low | correctness | logic-correctness | hooks/lib/h2_move.py:135 | A marker from older code without `started` is restarted at once |
| r-010 | low | smell | code-quality | hooks/lib/h2_move.py:139 | The start-a-move tail appears twice in settle |
| r-011 | low | correctness | logic-correctness | hooks/lib/h2_move.py:142 | Placement runs under the marker lock, past a waiting call's 2-second wait |
| r-012 | low | smell | consistency-sweep | hooks/lib/h2_move.py:152 | Same cause as r-011, seen as a retry state shown as a failure |
| r-013 | low | correctness | delta-sweep | hooks/lib/h2_move.py:153 | Same cause as r-011, seen from the delta |
| r-014 | low | smell | code-quality | scripts/afk-config.py:1504 | The retired key is special-cased by literal in three places |
| r-015 | low | smell | consistency-sweep | scripts/afk-move.py:133 | afk-move.py repeats the load-by-path idiom |
| r-016 | low | smell | code-quality | scripts/afk-move.py:133 | Same as r-015 |
| r-017 | low | correctness | logic-correctness | scripts/afk-move.py:266 | A create() that raises records no outcome |
| r-018 | low | smell | code-quality | scripts/create-worktree:308 | The placement answer's folder slot means three things |
| r-019 | low | smell | delta-sweep | scripts/remove-worktree.py:264 | The marker's lock file is never removed with its marker |
| r-020 | low | test | test-veracity | scripts/tests/test_h2_move.py:669 | The two-calls tests hold the lock for fixed sleeps near the 2-second wait |
| r-021 | low | test | delta-sweep | scripts/tests/test_h2_move.py:804 | Same as r-004, seen from the delta |

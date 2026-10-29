# Review — 0005-worktree-creator, round 10

- Verdict: **advisory** — crit=0 high=0 med=2 low=11
- Diff: the whole slice 55b4098..c251507 (scope stays escalated); the round-9 delta 9f596a5..c251507 for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep (no findings), test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 111 fixed keys), logic-correctness and code-quality (code delta 181 lines) · not activated: scope-and-impact (the delta touches only Scope files) · deferred: agents-md-compliance, design-quality, resilience
- Round cap: round 10 of 10 ends with findings open, so the settle loop ends in stalemate; nothing is fixed this round.
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | low | correctness | logic-correctness | hooks/lib/h2_move.py:134 | A creation that fails after `git worktree add` has its error dropped while the folder exists |
| r-002 | low | test | test-veracity | scripts/tests/test_h2_move.py:861 | The created-then-removed test pins only an aged `started` |
| r-003 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/PLAN.md:133 | PLAN.md smoke rows 21 and 22 keep the exit-code wording D-64 corrected |
| r-004 | low | correctness | consistency-sweep | scripts/afk-move.py:125 | afk-move.py record() still calls the marker the pane's |
| r-005 | low | test | consistency-sweep | scripts/tests/create-worktree-smoke.sh:231 | The smoke check that an unlisted entry is not copied passes on a failed run |
| r-006 | low | test | consistency-sweep | hooks/tests/hook-smoke.sh:358 | hook-smoke runs the H-2 guard refusal with the real home and live spawning (unverified) |
| r-007 | medium | smell | code-quality | scripts/create-worktree:350 | The short-name claim heredoc drives five private repo_list members |
| r-008 | low | smell | code-quality | scripts/create-worktree:314 | ask_placement reaches afk_config and pathlib through placement's imports |
| r-009 | low | smell | code-quality | scripts/create-worktree:306 | Parent mode copies placement's containment test and state literals |
| r-010 | medium | smell | code-quality | hooks/lib/h2_move.py:91 | The not-listed fallback path in target() lacks the creator's folder check |
| r-011 | low | smell | code-quality | hooks/lib/h2_move.py:119 | plan() hands results out of settle through a dict and reuses `chosen` |
| r-012 | low | smell | code-quality | scripts/afk-config.py:1500 | The resolve key is computed twice and the retired key is a literal three times |
| r-013 | low | pattern-debt | code-quality | scripts/afk-move.py:95 | A second new `_load` copy beside the repo's existing path loaders |

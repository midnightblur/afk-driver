# Review — 0005-worktree-creator, round 6

- Verdict: **advisory** — crit=0 high=0 med=2 low=14
- Diff: the whole slice 55b4098..6c84b5d (scope stays escalated); the round-5 delta 0870ac8..6c84b5d for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated, and fix-owner for round 5's high; fed the 40 fixed keys), scope-and-impact (the orchestrator's Scope grep over the delta hit skills/afk/setup/MANIFEST.md) · skipped: logic-correctness and code-quality (code delta 98 lines in 6 files) · deferred: agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 1 dropped as a duplicate (test-veracity's unreadable-marker finding is r-001's cause seen from its test).
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | delta-sweep | hooks/lib/h2_move.py:126 | A corrupt move marker makes the move helper name a new path on every call and never start a creation |
| r-002 | medium | test | test-veracity | scripts/tests/create-worktree-smoke.sh:202 | The smoke test's --skip-build-gate check passes even when the creator run failed |
| r-003 | low | spec | consistency-sweep | docs/afk/setup-per-repo/SDD.md:80 | SDD still says setup is the only writer of short-name markers; only the ledger records the creator as a second writer |
| r-004 | low | spec | consistency-sweep | docs/afk/setup-per-repo/SDD.md:130 | SDD's creator rows miss two exit-3 refusals (any catalog R rule, an agent's climbing --dir) |
| r-005 | low | smell | delta-sweep | scripts/tests/create-worktree-smoke.sh:48 | The smoke test's sandbox-home comment names a test 9 that does not exist |
| r-006 | low | test | test-veracity | scripts/tests/test_create_worktree_name.py:184 | A test claims a template without {name} never reuses a branch but creates one worktree |
| r-007 | low | test | test-veracity | scripts/tests/test_create_worktree_name.py:471 | The orphan-worktree test checks a different contract per git version inside one body |
| r-008 | low | test | test-veracity | scripts/tests/test_create_worktree_name.py:507 | The live-lock test proves a negative with a fixed sleep |
| r-009 | low | test | test-veracity | scripts/tests/test_create_worktree_placement.py:191 | The root-refusal test is parametrized by a bare index |
| r-010 | low | test | test-veracity | scripts/tests/test_create_worktree_placement.py:298 | A ~ parent inside the main checkout has no test |
| r-011 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:535 | Four plugin-source gate cases compare two silent passes |
| r-012 | low | test | delta-sweep | scripts/tests/test_protected_branch_acceptance.py:773 | The protected-branch acceptance and guard tests still read the developer's real ~/.afk |
| r-013 | low | compliance | consistency-sweep | skills/afk/bug/CONFIG.md:72 | The bug skill's fail-closed row still says a dispatch refusal is a root-rule failure |
| r-014 | low | scope | scope-and-impact | skills/afk/setup/MANIFEST.md:131 | Setup's H6 prose still names the derived worktree base the probe no longer asks for |
| r-015 | low | scope | scope-and-impact | skills/afk/setup/MANIFEST.md:149 | The slice edits setup's MANIFEST.md, outside its Scope, with the exception recorded nowhere |
| r-016 | low | compliance | consistency-sweep | skills/afk/setup/MANIFEST.md:1003 | The AFK_WORKTREE_FOLDER row does not say a listed repository ignores it |

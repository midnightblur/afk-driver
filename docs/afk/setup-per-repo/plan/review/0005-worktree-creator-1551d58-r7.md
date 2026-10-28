# Review — 0005-worktree-creator, round 7

- Verdict: **advisory** — crit=0 high=0 med=9 low=16
- Diff: the whole slice 55b4098..1551d58 (scope stays escalated: round 6 found four uncorrected copies); the round-6 delta 6c84b5d..1551d58 for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 56 fixed keys), scope-and-impact (the orchestrator's Scope grep over the delta hit setup's MANIFEST.md and two protected-branch test files), logic-correctness and code-quality (code delta 156 lines in 11 files) · deferred: agents-md-compliance, design-quality, resilience, and the smell findings r-002, r-006, r-007, r-017, r-018, r-021, r-022 (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped; r-014 and r-016 share causes with r-003 and r-005 and are settled by the same fix.
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | compliance | delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:424 | D-60 decided a Scope exception the protocol keeps outside agent authority |
| r-002 | medium | smell | code-quality | hooks/lib/h2_move.py:89 | The move helper's unlisted-folder fallback copies the creator's and skips its folder check |
| r-003 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:105 | The marker write needs hard links; a volume without them stops every move |
| r-004 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:109 | A failed temp-file cleanup after the marker link turns a recorded move into an exception |
| r-005 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:136 | A torn read deletes a live marker, and the move script's fallback write can tear it |
| r-006 | medium | smell | code-quality | scripts/create-worktree:304 | The creator's parent heredoc re-derives path containment placement owns |
| r-007 | medium | smell | code-quality | scripts/create-worktree:350 | The creator calls private repository-list helpers |
| r-008 | medium | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:62 | The excluded-gate reason claims the dispatcher case runs the gates; it stops first |
| r-009 | medium | scope | scope-and-impact | skills/afk/setup/MANIFEST.md:127 | Three out-of-Scope edits rest on a self-ruled decision |
| r-010 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:310 | D-44's member list still counts the four plugin-source gates as cases |
| r-011 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:391 | D-55 says all five private calls run under the lock; the marker read does not |
| r-012 | low | compliance | delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:421 | D-59 names a passage without quoting it; D-46 to D-60 have no journal lines |
| r-013 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:421 | D-59 quotes the settings-writer scenario as a marker rule |
| r-014 | low | correctness | delta-sweep | hooks/lib/h2_move.py:105 | Same cause as r-003, seen from the delta |
| r-015 | low | correctness | logic-correctness | hooks/lib/h2_move.py:133 | A marker dropped between the check and the read is reported as a failed creation |
| r-016 | low | correctness | delta-sweep | hooks/lib/h2_move.py:136 | Same cause as r-005, seen from the delta |
| r-017 | low | smell | code-quality | scripts/afk-config.py:1022 | An unexplained module alias in the root resolver |
| r-018 | low | smell | code-quality | scripts/afk-config.py:1479 | The resolve dispatch is split across two places |
| r-019 | low | correctness | consistency-sweep | scripts/afk-config.py:1503 | An unknown resolve key is offered the removed worktreeBasePath |
| r-020 | low | smell | code-quality | scripts/afk-move.py:131 | The move script's fallback write contradicts its own comment |
| r-021 | low | smell | code-quality | scripts/create-worktree:314 | The creator reaches another module through placement's imports |
| r-022 | low | smell | code-quality | scripts/create-worktree:396 | A second config call only decorates a status line |
| r-023 | low | test | test-veracity | scripts/tests/test_h2_move.py:654 | The swap-failure path of the outcome write has no test |
| r-024 | low | spec | consistency-sweep | skills/afk/bug/SKILL.md:67 | The bug skill says every fixer worktree goes under the root; an unlisted one does not |
| r-025 | low | spec | consistency-sweep | skills/afk/setup/MANIFEST.md:53 | Setup's notes still say H6 keeps a K3 probe |

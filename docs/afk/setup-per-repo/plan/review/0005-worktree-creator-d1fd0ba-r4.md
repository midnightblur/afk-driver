# Review — 0005-worktree-creator, round 4

- Verdict: **advisory** — crit=0 high=0 med=2 low=3
- Diff: the whole slice 55b4098..d1fd0ba (scope escalated after two rounds of fixes that left a sibling path); the round-3 delta 98a0a12..d1fd0ba for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 29 fixed keys) · no fix-owner specialists (round 3 had no critical or high finding) · skipped: scope-and-impact (the orchestrator's Scope grep over the delta found only Scope files and plan records), logic-correctness and code-quality (code delta 141 lines in 3 files) · deferred: agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design findings).
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | delta-sweep | hooks/lib/h2_move.py:104 | The move helper loads placement before it checks for this session's recorded move, so a repeat call re-places and a bad root hides the pending worktree |
| r-002 | medium | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:362 | The outside-root adopt case passes whether or not the hook adds the session as an owner |
| r-003 | low | spec | consistency-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:344 | D-48's debt line names three of the five private repository-list calls the creator makes |
| r-004 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:977 | The cleanup test picks its removal route with if/elif on the member name |
| r-005 | low | spec | consistency-sweep | skills/afk/bug/SKILL.md:67 | The bug skill calls every creator exit 3 a K3 refusal; it is also a folder refusal |

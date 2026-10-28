# Review — 0005-worktree-creator, round 3

- Verdict: **advisory** — crit=0 high=0 med=2 low=5
- Diff: the round-2 fix delta 37e699d..98a0a12; the whole slice 55b4098..98a0a12 as context.
- policy: lean, delta round · activated: delta-sweep, test-veracity (the delta changes tests) · no fix-owner specialists (round 2 had no critical or high finding) · skipped: scope-and-impact (the orchestrator's Scope grep over the delta found only Scope files and plan records) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design findings).
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | compliance | delta-sweep | scripts/create-worktree:349 | The folder claim calls `repo_list.all_entries()`, documented as setup-only |
| r-002 | medium | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:892 | The outside-root table still has no positive check per case, only a list of crash texts |
| r-003 | low | smell | delta-sweep | scripts/create-worktree:36 | A reworded header comment line runs about 150 characters |
| r-004 | low | correctness | delta-sweep | scripts/create-worktree:389 | A developer's climbing `--dir` keeps `..` in the printed path and can make an empty short-name folder |
| r-005 | low | correctness | delta-sweep | scripts/create-worktree:410 | In `--parent` mode the claim takes the short name from a link-resolved folder |
| r-006 | low | test | test-veracity | scripts/tests/test_create_worktree_placement.py:384 | No test fails if the claim stops skipping the lock when the marker is right |
| r-007 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:926 | Two writing cases make their own fixture inside the worktree, so `the member wrote something` cannot fail |

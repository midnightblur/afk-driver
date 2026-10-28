# Review — 0005-worktree-creator, round 2

- Verdict: **advisory** — crit=0 high=0 med=4 low=4
- Diff: the round-1 fix delta 865b5fd..37e699d; the whole slice 55b4098..37e699d as context.
- policy: lean, delta round · activated: delta-sweep, spec-fidelity and logic-correctness and refactor-safety (owners of round-1 high findings), test-veracity (the delta changes tests) · skipped: scope-and-impact (the orchestrator's Scope grep over the delta found only Scope files and plan records) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design findings).
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | spec | spec-fidelity, delta-sweep | scripts/create-worktree:384 | The `--dir` refusal also binds a developer, who may create a worktree anywhere |
| r-002 | medium | correctness | delta-sweep | scripts/create-worktree:605 | An empty short-name folder with no marker is not claimed, so the next creation is refused |
| r-003 | medium | correctness | refactor-safety | scripts/create-worktree:605 | Agent `--parent` mode still makes a missing short-name folder with no marker |
| r-004 | medium | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:892 | The outside-root table still has no positive check per case; a writing member with no change passes |
| r-005 | low | correctness | logic-correctness | scripts/create-worktree:358 | A busy list lock ends the folder claim in a Python traceback |
| r-006 | low | test | test-veracity | scripts/tests/test_create_worktree_placement.py:332 | The `--dir` refusal has no test for a `..` that stays inside, nor for a developer |
| r-007 | low | test | test-veracity | scripts/tests/test_create_worktree_placement.py:345 | The folder claim's failure path has no test |
| r-008 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:933 | The EXCLUDED test's second check can never fail for a key with a suffix |

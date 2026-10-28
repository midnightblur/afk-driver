# Review: 0013-config-contract, round 5

Verdict: advisory, crit=0 high=0 med=0 low=2. Delta f004ed4..13b21d8.

policy: lean · activated: delta-sweep, test-veracity (delta touches tests) · skipped: scope-and-impact (every delta file is inside the Scope globs), no fix-owner specialist (no critical or high finding remediated) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate) · verified: no design-level finding, no verify pass

| # | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | low | correctness | scripts/create-worktree:284 | The last-resort comment said a git dir outside the tree derives nothing; a separate git dir named `.git` now derives. |
| r-002 | low | test | scripts/tests/test_afk_config.py:617 | The separate-git tests looped over both worktrees in one body, and nothing pinned the docs' `git worktree list` claim. |

Both fixed in 1cfdabd: the comment names a bare clone or a git dir not named `.git` (D-49), and the tests are parametrized per worktree and compare the base with the first entry of `git worktree list --porcelain`.

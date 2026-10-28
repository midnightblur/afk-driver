# Review: 0013-config-contract, round 2

Verdict: advisory, crit=0 high=0 med=0 low=1. Delta e5b86be..51bf4ae.

policy: lean · activated: delta-sweep, test-veracity (delta touches tests), scope-and-impact (delta touches scripts/create-worktree, outside the Scope globs; D-48) · skipped: no fix-owner specialist (no critical or high finding remediated) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate) · verified: no design-level finding, no verify pass

| # | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | low | correctness | scripts/afk-config.py:851 | A separate git folder that is itself named `.git` still derives a worktree base, though the docstring, `CONFIG.md` and the CHANGELOG say a separate git folder derives nothing. |

Round 1's fix for this case narrowed the docs but left the code deriving. Fixed in 7b432e5: `worktree_base` returns nothing when the main checkout's top folder is not the git folder's parent, and the test runs for a store named `x.git` and one named `.git`.

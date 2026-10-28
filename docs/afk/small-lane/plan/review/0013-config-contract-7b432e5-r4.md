# Review: 0013-config-contract, round 4

Verdict: advisory, crit=0 high=0 med=1 low=2. Delta 7b432e5..f004ed4.

policy: lean · activated: delta-sweep, test-veracity (delta touches tests) · skipped: scope-and-impact (every delta file is inside the Scope globs), no fix-owner specialist (no critical or high finding remediated) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate) · verified: no design-level finding of medium or higher, no verify pass

| # | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | medium | test | scripts/tests/test_afk_config.py:605 | An if/else on the parametrize value picked which assertion ran. |
| r-002 | low | design | scripts/afk-config.py:866 | The round-2 guard made a `.git`-named separate git folder's main checkout derive nothing while its linked worktree derived a base, so one repository's worktrees disagreed. |
| r-003 | low | test | scripts/tests/test_afk_config.py:594 | The test named "derives no worktree base" also asserted a derivation, without a return-code check. |

All fixed in 13b21d8. The guard is gone, so every worktree agrees; a separate git folder named `.git` derives beside its own parent, the folder `git worktree list` names first, and `CONFIG.md`, the CHANGELOG and the docstring say so. Each layout has its own named test.

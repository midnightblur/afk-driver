# Review: 0013-config-contract, round 3

Verdict: advisory, crit=0 high=0 med=2 low=0. Delta 51bf4ae..7b432e5.

policy: lean · activated: delta-sweep, test-veracity (delta touches tests) · skipped: scope-and-impact (every delta file is inside the Scope globs), no fix-owner specialist (no critical or high finding remediated) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate) · verified: no design-level finding, no verify pass

| # | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | medium | spec | CONFIG.md:329 | `CONFIG.md` named `git worktree list` as the mechanism for a linked worktree of a separate-git-folder checkout; the code derives from the git folder's parent. |
| r-002 | medium | test | scripts/tests/test_afk_config.py:593 | No test resolved the worktree base from a linked worktree, of an ordinary checkout or of a separate-git-folder one. |

Both fixed in f004ed4: `CONFIG.md` states the parent-folder rule, a new test checks a main checkout and its linked worktree agree, and the separate-git-folder test resolves from a linked worktree for both store names.

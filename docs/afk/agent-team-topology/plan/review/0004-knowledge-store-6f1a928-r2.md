# Review — 0004-knowledge-store (base 6f1a928, round tag r2)

policy: lean · delta round · activated: delta-sweep, test-veracity (the delta touches tests) · skipped: scope-and-impact (the delta stays inside the Scope globs), logic-correctness and code-quality (delta under 150 lines and 6 files), the design-level concerns (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level findings, so no verify pass
reviewed head: 2f0d48b · delta: commit 2f0d48b · forge ledger: pull request 112, key 0004-knowledge-store/f006

Verdict: advisory — crit=0 high=0 med=0 low=1

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | low | correctness | scripts/team/knowledge.py:190 | A nested role list such as [["pro"]] escapes the new role check with a bare TypeError | fixed in 5ab9a72 |

The fix also gives the stages argument the same check, and refuses a debater map that is not a map; each refused shape has a test that failed first.

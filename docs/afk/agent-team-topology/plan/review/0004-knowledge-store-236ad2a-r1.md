# Review — 0004-knowledge-store (base 236ad2a, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0012 consumes this slice) · skipped: refactor-safety (new files only), domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level findings, so no verify pass · mutation probe: not applicable (no production Java)
caller sets: the new functions have no caller outside scripts/tests/test_team_knowledge.py (repository grep for each name and for the module import); .claude/wiring-ious.md owes each one to a later step
reviewed head: 6f1a928 · slice diff: commits bdb09da and 6f1a928 · forge ledger: pull request 112, keys 0004-knowledge-store/f001 to f005

Verdict: advisory — crit=0 high=0 med=0 low=5

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | low | correctness | scripts/team/knowledge.py:198 | Debater roles given as one text turn into a set of letters, so the draft is never released and no error is raised | fixed in 2f0d48b |
| r-002 | low | correctness | scripts/team/knowledge.py:145 | A failed write of the temporary file leaves a torn file in the store | fixed in 2f0d48b |
| r-003 | low | test | scripts/tests/test_team_knowledge.py:133 | No test sets a verdict outside a debate | fixed in 2f0d48b |
| r-004 | low | test | scripts/tests/test_team_knowledge.py:318 | No damaged-file case for a file name that disagrees with its entry, or for an extra field | fixed in 2f0d48b |
| r-005 | low | test | scripts/tests/test_team_knowledge.py:344 | The "nothing is promoted" check only searched function names | fixed in 2f0d48b |

The spec and scope reviewers found nothing. The two logic findings went through the bug-fix path, each with a test that failed first. The three test findings were fixed directly; a mutation of each guard they name now fails at least one test.

# Review — 0005-pattern-resolver-and-builtin-records (base b33b6d0, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: 0010 consumes this slice), refactor-safety (one changed line in skills/afk/setup/MANIFEST.md) · skipped: domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level concern finding, so no verify pass · mutation probe: run by test-veracity on a scratch copy; 13 mutants survived and became findings r-002, r-003, r-012 and r-014
caller sets: no caller of the new functions exists outside scripts/tests/test_team_resolver.py (repository search); .claude/wiring-ious.md owes resolve_pattern( to 0010 and resolved_path( to 0012
reviewed head: 03ec150 · slice diff: commit 03ec150 · forge ledger: pull request 112, keys 0005-pattern-resolver-and-builtin-records/f001 to f014

Verdict: advisory — crit=0 high=0 med=3 low=11

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | correctness | scripts/team/resolver.py:181 | An edge end or step role that is a list or map crashes, exit 1, instead of a refusal | fixed in 2454924 |
| r-002 | medium | test | scripts/tests/test_team_resolver.py:89 | The no-limit-field check compared the records against the resolver's own field set | fixed in 2454924 |
| r-003 | medium | test | scripts/tests/test_team_resolver.py:56 | No test reached the unsafe feature or role name refusals | fixed in 2454924 |
| r-004 | low | correctness | scripts/team/resolver.py:122 | A role reporting to itself, or a loop of report targets, was accepted | fixed in 2454924 |
| r-005 | low | correctness | scripts/team/resolver.py:240 | Two debate steps with no hub wrote every moderator edge twice | fixed in 2454924 |
| r-006 | low | correctness | scripts/team/resolver.py:257 | A role named moderator gave a refusal that named the same pattern twice | fixed in 2454924 |
| r-007 | low | design | scripts/team/resolver.py:264 | Implied edges carry an implied key and an empty end that the record rules would refuse | deferred to the feature review |
| r-008 | low | spec | scripts/team/resolver.py:280 | An empty moderator part was not refused | fixed in 2454924 |
| r-009 | low | spec | scripts/team/patterns/STANDARD.md:54 | The standard claimed a model-form check the resolver does not run | fixed in 2454924 |
| r-010 | low | spec | scripts/team/resolver.py:331 | A combined pick writes a fourth source value | withdrawn: plan decision D-56 records it |
| r-011 | low | scope | .claude/wiring-ious.md:30 | The wiring list is outside the contract's Scope | withdrawn: the workflow requires the entry there |
| r-012 | low | test | scripts/tests/test_team_resolver.py:373 | Seven input guards had no test | fixed in 2454924 |
| r-013 | low | test | scripts/tests/test_team_resolver.py:119 | The reporting-duty asserts did not name the failing part | fixed in 2454924 |
| r-014 | low | test | scripts/tests/test_team_resolver.py:305 | No test checked the one-off pattern's sources entry | fixed in 2454924 |

The refactor-safety reviewer found nothing. Each fix has a test that failed first and now passes, and the module's 106 tests are green. Two disputes went to a fresh adjudicator, and both findings were withdrawn on the evidence.

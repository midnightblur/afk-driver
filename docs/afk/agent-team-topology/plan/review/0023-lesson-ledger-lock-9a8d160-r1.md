# Review — 0023-lesson-ledger-lock (base 9a8d160, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (the slice changes lines that existed at its base) · skipped: logic-correctness (no later slice consumes this one; Complexity standard), domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level concern finding, so no verify pass · mutation probe: Java only, so no probe; the implementer ran hand-made mutants (the old gate walk and the old create-worktree each fail their test)
reviewed head: 0cf8d25 · slice diff: 9a8d160..0cf8d25 · forge ledger: pull request 112, keys 0023-lesson-ledger-lock/f001 to f006

Verdict: advisory — crit=0 high=0 med=2 low=4

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r1-1 | medium | spec | hooks/lesson-append.sh:124 | A late waiter could move a fresh lock that a faster waiter had just taken over | fixed in 27c8946 |
| r1-2 | low | spec | hooks/native-contract-gate.sh:78 | The walk ran again up to 5 times and then failed, instead of skipping the vanished folder | fixed in 27c8946 |
| r1-3 | medium | test | hooks/lesson-append.sh:168 | No test for the lost-lock retry or the signal traps | fixed in 27c8946 |
| r1-4 | low | test | scripts/tests/test_lesson_filing.py:341 | The walk test's decoy lock could go stale if the gate runs over 10 s | deferred to the feature review gate |
| r1-5 | low | test | scripts/tests/test_lesson_filing.py:278 | The 30 s give-up test waits 30 s for real | deferred to the feature review gate |
| r1-6 | low | correctness | hooks/lesson-append.sh:156 | The event time was stamped before the lock wait | fixed in 27c8946 |

After the fix, removing the hand-back, the lost-lock re-check or the TERM trap each fails its new test.

# Review — 0001-safe-writer, round 3

- Verdict: **advisory** — crit=0 high=0 med=0 low=5
- Diff: the round-2 fix commit, ae9256a to 77ae17e (delta round).
- policy: lean · activated: delta-sweep, refactor-safety, test-veracity, logic-correctness, resilience (contract opt-in) · deferred: code-quality, agents-md-compliance, design-quality (→ feature gate)

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | low | correctness | logic-correctness, resilience | scripts/safe_write.py:178 | A temp file another process holds fails both deletes, and the second delete error still hides the refusal. |
| r-002 | low | test | delta-sweep, test-veracity | scripts/tests/test_safe_write.py:295 | `handle.closed` is true even when the handle never closed its descriptor, so a leak still passes. |
| r-003 | low | test | test-veracity, delta-sweep | scripts/tests/test_safe_write.py:339 | Under umask 027, a create mode of 644 and of 666 both give 640, so the test cannot tell them apart. |
| r-004 | low | test | test-veracity | scripts/tests/test_safe_write.py:367 | The path check uses a plain file, so naming the resolved file instead of the caller's path still passes. |
| r-005 | low | correctness | logic-correctness, resilience | scripts/tests/test_safe_write.py:379 | A read-only file on Windows is retried and reported as a busy swap, and the new test pins that wrong cause. |

Full finding data (why, fix, evidence): `0001-safe-writer-ae9256a-r3.findings.json`.

# Review — 0001-safe-writer, round 2

- Verdict: **advisory** — crit=0 high=0 med=1 low=4
- Diff: the round-1 fix commit, e7af26c to ae9256a (delta round).
- policy: lean · activated: delta-sweep, refactor-safety, test-veracity, logic-correctness · deferred: code-quality, agents-md-compliance, design-quality (→ feature gate)

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | logic-correctness | scripts/safe_write.py:191 | On Windows, a refused swap onto a read-only file leaves its read-only temp file behind, and the delete error hides the refusal. |
| r-002 | low | smell | delta-sweep | scripts/safe_write.py:167 | The "no free temp file name" refusal names the real file, not the caller's path; the docstring and the tests miss it. |
| r-003 | low | test | test-veracity | scripts/tests/test_install_block.py:438 | The test name says "creates nothing" though the lock file is created; the error-output check is weak. |
| r-004 | low | test | test-veracity | scripts/tests/test_safe_write.py:274 | The "closed exactly once" test cannot catch a descriptor that is never closed. |
| r-005 | low | test | test-veracity | scripts/tests/test_safe_write.py:305 | The umask test runs under whatever umask the process has, and its mode check sits inside an `if`. |

Full finding data (why, fix, evidence): `0001-safe-writer-e7af26c-r2.findings.json`.

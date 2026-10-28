# Review — 0001-safe-writer, round 4

- Verdict: **advisory** — crit=0 high=1 med=0 low=0
- Diff: the round-3 fix commit, 77ae17e to f45953e (delta round).
- policy: lean · activated: delta-sweep, refactor-safety, test-veracity, logic-correctness, resilience (contract opt-in) · deferred: code-quality, agents-md-compliance, design-quality (→ feature gate)
- verified: 1 upheld (a busy-swap test on a missing file failed against f45953e)

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | all five | scripts/safe_write.py:193 | The read-only check also fires for a file that does not exist yet, so on Windows a busy swap that creates a new file is refused at once as "is read-only" instead of retried. |

Full finding data (why, fix, evidence): `0001-safe-writer-77ae17e-r4.findings.json`.

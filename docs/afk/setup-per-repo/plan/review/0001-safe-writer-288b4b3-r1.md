# Review — 0001-safe-writer, round 1

- Verdict: **advisory** — crit=0 high=0 med=2 low=10
- Diff: the slice's `[0001-safe-writer]` commits from 288b4b3 to e7af26c. The INV-023 `COVERAGE.json` ledger was left out of the diff file because of its size. The reviewers could read it in the worktree.
- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (pre-existing lines changed), logic-correctness (later slices consume `update_locked`), resilience (contract opt-in) · skipped: domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality (→ feature gate)
- verified: 0 upheld / 1 downgraded / 0 dropped (r-001, medium → low)
- Caller set: INV-023 (`investigations/INV-023-safe-writer-move/`), taken at bd921b8. Production code did not change after that commit.
- Mutation probe: not applicable. The probe covers Maven modules only, and this diff is Python.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-002 | medium | correctness | logic-correctness, refactor-safety | scripts/safe_write.py:194 | The temp-file descriptor is closed twice: once by `fdopen` and again in `finally`. |
| r-003 | medium | correctness | refactor-safety, test-veracity | skills/afk/setup/scripts/install_block.py:236 | No test runs the rewritten legacy CLI path `_legacy`. |
| r-001 | low | design | resilience | scripts/safe_write.py:166 | A read-denying handle makes the between-retry re-read raise a raw `PermissionError`. |
| r-004 | low | scope | scope-and-impact | investigations/INV-008-secret-storage/COVERAGE.json:45238 | The commit range also masks five other ledgers (D-4). Those edits are not in the review diff. |
| r-005 | low | scope | scope-and-impact | investigations/INV-023-safe-writer-move/REPORT.md:7 | INV-023 says a busy swap used to exit 1. The old `main()` already exited 2. |
| r-006 | low | scope | scope-and-impact | hooks/genericity-allow.txt:41 | The allow-list edit lies outside `## Scope`, and no decision records it. |
| r-007 | low | design | resilience | scripts/safe_write.py:57 | The transform runs inside the lock, and no rule limits how long it can run. |
| r-008 | low | correctness | logic-correctness | scripts/safe_write.py:150 | Reading the umask briefly sets the umask to 0 for the whole process. |
| r-009 | low | design | resilience | scripts/safe_write.py:172 | A hard kill leaves a `.tmp` copy of the file, and nothing deletes it. |
| r-010 | low | test | test-veracity | scripts/safe_write.py:184 | No test proves the re-check after the temp-file write. |
| r-011 | low | test | test-veracity | scripts/tests/test_safe_write.py:214 | The real Windows busy-swap test depends on a timer and never asserts that a retry happened. |
| r-012 | low | correctness | logic-correctness | skills/afk/setup/scripts/install_block.py:153 | `write_if_unchanged(b"", b"")` on a missing file no longer creates an empty file. |

Full finding data (why, fix, evidence): `0001-safe-writer-288b4b3-r1.findings.json`.

# Review — 0005-worktree-creator, round 1

- Verdict: **blocking** — crit=0 high=2 med=5 low=7
- Diff: the slice's `[0005-worktree-creator]` commits from 55b4098 to 865b5fd.
- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complex), refactor-safety (pre-existing lines of create-worktree, afk-config.py and bug skill files changed) · skipped: domain-alignment (no entity, transaction or service method), api-contract (no new public interface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design findings).
- Caller set: INV-025 (`docs/afk/setup-per-repo/investigations/INV-025-reach-creator-at-head/`).
- Mutation probe: does not apply (no Java). No signal.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | refactor-safety | scripts/afk-config.py:1482 | `resolve worktreeBasePath` now exits 2, but the setup H6 probe still calls it |
| r-002 | high | spec | spec-fidelity, logic-correctness | scripts/create-worktree:332 | A listed repository's `--dir ../x` is refused by placement, but the creator ignores the verdict and cuts the worktree outside the short-name folder |
| r-003 | medium | scope | scope-and-impact | docs/afk/setup-per-repo/investigations/INV-025-reach-creator-at-head/COVERAGE.json:135 | The INV-025 caller-set ledger is verdict `partial`, not closed |
| r-004 | medium | correctness | logic-correctness | scripts/create-worktree:310 | Parent mode passes all 6 verdict fields, so a root refusal prints a corrupted ERROR line |
| r-005 | medium | test | test-veracity | scripts/tests/test_create_worktree_placement.py:279 | No test that `--name` ignores `--parent` |
| r-006 | medium | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:900 | Every AC-060 case only compares the outside twin with the inside twin |
| r-007 | medium | scope | scope-and-impact | skills/afk/bug/CONFIG.md:39 | K3 is redefined as `worktreeRoot`, but the setup H6 probe and the developer-values script still name the old key, with no hand-off |
| r-008 | low | scope | scope-and-impact | hooks/genericity-allow.txt:43 | `hooks/genericity-allow.txt` is edited but is not in Scope |
| r-009 | low | correctness | refactor-safety | scripts/create-worktree:381 | The destination check changed from `-d` to `-e` |
| r-010 | low | correctness | logic-correctness | scripts/create-worktree:576 | `mkdir -p` makes a short-name folder with no marker |
| r-011 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:43 | The EXCLUDED dict is read by no test |
| r-012 | low | test | test-veracity | scripts/tests/test_existing_worktree_outside_root.py:901 | A test body branches on the case's fields |
| r-013 | low | test | test-veracity | scripts/tests/test_h2_move.py:579 | h2_move's placement-read-failure branch has no test |
| r-014 | low | test | test-veracity | scripts/tests/test_h2_move.py:585 | The lazy-load test pins the loading mechanism, not the behaviour |

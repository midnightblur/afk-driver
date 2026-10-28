# Review — 0004-placement, round 1

- Verdict: **advisory** — crit=0 high=0 med=6 low=14
- Diff: the slice's `[0004-placement]` commit from cc6bff8 to 540a7d9.
- policy: lean, opt-in design-quality · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complex; 0005, 0006 and 0010 consume this slice), design-quality (opt-in), api-contract (new public result types for three consumers), refactor-safety (one PLAN.md status cell changed) · skipped: domain-alignment (no entity, transaction or service method) · deferred: code-quality, agents-md-compliance, resilience (→ feature gate)
- verified: 2 upheld / 2 downgraded / 0 dropped. r-003 was upheld with the settled design text, so its class names that cause (spec). r-007 and r-008 were downgraded to low.
- Caller set: every public symbol is new. Only the new test file calls it today. The later consumers are declared in `.claude/wiring-ious.md`.
- Mutation probe: does not apply (no Java). No signal.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | logic-correctness | scripts/placement.py:280 | A nested repository inside a worktree under the root is taken for the outer listed repository |
| r-002 | medium | correctness | spec-fidelity | scripts/placement.py:243 | `link/..` in a target is folded by text before links are resolved |
| r-003 | medium | spec | api-contract | scripts/placement.py:248 | An unlisted repository can still get an error from a broken machine file, though the design says "not listed" comes first |
| r-004 | medium | design | design-quality, refactor-safety | scripts/placement.py:162 | R-06 repeats the list module's folder-ownership rule through its private helpers |
| r-005 | medium | test | test-veracity | scripts/tests/test_placement.py:354 | No test of a sibling folder that shares the short name's prefix |
| r-006 | medium | test | test-veracity | scripts/tests/test_placement.py:430 | D-35 (git cannot name the main checkout) has no test |
| r-007 | low | design | api-contract | scripts/placement.py:236 | `check_target(target, folder)` lets a caller swap the two paths without an error |
| r-008 | low | design | api-contract | scripts/placement.py:76 | The result types do not say which fields each state sets |
| r-009 | low | correctness | refactor-safety | scripts/placement.py:54 | A module already loaded under the same name is reused without checking its file |
| r-010 | low | scope | scope-and-impact | scripts/placement.py:150 | The use of the list module's private helpers is not declared |
| r-011 | low | test | test-veracity | scripts/tests/test_placement.py:494 | The read test pins an exact count of four opens |
| r-012 | low | test | test-veracity | scripts/tests/test_placement.py:269 | Two R-06 outcomes have no test: an unreadable marker, and a file at the short-name path |
| r-013 | low | test | test-veracity | scripts/tests/test_placement.py:188 | Some test bodies branch or loop to pick their setup or checks |
| r-014 | low | design | design-quality | scripts/placement.py:303 | Two modules work out the main checkout from git |
| r-015 | low | design | design-quality | scripts/placement.py:246 | One private body serves both public calls, steered by which argument is None |
| r-016 | low | design | design-quality | scripts/placement.py:249 | The chain knows the literal rule id R-01 and filters rules by a scope string |
| r-017 | low | design | api-contract | scripts/placement.py:58 | The error carries only a message, unlike the list module's error |
| r-018 | low | design | api-contract | scripts/placement.py:97 | `machine_file()` is public with no named consumer |
| r-019 | low | design | api-contract | scripts/placement.py:93 | `ROOT_RULES` exposes a check that takes a private type |
| r-020 | low | design | api-contract | scripts/placement.py:223 | The root path has one shape when it passes and another when it is refused |

The full text of each finding (why, fix, evidence) is in `0004-placement-cc6bff8-r1.findings.json`.

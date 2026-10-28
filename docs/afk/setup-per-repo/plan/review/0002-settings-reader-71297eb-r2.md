# Review — 0002-settings-reader, round 2

- Verdict: **advisory** — crit=0 high=0 med=6 low=3
- Diff: the delta from 71297eb to 5f69f1b (round-1 fixes and the five carried keys); the full slice from 09444b0 was context only.
- policy: lean · delta round · activated: delta-sweep, refactor-safety, spec-fidelity, scope-and-impact, logic-correctness (fix owners of the round-1 high finding), test-veracity (delta touches tests) · skipped: domain-alignment, api-contract (no delta trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding, no verify pass
- Caller set: C:/t/p2b/rv/callers.md for symbols changed before the delta, plus C:/t/p2c/rv/callers-r2.md for the delta's additions.
- Ledger keys: r-001..r-009 posted as f018..f026 on PR #145; r-005 (f022) has no diff anchor and rides the summary note.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | scope | scope-and-impact, spec-fidelity, delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:175 | D-25 defers the stale MANIFEST.md obsidian row to 0010-setup-walk, but no contract or wiring IOU names that row. |
| r-002 | medium | correctness | logic-correctness | scripts/afk-config.py:549 | validate FILE on the machine file takes the layer 'repo' instead of 'home' when the repository root is the home folder. |
| r-003 | medium | spec | spec-fidelity | scripts/afk-config.py:477 | The public layer_reads widens the SDD §8 interface the Acceptance bullet says is implemented unmodified. |
| r-004 | medium | spec | delta-sweep, spec-fidelity | scripts/afk-config.py:827 | The jira.site check refuses any address with a path, though the spec types the key as a URL. |
| r-005 | medium | compliance | delta-sweep | CONFIG.md:257 | CONFIG.md still says the no-Python commit check blocks when any Discovery layer mentions repo-hooks. |
| r-006 | medium | test | test-veracity | scripts/afk-config.py:558 | Deleting the .git/HEAD check from the other-checkout detection fails no test. |
| r-007 | low | correctness | delta-sweep | scripts/afk-config.py:559 | The other-checkout branch finds the true checkout root, but main keeps the guessed root. |
| r-008 | low | spec | spec-fidelity, scope-and-impact, delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:157 | D-23 and D-11 still describe the state before the delta. |
| r-009 | low | test | test-veracity | scripts/tests/test_precommit_config_gate.py:172 | The blocked cases assert only exit status 2, not that the no-launcher block caused it. |

Details per finding (why, fix, evidence): `0002-settings-reader-71297eb-r2.findings.json`.

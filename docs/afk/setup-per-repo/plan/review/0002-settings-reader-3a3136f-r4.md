# Review — 0002-settings-reader, round 4

- Verdict: **advisory** — crit=0 high=0 med=0 low=2
- Diff: the delta from 3a3136f to eb22541 (round-3 fixes); the full slice from 09444b0 was context only.
- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests), scope-and-impact (delta edits `.claude/wiring-ious.md`, outside Scope), refactor-safety (pre-existing lines changed) · skipped: logic-correctness, code-quality (delta under 150 lines), domain-alignment, api-contract (no delta trigger), no fix owner (round 3 had no critical or high finding) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding, no verify pass
- Caller set: C:/t/p2c/rv/callers-r4.md.
- Ledger keys: r-001 → f031, r-002 → f032 on PR #145. test-veracity, scope-and-impact and refactor-safety returned no finding.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | low | correctness | delta-sweep | scripts/afk-config.py:555 | validate with no argument still warns about a home checkout's committed file, which validate FILE reads as both layers. |
| r-002 | low | compliance | delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:192 | D-28 leaves the two stale MANIFEST.md sentences to prose no gate reads. |

r-002 is deferred to the feature gate (lean policy, low compliance). Details per finding: `0002-settings-reader-3a3136f-r4.findings.json`.

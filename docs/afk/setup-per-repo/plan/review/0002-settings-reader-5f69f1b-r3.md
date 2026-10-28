# Review — 0002-settings-reader, round 3

- Verdict: **advisory** — crit=0 high=0 med=2 low=2
- Diff: the delta from 5f69f1b to 3a3136f (round-2 fixes); the full slice from 09444b0 was context only.
- policy: lean · delta round · activated: delta-sweep, test-veracity (delta touches tests), scope-and-impact (delta edits `.claude/wiring-ious.md`, outside Scope), refactor-safety (pre-existing lines changed) · skipped: logic-correctness, code-quality (delta under 150 lines), domain-alignment, api-contract (no delta trigger), no fix owner (round 2 had no critical or high finding) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: no design-level finding, no verify pass
- Caller set: C:/t/p2c/rv/callers-r3.md.
- Ledger keys: r-001..r-004 posted as f027..f030 on PR #145; r-004 (f030) has no diff anchor. test-veracity returned no finding.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | scope | scope-and-impact, delta-sweep | .claude/wiring-ious.md:12 | The new IOU is outside Scope, can never close or block, and is anchored to a decision rather than a 0010-setup-walk contract line. |
| r-002 | medium | spec | delta-sweep | scripts/afk-config.py:828 | jira.site now accepts a path, though INV-016 sets the base as scheme plus host and ADR-0004 keys sign-ins by host. |
| r-003 | low | correctness | refactor-safety | scripts/afk-config.py:550 | When the home folder really is a checkout, validate FILE reads its committed file as the home layer alone, unlike load(). |
| r-004 | low | correctness | delta-sweep | skills/afk/setup/MANIFEST.md:633 | MANIFEST.md P1 still says the commit gate blocks when any configuration layer mentions repo-hooks. |

Details per finding (why, fix, evidence): `0002-settings-reader-5f69f1b-r3.findings.json`.

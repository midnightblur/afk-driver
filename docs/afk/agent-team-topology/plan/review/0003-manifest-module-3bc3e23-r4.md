# Review — 0003-manifest-module (delta base 3bc3e23, round tag r4)

policy: lean · delta round · activated: delta-sweep, test-veracity (test code changed), scope-and-impact (the delta touches .claude/wiring-ious.md, outside the contract's Scope list, sanctioned by D-50 and D-51) · skipped: fix-owner specialists (no critical or high finding in round 3), logic-correctness and code-quality (delta under 150 lines and 6 files), agents-md-compliance (no new AGENTS.md chain), design-level triggers (none hit) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no finding from a design-level concern, so no verify pass · mutation probe: test-veracity found one surviving mutant (r-002); all 10 tried after the fix are killed · caller sets: no public signature changed
reviewed head: 284390f · delta: 3bc3e23..284390f (commit 284390f) · forge ledger: pull request 112, keys 0003-manifest-module/f038 and f039

Verdict: advisory — crit=0 high=0 med=2 low=0

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | correctness | scripts/team/manifest.py:277 | New comment claims the refresh closes the steal window, but a stealer that judged the lock stale before the utime can still rename it after the owner check | fixed in 130acfe |
| r-002 | medium | test | scripts/tests/test_team_manifest.py:380 | The refresh-before-check test does not pin the order its name claims; swapping the utime and the owner check survives | fixed in 130acfe |

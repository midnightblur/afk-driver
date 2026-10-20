# Review — 0003-manifest-module (delta base 284390f, round tag r5)

policy: lean · delta round · activated: delta-sweep, test-veracity (test code changed) · skipped: fix-owner specialists (no critical or high finding in round 4), scope-and-impact (orchestrator Scope grep: the delta touches only scripts/team/manifest.py and scripts/tests/test_team_manifest.py, inside Scope), logic-correctness and code-quality (delta under 150 lines and 6 files), agents-md-compliance (no new AGENTS.md chain), design-level triggers (none hit) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no finding from a design-level concern, so no verify pass · mutation probe: test-veracity found two surviving mutants, merged into r-001 at the same line; all 13 tried after the fix are killed · caller sets: no public signature changed
reviewed head: 130acfe · delta: 284390f..130acfe (commit 130acfe) · forge ledger: pull request 112, keys 0003-manifest-module/f040 to f042

Verdict: advisory — crit=0 high=0 med=2 low=1

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | correctness | scripts/team/manifest.py:212 | Give-back of a lock just proven live is not retried on a Windows file-in-use error, so it falls through to deleting that live lock | fixed in 23aae3a |
| r-002 | medium | correctness | scripts/team/manifest.py:280 | Comment says a steal judged before the refresh is given back, but a third writer that mkdirs the lock in the rename gap defeats the give-back | fixed in 23aae3a |
| r-003 | low | test | scripts/tests/test_team_manifest.py:394 | The first item of `held` is a constant sentinel, so `held == [True, True]` partly asserts the fake's own recording | fixed in 23aae3a |

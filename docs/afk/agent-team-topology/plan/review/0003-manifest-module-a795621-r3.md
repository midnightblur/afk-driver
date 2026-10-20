# Review — 0003-manifest-module (delta base a795621, round tag r3)

policy: lean · delta round · activated: delta-sweep, test-veracity (fix owner of round 2's high finding; test code changed), logic-correctness (delta over 150 lines; lean trigger), scope-and-impact (the delta touches .claude/wiring-ious.md, outside the contract's Scope list, sanctioned by D-50 and D-51) · skipped: agents-md-compliance (no new AGENTS.md chain), design-level triggers (none hit) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no finding from a design-level concern, so no verify pass · mutation probe: test-veracity sampled mutants on a scratch copy; 2 survived (r-003, r-005), all 8 tried after the fix are killed · caller sets: no public signature changed
reviewed head: 3bc3e23 · delta: a795621..3bc3e23 (commit 3bc3e23) · forge ledger: pull request 112, keys 0003-manifest-module/f029 to f037

Verdict: advisory — crit=0 high=0 med=5 low=4

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | medium | scope | .claude/wiring-ious.md:23 | The adopt_manifest IOU cites a 0015 acceptance about the wait job, not about adoption; no later contract plans the call that record_entry now requires first | fixed in 284390f |
| r-002 | medium | correctness | scripts/team/manifest.py:273 | The stated lock window is measured from the owner check, but staleness is measured from acquire, so the rename can land after the lock is stolen | fixed in 284390f |
| r-003 | medium | test | scripts/team/manifest.py:282 | The retry on deleting the temporary file is unproven: removing it leaves every test green | fixed in 284390f |
| r-004 | medium | test | scripts/tests/test_team_manifest.py:291 | The '100 polls' test depends on real sleeps, so whether it gets past 100 polls depends on machine speed | fixed in 284390f |
| r-005 | medium | test | scripts/tests/test_team_manifest.py:353 | The mid-write theft test deletes the lock before the check, so the branch for a lock now held by another writer is never exercised | fixed in 284390f |
| r-006 | low | correctness | scripts/team/manifest.py:284 | Likely: a temporary file that will not delete is now silently left in the run directory, not freed | fixed in 284390f |
| r-007 | low | test | scripts/tests/test_team_manifest.py:255 | A loop over lambdas drives the assertions, so a failure does not say which call broke | fixed in 284390f |
| r-008 | low | smell | scripts/tests/test_team_manifest.py:327 | Possible near-copy: new give-up test and mkdir_refused helper duplicate the existing always-refuse test and its inline refused stub | fixed in 284390f |
| r-009 | low | test | scripts/tests/test_team_manifest.py:375 | Possible fragile test: the unreadable owner hits the publish check only because the publish check happens to be the first `_owner` call | fixed in 284390f |

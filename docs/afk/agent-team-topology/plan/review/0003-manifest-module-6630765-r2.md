# Review — 0003-manifest-module (delta base 6630765, round tag r2)

policy: lean · delta round · activated: delta-sweep, test-veracity (fix owner of round 1's two high findings; test code changed), logic-correctness (delta over 150 lines; lean trigger), scope-and-impact (the delta touches .claude/wiring-ious.md, outside the contract's Scope list, sanctioned by D-50) · skipped: agents-md-compliance (no new AGENTS.md chain), design-level triggers (none hit) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no finding from a design-level concern, so no verify pass · mutation probe: test-veracity sampled 4 mutants on a scratch copy; 3 survived (r-001, r-003, r-004), all killed after the fix · caller sets: one private signature changed (_publish), no outside caller
reviewed head: a795621 · delta: 6630765..a795621 (commit a795621) · forge ledger: pull request 112, keys 0003-manifest-module/f020 to f028

Verdict: blocking — crit=0 high=1 med=5 low=3

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | high | test | scripts/team/manifest.py:228 | Surviving mutant: counting every lock refusal (FileExistsError too) passes all 111 tests, yet a writer behind a live lock then gives up after ~2s instead of waiting | fixed in 3bc3e23 |
| r-002 | medium | design | .claude/wiring-ious.md:23 | The one IOU line that D-50 relies on for adopt_manifest, remove_process and checkpoint_path is closed by the wiring gate on its next run, before any of those functions has a caller | fixed in 3bc3e23 |
| r-003 | medium | test | scripts/team/manifest.py:229 | The transient case (PermissionError while the lock folder still exists, i.e. being deleted) and the 100-refusal threshold have no test; both mutants survive | fixed in 3bc3e23 |
| r-004 | medium | test | scripts/team/manifest.py:269 | The unreadable-owner branch (`None` in `(token, None)`) is untested; replacing the check with `!= token` survives | fixed in 3bc3e23 |
| r-005 | medium | correctness | scripts/team/manifest.py:276 | Temp-file cleanup in finally can raise a raw PermissionError that replaces the module's ManifestError or aborts the lost-lock retry | fixed in 3bc3e23 |
| r-006 | medium | test | scripts/tests/test_team_manifest.py:311 | The mid-write steal test catches the check-before-write regression only through a 0.3s race on a leftover lock folder, not by asserting the stolen write was withheld | fixed in 3bc3e23 |
| r-007 | low | smell | scripts/team/manifest.py:240 | The same 'cannot write the manifest' error is built twice in _acquire | fixed in 3bc3e23 |
| r-008 | low | test | scripts/tests/test_team_manifest.py:257 | The 'and kept' half of the non-UTF-8 test is vacuous: only read_manifest runs, which never writes | fixed in 3bc3e23 |
| r-009 | low | test | scripts/tests/test_team_manifest.py:321 | A for-loop over ("replace", "fsync") with monkeypatch.undo() mid-body drives the asserts of two cases in one test | fixed in 3bc3e23 |

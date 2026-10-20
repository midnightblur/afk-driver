# Review — 0003-manifest-module (base b09d45b, round tag r1)

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (lean trigger: complexity is complex, and 0010, 0012 and 0025 consume this slice) · skipped: refactor-safety (new files only), domain-alignment, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
verified: no design-level findings, so no verify pass · mutation probe: not applicable (no production Java)
reviewed head: 6630765 · slice diff: commits 5d9b93f and 6630765 · forge ledger: pull request 112, keys 0003-manifest-module/f001 to f019

Verdict: blocking — crit=0 high=2 med=8 low=9

| Id | Severity | Class | Location | Finding | Outcome |
|---|---|---|---|---|---|
| r-001 | high | test | scripts/tests/test_team_manifest.py:78 | No test stores a valid park_until or started_at in an agent entry; a validator that rejects every ISO time passes | fixed in a795621 |
| r-002 | high | test | scripts/tests/test_team_manifest.py:201 | No test proves the publish is write-then-rename; a direct in-place write passes all 83 tests | fixed in a795621 |
| r-003 | medium | correctness | scripts/team/manifest.py:148 | A manifest file with invalid UTF-8 raises a bare UnicodeDecodeError, not ManifestError | fixed in a795621 |
| r-004 | medium | correctness | scripts/team/manifest.py:276 | Possible lost update: the lock-ownership check is not atomic with the publish, and a steal can evict a fresh lock | fixed in a795621 |
| r-005 | medium | scope | scripts/team/manifest.py:284 | adopt_manifest has no consumer named in any later contract and no wiring IOU | fixed in a795621 |
| r-006 | medium | scope | scripts/team/manifest.py:369 | remove_process has no named consumer; cleanup contract Consumes only move_entry | fixed in a795621 |
| r-007 | medium | test | scripts/tests/test_team_manifest.py:87 | No boundary cases for the int and ostime kinds, or for a colon or NUL in names | fixed in a795621 |
| r-008 | medium | test | scripts/tests/test_team_manifest.py:160 | The adopt-first guard is tested only for a missing run directory, not for a directory with no manifest | fixed in a795621 |
| r-009 | medium | test | scripts/tests/test_team_manifest.py:179 | Stale-lock test never checks the redo after a lock is taken from a live writer and never checks the write landed | fixed in a795621 |
| r-010 | medium | test | scripts/tests/test_team_manifest.py:191 | The live-lock test does not prove the writer waits, and no test shows a waiting writer proceeds after release | fixed in a795621 |
| r-011 | low | spec | scripts/team/manifest.py:77 | ManifestBusy and the LOCK_WAIT/LOCK_STALE constants surface the lock to callers | fixed in a795621 |
| r-012 | low | scope | scripts/team/manifest.py:92 | checkpoint_path has no named consumer in any later contract | fixed in a795621 |
| r-013 | low | correctness | scripts/team/manifest.py:222 | A real permission error on mkdir is reported as a lock held past 30s | fixed in a795621 |
| r-014 | low | correctness | scripts/team/manifest.py:230 | A failed owner-file write leaves the lock folder held, and a failed publish leaves a temp file | fixed in a795621 |
| r-015 | low | spec | scripts/team/manifest.py:347 | record_entry merges fields into an existing entry whatever its state, including the terminal cleaned | fixed in a795621 |
| r-016 | low | test | scripts/tests/test_team_manifest.py:116 | test_every_move_follows_the_table steers its asserts with if/else over the oracle | fixed in a795621 |
| r-017 | low | test | scripts/tests/test_team_manifest.py:147 | The adoption test checks five behaviours in one body | fixed in a795621 |
| r-018 | low | test | scripts/tests/test_team_manifest.py:165 | Foreign-version test omits a boolean format_version and move_entry/remove_process on a foreign file | fixed in a795621 |
| r-019 | low | test | scripts/tests/test_team_manifest.py:231 | The checkpoint test compares the function with a second call of itself | fixed in a795621 |

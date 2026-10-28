# Review — 0005-worktree-creator, round 8

- Verdict: **advisory** — crit=0 high=0 med=5 low=15
- Diff: the whole slice 55b4098..304657f (scope stays escalated: round 7 found more uncorrected copies); the round-7 delta 1551d58..304657f for orientation.
- policy: lean, delta round, scope escalated · activated: delta-sweep, test-veracity (the delta changes tests), consistency-sweep (scope escalated; fed the 74 fixed keys), scope-and-impact (the orchestrator's Scope grep over the delta hit setup's MANIFEST.md and two protected-branch test files), logic-correctness and code-quality (code delta in 10 files) · deferred: agents-md-compliance, design-quality, resilience, and the smell finding r-016 (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped; r-004 and r-015 share r-003's cause and are settled by the same fix.
- Mutation probe: not run on a delta round.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:154 | Dead-owner and corrupt-marker resets unlink the current marker, so two calls can each start a move |
| r-002 | medium | correctness | logic-correctness | hooks/lib/h2_move.py:158 | The retry restart is not claimed, so concurrent calls each start a helper |
| r-003 | medium | correctness | logic-correctness | scripts/afk-move.py:131 | An outcome lost after the swap retries is never logged |
| r-004 | medium | smell | code-quality | scripts/afk-move.py:137 | Same cause as r-003, seen as a swallowed failure |
| r-005 | medium | test | test-veracity | scripts/tests/test_h2_move.py:720 | The blocked-swap test stubs the back-off and never checks it |
| r-006 | low | spec | consistency-sweep | docs/afk/setup-per-repo/VERIFICATION-PLAN.md:147 | The verification plan's A3 and A4 cells keep the exit codes D-59 corrected in the SDD |
| r-007 | low | spec | delta-sweep | docs/afk/setup-per-repo/plan/DECISIONS.md:442 | D-62's correction of D-55 misplaces one `_key` call |
| r-008 | low | scope | scope-and-impact | hooks/genericity-allow.txt:43 | D-50's reason for the INV-025 allow line names the wrong trigger |
| r-009 | low | smell | code-quality | hooks/lib/h2_move.py:79 | The load-a-script-by-path idiom appears three times in the move helper |
| r-010 | low | smell | code-quality | hooks/lib/h2_move.py:97 | The error result is typed out three times |
| r-011 | low | smell | code-quality | hooks/lib/h2_move.py:120 | plan's docstring omits its error result |
| r-012 | low | smell | delta-sweep | hooks/lib/h2_move.py:147 | A retry-me state reads as a failed creation in the guard's wrapper |
| r-013 | low | correctness | logic-correctness | hooks/lib/h2_move.py:157 | A recorded move keeps a stale error after its worktree exists or a retry starts |
| r-014 | low | correctness | logic-correctness | hooks/lib/h2_move.py:161 | A helper that fails to start leaves a marker nothing works on |
| r-015 | low | correctness | delta-sweep | scripts/afk-move.py:137 | Same cause as r-003, seen from the delta |
| r-016 | low | smell | code-quality | scripts/create-worktree:416 | DEST is derived twice behind a flag that mirrors the placement state |
| r-017 | low | test | consistency-sweep | scripts/tests/create-worktree-smoke.sh:213 | The --no-npm smoke check trusts an empty log without the run's exit code |
| r-018 | low | test | test-veracity | scripts/tests/test_h2_move.py:641 | The still-being-written test depends on wall-clock speed |
| r-019 | low | test | test-veracity | scripts/tests/test_h2_move.py:652 | The marker-vanished-after-read branch has no test |
| r-020 | low | test | consistency-sweep | scripts/tests/test_main_sync.py:43 | Two more guard test files run without a sandbox home and no hand-off names them |

# Review — 0010-team-entry-script (base 0420e545, round tag r3)

policy: lean · delta round · reviewers: logic-correctness, test-veracity, delta-sweep · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: 2a5751b · forge ledger: pull request 112, round 3

Verdict: advisory — crit=0 high=0 med=3 low=4

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f047 | medium | correctness | logic-correctness | scripts/remove-worktree.py:422 | adopt writes the owner record in place with write_text (truncate then write) while add_owner's lookup reads each record without the lock; a read in the gap sees a truncated file and add_owner skips the record | fixed 360598c |
| r-002 | f048 | medium | test | test-veracity | scripts/worktree_owner.py:273 | The new token-checked lock release has no test: no test makes the holder's lock be replaced by another holder's lock and shows the first holder leaves it. | fixed 360598c |
| r-003 | f049 | medium | correctness | logic-correctness | scripts/worktree_owner.py:295 | _take_if_stale reads the lock content (the 'judged' snapshot) after the mtime staleness check, so a fresh lock that replaced the stale one in between is judged as stale and deleted | fixed 360598c |
| r-004 | f050 | low | correctness | delta-sweep | scripts/team/entry.py:298 | agent-start closes the `-sup` id overlap but leaves the `contact` id: agent id `contact` is not refused | fixed 360598c |
| r-005 | f051 | low | correctness | logic-correctness | scripts/team/manifest.py:376 | NameTaken names sorted(names)[0], the first of the entry's own names, not the name the other entry holds | fixed 360598c |
| r-006 | f052 | low | test | test-veracity | scripts/tests/test_team_entry.py:397 | test_a_name_lost_5_times_answers_exit_4_and_starts_nothing does not count the attempts, so the 5-try cap that D-146 decides is not pinned. | fixed 360598c |
| r-007 | f053 | low | correctness | logic-correctness | scripts/worktree_owner.py:264 | record_lock creates the lock file, then writes the token; an OSError on the write leaves an empty lock that nothing removes | fixed 360598c |

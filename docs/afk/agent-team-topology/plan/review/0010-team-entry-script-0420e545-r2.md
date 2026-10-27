# Review — 0010-team-entry-script (base 0420e545, round tag r2)

policy: lean · delta round · reviewers: logic-correctness, test-veracity, delta-sweep · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: b2fd47b · forge ledger: pull request 112, round 2

Verdict: advisory — crit=0 high=0 med=4 low=9

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f034 | medium | correctness | logic-correctness | scripts/team/entry.py:275 | A buffered write that fails at close leaves a partial settings file that the next start then skips as 'exists'. | fixed 2a5751b |
| r-002 | f035 | medium | correctness | logic-correctness | scripts/team/entry.py:324 | Possible duplicate agent name: the lowest-agent-id-wins check misses the interleaving where the higher id writes and reads first. | fixed 2a5751b |
| r-003 | f036 | medium | correctness | delta-sweep | scripts/worktree_owner.py:241 | The new record lock guards add_owner only; adopt() in scripts/remove-worktree.py still rewrites the same record unlocked from an earlier read | fixed 2a5751b |
| r-004 | f037 | medium | correctness | delta-sweep | scripts/worktree_owner.py:268 | _record_lock retries a persistent OSError forever: the bare `except OSError: continue` skips both the LOCK_WAIT deadline and the sleep | fixed 2a5751b |
| r-005 | f038 | low | correctness | logic-correctness | scripts/team/entry.py:327 | When the 5th pass still finds a conflict, the renamed label and name are never recorded, yet the transport call uses them. | fixed 2a5751b |
| r-006 | f039 | low | correctness | logic-correctness | scripts/team/entry.py:575 | A start-request `effort` that is a list or object raises TypeError and answers exit 4 'unavailable', not exit 2 naming the field. | fixed 2a5751b |
| r-007 | f040 | low | correctness | delta-sweep | scripts/team/entry.py:617 | The message-id form is not disjoint across senders when an agent id ends in -sup: agent `x-sup` sends `x-sup-1`, and the job supervisor of agent `x` sends `x-sup-1` | fixed 2a5751b |
| r-008 | f041 | low | smell | delta-sweep | scripts/tests/test_team_entry.py:325 | New helper refuse_the_write_after duplicates the inline lambda that test_exit_5_omits_pane_fields still carries 6 lines above | deferred to the feature review gate |
| r-009 | f042 | low | test | test-veracity | scripts/tests/test_team_entry.py:950 | The gone-agent-close-fails test branches with if/else on the parameter and holds a vacuous clause | fixed 2a5751b |
| r-010 | f043 | low | test | test-veracity | scripts/tests/test_team_transport.py:624 | The late-dialog watch is tested for a plain start only; the Codex resume path that herdr.md now says runs the same watch has no test | fixed 2a5751b |
| r-011 | f044 | low | test | test-veracity | scripts/tests/test_worktree_owner.py:149 | The 'waits for the record lock' test never shows that add_owner waits | fixed 2a5751b |
| r-012 | f045 | low | test | test-veracity | scripts/tests/test_worktree_owner.py:168 | The parallel add_owner test may pass without the lock (possible) | fixed 2a5751b |
| r-013 | f046 | low | correctness | logic-correctness | scripts/worktree_owner.py:265 | Possible double hold of the record lock when two waiters take over the same stale lock. | fixed 2a5751b |

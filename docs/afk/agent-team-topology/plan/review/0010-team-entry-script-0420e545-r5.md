# Review — 0010-team-entry-script (base 0420e545, round tag r5)

policy: lean · delta round · reviewers: delta-sweep, logic-correctness, test-veracity · deferred: code-quality, agents-md-compliance, design-quality, resilience (-> feature gate)
reviewed head: 0ee8d66 · forge ledger: pull request 112, round 5

Verdict: advisory — crit=0 high=0 med=0 low=5

| Id | Key | Severity | Class | Concern | Where | Finding | Outcome |
|---|---|---|---|---|---|---|---|
| r-001 | f060 | low | smell | delta-sweep | scripts/remove-worktree.py:410 | adopt() keeps a `record` parameter its body no longer reads | fixed 684aa31 |
| r-002 | f061 | low | test | test-veracity | scripts/tests/test_remove_worktree.py:466 | Possible fragile closure: `real` is rebound from Path.write_text to os.replace while the earlier write_text stub still calls `real(self, ...)`. | deferred to the feature review gate |
| r-003 | f062 | low | test | test-veracity | scripts/tests/test_team_entry.py:412 | Possible gap: the case-insensitive `-sup` check in `_check_agent_id` has no test with a mixed-case id. | deferred to the feature review gate |
| r-004 | f063 | low | test | test-veracity | scripts/tests/test_worktree_owner.py:258 | Possible weak bound: the give-up half of the patient test only asserts `len(calls) > 3`. | deferred to the feature review gate |
| r-005 | f064 | low | test | test-veracity | scripts/tests/test_worktree_owner.py:292 | The parametrized append_owner test steers its asserts with try/except and an `added` flag. | deferred to the feature review gate |

# Review — 0003-repository-list, round 1

- Verdict: **blocking** — crit=0 high=2 med=6 low=11
- Diff: the slice's `[0003-repository-list]` commits from f53fef5 to 8891f99.
- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (0004 and 0010 consume this slice), domain-alignment (new public list operations), refactor-safety (one PLAN.md status cell changed) · skipped: design-quality, resilience, api-contract (no trigger) · deferred: code-quality, agents-md-compliance, design-quality (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- Caller set: every public symbol is new; no caller outside the new module and its test.
- Mutation probe: run by hand on a copy outside the worktree; 21 mutants, 14 caught.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | domain-alignment, logic-correctness, spec-fidelity | scripts/repo_list.py:157 | Remove deletes the marker and its folder inside the list transform, before the list write that can still be refused, so a refused remove leaves the entry listed with no marker |
| r-002 | high | test | test-veracity | scripts/tests/test_repo_list.py:415 | The read-only-list test patches only builtins.open, so find_entry reading a marker through pathlib passes it |
| r-003 | medium | spec | scope-and-impact, spec-fidelity | scripts/repo_list.py:108 | find_entry returns None for a worktree outside both the main checkout and <root>/<shortName>, even though the Goal says it finds the entry for any worktree path |
| r-004 | medium | test | test-veracity | scripts/repo_list.py:211 | No test adds a worktree whose main checkout folder is gone |
| r-005 | medium | correctness | logic-correctness | scripts/repo_list.py:236 | Re-adding a listed path reports a short-name clash instead of 'already listed' when an earlier entry holds the default short name |
| r-006 | medium | test | test-veracity | scripts/repo_list.py:283 | Remove's marker-identity guard is untested on both branches: a foreign marker and an absent marker/folder |
| r-007 | medium | test | test-veracity | scripts/tests/test_repo_list.py:168 | Possible conditional test logic: IS_WINDOWS if/else steers which behaviour each test asserts |
| r-008 | medium | scope | scope-and-impact | scripts/tests/test_repo_list.py:459 | The setup-only guard test exempts only skills/afk/setup/, so later in-plan test files that call all_entries( will fail a test owned by this slice |
| r-009 | low | scope | spec-fidelity | docs/afk/setup-per-repo/plan/0010-setup-walk.md:69 | No later contract consumes remove_repository or repoint_repository: 0010 lists only all_entries and add_repository, yet its Acceptance needs remove and repoint (AC-006) |
| r-010 | low | scope | scope-and-impact | docs/afk/setup-per-repo/plan/DECISIONS.md:98 | D-14 narrows catalog rule R-06 plan-wide, but 0004's Acceptance and context excerpt and smoke row U4 still quote the un-narrowed rule |
| r-011 | low | spec | spec-fidelity | scripts/repo_list.py:224 | The short-name rule is narrowed off the record: a name ending in a dot is refused on every OS, and Windows device names are refused, with no DECISIONS entry |
| r-012 | low | design | domain-alignment | scripts/repo_list.py:247 | Possible gap: the list module guards the marker invariant, but no public call lets placement, which SDD §6 says also asks it, check a marker |
| r-013 | low | test | test-veracity | scripts/repo_list.py:256 | A marker whose `path` is not a string is never tested |
| r-014 | low | design | refactor-safety, scope-and-impact | scripts/repo_list.py:276 | New cross-module caller of the safe writer's private `_replace_if_unchanged`; the next refactor of safe_write.py internals has no public-contract signal that this caller exists |
| r-015 | low | test | test-veracity | scripts/repo_list.py:315 | The 'unknown schema' refusal (schema below 1) has no test |
| r-016 | low | test | test-veracity | scripts/tests/test_repo_list.py:209 | Eager test: one body checks a foreign-content folder and an unreadable marker, without asserting the first refusal left state alone |
| r-017 | low | test | test-veracity | scripts/tests/test_repo_list.py:234 | Possible fragile test: the stopped-add test replicates the private `safe_write._swap` positional signature |
| r-018 | low | test | test-veracity | scripts/tests/test_repo_list.py:283 | Possible erratic test: lock test relies on a 6 s sleep outlasting git plus the 2 s lock wait |
| r-019 | low | test | test-veracity | scripts/tests/test_repo_list.py:332 | Refused repoint compares the marker to the stored list instead of to the original path |

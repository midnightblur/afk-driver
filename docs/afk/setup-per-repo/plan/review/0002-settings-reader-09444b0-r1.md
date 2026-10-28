# Review — 0002-settings-reader, round 1

- Verdict: **blocking** — crit=0 high=1 med=9 low=7
- Diff: the slice's `[0002-settings-reader]` commits from 09444b0 to 71297eb.
- policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (complexity is complex), refactor-safety (pre-existing lines changed), api-contract (public reader functions changed) · skipped: domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: r-003 and r-012 downgraded to low; none dropped
- Caller set: one ledger at C:/t/p2b/rv/callers.md, verdict closed-with-frontier (4 frontier items left unverified).
- Fixes: commit 24e1bc0. Five keys need files outside this slice's Scope and are carried to the human: r-002 (rest), r-005, r-006, r-007, r-013.

| Id | Sev | Class | Concern | Location | Finding |
|---|---|---|---|---|---|
| r-001 | high | correctness | refactor-safety, scope-and-impact, spec-fidelity, logic-correctness | skills/utils/investigate/scripts/seed_map.py:295 | seed_map --config PATH still runs raw parse then validate, so the CHILD_KEYS change makes it refuse a file that holds jira.credentials-env. |
| r-002 | medium | spec | spec-fidelity, scope-and-impact | hooks/precommit-gates.sh:192 | The no-Python fallback still greps every raw file for repo-hooks, including files the owner rule ignores for that team setting. |
| r-004 | medium | spec | spec-fidelity, logic-correctness | scripts/afk-config.py:1192 | The init scaffold still suggests the removed jira.credentials-env and writes notes and the forge remote into the committed file, where both are ignored. |
| r-005 | medium | spec | spec-fidelity | adapters/notes/notion/NOTES.md:12 | The notion kind's instructions still read the machine-owned notion.parent-page-id directly from the committed .afk/config.yaml. |
| r-006 | medium | scope | scope-and-impact | providers/CONFORMANCE.md:93 | The obsidian kind no longer roots at the vault, but its documents still say so and both kinds' notes_root functions are now orphans; D-11's 'later slice' is named by no contract. |
| r-007 | medium | scope | scope-and-impact, refactor-safety, spec-fidelity | adapters/tracker/jira/adapter.json:25 | The Jira adapter manifest's configKeys still lists the removed jira.credentials-env and omits the new jira.site. |
| r-008 | medium | correctness | refactor-safety, scope-and-impact | scripts/afk-config.py:521 | The caller ledger for load() and the other changed symbols has no closure verdict, and its second test run section is empty. |
| r-009 | medium | correctness | logic-correctness | scripts/afk-config.py:1422 | validate FILE on the repository personal file, run from outside the checkout, treats it as the unfiltered env layer: no ignored-value warnings, and it accepts schema though load() refuses it. |
| r-010 | medium | test | test-veracity | scripts/tests/test_afk_config_owner.py:361 | validate FILE layer detection has one test, for the committed file only. |
| r-011 | medium | test | test-veracity | scripts/tests/test_precommit_config_gate.py:79 | No test proves the commit-gate adoption check runs without Python, though the acceptance bullet requires it. |
| r-003 | low | correctness | api-contract, refactor-safety, logic-correctness | skills/afk/setup/scripts/developer_values.py:169 | status reports a source file for a developer value the owner rule dropped. |
| r-012 | low | design | api-contract | scripts/afk-config.py:1436 | Possible protocol inconsistency: validate writes the two kinds of warning line to different streams, and the (N warnings) count covers only path warnings. |
| r-013 | low | scope | scope-and-impact | .afk/config.yaml:16 | The plugin's own committed config now holds two values the owner rule ignores: notes (machine) and github.remote (personal). |
| r-014 | low | correctness | logic-correctness | scripts/afk-config.py:816 | The jira.site check accepts strings that are not a site address, e.g. `https://a b`. |
| r-015 | low | test | test-veracity | scripts/tests/test_afk_config.py:37 | Every CLI test's HOME points at one fixed directory in the system temp folder. |
| r-016 | low | design | api-contract | scripts/afk-config.py:526 | Possibly easy to misuse: ignored_values returns bare tuples whose third field is an owner-rule sentence or the removed-key message. |
| r-017 | low | design | api-contract | scripts/afk-config.py:531 | ignored_line is a new public name that neither SDD §8 nor Produces lists; only main calls it. |

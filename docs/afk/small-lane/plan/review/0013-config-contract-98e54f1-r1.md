# Review: 0013-config-contract, round 1

Verdict: advisory, crit=0 high=0 med=2 low=6. Base 98e54f1, head e5b86be.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (pre-existing lines changed) · skipped: domain-alignment, api-contract (no trigger); logic-correctness (no lean trigger: no later contract consumes this slice, complexity standard) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate) · verified: no design-level finding, no verify pass

The caller set was enumerated by grep in the orchestrator (`callers-0013.md` in the run scratch), not by a closed investigation ledger.

| # | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | medium | spec | scripts/afk-config.py:858 | The worktree-base rule still derives for a separate git dir that is itself named `.git`, while `CONFIG.md` promises any checkout whose git dir lies outside it derives nothing. |
| r-002 | medium | test | scripts/tests/test_afk_config.py:587 | No test covers a separate git dir, the case the new `CONFIG.md` sentence promises. |
| r-003 | low | spec | scripts/afk-config.py:1339 | A blank misspelled key is named by `resolve` and `status` but not by `validate`, because the merge drops blank keys before validation. |
| r-004 | low | spec | skills/afk/setup/MANIFEST.md:190 | H6 Fix step 1 does not mention the new `problems` list or what the agent does with it. |
| r-005 | low | scope | scripts/create-worktree:227 | A comment there still says `resolve` reads the repository's committed default (outside this slice's Scope). |
| r-006 | low | test | scripts/tests/test_setup_h6_probe.py:158 | The committed-block probe test does not show that the committed value goes unread. |
| r-007 | low | test | scripts/tests/test_afk_config.py:569 | One test checks four behaviours and compares a temp path without resolving it. |
| r-008 | low | correctness | scripts/afk-config.py:411 | A file named by `AFK_CONFIG` that is the committed file still has its `developer:` block read. |

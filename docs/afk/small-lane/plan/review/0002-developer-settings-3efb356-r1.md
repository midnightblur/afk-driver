# Review — 0002-developer-settings-3efb356-r1

- policy: lean · full-unit round · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness, refactor-safety (modified pre-existing lines) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verdict: findings — 2 medium, 2 low; all fixed in ea2cdac
- head: b7409d31f8e00b4e09eedb8938371d51037c5ef8
- counts: crit=0 high=0 med=2 low=2

## r-001 · medium · test · `scripts/tests/test_setup_developer_values.py:54`
Only a recorded `mrReviewer: none` is shown to leave `missing`; a recorded `trackerAssignee: none` and the H6 probe's handling of a person-key `none` are unpinned.

- Why: D-4 and the CHANGELOG promise `none` is an answer for trackerAssignee too; a regression special-casing mrReviewer would pass every new test.
- Fix: Parametrize the status test over (tracker=jira, trackerAssignee) and (forge=github, mrReviewer); add an H6 probe test with both keys recorded `none` expecting `ok`.
- Concern: ['test-veracity'] (Happy-path-only / missing negative cases)

## r-002 · medium · test · `scripts/tests/test_afk_config_init.py:205`
The test passes hand-built dicts to `developer_value`, so a narrower layer's `none` overriding a broader layer's person, and `afk-config.py resolve` exiting 1, are never exercised.

- Why: Layer override is the behaviour the comment and CONFIG.md promise; a dict that already holds `none` cannot show it.
- Fix: Write a machine file with the person and a repository file with `none`; assert `afk-config.py resolve <key>` exits 1 with no output, for trackerAssignee and mrReviewer.
- Concern: ['test-veracity'] (Mock echo / does the test prove the behaviour)

## r-003 · low · correctness · `skills/afk/bug/CONFIG.md:26`
A recorded `trackerAssignee: none` now satisfies setup but resolves to nothing, so the bug pipeline's publish still fails closed; the K1 row does not say `none` blocks, unlike the K2 row.

- Why: A developer who answers `none` passes setup yet cannot publish a bug, and nothing tells them why.
- Fix: Name `or the literal none` in the K1 row of the bug pipeline's fail-closed matrix.
- Concern: ['refactor-safety'] (behaviour change of a widely-called helper)

## r-004 · low · test · `skills/afk/setup/MANIFEST.md:159`
The rewritten H6 probe's new branches have no test: an underivable worktreeBasePath reported through `missing`, and the `status failed` fallback.

- Why: The probe now depends on the status JSON; a broken status or an unresolved worktree base changes the verdict with no test noticing.
- Fix: Add probe tests for a status that fails (expect the status-failed text and exit 1) and for an unresolved worktreeBasePath (expect it named).
- Concern: ['test-veracity'] (open-question)

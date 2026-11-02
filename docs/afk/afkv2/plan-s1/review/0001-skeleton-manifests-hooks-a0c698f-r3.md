# Review of 0001-skeleton-manifests-hooks, round 3

Telemetry only. The review record is pull request 155.

policy: lean. Delta round on d2239c37..4f887a02. Activated: delta-sweep, logic-correctness, scope-and-impact, test-veracity. Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience, and finding f054.

## Commit 4f887a02: 0/3/12/6 (critical/high/medium/low)

| Id | Key | Severity | Class | Where | Outcome | Finding |
|---|---|---|---|---|---|---|
| r-001 | f040 | high | correctness | `afkv2/scripts/plugin_check.py:38` | fixed | Regression: tightening this pattern lets a lowercase v1 prefix with a trailing separator pass the no-v1-name rule. |
| r-002 | f041 | high | correctness | `afkv2/scripts/plugin_check.py:61` | fixed | SUBSTRING_MATCH has no IGNORECASE flag, so the common JS, PowerShell and cmd spellings of prefix and substring matches pass the marker check. |
| r-003 | f042 | high | compliance | `afkv2/tests/test_hooks.py:132` | verdict withdrawn | The new skip branch lets a hook of any speed end as a skip, not a failure, when the empty .cmd floor is over 50 ms in all five attempts. |
| r-004 | f043 | medium | correctness | `afkv2/scripts/plugin_check.py:40` | fixed | A v1 name with a leading underscore and no alphanumeric before it passes the rule in code files. |
| r-005 | f044 | medium | correctness | `afkv2/scripts/plugin_check.py:57` | fixed | The new slice-compare rule only sees the slice on the left of the operator, and the operator list misses other partial-match forms. |
| r-006 | f045 | medium | correctness | `afkv2/scripts/plugin_check.py:214` | fixed | A code file that cannot be read passes the check silently, so the gate fails open. |
| r-007 | f046 | medium | correctness | `afkv2/scripts/plugin_check.py:140` | fixed | `build` still ends in a traceback with empty stdout when `hooks/built` is a file, because `mkdir` sits outside the new try block. |
| r-008 | f047 | medium | correctness | `afkv2/scripts/plugin_check.py:58` | fixed | The widened substring-match rule is case-sensitive and misses sibling forms, so common PowerShell, cmd and JS prefix or substring marker matches still pass. |
| r-009 | f048 | medium | test | `afkv2/tests/test_plugin_check.py:187` | fixed | The delta narrowed the v1 pattern, and no test case holds a v1 prefix that ends at the separator, so the regression is not caught. |
| r-010 | f049 | medium | test | `afkv2/tests/test_plugin_check.py:196` | fixed | The test takes its suffix cases from the production constant, so deleting a suffix removes its case and the test stays green. |
| r-011 | f050 | medium | test | `afkv2/tests/test_plugin_check.py:248` | fixed | The new slice-compare rule has one sunny case: no case for the reversed operand and no pass-side case, and both directions give a wrong answer. |
| r-012 | f051 | medium | test | `afkv2/tests/test_hooks.py:129` | verdict withdrawn | The timing gate can still pass by chance and can fail on load alone, because it uses the first passing attempt and absolute limits. |
| r-013 | f052 | medium | scope | `docs/afk/afkv2/plan-s1/DECISIONS.md:76` | verdict withdrawn | D-11 understates why the v1 CI job is red, so the two paths it hands to the owner cannot turn CI green. |
| r-014 | f053 | medium | scope | `docs/afk/afkv2/plan-s1/DECISIONS.md:55` | verdict withdrawn | After the entry was removed, afkv2 has no Codex install path in the repository, and no plan step or IOU owns adding one. |
| r-015 | f054 | medium | design | `afkv2/scripts/plugin_check.py:97` | deferred | The no-v1-name scan has no exemption for code that must name v1 artifacts, so planned takeover code can only pass by hiding those names from the check. |
| r-016 | f055 | low | correctness | `afkv2/scripts/plugin_check.py:180` | fixed | The registration check accepts a non-empty list that holds no handler. |
| r-017 | f056 | low | correctness | `afkv2/scripts/plugin_check.py:95` | fixed | A UTF-16 code file with no BOM passes as UTF-8, and its v1 names are not seen. |
| r-018 | f057 | low | correctness | `afkv2/scripts/plugin_check.py:31` | fixed | Widening CODE_SUFFIXES applies the one-line operator check to page text and config values, and the new slice rule flags a plain key lookup, so valid lines are refused. |
| r-019 | f058 | low | smell | `afkv2/scripts/plugin_check.py:208` | fixed | `_is_utf8` is a drifted twin of the new `_read_text` and the existing `_text_lines`: three wrappers around one read, and each code file is now read twice. |
| r-020 | f059 | low | test | `afkv2/tests/test_plugin_check.py:338` | fixed | The usage-error assert compares `reason` with itself, so any value passes, including null or an empty string. |
| r-021 | f060 | low | test | `afkv2/tests/test_hooks.py:192` | fixed | The no-data-folder test reads machine-wide state at the drive root and checks only that one path, so a record written elsewhere passes. |

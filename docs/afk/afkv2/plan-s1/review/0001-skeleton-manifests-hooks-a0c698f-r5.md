# Review of 0001-skeleton-manifests-hooks, round 5

Telemetry only. The review record is pull request 155.

policy: lean. Delta round on 3051e9df..9fad111b. Activated: delta-sweep, logic-correctness, test-veracity. Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience.

## Commit 9fad111b: 0/0/4/3 (critical/high/medium/low)

| Id | Key | Severity | Class | Where | Outcome | Finding |
|---|---|---|---|---|---|---|
| r-001 | f078 | medium | correctness | `afkv2/scripts/plugin_check.py:51` | fixed | Word operators also match inside the marker token itself, so a full-line compare of a marker name that holds such a word fails. |
| r-002 | f079 | medium | correctness | `afkv2/scripts/plugin_check.py:38` | fixed | URL stripper still swallows a v1 name placed inside a URL by interpolation. |
| r-003 | f080 | medium | correctness | `afkv2/scripts/plugin_check.py:99` | fixed | The marker rule skips every .json file, but hooks/hooks.json holds executable hook command strings. |
| r-004 | f081 | medium | test | `afkv2/tests/test_plugin_check.py:401` | fixed | No negative case for a bracket that holds a dict literal and a marker; the new slice rule flags it. |
| r-005 | f082 | low | test | `afkv2/tests/test_plugin_check.py:404` | fixed | D-14's chosen behaviour (ordinary text with a marker and a listed word fails) has no test; the two old pass cases were deleted, not flipped. |
| r-006 | f083 | low | test | `afkv2/tests/test_plugin_check.py:342` | fixed | test_every_method_operator_fails cannot prove `find` is in the method list. |
| r-007 | f084 | low | test | `afkv2/tests/test_plugin_check.py:213` | fixed | The suffix-set test echoes the production constants; only .png has a behaviour test. |

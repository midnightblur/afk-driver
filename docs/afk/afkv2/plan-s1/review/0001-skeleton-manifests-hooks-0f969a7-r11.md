# Review of 0001-skeleton-manifests-hooks, round 11

Telemetry only. The review record is pull request 155.

Delta 0f969a70..a03a92c2: the 3 new Acceptance bullets (D-45, D-46, D-47). policy: lean, owner ruling R-2 · activated: delta-sweep, logic-correctness, test-veracity, spec-fidelity (the delta carries new Acceptance bullets) · skipped: scope-and-impact (the inline Scope grep over the delta has no hit), refactor-safety (one small edit in check_no_v1_names; delta-sweep read it) · caller set: enumerated by grep, no investigation ledger.

## Commit a03a92c2: 0/0/2/5 (critical/high/medium/low)

| Id | Key | Severity | Class | Where | Outcome | Finding |
|---|---|---|---|---|---|---|
| r-001 | f089 | medium | correctness | `afkv2/scripts/afkv2_config.py:126` | advice | The named consumers on feat/afkv2-s3 lose the new bad-value refusal for forge: a bad forge routes by origin, and it also removes the tracker from the tracker port. |
| r-002 | f090 | medium | test | `afkv2/tests/test_plugin_check.py:620` | advice | No negative case pins the `.py` end of the `test_*v1_facts*.py` exemption, so the word 'only' in the acceptance bullet is not proved for the test-file pattern. |
| r-003 | f091 | low | spec | `afkv2/scripts/plugin_check.py:87` | advice | Possible over-wide exemption: a v1 name in the file name of a v1_facts file also passes. |
| r-004 | f092 | low | spec | `afkv2/scripts/afkv2_config.py:47` | advice | The reader now answers forge, but the SDD rows that describe the reader and the config file do not name that key. |
| r-005 | f093 | low | test | `afkv2/tests/test_plugin_check.py:580` | advice | The `.pyi` parameter cannot fail: the check groups by the whole file name, so `sample_mod.py` and `sample_mod.pyi` never share a key, with or without the suffix filter. |
| r-006 | f094 | low | test | `afkv2/tests/test_plugin_check.py:545` | advice | The clash tests pin case folding of the file stem only, not of the suffix or of the `__init__.py` exclusion. |
| r-007 | f095 | low | test | `afkv2/tests/test_config.py:175` | advice | Possible eager test: one test verifies 2 independent command behaviours, the good answer and the refusal of a bad forge. |

No critical or high finding. Under R-2 the gate passes after this round. The medium and low findings stay on the pull request as advice, with no fix and no dispute round.

Earlier finding f054 (no exemption for code that must name v1 things) closes as fixed in fd8b4679 (D-46).

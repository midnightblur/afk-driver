# Review of 0001-skeleton-manifests-hooks, round 4

Telemetry only. The review record is pull request 155.

policy: lean. Delta round on 4f887a02..3051e9df. Activated: delta-sweep, logic-correctness, test-veracity. Deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience.

## Commit 3051e9df: 0/2/10/5 (critical/high/medium/low)

| Id | Key | Severity | Class | Where | Outcome | Finding |
|---|---|---|---|---|---|---|
| r-001 | f061 | high | spec | `afkv2/scripts/plugin_check.py:233` | fixed | Word operators now apply only to script suffixes, so real marker matches in .yaml, .yml and .html pass the check. |
| r-002 | f062 | high | spec | `afkv2/scripts/plugin_check.py:45` | fixed | The slice pattern now rejects any bracket that holds a quote, so a prefix compare that slices with `len("...")` passes the check. |
| r-003 | f063 | medium | correctness | `afkv2/scripts/plugin_check.py:91` | fixed | The URL scrub removes every non-space character after a URL, so a v1 name on the same token passes the no-v1-name rule. |
| r-004 | f064 | medium | correctness | `afkv2/scripts/plugin_check.py:46` | fixed | The Python spellings of the marker rule miss slices with a call or index in the chain, and regex methods on a compiled pattern. |
| r-005 | f065 | medium | correctness | `afkv2/scripts/plugin_check.py:47` | fixed | The marker rule misses the usual cmd, bash and PowerShell substring forms, in the languages the plugin's hooks and scripts can use. |
| r-006 | f066 | medium | compliance | `docs/afk/afkv2/plan-s1/DECISIONS.md:90` | fixed | D-13 puts a second fork, the narrowing of the marker rule, inside the Chosen line of a v1-name decision, with no options and no Supersedes quote. |
| r-007 | f067 | medium | design | `afkv2/scripts/plugin_check.py:31` | fixed | Possible gap: every suffix outside the code list takes the prose exception, not only `.md`, `.txt` and `.json` as D-13 states, so a bare v1 word passes in any unlisted script or config file. |
| r-008 | f068 | medium | test | `afkv2/tests/test_hooks.py:195` | fixed | The no-data-folder test goes blind once the root folder exists, and one failing run creates that folder. |
| r-009 | f069 | medium | test | `afkv2/tests/test_plugin_check.py:308` | fixed | Many operators in the rewritten marker rule have no failing case, including `.match(` and all of the `re.` alternative. |
| r-010 | f070 | medium | test | `afkv2/tests/test_plugin_check.py:210` | fixed | The script/data split in `SCRIPT_SUFFIXES` is not pinned; only the union is, so `.sh` can lose the `grep`, `sed` and `awk` rule with all tests passing. |
| r-011 | f071 | medium | test | `afkv2/tests/test_plugin_check.py:345` | fixed | The new reverse-order slice alternative has no key-lookup negative, so its quote exclusion is unproven. |
| r-012 | f072 | medium | test | `afkv2/tests/test_plugin_check.py:251` | fixed | The new NUL branch in `_read_lines` is tested only for code files; no case covers a text file outside code that decodes with NUL characters. |
| r-013 | f073 | low | correctness | `afkv2/scripts/plugin_check.py:49` | fixed | The PowerShell operator alternative also matches inside a marker token, so a legal afkv2 name fails the check. |
| r-014 | f074 | low | correctness | `afkv2/scripts/plugin_check.py:216` | fixed | A text file outside the code suffixes that is not UTF-8 skips the no-v1-name rule with no problem reported. |
| r-015 | f075 | low | smell | `afkv2/scripts/plugin_check.py:218` | fixed | Possible duplicated code: `_read_lines` holds the same return twice, and its message says "not UTF-8" for a NUL in text that decoded as valid UTF-8. |
| r-016 | f076 | low | test | `afkv2/tests/test_plugin_check.py:268` | fixed | The boundaries of the D-13 prose exception are only partly tested. |
| r-017 | f077 | low | test | `afkv2/tests/test_plugin_check.py:217` | fixed | No test uses an upper-case suffix, so `.lower()` in both checks is unpinned. |

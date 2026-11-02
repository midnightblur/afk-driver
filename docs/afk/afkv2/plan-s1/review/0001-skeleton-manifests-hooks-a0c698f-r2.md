# Review of 0001-skeleton-manifests-hooks

Telemetry only. The review record is pull request 155.

policy: lean · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (first round); delta-sweep, logic-correctness, test-veracity, scope-and-impact (second round) · deferred to the feature gate: code-quality, agents-md-compliance, design-quality, resilience

The loop did not settle. One finding stands and needs the owner: three seed files are outside the 0001 scope. A third round on commit 56e5704b is still owed.

## First round, commit efd83cdb: 0/2/4/11 (critical/high/medium/low)

| Id | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | high | correctness | `afkv2/scripts/plugin_check.py:35` | The no-v1-name text rule misses `afk` followed by a backslash, a quote, a bracket or end of line. The lookahead allows only `[-_:./a-z0-9]`, so a Windows data-folder path, a quoted storage key and a CSS class pass the check. |
| r-002 | high | correctness | `afkv2/hooks/subagent-start.cmd:10` | Parallel hook runs race on one fired-record file. The last line truncates %LOCALAPPDATA%\afkv2\fired-claude.txt; when two subagents (or a subagent and the session) start at the same time, cmd's redirect hits a sharing violation and the hook exits 1. session-start.cmd:7 writes the same file and has the same defect. |
| r-003 | medium | correctness | `afkv2/hooks/session-start.cmd:5` | With LOCALAPPDATA unset the hooks write the fired record to `\afkv2` at the current drive root, while the config reader refuses the same case |
| r-004 | medium | scope | `afkv2/.codex-plugin/plugin.json:2` | The Codex manifest has no install path. Codex reads this repository's marketplace from .agents/plugins/marketplace.json, which still lists only the v1 'afk' entry. The slice added afkv2 only to the Claude marketplace (.claude-plugin/marketplace.json). So the owner-run Codex live check, step 3 ('Enable afkv2 in Codex from the plugin marketplace of this repository'), cannot be done as written, and the Codex hook is never loaded. |
| r-005 | medium | test | `afkv2/tests/test_hooks.py:105` | The 'parses no shell command' half of AC-013 is proved only by a deny-list grep of the .cmd source. The payload carries a destructive command (`git status && del /q *`), but no test observes whether it runs. run_hook sets no cwd, so the hook inherits the pytest cwd (probably the worktree). |
| r-006 | medium | test | `afkv2/tests/test_hooks.py:149` | test_rule_text_reaches_a_session_only_through_the_plugin stands in for AC-011 ('with afkv2 disabled, a new session holds no afkv2 rule text'). It checks only for the marker string, and only in this repo's root CLAUDE.md/AGENTS.md, behind `if path.is_file()`. Rule text copied without the marker line passes. A missing file passes without a check. |
| r-007 | low | spec | `docs/afk/afkv2/plan-s1/JOURNAL.md:10` | Live-check record proves the post-compaction case by transcript content, not by the session reporting the end marker, and does not say the session was non-interactive |
| r-008 | low | scope | `afkv2/core/CORE-BEHAVIORS.md:1` | Three changed files match no 0001 ## Scope glob: afkv2/core/CORE-BEHAVIORS.md, afkv2/hooks/built/afkv2-core-behaviors.txt, afkv2/hooks/built/afkv2-core-behaviors.claude-subagent.json. Contract 0002 ## Scope owns them ('afkv2/core/CORE-BEHAVIORS.md', 'afkv2/hooks/built/*'). |
| r-009 | low | test | `afkv2/tests/test_plugin_check.py:192` | The prefix/substring marker cases use only inline literals. No case checks a marker held in a constant and matched on another line. The shipped suite holds that pattern itself (test_hooks.py line 150: `assert marker not in path.read_text(...)` with `marker = plugin_check.MARKER`), and check_marker_matching passes it. DECISIONS D-4 records this as a known gap, but no test pins the gap. |
| r-010 | low | test | `afkv2/tests/test_config.py:85` | The 'C:/abs' refusal case depends on the platform. On POSIX, PurePath('C:/abs').anchor is '' (I checked PurePosixPath), so the reader accepts the value and this case fails. test_config.py has no Windows skip, but test_hooks.py does. No POSIX absolute case ('/abs') exists either. |
| r-011 | low | test | `afkv2/tests/test_hooks.py:99` | The 50 ms median check measures wall-clock time around subprocess.run in the unit suite. That time includes Python process creation and cmd.exe startup, and there is no warm-up run. On a loaded Windows host the median can exceed 50 ms while the hook itself does not change. |
| r-012 | low | test | `afkv2/tests/test_hooks.py:49` | No test runs a hook with the prebuilt file missing. The `type ... \|\| exit /b 1` branch in both .cmd hooks makes sure that no fired record is written when no text was printed. The setup proof depends on that relation (fired record => text printed), and no test checks it. |
| r-013 | low | test | `afkv2/tests/test_plugin_check.py:254` | The marketplace test checks only the v1 entry's `source` field. The acceptance bullet requires that the v1 entry stays byte-identical. Today the diff leaves it unchanged (checked with git diff), but the test would pass if a later change edited the v1 name/description/version. Also, test_manifests_must_name_the_plugin_afkv2 changes only the Claude manifest. The Codex manifest name check has no negative case. |
| r-014 | low | correctness | `afkv2/scripts/plugin_check.py:134` | The stale check is blind to line endings. `read_text` uses universal newlines, so a prebuilt file converted to CRLF compares equal and passes, while the hook `type`s the CRLF bytes. |
| r-015 | low | correctness | `afkv2/scripts/plugin_check.py:151` | A hooks.json whose `hooks` value is null (or not an object) crashes the check with a traceback instead of a problem line and the JSON answer. |
| r-016 | low | correctness | `afkv2/scripts/afkv2_config.py:125` | `-h`/`--help` bypasses the JSON envelope: argparse prints plain usage text and exits 0, so a caller parsing stdout as one JSON object fails on an exit code that says ok. |
| r-017 | low | correctness | `afkv2/scripts/plugin_check.py:59` | Which bytes does 'the text between the marker lines' mean? The build hashes the body without its final newline, but the bytes between the end of the begin line and the start of the end line are body + "\n". |

## Second round, commit d2239c37: 0/2/7/13 (critical/high/medium/low)

| Id | Severity | Class | Where | Finding |
|---|---|---|---|---|
| r-001 | high | scope | `.agents/plugins/marketplace.json:8` | Out-of-scope path: decision D-5 cannot sanction it, because a Scope change is outside agent authority |
| r-002 | high | test | `afkv2/tests/test_hooks.py:118` | The 50 ms test now passes on the best of up to five medians, and D-7 wrongly says a slower hook fails all five attempts |
| r-003 | medium | scope | `docs/afk/afkv2/plan-s1/JOURNAL.md:18` | Second gate bypass: no plan step or decision owns how the v2 files pass the v1 gates, and the v1 test job is red on them |
| r-004 | medium | correctness | `afkv2/hooks/session-start.cmd:8` | The new bracket block makes a `)` in %DATE% or %TIME% a parse error, so the hook exits 255 and writes no record (subagent-start.cmd:11 has the same line) |
| r-005 | medium | compliance | `afkv2/scripts/plugin_check.py:86` | The bare-word check runs only on CODE_SUFFIXES, so a v1 name in a CSS class, a storage key or a .tsx/.jsx/.vue file passes, and D-6 records a smaller gap than the real one |
| r-006 | medium | spec | `afkv2/scripts/plugin_check.py:40` | The no-v1-name rule passes a CSS class or a storage key that ends in '-af' + 'k' in HTML and CSS files, and every bare word in .html, .css, .tsx and .jsx files. |
| r-007 | medium | correctness | `afkv2/scripts/plugin_check.py:87` | A code file that is not UTF-8 is skipped in silence, so the v1-name check and the marker check pass it with a v1 variable in it. |
| r-008 | medium | test | `afkv2/tests/test_plugin_check.py:311` | The Codex marketplace test pins only source, so a default-on afkv2 policy and a changed v1 entry both pass |
| r-009 | medium | test | `afkv2/tests/test_hooks.py:130` | No CI job runs afkv2/tests, so none of these tests guards a later change |
| r-010 | low | scope | `docs/afk/afkv2/plan-s1/DECISIONS.md:49` | D-7 says 'Supersedes: none' but changes the contract's timing check, and it does not record the added warm-up run |
| r-011 | low | compliance | `afkv2/tests/live/CODEX-LIVE-CHECKS.md:11` | Shipped plugin files cite plan decisions that /afk:gc deletes after the merge (also afkv2/tests/test_plugin_check.py:252) |
| r-012 | low | compliance | `docs/afk/afkv2/plan-s1/JOURNAL.md:18` | The committed journal line points to a session scratch file for the gate output instead of holding the facts |
| r-013 | low | correctness | `afkv2/scripts/plugin_check.py:42` | A name that ends in '_' + the v1 word passes in code files, because V1_WORD_IN_CODE treats '_' as a word character and no other pattern covers that form. |
| r-014 | low | correctness | `afkv2/scripts/plugin_check.py:35` | A prose sentence in a text file that has the v1 word before a full stop or a colon fails the check, against the rule of D-6. |
| r-015 | low | correctness | `afkv2/scripts/plugin_check.py:46` | Same-line substring and prefix marker matches in languages that the check scans pass, because the operator list has no JS '.test(', PowerShell 'Select-String', 'sed' or slice compare. |
| r-016 | low | correctness | `afkv2/scripts/plugin_check.py:164` | The check answers ok when a hook event has an empty or null registration, so the hook never fires and the tree still passes. |
| r-017 | low | correctness | `afkv2/scripts/plugin_check.py:220` | An unreadable source or prebuilt file makes the command print a traceback and no JSON, although the module docstring says it answers one JSON object. |
| r-018 | low | test | `afkv2/tests/test_hooks.py:167` | The no-data-folder test probes the real drive root and does not assert stderr |
| r-019 | low | test | `afkv2/tests/test_plugin_check.py:247` | The new hooks-value test covers the wrong-type guard, but no test covers the missing-event branch directly below it |
| r-020 | low | test | `afkv2/tests/test_plugin_check.py:171` | Four name forms that the new patterns accept have no test case: a forward-slash path part, ${name}, className=, and name\path with no separator before it |
| r-021 | low | test | `afkv2/tests/test_plugin_check.py:178` | The bare-word test runs only on .py, although the plugin's hooks are .cmd and CODE_SUFFIXES lists nine suffixes |
| r-022 | low | test | `afkv2/tests/test_plugin_check.py:262` | The usage-error tests do not assert ok is false, so a usage answer with ok true passes |

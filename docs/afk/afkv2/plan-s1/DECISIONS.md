# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — 0001 needs a core-behaviors source and prebuilt files that 0002 owns
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — seed a short placeholder `afkv2/core/CORE-BEHAVIORS.md` and its generated `afkv2/hooks/built/*` vs B — leave both out; the plugin check fails on the tree and the hooks print nothing
- Chosen: A — the 0001 static tier needs `plugin_check.py` exit 0 on the tree and the 0001 live check needs a printed end marker; neither holds without a source and its prebuilt files. 0002 replaces the placeholder text and rebuilds the files with the 0001 build verb.
- Supersedes: none (0001 `## Scope` does not list the two paths; 0002 `## Scope` keeps them)
- To reverse: delete the two seeded paths; the plugin check then reports the missing source

## D-2 — file and shape of the `.afkv2` config
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `.afkv2/config.json`, JSON, keys `spec_folder`, `tracker` {kind, ...}, `ownership` {own, shared} vs B — `.afkv2/config.yaml` with a hand-written YAML subset reader (v1 way)
- Chosen: A — the Python standard library reads JSON, so the reader has no parser of its own to maintain; SDD §8 fixes only "one read command, JSON answer" and the three values.
- Supersedes: none
- To reverse: change `CONFIG_FILE` and the loader in `afkv2/scripts/afkv2_config.py` and the tests

## D-3 — one hooks file for both harnesses
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `afkv2/hooks/hooks.json` serves both: Claude runs `cmd.exe` with `args` (exec form), Codex runs `commandWindows` vs B — Claude file plus an inline hooks object in the Codex manifest
- Chosen: A — Claude docs (code.claude.com/docs/en/hooks): shell form runs through Git Bash on Windows (97 ms start, over the 50 ms rule) and exec form needs a real executable, so `cmd.exe` + `args`; Codex docs (learn.chatgpt.com/docs/hooks): `commandWindows` is the Windows command, the default file is `hooks/hooks.json`, and the inline-object shape is not documented. Codex ignoring `args` is unverified: owner-run check 1 proves it.
- Supersedes: none
- To reverse: move the Codex handlers to an inline `hooks` object in `afkv2/.codex-plugin/plugin.json`

## D-4 — how the plugin check finds a prefix or substring marker match
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — flag a code line that holds a marker token (`afkv2-…` or `afkv2:…`, and the v1 form) together with a substring or prefix operator (`startswith`, `in`, `find`, `search`, `match`, `includes`, `findstr`, …); `==` and `fullmatch` pass vs B — data-flow analysis of marker strings
- Chosen: A — a same-line rule is deterministic and cheap; the author writes a full-line compare with `==` or `fullmatch`. Data flow through a variable is not traced (known gap).
- Supersedes: none
- To reverse: change `check_marker_matching` in `afkv2/scripts/plugin_check.py`

## D-5 — the Codex marketplace also lists afkv2
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — add a pure-addition afkv2 entry to `.agents/plugins/marketplace.json`; the v1 entry stays as is vs B — leave the file; the owner cannot enable afkv2 in Codex from this repository, and owner-run checks 1 and 2 have no install path
- Chosen: A — the 0001 Goal is the Claude and Codex skeleton, and the owner-run checks need an install path. No plan step adds the entry. An entry with `"installation": "AVAILABLE"` installs nothing until the owner enables it (Codex behavior not verified here; owner-run check 1 covers the path).
- Supersedes: none (0001 `## Scope` lists only `.claude-plugin/marketplace.json`; this adds one path outside it)
- To reverse: delete the afkv2 entry from `.agents/plugins/marketplace.json` and `test_codex_marketplace_lists_afkv2_beside_the_v1_plugin`

## D-6 — what the no-v1-name rule treats as prose
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — every file: flag name-shaped forms (path part, quoted whole word, `%name%`, `$name`, `name=`, CSS class); code files also flag the bare word; a bare word in other text files passes as prose vs B — flag the bare word in every file
- Chosen: A — the manifests and the marketplace description name the product "AFK 2.0 beta" in prose, and that text is a required value of the manifests, not a v1 identifier (0001 Acceptance lists file names, environment variables, markers, storage keys and CSS classes). A v1 name in a prose sentence of a text file is not found (known gap).
- Supersedes: none
- To reverse: move `V1_WORD_IN_CODE` into `V1_TEXT` in `afkv2/scripts/plugin_check.py` and reword the descriptions

## D-7 — the 50 ms test tries a median of 7 up to five times
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — pass on the first median of 7 under 50 ms, in at most five attempts vs B — one attempt
- Chosen: A — with other work on the machine, the same hook gave medians from 41 ms to 81 ms in one probe (`session-start.cmd`: 45.5, 40.9, 45.4, 68.3, 81.5, 47.7 ms). One attempt fails on machine load, not on the hook. A hook that is slower than 50 ms fails all five attempts, so the PRD AC-013 rule still holds.
- Supersedes: none
- To reverse: set `TIMING_ATTEMPTS` to 1 in `afkv2/tests/test_hooks.py`

## D-8 — take the Codex marketplace entry back out
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — remove the afkv2 entry from `.agents/plugins/marketplace.json`; the owner-run steps add it in a test copy, and the final report names the plan gap vs B — keep the entry of D-5
- Chosen: A — root DECISIONS.md condition 3 ("it reshapes no plan structure (Scope globs ...)") does not let an agent add a Scope path that its own Goal and Acceptance do not need, and D-5 said it adds one; the Codex checks are owner-run (plan-s1 D-S-8).
- Supersedes: D-5 in full
- To reverse: the owner adds the path to a plan step, then that step adds the entry from `afkv2/tests/live/CODEX-LIVE-CHECKS.md`

## D-9 — the 50 ms test measures an empty .cmd in the same attempt
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — each attempt runs 7 pairs of an empty `.cmd` and the hook after one discarded warm-up; pass on the first attempt with both medians under 50 ms, skip as no verdict if the empty `.cmd` is over 50 ms in all five attempts, otherwise fail vs B — one median of 7 with no floor vs C — the D-7 rule
- Chosen: A — probes on this machine: an empty `.cmd` takes 40 ms to 47 ms in the same harness, so the hook body has about 3 ms to 10 ms of margin, and the same hook gave medians from 41 ms to 81 ms under load. D-7 was wrong to say that a hook slower than 50 ms fails all five attempts: the gate is the first median under the limit, so a hook near the limit can pass by chance. Load only adds time, so a hook far over the limit still fails.
- Supersedes: D-7 in full; 0001 `## Verification` "run each `.cmd` 7 times with a sample hook payload on stdin, median < 50 ms"
- To reverse: restore one median of 7 in `afkv2/tests/test_hooks.py`

## D-10 — extra forms of the no-v1-name rule
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — also flag a name part at the end of a longer name (`-name`, `_name`), `#name`, and the bare word in `.jsx`, `.tsx`, `.vue`, `.html`, `.css`, `.yaml`, `.yml`, `.toml`; a code file that is not UTF-8 is a problem vs B — keep the D-6 forms
- Chosen: A — 0001 Acceptance lists environment variables, storage keys and CSS classes, and these forms are those. Remaining known gap: a bare word in `.md`, `.txt` and `.json` passes (the manifest description is prose), and a joined word such as `notafk` passes. Page text in `.html` must say afkv2, not the bare word.
- Supersedes: the D-6 sentence "a bare word in other text files passes as prose" for the suffixes above
- To reverse: change `CODE_SUFFIXES` and `V1_TEXT` in `afkv2/scripts/plugin_check.py`

## D-11 — two continuous-integration gaps have no owner in any plan
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — record the gaps here and name them in the final report; the owner names the plan step vs B — edit `.github/workflows/tests.yml` and `hooks/native-contract-allow.txt` in this slice
- Chosen: A — both paths are outside every 0001 `## Scope` glob, so root DECISIONS.md condition 3 stops the agent. Gap 1: no job runs `afkv2/tests` (`.github/workflows/tests.yml:64` runs `scripts/tests` only). Gap 2: the v1 native-contract gate refuses the two tool names in `afkv2/tests/live/CODEX-LIVE-CHECKS.md` and in `docs/afk/afkv2`, so the v1 unit-test job on pull request 155 is red, and the rule "at ship, CI must be green" has no plan step behind it.
- Supersedes: none
- To reverse: the owner names a plan step for the two paths

## D-12 — ruling on the 0001 seed files: resolves D-1 and review finding f008
- 2026-10-30 · decided by the plan author (the human who sliced this plan; the owner delegated reversible plan calls), relayed in session S1
- Options: A — keep the 3 files and add them to the 0001 `## Scope` as seed only vs B — remove the files and move the plugin-check and live-check rows of 0001 to after 0002
- Chosen: A — ruling of the plan author. The 3 paths are now in the 0001 `## Scope`, each with the comment `# seed only; 0002 owns the content`: `afkv2/core/CORE-BEHAVIORS.md`, `afkv2/hooks/built/afkv2-core-behaviors.txt`, `afkv2/hooks/built/afkv2-core-behaviors.claude-subagent.json`
- Supersedes: "0001 `## Scope` does not list the two paths" (D-1)
- To reverse: 0002 overwrites the seed; to undo the Scope change, remove the 3 lines from the 0001 `## Scope`

## D-13 — the no-v1-name rule becomes one pattern plus one prose exception
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — in a code file, flag every `afk` (any case) that is not followed by `v2` and has no letter or digit before it; in another text file, flag the same hit unless it has the shape of a prose word (start of line, a space, a bracket, a backtick or a quote before it; end of line, a space, a bracket, a backtick, `,` `;` `!` `?`, or `.` or `:` before a space after it), and always flag it in a `class` value vs B — add more forms to the list of 9 patterns of D-6 and D-10
- Chosen: A — 3 review rounds each found forms the list missed, and the last list change lost `afk_` and `afk:` prefixes. One pattern has no list to fall behind. Remaining known gaps: a joined word such as `notafk`, and a prose-shaped word in `.md`, `.txt` and `.json` (a `.json` value that is a sentence stays legal because the manifest description is prose). Same-line marker rule: the operator list is case-insensitive, word operators (`in`, `find`, `grep`, `sed`, `awk`, `sls`, `findstr`, `strstr`) apply only to script files, and a slice with a quote inside the brackets is a key lookup, not a slice. The list is finite and data flow is not traced (D-4).
- Supersedes: the forms and the bare-word sentence of D-6 ("every file: flag name-shaped forms (path part, quoted whole word, `%name%`, `$name`, `name=`, CSS class); code files also flag the bare word; a bare word in other text files passes as prose"); the forms of D-10 ("also flag a name part at the end of a longer name (`-name`, `_name`), `#name`")
- To reverse: restore the pattern list from commit 56e5704b in `afkv2/scripts/plugin_check.py`

## D-14 — the marker rule is a bounded list of same-line forms
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — one operator list applies to every file that is not prose or binary, on any line that holds a marker token; a line of ordinary text in a code-shaped file that holds a marker and a listed word fails, and the author rewords it vs B — apply word operators to script files only, which keeps that text legal vs C — trace data flow so that a marker held in a variable is found
- Chosen: A — the script-file split of round 3 made a real match pass in `.yaml` and `.html` to silence one low false positive. A slice is any bracket with a colon outside a quoted key, with or without a compare, so `line[:20].strip() == "m"` fails and `d["a:b"]` passes. C needs a parser for every language and has no reader in this slice. Remaining known gaps: a marker held in a variable and matched on another line (strict xfail in `afkv2/tests/test_plugin_check.py`), and spellings outside the list. A further spelling is a list addition, disputable citing this decision. The SDD §7 row "no substring or prefix marker match in afkv2 code" holds for the listed forms only
- Supersedes: the D-13 sentence "Same-line marker rule: the operator list is case-insensitive, word operators (`in`, `find`, `grep`, `sed`, `awk`, `sls`, `findstr`, `strstr`) apply only to script files, and a slice with a quote inside the brackets is a key lookup, not a slice. The list is finite and data flow is not traced (D-4)."; the operator list of D-4
- To reverse: restore `SCRIPT_SUFFIXES` and `SUBSTRING_WORD` from commit 3051e9df in `afkv2/scripts/plugin_check.py`

## D-15 — files fall in three classes by suffix: prose, binary, code
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `.md`, `.txt`, `.json` are prose; 10 listed image, font and archive suffixes are binary and skipped; every other file takes the code rule, and a non-binary file that is not UTF-8 text is one problem vs B — keep a list of code suffixes, so a new suffix such as `.psm1` or `.svg`, or a file with no suffix, takes the prose exception and the marker rule skips it
- Chosen: A — a suffix nobody listed now fails closed. Remaining known gap: a file with a binary suffix is not read, so a text file named `.png` passes
- Supersedes: `CODE_SUFFIXES` of D-10 and D-13; the D-10 sentence "a code file that is not UTF-8 is a problem" widens to every non-binary file
- To reverse: restore `CODE_SUFFIXES` and `_read_lines` from commit 3051e9df in `afkv2/scripts/plugin_check.py`

## D-16 — the hook registration is code, although its suffix is prose
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — `afkv2/hooks/hooks.json` takes the code rule and the marker rule; every other `.json` stays prose vs B — read every `.json` as code, which fails the prebuilt subagent output and the manifest descriptions vs C — keep it prose and record a known gap
- Chosen: A — that file holds commands that run. The prebuilt output is one long line of prose, and a manifest description is prose
- Supersedes: the D-15 sentence "`.md`, `.txt`, `.json` are prose" for this one file
- To reverse: remove `_is_prose` from `afkv2/scripts/plugin_check.py`

## D-17 — ruling on adversary finding A-1: pin the prebuilt files to LF
- 2026-10-30 · decided by the owner, in session S1
- Options: A — add `.gitattributes` to the 0001 `## Scope` with one line, `afkv2/hooks/built/* text eol=lf` vs B — hash over LF-joined lines and readers strip CR vs C — byte compare only, inside Scope
- Chosen: A — the orchestrator reproduced A-1 on a fresh clone with `core.autocrlf=true` (5 CR bytes on stdout, begin line ends in CR, check exits 0); with the rule set through `.git/info/attributes`, stdout has 0 CR, the span hashes to `7f976c7ee15c`, and check exits 0
- Supersedes: none
- To reverse: remove the line from `.gitattributes` and the path from the 0001 `## Scope`

## D-18 — owner ruling R-1: the adversarial gate is skipped for afkv2
- 2026-10-30 · decided by the owner, recorded by autopilot (session brief, section Owner rulings)
- Options: A — skip execute Step 10.5 on every afkv2 plan vs B — run it
- Chosen: A — owner: "Skip for afkv2". Cause: no running app to attack. Each slice journals `adversary: skipped (owner ruling R-1)`
- Supersedes: the "Step 10.5 mandatory" line of the execute contract's Driven mode, for this build
- To reverse: the owner withdraws R-1; slices that skipped the gate then run it

## D-19 — owner ruling R-2: at most 3 review rounds, fix only critical and high
- 2026-10-30 · decided by the owner, recorded by autopilot (session brief, section Owner rulings)
- Options: A — at most 3 rounds per slice, medium and low stay on the PR as advisory with no fix and no dispute round vs B — settle until a round is clean
- Chosen: A — owner ruling. After round 3, an open critical or high finding parks the slice; otherwise the gate passes
- Supersedes: the settle-until-clean rule of skills/afk/review/SETTLEMENT.md, for this build
- To reverse: the owner withdraws R-2; re-review the slices that passed under it

## D-20 — owner ruling R-3: a note that changes a sign-off card's wording sends the card back
- 2026-10-30 · decided by the owner, recorded by autopilot (session brief, section Owner rulings)
- Options: A — the card goes back for a sign mark vs B — the note settles the card
- Chosen: A — owner chose this for HL-4 (closes S2 D-15 and finding f074). Binding here if a plan-s1 slice handles a note on a sign-off card
- Supersedes: none in plan-s1
- To reverse: the owner withdraws R-3

## D-21 — owner ruling R-4: skipping pre-commit gates is accepted for this build
- 2026-10-30 · decided by the owner, recorded by autopilot (session brief, section Owner rulings)
- Options: A — AFK_SKIP_PRECOMMIT_GATES=1 on all afkv2 commits, PR CI catches the rest, the ship gate must be green vs B — skip only on proven v1 friction
- Chosen: A — owner ruling. Skipped commits stay listed in the journal
- Supersedes: the friction-only skip rule of the session brief
- To reverse: the owner withdraws R-4; run the gates on later commits

## D-22 — plan author's ruling on A-1: scope wording, rule comment, check and test
- 2026-10-30 · decided by the plan author (reversible), relayed in session S1
- Options: A — `.gitattributes` in the 0001 `## Scope` for afkv2 lines only, the rule with a one-line comment, the check fails on a built file that does not hash to its marker or holds a CR byte, and a test of both on a CRLF-converted fixture vs B — the D-17 form: one line with no comment, and the existing tests
- Chosen: A — ruling of the plan author. Its condition holds: Acceptance 4 defines the marker hash over the text between the marker lines, and Acceptance 7 says the check refuses a stale prebuilt file. A-2 to A-9 stay advisory under R-2; no new adversary run under R-1
- Supersedes: the Scope comment and the "one line" wording of D-17 (D-17)
- To reverse: restore the D-17 Scope comment, remove the comment line and the new test

## D-23 — which v1 behaviors the core text carries
- 2026-10-30 · decided by execute (0002-core-behaviors)
- Options: A — carry the interim behaviors whole, and each v1 behavior whose rule still applies, as self-contained text vs B — carry the interim behaviors only and leave out every v1 behavior vs C — carry every v1 behavior, with its pointer to a v1 file
- Chosen: A — the contract Goal says the text grows from both sources, and C breaks the no-v1-name rule in Acceptance 3. Not carried, with cause: `ci-parity-before-push` and the "do not merge the target branch locally" half of `change-landing` (interim rules say the opposite); `lavish-grilling-render` (a page skill owns it; PRD SK row for the page engine); `rationale-on-change` (the PRD has no such transport); `phase-boundary-review` (the PRD chain has no manual phased plan). Also carried from decisions 18, 28, 33, 58 of issue 153: environment awareness, collaboration branch, verify premises. The background-job recipes of issue row W1 are not carried: they are not in the Acceptance, and the two-harness facts are not verified in this slice.
- Supersedes: none
- To reverse: edit `afkv2/core/CORE-BEHAVIORS.md`, then run `plugin_check.py build`

## D-24 — what the search benchmark counts as a hit
- 2026-10-30 · decided by execute (0002-core-behaviors)
- Options: A — a hit is one matching text line, compared as a multiset of `path:text` in each timed run; a binary-file notice is not a hit, and the answer counts notices per tool vs B — a binary-file notice counts as a hit, so one tool that reports a binary match and the other that does not fail the compare
- Chosen: A — a notice names a file and no line, so an agent cannot act on it as a hit. Measured on the benchmark repository, pattern `Transactional`: both tools have the same text lines, and `git grep --untracked` adds 1 notice for a `.jar` file that rg does not report. rg stops reading a file at the first NUL byte (inferred from that output; not verified against the rg source).
- Supersedes: none
- To reverse: count notices in `normalize_hits` in `afkv2/scripts/search_bench.py`

## D-25 — owner ruling: 0001 owns the Codex marketplace entry
- 2026-10-30 · decided by the owner, relayed in session S1
- Options: A — add `.agents/plugins/marketplace.json` to the 0001 `## Scope` and restore the afkv2 entry, with v1 entries byte-identical vs B — keep D-8: the owner-run steps add the entry in a test copy
- Chosen: A — owner ruling. It closes findings f004 and f053 on that basis. A wiring IOU is written only if the consumer of the entry is still later. The orchestrator found no later plan step that names this file (grep of plan-s1 to plan-s4, SDD and PRD); the consumer is Codex, reading the marketplace, and owner-run check 1 uses it, so no IOU is expected. The 0001 agent confirms this when it restores the entry
- Supersedes: D-8 in full
- To reverse: delete the afkv2 entry and the path in the 0001 `## Scope`; D-8 then applies again

## D-26 — plan author's update: 3 Acceptance bullets on 0001, and CI runs the v2 tests
- 2026-10-30 · decided by the plan author (reversible, in goal), relayed in session S1
- Options: A — merge origin/feat/afkv2 (SDD §7 gained 5 rows at 05ef43e8), add the 3 bullets citing SDD §7, and add `.github/workflows/tests.yml` to the 0001 `## Scope` for one step that runs `afkv2/tests` on both OSes, skipping only the live tests that need a harness login vs B — leave CI on the v1 suites only (D-11)
- Chosen: A — ruling of the plan author. The step follows the existing matrix, so it runs on Linux while that row exists. The owner has an open question on removing the Linux row; if it goes, this step goes with it and needs no edit. The hook tests already skip off Windows (`afkv2/tests/test_hooks.py:21`)
- Supersedes: gap 1 of D-11 (no job runs `afkv2/tests`); the other D-11 gap stands
- To reverse: remove the step and the path in the 0001 `## Scope`, and the 3 bullets

## D-27 — findings f004 and f053 keep their terminal records; the citation of D-25 is a plain reply
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — leave the terminal records, the threads stay resolved, and each thread gets a plain reply that cites D-25 vs B — post new finding keys for the recurrence and close those with `fixed`
- Chosen: A — both keys are already terminal, f004 as `fixed` and f053 as `verdict withdrawn`, and their threads are resolved. skills/afk/review/SETTLEMENT.md lists no transition out of a terminal state, and forge_ledger.py raises "illegal transition from terminal". Option B adds two findings and closes nothing more. The reason text of f053 still names D-8 and is out of date; the reply says so
- Supersedes: none
- To reverse: post new keys for the recurrence and close them with `fixed`

## D-28 — the afkv2 CI step: the timing test warns, the step runs before the v1 unit tests, and it installs ripgrep
- 2026-10-30 · decided by execute (0001-skeleton-manifests-hooks)
- Options: A — one step with two commands: all tests except `test_hook_median_of_7_runs_is_under_50_ms` gate, then that test runs alone and a failure prints a warning vs B — the timing test gates on the runner vs C — deselect the timing test in CI
- Chosen: A — D-9 measured a margin of 3 ms to 10 ms on this machine, and the same hook gave medians up to 81 ms under load, so a gate on a shared runner can fail a correct hook. Option C loses the number. The latency step in the same workflow already reports and does not gate. The local run stays the gate. The step comes before `Unit tests`: a failed step stops the later steps of the job, D-11 says the v1 unit-test job on this pull request is red, and D-26 allows no `if`. The cost is that a red afkv2 step hides the v1 steps of that leg. The step installs ripgrep when the runner has none, as `Install jq` does for jq; without it 4 search tests in `afkv2/tests/test_core_behaviors.py` skip, and D-26 allows only live-test skips. No test in `afkv2/tests` starts a harness, so the step skips none for a login
- Supersedes: none
- To reverse: remove the `||` warning and the `-k` filters from the `afkv2 tests` step, move the step, or remove the ripgrep install

## D-29 — owner ruling: afkv2 sets no hook time limit and has no timing test
- 2026-10-30 · decided by the owner (AC-013, commit ce72dc30), relayed in session S1
- Options: A — no time limit and no timing test; the harness's own hook timeout applies vs B — keep the 50 ms limit and its test (D-7, D-9, D-28)
- Chosen: A — owner ruling. The 0001 contract drops the timing part of its Acceptance bullet and integration row, and the 50 ms clause of the fallback bullet. The excerpts for AC-013, SK-02 and ADR-0005 are refreshed. That bullet keeps "parses no shell command" and "extra output fails", because SK-02 and AC-013 still require both. Findings f042 and f051 close on this ruling
- Supersedes: D-7 and D-9 in full; the timing part of D-28
- To reverse: restore the test, the bullet and the excerpts from the commit before this entry

## D-30 — engine layout: component and shell files are found by name, and banner and card are registered types
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — the registry loads every `components/*.py` and the page inlines every `shell/*.css` and `shell/*.js`, so 0004 and 0005 add files and edit no list vs B — a hand-written list that each later slice edits
- Chosen: A. A component calls `register_component(name, schema, render, *, nested=None, check=None, inline=False, takes_html=False)`, and render takes `(props, children)` (SDD §9). `round-banner` and `card` are registered types, so the page has one way to draw a component. Slot `#afkv2-notes-replies` draws a registered type `notes-and-replies` if one exists, with props `{"document": doc}`; 0005 registers it
- Supersedes: none
- To reverse: replace the two scans with lists

## D-31 — where each verb works, and where the saved copy lives
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — `check` works at any path with no config; `render` and `show` also need config and the home `<spec folder>/<feature>/pages/<skill>-<session id>.json`; the saved copy is `<data folder>/page-copies/<sha12>.json` vs B — every verb needs the home
- Chosen: A, because a document can be checked before it has a home and a recorded fake test checks a temp path. `check` reports `saved_copy` as none, compared or unavailable; with no data folder it answers unavailable and `render` exits 2. `engine.save_settled_copy(document, doc)` is public: 0005 ingest calls it after a late note changes a settled round, or the next check refuses that round
- Supersedes: none
- To reverse: make `_require_home` run in `cmd_check`

## D-32 — error codes, mark tokens and the raw grammar
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — the codes and tokens below vs B — free text reasons
- Chosen: A. Codes: schema, unknown-schema, invariant, unreadable, usage, bad-location, duplicate-session, markdown-fallback, host-error, page-ended, page-browser-disconnected. Tokens: decided accept or reopen; confirm accept or write-in; debate a letter or write-in; signoff sign or changes; info, blocked and needs-reading items take a note only. Raw lines: `[round R-n]`, then `<id> <token> | <note>`, with `—` for no choice. A multi-line note stays raw, and the 0005 parser owns continuation lines. A response with no signal is refused, so 0005 ingest always writes at least one signal; it stamps each with `invariants.ingest_stamp`. For R-3, a sign-off card goes back through the fields that exist: state `open` in the current round, with `settled` removed. No schema change is needed
- Supersedes: none
- To reverse: change the tokens in `components/base_card.py` and the 0005 parser together

## D-33 — launcher: exact pin, three verbs, inject on open only
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — the launcher accepts open, poll and end only, and refuses any host version other than 0.1.80 with exit 64 vs B — keep the v1 grammar with `stop` and a minimum version
- Chosen: A. `stop` is out of the grammar because it would end the server for every session (exit 64). So `engine show` answers `markdown-fallback` on this machine until setup moves the global install from 0.1.63 to 0.1.80. Poll is not refused on Codex, which differs from v1 `lavish_poll:false`, because the Stop hook and the one-message fallback both need it. Tooltips are injected on open and not on poll, because a write during poll would reload the page the person is answering
- Supersedes: none
- To reverse: widen the grammar and the pin check in `launcher.run`

## D-34 — Codex Stop hook: no-op on Claude, one hour, 60-second polls
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — one hook entry, an empty command on Claude and `codex_stop.py` on Codex, timeout 3610 s, internal wait 3600 s in 60 s polls vs B — a shorter wait
- Chosen: A. The wait ends before the harness can cut it, and then the hook returns a `systemMessage` that names the one-chat-message fallback. Each poll is 60 s because a long request with no bytes hits the Node fetch header limit (inferred, 300 s). `show` writes the record only when `CODEX_THREAD_ID` is set, and the record name uses that value. That it equals the Stop event's `session_id` is unverified; live check 3 proves or disproves it (D-S-8)
- Supersedes: none
- To reverse: change `timeout_s` in `wait_for_answer` and `timeout` in `hooks.json` together

## D-35 — the live seam test: Playwright library, local host, one kept tab
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — `playwright-core` with Edge against a scratchpad lavish-axi@0.1.80 on its own port and state folder, with one tab kept open across rounds vs B — Playwright MCP against the global install
- Chosen: A. No Playwright MCP tool is present in this run, and the global install is 0.1.63 and must stay (brief). The contract's "Playwright MCP" row is met by the same browser steps through the library. The test is skipped unless `AFKV2_TEST_LAVISH_DIR` is set. One kept tab models the person; it reloads by itself after a re-render (observed). `afkv2/tests/live/CODEX-LIVE-CHECKS.md` is outside the Scope globs, but the contract Acceptance and the brief name it. Fixtures from the v1 round documents are sanitized, and `v0-sdd-pass.json` is derived from `v1-sdd.json`
- Supersedes: none
- To reverse: delete the test and record the seam result by hand

## D-36 — v1 page parts this shell does not carry
- 2026-10-30 · decided by execute (0003-engine-core-schema-show-poll)
- Options: A — drop the side-question control and the dark-invert override vs B — port both
- Chosen: A. Side-question text would reach ingest as an answer. The kit is dark-first, so the override has nothing to do. Draft storage is keyed `afkv2-draft:<session>:<round>` and clears after send, and the round colour comes from a golden-angle hue unless the round sets `colour`
- Supersedes: none
- To reverse: port the two parts from the v1 kit

## D-37 — orchestrator ruling: 0003 Scope gains the 2 paths it edited
- 2026-10-30 · decided by autopilot, as orchestrator (AC-072; owner's green-light rule of 2026-10-30)
- Options: A — add `afkv2/tests/live/CODEX-LIVE-CHECKS.md` and `.claude/wiring-ious.md` to the 0003 `## Scope` vs B — revert both edits and park 0003
- Chosen: A — the 0003 Acceptance names the live-check file; the user's global wiring rule names the IOU file for declaring a later consumer. The agent edited both before asking, and an executor never changes its own Scope, so the plan records the call here. This covers these 2 paths on 0003 only
- Supersedes: none
- To reverse: remove the 2 lines from the 0003 `## Scope`, and revert the edits to those paths

## D-38 — diagram type names and props follow the pages session S2 wrote for authors
- 2026-10-30 · decided by execute (0004-diagram-components)
- Options: A — types `map`, `graph`, `sequence`, `run-strip`, with the props in `afkv2/skills/visualize/components/*.md` on branch feat/afkv2-s2 (read at 1a538932), and an optional `title` on all four; map node state is `settled`, `open` or `focus` vs B — own names and props, and S2 changes its pages and its `PICTURES` set
- Chosen: A — SDD §4 fixes only "checked by the type's own schema", so the S2 pages are the one written use of these props. S2's `examples/all-components.json` passes `engine check` on this slice. Beyond the S2 pages: a label may hold a component (AC-031), and `groups` and `direction` also work on a map, because the map and the graph share one drawing
- Supersedes: none
- To reverse: change the schemas in `afkv2/engine/shell/diagram_boxes.py` and `afkv2/engine/components/diagram_*.py`, and the S2 pages

## D-39 — computed layout, no browser script; shared code in the shell package
- 2026-10-30 · decided by execute (0004-diagram-components)
- Options: A — Python computes each box and arrow in pixels from an estimated label size, and a box scrolls if its label is larger than the estimate; shared code is `shell/diagram_parts.py` and `shell/diagram_boxes.py` vs B — a browser script measures the boxes and draws the arrows, which the unit tier cannot test
- Chosen: A — same document, same bytes, and the unit tier can check box overlap and arrows. `registry.load_components` loads every `components/*.py` as a page component, so shared code stays out of that folder. The sequence diagram and the run strip are CSS grid and flex and need no estimate. Checked by eye in headless Edge on S2's example plus a down-direction graph with groups and loops. The lavish layout audit did not run on these parts (not verified); the 0005 live test is the first run. An arrow that spans ranks or a back arrow can pass behind a box, and its label can sit on a box in a stack (known gap)
- Supersedes: none
- To reverse: add `shell/diagram.js` and remove the arrow geometry from `diagram_boxes.py`

## D-40 — a map node is a note target; a graph node is not
- 2026-10-30 · decided by execute (0004-diagram-components)
- Options: A — a map node carries `data-afkv2-element` with its id; a graph node id is local to its graph, and the whole graph is the target when it has an id vs B — both node kinds carry the attribute, so 2 graphs with the same node id collide, and `engine._element_ids` holds no graph node, so the check refuses a note on one
- Chosen: A — PRD AC-035 lists map node and diagram as note targets. Known gap: `engine._element_ids` reads nodes only from the document's `maps` list, so a map held in a card or a cell draws, but a note on one of its nodes resolves to no element, and its node ids are not checked for uniqueness. `afkv2/engine/engine.py` is outside the 0004 `## Scope`. S2's page says a map goes in the `maps` list
- Supersedes: none
- To reverse: add the attribute in `_plain` in `diagram_boxes.py` and register graph nodes in `engine._element_ids`

## D-41 — orchestrator ruling: 0004 may make one edit in test_engine_core.py
- 2026-10-30 · decided by autopilot, as orchestrator (AC-072; owner's green-light rule of 2026-10-30)
- Options: A — add `afkv2/tests/engine/test_engine_core.py` to the 0004 `## Scope` for one change: delete `scratch_type("map")` and the test's `scratch_type` parameter vs B — rename the type, which breaks S2's use of `map` vs C — leave the test red, with CI red
- Chosen: A — I reproduced it: 1 failed, 171 passed, 1 skipped, from `ValueError` at `afkv2/engine/registry.py:42`. The test stood in a scratch `map` until the real one existed, and 0004 adds the real one. The fixture stays, because 2 other tests use it. The 0004 agent also runs this test file. This covers this one edit on 0004 only
- Supersedes: none
- To reverse: remove the path from the 0004 `## Scope` and restore the 2 lines

## D-42 — an arrow that skips a rank takes a free lane, and an arrow label moves clear
- 2026-10-30 · decided by execute (0004-diagram-components)
- Options: A — Python keeps the computed layout: a forward arrow with a box in its way runs in the nearest free lane through straight segments, and each label moves across the ranks until it touches no box and no earlier label, and the canvas grows to hold it vs B — a browser script measures and routes, which D-39 refused
- Chosen: A — review round 1 of this slice found 2 high defects on PRD CMP-5 and AC-042. A label size is an estimate. Headless Edge measured 14 hard graphs in both directions, and no label touched a box or a label or left the canvas. Still a known gap: a back arrow can pass behind a box in a tall stack
- Supersedes: D-39 "An arrow that spans ranks or a back arrow can pass behind a box, and its label can sit on a box in a stack (known gap)", for forward arrows and all labels
- To reverse: remove `_lanes` and `_Taken` from `diagram_boxes.py`

## D-43 — the gap of a map held in a card goes to 0005 by orchestrator ruling
- 2026-10-30 · decided by the orchestrator, recorded by execute (0004-diagram-components)
- Options: A — 0004 leaves `afkv2/engine/engine.py` as it is and 0005 takes the gap vs B — 0004 widens its Scope and changes `engine._element_ids`
- Chosen: A — the orchestrator's words: "D-40's gap stays as you recorded it. `afkv2/engine/engine.py` is outside your Scope, and I am passing the gap to 0005, which has that file in its Scope and builds notes. Do not fix it here." Review round 1 widens what 0005 must cover. For a map held in a card or a table cell: a note on its node is refused, an item cannot link to its node, 2 held maps with one node id pass the check, and a node round past the last round passes the check. S2's `round_document.py` accepts `map` as a card body, so this shape is reachable (read in the reviewer's evidence, not re-run here)
- Supersedes: none
- To reverse: walk every map with `registry.walk` in `engine._element_ids`

## D-44 — D-42 narrowed: what is closed and what stays open after review round 2
- 2026-10-30 · decided by execute (0004-diagram-components)
- Options: A — every forward arrow runs straight to the end of its rank before it bends, and a label is also kept on the canvas along the ranks, and the rest stays as advice under owner ruling R-2 vs B — also route back arrows and measure labels word by word, which R-2 does not ask for
- Chosen: A — a seeded test of 120 graphs finds no forward arrow behind a box, and no label on a box or on a label by the estimated size. D-42's words "for forward arrows and all labels" claim too much. Known gaps that stay open as medium findings on the pull request: a back arrow can run behind the next box in its stack, also with one box below (not only a tall stack); a label of many long words or wide glyphs is larger than the estimate, so it can land on a box or a label or leave the canvas; a label can cover a group title; and arrows that skip a rank at every step cost about the cube of the arrow count (28 s at 800 nodes, reviewer's timing, not re-run here)
- Supersedes: D-42 "for forward arrows and all labels"
- To reverse: remove the straight first leg in `_forward` and the floor on `low` in `_arrows`

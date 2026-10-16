C:\Users\mvu\PersonalProjects\afk-driver-agent-teams@7e9c87a · partial · boundaries 11/14 · unverified 5 (load-bearing 3) · ledger: docs/afk/agent-team-topology/investigations/INV-036-report-file-fallback/COVERAGE.json

## Answer
- Q1, the writers today: 3 kinds of role child write their own file. The adversary writes `plan/review/{NNNN-slug}-adversary.md` (skills/afk/adversary/SKILL.md:40), started by /afk:execute Step 10.5 (skills/afk/execute/SKILL.md:89). A spawned /afk:investigate run writes COVERAGE.json and REPORT.md at step 7 (skills/utils/investigate/SKILL.md:62); its starters are grill-requirements SKILL.md:46 and ROUND.md:52, grill-solution SKILL.md:76 and GROUNDING-RULE.md:25, :40. Each afk-tracer writes its fragment and evidence files (agents/afk-tracer.md:16); the starter is investigate step 4 or step 5 (SKILL.md:44, :53). Each starter reads the file by path (c-656cb7e5, c-b3b40077, c-150d33ea, c-5c3d20ff).
- Other children keep writing (c-51e28d67, c-7552b5bb): the runner helpers' evidence files (agents/afk-runner.md:14), afk-implementor (agents/afk-implementor.md:16), the page writer (LAVISH.md:268, :291), the settle-change fixers (settle-change SKILL.md:57), and /afk:fix lesson-ledger appends (fix SKILL.md:76).
- Refusal today (c-3c7eadf6, c-e3b440fb, from providers/CONFORMANCE.md:329): a Claude subagent's Write is refused for REPORT.md but succeeds for -adversary.md, fragment.json and COVERAGE.json. A Codex sub-agent writes every name. Of the moved files, only REPORT.md hits the refusal (c-854b090a).
- Q2, readers by path, all unchanged if the starter writes the returned text verbatim (c-e8ed64a9, c-6bee9be2, c-b99ad411): merge_fragments.py:627, check_sdd_investigations.py:119, validate_plan.py:461, CITED-MODE.md:53, :78, review SKILL.md:38, :167, retro SKILL.md:29, verify-seams SKILL.md:23, understand SKILL.md:49, wiring-gate.sh:49, and mission control gates.py:114 and insights.py:206 (these 2 read the verdict from the first 4000 characters).
- Q3, breaks (all unguarded except where noted):
  - The starters gain the write: execute SKILL.md:89, :143; investigate SKILL.md:44, :53, :62; grill-requirements SKILL.md:46; grill-solution SKILL.md:76; GROUNDING-RULE.md:25, :40, :42, :43 (c-82baecb6, c-fec6258d, c-39eff6e6).
  - Statements that name the old writer: investigate SKILL.md:8, :10; CLAUDE.md and AGENTS.md :65-66, :160; agents/afk-tracer.md:16, :40; afk-afk-tracer.toml:2; LEDGER-FORMAT.md:255; CONFORMANCE.md:26; DELEGATION.md:26, :66, :68 (bulk goes to a file, not the return); CITED-MODE.md:83; ground_diff.py:7 (c-d4330950, c-362024d6, c-c05c8beb, c-7ec3dfb2).
  - The /afk:bug retester: SKILL.md:30, :87 and RETEST-PROMPT.md:12 forbid the file write that premise 7 keeps (c-f261ac68).
  - The switch has no key: scripts/afk-config.py:51 refuses unknown keys, pinned by scripts/tests/test_afk_config.py:134 (c-7c40b74a, c-23419c21). No other test pins a moved write (c-583ceee3).
  - The feature documents contradict themselves: SDD.md:591, INDEX.md:3, GRILL-LOG.md:674, :681, PRD.md:148, :149, :174, ADR-0015:8 (c-e07846c3, c-d2ecd5f0, c-656c764d).
  - Inline runs still write REPORT.md inside the autopilot subtask agent and the /afk:bug fixer (c-901692d9).
## Sites
- breaks: the Q3 sites above, plus SDD.md:591, INDEX.md:3, GRILL-LOG.md:674, :681, PRD.md:148, :149, :174 and ADR-0015:8.
- traced, unchanged: GRILL-LOG.md:160, 166, 167, 459, 462, 491, 525, 551, 560, 561; PRD.md:101, :144; autopilot:33; bug FIXER-PROMPT.md:28, RETEST-PROMPT.md:25, SKILL.md:39; CITED-MODE.md:75; execute:51, :67, :71; fix:30; review:38; test-veracity.md:25; to-prd:12; understand:54; diagnose:83; investigate:45, :49 (pinned by test_merge_fragments.py:96); settle-change:57; verify-seams:15.
- terminal, unchanged: every other node in COVERAGE.json outside the prior ledgers, among them the runner, implementor and Codex stubs, LAVISH.md, REPORTING.md:31, mutation-probe.sh:68, stall-watchdog.sh, CONFORMANCE.md probe rows, and the tests under scripts/tests.
- irrelevant: lines of the prior ledgers `docs/afk/agent-team-topology/investigations/INV-*/` and rendered pages (`*.html`, `*.round.json`), plus name-form matches not about the subject (CHANGELOG.md, test_lavish_render.py, tracker adapters, research/ notes).
## Frontier
- docs/afk/agent-team-topology/PRD.md:144: how a subagent's final text reaches its starter and how much text 1 reply carries. This is harness runtime, and no probe row states it.
- skills/afk/setup/INVESTIGATION-SESSIONS.md:18: whether a subagent loads the user's steering files. Harness runtime.
- skills/afk/review/SKILL.md:157: whether the harness refuses the review gate's own file names. No probe row covers it.
- B1 is partial: COVERAGE.json was not enumerated in 33 of the 34 prior ledgers' own COVERAGE.json files. Those files hold 345828 matching lines, and the class limit is 20000. B13 is partial: prose states writers with no searchable form.
## Unverified
- c-eafe6df3 (load-bearing): whether a subagent may write the review files plan/review/*.md, *.findings.json and INDEX.md.
- c-86e07f89 (load-bearing): whether a subagent may write the result file of the /afk:bug publisher and retester.
- c-80e1da73 (load-bearing): the reply channel and its size.
- c-4f518f1f: whether a subagent loads the steering file. c-7971da67: the seed's hit-set claim. The fold keeps it unverified; c-6e53c8d4, c-353547af, c-c972dbc0 and c-465a210d answer it.
## Premises
- Premise: At review:38, diagnose:83 and to-prd:12 the invoking agent runs /afk:investigate inline; the L9 seam runs are the grill-solution premise runs that S-208 counts as role spawns.
- Premise: The fallback moves the report writes of 3 kinds of role child only; afk-runner helpers keep writing evidence files.
- Premise: Every page writer on the authored path, the /afk:prototype one included, is a pane role agent with lifespan Feature that writes its page.
- Premise: Under the fallback, the starter writes the returned adversary report to the named path before it cites any finding.
- Premise: A helper never runs /afk:investigate; it returns open code claims as unverified, and its pane-agent starter investigates them.
- Premise: The mutation-probe output of a review worker is build output, not a report file; the fallback leaves it with the worker.
- Premise: The retester writes only its result file; the main /afk:bug session copies the evidence into the bug directory and records the path.

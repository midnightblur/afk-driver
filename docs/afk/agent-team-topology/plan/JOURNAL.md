# Journal — append-only event log (format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.
2026-10-16 13:57 | autopilot | run | run start (26 runnable) — the plan's 26 steps start one by one; Draft PR #112 opened for the review ledger; full test suites run on both systems after the last step (human call 2026-10-16)
2026-10-16 13:58 | execute | 0001-glossary-terms | designing — started planning the glossary entries
2026-10-16 13:59 | execute | 0001-glossary-terms | developing — writing the new team terms into the plugin glossary
2026-10-16 18:04 | execute | 0001-glossary-terms | pushed c3d0751..52ada6a (1 commits) — the new glossary entries are on the shared branch
2026-10-16 18:05 | execute | 0001-glossary-terms | verifying — all three checks pass: the entries exist, the old relay sentence is gone, the glossary usage test passes
2026-10-16 18:05 | execute | 0001-glossary-terms | reviewing — an independent review of the glossary change starts
2026-10-16 18:14 | execute | 0001-glossary-terms | review advisory crit=0 high=0 med=1 low=0 — one medium note (common words now get tooltips), disputed on the PR as required by the contract's term list
2026-10-16 18:14 | execute | 0001-glossary-terms | parked(other) — the review record cannot be checked: GitHub refuses to send the PR's full diff (about 86 MB, mostly committed investigation files), so the gate that proves findings were posted fails every time
2026-10-16 18:19 | autopilot | 0001-glossary-terms | parked(other) — the glossary work is pushed (52ada6a), but the review step cannot read the change: GitHub's diff of PR #112 is 208 MB, almost all investigation coverage files, and the forge diff call fails; every later step's review would stop at the same point, so the run waits for the human
2026-10-19 14:07 | autopilot | 0001-glossary-terms | resumed at standard sizing — the human chose a fix branch off main (PR #116) that builds the change's diff from local commits; the rest of the run uses that branch's tree as the plugin root, and the step re-runs once at standard size per the park rule
2026-10-19 14:09 | execute | 0001-glossary-terms | reviewing — the review resumes with the repaired diff reader; the one open review note goes to an independent judge
2026-10-19 14:12 | execute | 0001-glossary-terms | review advisory crit=0 high=0 med=1 low=0 — round 1 closed: an independent judge withdrew the one note, since the plan requires those glossary words and the tooltip effect already existed
2026-10-19 14:14 | execute | 0001-glossary-terms | decision(D-40) — the attack test for this step runs against the plugin's own scripts, since the plugin has no app
2026-10-19 14:14 | execute | 0001-glossary-terms | decision(D-41) — the second review round re-reads the glossary change itself, not the unrelated commit added after it
2026-10-19 14:31 | execute | 0001-glossary-terms | developing — fixing two glossary entries the second review found incomplete
2026-10-19 14:44 | execute | 0001-glossary-terms | review advisory crit=0 high=0 med=3 low=1 — round 2: two glossary entries corrected and pushed (0d3bd80), one note withdrawn by an independent judge, one wording note moved to the whole-feature review
2026-10-19 14:44 | execute | 0001-glossary-terms | pushed ade8ab1..0d3bd80 (1 commits) — the two corrected glossary entries are on the shared branch
2026-10-19 14:45 | execute | 0001-glossary-terms | reviewing — a third review checks only the two corrected entries
2026-10-19 14:49 | execute | 0001-glossary-terms | review clean crit=0 high=0 med=0 low=0 — round 3 found nothing in the two corrected entries; the review record on the PR is settled, with one wording note held for the whole-feature review
2026-10-19 14:57 | execute | 0001-glossary-terms | adversary findings probed=18 crit=0 high=0 med=1 low=2 — an independent attack test found the glossary entries present and correct, plus three wording notes that do not block; noted on the PR
2026-10-19 14:58 | execute | 0001-glossary-terms | wiring clean — the check for unused new files found nothing
2026-10-19 14:58 | execute | 0001-glossary-terms | done — the glossary step is finished and pushed; the PR stays a draft for the human
2026-10-19 14:58 | autopilot | run | heartbeat 1/26 done, starting 0002-config-transport-and-pattern-keys — the glossary step passed review and the attack test; the next step adds the team settings keys
2026-10-19 15:00 | execute | 0002-config-transport-and-pattern-keys | designing — started planning the new team settings keys in the configuration reader
2026-10-19 15:10 | execute | 0002-config-transport-and-pattern-keys | decision(D-42) — the code these settings touch changed since it was studied, so one fresh study of it runs before the change lands
2026-10-19 15:10 | execute | 0002-config-transport-and-pattern-keys | decision(D-43) — the spec left the new setting names open; the run picked them to match the existing settings
2026-10-19 15:10 | execute | 0002-config-transport-and-pattern-keys | decision(D-44) — the reader keeps the five built-in team names until the step that ships the team records
2026-10-19 15:10 | execute | 0002-config-transport-and-pattern-keys | decision(D-45) — the reader checks setting names and shapes; the team builder checks the values
2026-10-19 15:10 | execute | 0002-config-transport-and-pattern-keys | developing — writing the new settings checks and their tests
2026-10-19 16:13 | execute | 0002-config-transport-and-pattern-keys | pushed — the settings change and its fresh code study are on the branch, ticked on pull request 112, with three reasons posted on its lines
2026-10-19 16:13 | execute | 0002-config-transport-and-pattern-keys | verifying — re-running every check the contract lists on the pushed code
2026-10-19 16:40 | execute | 0002-config-transport-and-pattern-keys | verified — every listed check passed again and the three promised names exist in the code
2026-10-19 16:43 | execute | 0002-config-transport-and-pattern-keys | reviewing — fresh reviewers check the change one concern at a time, round 1
2026-10-19 16:55 | execute | 0002-config-transport-and-pattern-keys | developing — fixing round 1 review findings: a crash on a malformed include, an empty stage entry, a wrong sentence in CONFIG.md, and missing tests
2026-10-19 17:13 | execute | 0002-config-transport-and-pattern-keys | review — round 1 found 9 issues; 6 fixed in 44b1c34 and pushed, 1 withdrawn by an adjudicator, 2 left open because their fix is outside this slice's Scope
2026-10-19 17:13 | execute | 0002-config-transport-and-pattern-keys | lesson(L-0001) — slicing left the reader of a new report field out of Scope; drafted a rule for the subtask contract
2026-10-19 17:13 | execute | 0002-config-transport-and-pattern-keys | blocked(needs_decision) — the issue template row that shows the new transport field is outside Scope; a human must widen the Scope or give that row to another subtask
2026-10-19 17:15 | autopilot | 0002-config-transport-and-pattern-keys | parked(needs_decision) — the issue template row that would show the new transport setting is outside this step's file list
2026-10-19 17:15 | autopilot | 0002-config-transport-and-pattern-keys | agent-decided — widen the step's file list to ISSUE-TEMPLATE.md and add the transport row (option A); no other step touches that file; reversible on the branch
2026-10-19 17:15 | autopilot | 0002-config-transport-and-pattern-keys | resumed — re-run from the review step, round 2
2026-10-19 17:20 | execute | 0002-config-transport-and-pattern-keys | decision(D-46) — the issue template now shows the transport setting the collector writes; the orchestrator widened this step's file list to allow it
2026-10-19 17:31 | execute | 0002-config-transport-and-pattern-keys | decision(D-47) — the code-study record quoted a fake machine name from a test, which made the privacy filter trust it; the quote now uses a placeholder
2026-10-19 17:41 | execute | 0002-config-transport-and-pattern-keys | pushed 017eb11..48fb989 (1 commits) — the issue template now shows the transport setting, with a test that every collected field appears in it
2026-10-19 17:41 | execute | 0002-config-transport-and-pattern-keys | reviewing — round 2 of the review checks the two fixes since round 1
2026-10-19 17:54 | execute | 0002-config-transport-and-pattern-keys | verified — on the new head the report-issue tests (307), publish-smoke (44), the settings tests and the native contract tests (42) all pass, and the native contract gate reports nothing
2026-10-19 18:07 | execute | 0002-config-transport-and-pattern-keys | review advisory crit=0 high=0 med=0 low=1 — round 2: the two round 1 notes are fixed; one new note about an edited quote in the code-study record was withdrawn by an independent judge
2026-10-19 18:11 | execute | 0002-config-transport-and-pattern-keys | review clean crit=0 high=0 med=0 low=0 — round 3 found nothing in the plan records; the review record on the PR is settled
2026-10-19 18:23 | execute | 0002-config-transport-and-pattern-keys | adversary findings probed=126 crit=0 high=0 med=1 low=0 — an independent attack test found every bad setting refused, plus one non-blocking note: an empty transport section blanks the launch method; noted on the PR for the step that adds the machine check
2026-10-19 18:23 | execute | 0002-config-transport-and-pattern-keys | wiring clean — the check for unused new files found nothing
2026-10-19 18:24 | execute | 0002-config-transport-and-pattern-keys | done — the settings step is finished and pushed, all three posted reasons are confirmed on the PR, and the PR stays a draft for the human

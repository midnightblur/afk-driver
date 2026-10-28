# Journal — append-only event log (format: skills/afk/to-subtasks/JOURNAL-FORMAT.md). Newest last.
2026-10-20 14:06 | execute | 0001-diagnosis-format | designing — started designing the diagnosis record: its format file, its check script and the one helper that logs outside writes
2026-10-20 14:21 | execute | 0001-diagnosis-format | decision(D-1) — the check script reports only the bug states written in the diagnosis file; the fix skill reads the other two from git and the grill log
2026-10-20 14:28 | execute | 0001-diagnosis-format | developing — wrote the format file and failing tests; now writing the check script and the outside-writes helper
2026-10-20 14:34 | execute | 0001-diagnosis-format | pushed 3de5d14..190105b (1 commits) — the format file, check script, helper and their tests are on the pull request
2026-10-20 14:35 | execute | 0001-diagnosis-format | pushed 3efbfeb..190105b (1 commits) — corrects the line above, which named the wrong starting commit
2026-10-20 14:35 | execute | 0001-diagnosis-format | verifying — running every check the slice declares: gates, its unit tests, and the full suite on Windows and Linux
2026-10-20 15:04 | execute | 0001-diagnosis-format | reviewing — gates, unit tests and the Linux suite are green; independent reviewers now read the change while the Windows suite finishes
2026-10-20 15:28 | execute | 0001-diagnosis-format | review r1 — 15 findings (1 high): 12 fixed, 2 low design deferred to the feature gate, 1 disputed and withdrawn
2026-10-20 15:28 | execute | 0001-diagnosis-format | decision(D-2) — D-1's ledger entry now quotes the contract bullet and SDD rows it overrides
2026-10-20 15:28 | execute | 0001-diagnosis-format | developing — fixing review round 1 findings inside the slice
2026-10-20 15:51 | execute | 0001-diagnosis-format | review r2 — 6 findings (1 medium test gap, 5 low); all fixed
2026-10-20 16:07 | execute | 0001-diagnosis-format | review r3 — 1 low finding (the checker and appender split lines differently); fixed
2026-10-20 16:14 | execute | 0001-diagnosis-format | review r4 clean — closure gate settled after 4 rounds (19 fixed, 1 withdrawn, 2 deferred to the feature gate)
2026-10-20 16:14 | execute | 0001-diagnosis-format | decision(D-3) — the adversary probes the check script's command line and the helper's functions, since this slice has no running app
2026-10-20 16:52 | execute | 0001-diagnosis-format | adversary findings — 150 probes, 0 critical/high, 2 medium (carriage return in an appended entry, indented unmarked first line) and 7 low; advisory, noted on the pull request
2026-10-20 17:05 | execute | 0001-diagnosis-format | done — rationale receipt confirmed, wiring anchored to slices 0004, 0005, 0007 and 0008; waiting on the Windows failure split before push
2026-10-20 17:40 | execute | 0001-diagnosis-format | pushed 9f54e99..3efb356 (2 commits) — round 4 and adversary records, done status; Windows failures split: none caused by this branch (3 fail on main too, 1 flaky, 9 from untracked investigation files)
2026-10-20 17:55 | execute | 0002-developer-settings | decision(D-4) — none means unset for all three person keys; the bug skill keeps its own stop table until it is removed; ground re-read by hand because the scripted check hit its hit cap
2026-10-20 18:20 | execute | 0002-developer-settings | developing — K1-K5 docs moved to CONFIG.md, none = unset for the three person keys, setup still counts a recorded none as answered
2026-10-20 18:45 | execute | 0002-developer-settings | verifying — gates and unit tests green; full suite and hook smoke running on Windows and Linux before the push
2026-10-20 19:10 | execute | 0002-developer-settings | WSL suite: 3350 passed, 25 failed — the same 25 fail on main, none from this branch; hook smoke not run there (jq missing in WSL)
2026-10-20 20:35 | execute | 0002-developer-settings | pushed 3efb356..b7409d3 (1 commit); Windows suite green against its baseline, hook smoke green; reviewing — independent reviewers read the change
2026-10-20 21:05 | execute | 0002-developer-settings | review r1 — 4 findings (2 medium tests, 1 low bug-page gap, 1 low probe test gap); decision(D-6) — the H6 probe's test file joins the slice; developing — fixing them
2026-10-22 12:10 | execute | 0002-developer-settings | branch rebased onto main 82c3db8 (PR conflicted, so CI never ran) and force-pushed with lease to ea2cdac; tests now run in CI on the human's call
2026-10-22 12:40 | execute | 0002-developer-settings | review r1 fixes posted and resolved (f001–f004); forge_ledger.py could not summarize a listed concern — fixed outside the slice in cd6cf95; r1 summary posted
2026-10-22 13:00 | execute | 0002-developer-settings | reviewing — review r2 on the fix delta (delta-sweep, test-veracity)
2026-10-22 13:19 | execute | 0002-developer-settings | review r2 — 1 low test finding, fixed in 2f68fbd; review r3 clean; review gate settled (closure ok at round 3, 5 findings, all fixed); adversary gate running
2026-10-22 13:41 | execute | 0002-developer-settings | adversary — findings, high=1 med=5 low=5 (D-3 runtime probe); decision(D-7) — F1, F2, F4, F5 predate the slice and route to new slice 0013-config-contract, the rest advisory; rationale receipt sealed
2026-10-22 13:41 | execute | 0002-developer-settings | done
2026-10-24 03:55 | execute | 0003-tracker-attach | designing — ground for INV-024 held (D-5, and main's 22 commits since touch none of its cited lines)
2026-10-24 03:56 | execute | 0003-tracker-attach | developing — implementor working the contract test-first; focused tests local, full suites in CI
2026-10-24 05:40 | execute | 0003-tracker-attach | decision(D-8) — scripts/tracker_api.py joins Scope for its verb count; decision(D-9) — four cases the contract left open
2026-10-24 07:05 | execute | 0003-tracker-attach | verifying — static gates + Produces greps green; CI green on 2fe97a9 (ubuntu, windows); rationale batch 83e48e8efa8f3a25 posted
2026-10-24 07:05 | execute | 0003-tracker-attach | reviewing — round 1: spec-fidelity, scope-and-impact, test-veracity, logic-correctness, refactor-safety, api-contract
2026-10-26 09:00 | execute | 0003-tracker-attach | review r1 — 14 findings (8 med, 6 low), fixed in 7feb708; r2 — 8 findings (2 med, 6 low), fixed in 20b3e5e; r3 — 1 low, fixed in d08987d; r4 clean
2026-10-26 09:00 | execute | 0003-tracker-attach | review closure failed — fix commits lacked Settles trailers; 7281545 carries them, dc02009 lets closure read a later trailer (human chose the script fix); review gate settled (closure ok at round 5, 23 findings, all fixed)
2026-10-26 10:30 | execute | 0003-tracker-attach | adversary — findings, high=1 med=2 low=4 (D-3 runtime probe); F1 (Windows gh body not UTF-8, hang) and F3 fixed in 297ef3c; review r6 — 2 test findings fixed in 396d378; r7 clean; review gate settled (closure ok at round 7, 25 findings, all fixed)
2026-10-26 10:30 | execute | 0003-tracker-attach | adversary pass 2 — findings, crit=0 high=0 med=4 low=5; gate passes; position pairing waits on the 0011 live check, the rest advisory; rationale receipt sealed
2026-10-26 10:30 | execute | 0003-tracker-attach | done
2026-10-26 22:11 | autopilot | — | run start — 10 subtasks left (0004-0011, 0013, 0012); 0004 runnable now; no app to boot (D-3), tests run focused locally and in full in CI (human instruction)
2026-10-26 22:42 | execute | 0004-diagnose-rewrite | designing — ground for INV-022 held, re-read by hand (decision(D-10)); no rationale notes on the edited lines
2026-10-26 22:42 | execute | 0004-diagnose-rewrite | decision(D-11) — an invoker may hand diagnose a worktree; no person and no starting-branch answer ends blocked; decision(D-12) — AC-008 binds writes, size-call bar; decision(D-13) — fix applies the proposal test-first until its rewrite
2026-10-26 22:51 | execute | 0004-diagnose-rewrite | developing — diagnose rewritten, size-call file and row, grills and fix pointed at them; pushed f86eb43..ac7bb38 (1 commit)
2026-10-26 22:51 | execute | 0004-diagnose-rewrite | verifying — plugin-source gates and Produces greps green; focused unit tests 112 passed; full suites and hook smoke run in CI
2026-10-26 22:52 | execute | 0004-diagnose-rewrite | reviewing — round 1: spec-fidelity, scope-and-impact, test-veracity, logic-correctness, refactor-safety, api-contract
2026-10-27 01:07 | execute | 0004-diagnose-rewrite | reviewing — round 1: 2 high, 15 medium, 7 low, all fixed in d22496e; decision(D-14) — any linked worktree goes to diagnose, fix takes a path and still-small rows; decision(D-15), decision(D-16)
2026-10-27 01:07 | execute | 0004-diagnose-rewrite | reviewing — round 2 (delta): 6 medium, 4 low; 9 fixed in b6b4c0b, 1 verified (caller routing is slice 0009's); decision(D-17) — handed worktree's Base, SDD rows narrowed, WORKFLOW-FEEDBACK in Scope
2026-10-27 01:36 | execute | 0004-diagnose-rewrite | reviewing — round 3 (delta): 1 high, 3 medium, 4 low, all fixed; round 2 was 5 medium and 5 low (the earlier line miscounted); decision(D-18) — a re-run whose worktree is gone is found after the starting-branch question; handed branch name rows narrowed
2026-10-27 02:14 | execute | 0004-diagnose-rewrite | reviewing — round 4 (delta): 2 medium, 2 low, all fixed; decision(D-19) — fix works in the worktree that holds the diagnosis
2026-10-27 02:34 | execute | 0004-diagnose-rewrite | reviewing — round 5 (delta): 3 medium, 1 low, all fixed; decision(D-20) — a re-run needs its record or its diagnosis; decision(D-21) — fix cuts onto the Diagnosis branch when it holds the failing test
2026-10-27 02:57 | execute | 0004-diagnose-rewrite | reviewing — round 6 (delta): 2 high, 1 medium, all fixed; decision(D-22) — a re-run is proved only by its DIAGNOSIS.md; fix takes the deepest listed worktree
2026-10-27 03:25 | execute | 0004-diagnose-rewrite | reviewing — round 7 (delta): 2 medium, both fixed; decision(D-23) — a worktree for the work id with no diagnosis ends blocked, naming it
2026-10-27 03:49 | execute | 0004-diagnose-rewrite | reviewing — round 8 (delta): 1 medium, fixed; decision(D-24) — the blocked reason names remove-worktree.py, which also clears the owner record and an empty branch
2026-10-27 04:08 | execute | 0004-diagnose-rewrite | reviewing — round 9 (delta): 2 medium, 1 low, all fixed; decision(D-25) — the blocked reason says what a retry needs gone, warns it discards work, and names a removal for worktrees with and without an owner record
2026-10-27 04:27 | execute | 0004-diagnose-rewrite | blocked(review_fail) — round 10 (delta): 2 medium open (f060 branch name lost before git branch -D; f061 no-record case deletes the wrong branch); settle loop hit its 10-round cap, adversary not run
2026-10-27 04:30 | autopilot | 0004-diagnose-rewrite | parked — review_fail: 10-round review limit with 2 medium findings open (f060, f061) in one sentence of diagnose step 3; adversary gate not run; a person must settle that sentence
2026-10-27 04:30 | autopilot | 0008-standalone-fix | parked(waiting on 0004-diagnose-rewrite)
2026-10-27 04:30 | autopilot | 0010-out-of-slice | parked(waiting on 0008-standalone-fix)
2026-10-27 04:30 | autopilot | 0011-bug-removal-release | parked(waiting on 0004-diagnose-rewrite)
2026-10-27 04:30 | autopilot | 0012-sync-harness | parked(waiting on 0004-diagnose-rewrite)
2026-10-27 04:30 | autopilot | — | 0/10 done this run, starting 0005-bug-mode
2026-10-27 04:56 | execute | 0005-bug-mode | designing — consumer preflight passed (6 of 6); decision(D-26) — ground re-read by hand, it holds; decision(D-27) — per-kind table over the existing tracker verbs
2026-10-27 05:24 | execute | 0005-bug-mode | developing — publish_bug_mode.py, BUG-MODE.md and 40 stub-tracker tests (Jira and GitHub Issues) green; SKILL.md, AGENTS.md and CHANGELOG.md point at the mode
2026-10-27 05:40 | execute | 0005-bug-mode | pushed — 9f50c24; PR 126 checklist ticked; 4 rationale entries posted with their receipt
2026-10-27 05:40 | execute | 0005-bug-mode | verifying — static green (plugin-source gates over the slice commit, both Produces anchors), unit green (40 tests), integration -k load green; full suite and hook smoke run in CI: not run (PR conflicting)
2026-10-27 05:40 | execute | 0005-bug-mode | reviewing — round 1: spec-fidelity, scope-and-impact, test-veracity, refactor-safety, logic-correctness (lean policy)
2026-10-27 06:35 | execute | 0005-bug-mode | reviewing — round 1: 1 high, 12 medium, 8 low; 20 fixed, 1 medium design finding deferred to the feature gate; decision(D-28) — two one-line edits outside Scope; decision(D-29) — created ticket's in-review match runs after the create, markers keyed on the created key
2026-10-27 06:50 | execute | 0005-bug-mode | reviewing — decision(D-30) — a Windows-held diagnosis file made the swap fail one run in five; the shared swap now retries
2026-10-27 07:55 | execute | 0005-bug-mode | reviewing — round 2 (delta): 5 medium, 5 low; all 10 fixed; decision(D-31) — in-review means a state of that name, keys in the tracker's spelling, description work id from two slugs
2026-10-27 08:40 | execute | 0005-bug-mode | reviewing — round 3 (delta): 3 medium, 3 low; all 6 fixed; decision(D-32) — D-30's helper edits widened; decision(D-33) — description work id carries a hash of its exact names
2026-10-27 09:30 | execute | 0005-bug-mode | reviewing — round 4 (delta): 3 medium, 3 low; all 6 fixed; decision(D-34) — description work id hashes the stored names
2026-10-27 09:55 | execute | 0005-bug-mode | reviewing — round 5 (delta): 1 medium, 1 low; both fixed; decision(D-35) — work id names read from folder listings
2026-10-27 10:20 | execute | 0005-bug-mode | reviewing — round 6 (delta): 1 medium, 2 low; all 3 fixed
2026-10-27 10:45 | execute | 0005-bug-mode | reviewing — round 7 (delta): 2 low; both fixed
2026-10-27 11:05 | execute | 0005-bug-mode | reviewing — round 8 (delta): 1 medium (a low merged at the same line); fixed
2026-10-27 11:25 | execute | 0005-bug-mode | reviewing — round 9 (delta): clean; closure gate settled at 1df30f3 (9 rounds, 51 findings, all fixed)
2026-10-27 12:05 | execute | 0005-bug-mode | adversary — findings, crit=0 high=0 med=3 low=4 (D-3 runtime probe, 94 scenarios, local fakes); gate passes; advisory, noted on the change
2026-10-27 12:05 | execute | 0005-bug-mode | wiring scan — exit 0; rationale receipt verified (4 entries durable)
2026-10-27 12:05 | execute | 0005-bug-mode | done
2026-10-27 12:05 | execute | 0005-bug-mode | outcome success — review settled at round 9 (51 findings, all fixed), adversary passes with 3 medium and 4 low advisory; CI not run (PR conflicting)
2026-10-27 11:37 | autopilot | 0005-bug-mode | done — 1/10 done this run; review settled at round 9 (51 fixed), adversary passes with 3 medium and 4 low advisory
2026-10-27 11:37 | autopilot | — | rebased onto origin/main 3c6bd7c and force-pushed with lease (human approved); closure now accepts a rebased fix by its Settles line (507d029, human chose); resuming 0004-diagnose-rewrite with the human's call on f060 and f061
2026-10-27 11:42 | execute | 0004-diagnose-rewrite | decision(D-36) — the human settles the round 10 stalemate: the blocked reason names the worktree's branch from `git worktree list`; with no owner record only the branch `create-worktree --name` would create is deleted, when it exists; review cap lifted to round 13
2026-10-27 11:42 | execute | 0004-diagnose-rewrite | developing — f060 and f061 fixed in diagnose Phase 0 step 3
2026-10-27 12:02 | execute | 0004-diagnose-rewrite | pushed 507d029..8c6ffa2 (1 commits) — the human's fix for the round 10 findings is on the pull request
2026-10-27 12:02 | execute | 0004-diagnose-rewrite | review advisory crit=0 high=0 med=0 low=3 — round 11 (delta): 2 low on how the no-record branch is found and when it is kept, both fixed; 1 low on the format of 2 earlier journal lines, deferred to the feature gate
2026-10-27 12:22 | execute | 0004-diagnose-rewrite | review advisory crit=0 high=0 med=0 low=3 — round 12 (delta): step 4 still filled the branch by hand, fixed; the round 11 choices lacked a ledger entry, recorded; reading the script's rule by hand deferred to the feature gate
2026-10-27 12:22 | execute | 0004-diagnose-rewrite | decision(D-37) — the no-record branch follows the script's rule and is kept when step 4 would resume it; step 4 reads the Diagnosis branch from the new worktree
2026-10-27 13:58 | execute | 0004-diagnose-rewrite | review advisory crit=0 high=0 med=0 low=2 — round 13 (delta): the format, design and contract text still said the Diagnosis branch comes from the branch template; D-37's undo line pointed at wording D-36 does not hold; both fixed by the human's D-38
2026-10-27 13:58 | execute | 0004-diagnose-rewrite | decision(D-38) — the human: a cut worktree's Diagnosis branch is the branch it is on, over the format, design and contract text; D-37's undo line quotes the step 4 sentence it replaced
2026-10-27 14:12 | execute | 0004-diagnose-rewrite | review advisory crit=0 high=0 med=1 low=3 — round 14 (delta, the last the human allowed): D-38 changes the shipped format row only through the plan ledger, which is deleted after merge; its quotes override more than the branch clause; 2 wording defects in its override and undo lines; all 4 open
2026-10-27 14:12 | execute | 0004-diagnose-rewrite | parked(review_fail) — round 14 left 4 findings open on the D-38 entry (1 medium spec, 3 low correctness); the human allowed no more rounds, so a human must decide; adversary gate not run
2026-10-27 15:51 | execute | 0004-diagnose-rewrite | decision(D-39) — the human: the format, design and contract text now say the Diagnosis branch is the diagnosis worktree's branch; the format file joins this slice's Scope; D-38's override and undo lines are replaced
2026-10-27 16:16 | execute | 0004-diagnose-rewrite | pushed a6d78da..5781d42 (1 commits) — the human's D-39 edits to the format, design and contract text fix the 4 round 14 findings
2026-10-27 16:16 | execute | 0004-diagnose-rewrite | review advisory crit=0 high=0 med=2 low=3 — round 15 (delta, the last the human allowed): the SDD edit has no Scope entry; the format row says "made from the Base tip", which is wrong for a handed worktree; 3 low on D-39's quote retarget, its undo line and the two homes of the Scope list; all 5 open
2026-10-27 16:16 | execute | 0004-diagnose-rewrite | parked(review_fail) — round 15 left 5 findings open on D-39 (2 medium, 3 low; scope and correctness); the human allowed no more rounds, so a human must decide; adversary gate not run
2026-10-27 16:19 | autopilot | 0004-diagnose-rewrite | parked — review_fail: round 15 left 5 open on D-39 (each round now reviews the previous round's decision entry); waits on the human
2026-10-27 16:19 | autopilot | — | rebased onto origin/main f9208fc (1.16.1) and force-pushed with lease (human approved); starting 0006-fix-procedure
2026-10-27 16:26 | execute | 0006-fix-procedure | designing — reading the contract, the design record and the fix skill before writing the shared fix procedure
2026-10-27 16:58 | execute | 0006-fix-procedure | decision(D-40) — the ground for the fix seams held by re-reading the lines it cites; a finding the fix cannot show returns blocked; a stale document is named, not a new result; only three results undo the edits
2026-10-27 16:58 | execute | 0006-fix-procedure | developing — the shared fix procedure is written; the fix skill, escape analysis, workflow feedback, the lesson format and AGENTS.md now point at it
2026-10-27 17:15 | execute | 0006-fix-procedure | pushed 554b28a..54c0b4e (1 commits) — the shared fix procedure and the repointed links are on the pull request
2026-10-27 17:15 | execute | 0006-fix-procedure | verifying — plugin-source gates pass, the wiring scan is clean, the declared result heading is in place, and 108 focused tests pass on Windows; the full suites run in the pull request's checks
2026-10-27 17:15 | execute | 0006-fix-procedure | reviewing — round 1, full slice
2026-10-27 17:50 | execute | 0006-fix-procedure | reviewing — round 1: 1 high, 15 medium, 6 low; all 22 fixed in place; decision(D-41) — the last stale pointer to a fix phase and a pointer test join Scope, catalog scenarios pass the paths rule, a flaky check still records its lesson, D-40's ground fact corrected
2026-10-27 18:44 | execute | 0006-fix-procedure | reviewing — round 2 (delta): 6 medium, 7 low; all 13 fixed; decision(D-42) — a catalog scenario outside the caller's paths stops the fix, and only a fix on an unreleased feature records a workflow lesson
2026-10-27 19:22 | execute | 0006-fix-procedure | reviewing — round 3 (delta): 5 medium, 1 low; all 6 fixed; the restart rule now lives in one place for every step; round 4 widens to the whole touched surface because two rounds in a row left a sibling passage stale
2026-10-27 20:20 | execute | 0006-fix-procedure | reviewing — round 4 (scope-escalated delta): 6 medium, 7 low; all 13 fixed; D-43 records the wider hand-over, stale-artifact routing and three corrected lines
2026-10-27 21:20 | execute | 0006-fix-procedure | reviewing — round 5 (scope-escalated delta): 6 medium, 5 low; all 11 fixed; D-44 adds the capture trigger and glossary line to Scope; the forge adapter hit the Windows argument limit, worked around with a scratch copy
2026-10-27 21:39 | autopilot | 0006-fix-procedure | parked — blocked: Claude Code killed the PR-reply job for low memory mid round 5 (f064 resolve, f065 reply, round 5 summary pending); review loop not settled; fixes through 2cfd96b pushed
2026-10-27 21:39 | autopilot | 0009-in-place-callers | parked(waiting on 0006-fix-procedure)
2026-10-27 21:39 | autopilot | run | 5/13 done, starting 0007-ship-script
2026-10-27 21:50 | execute | 0007-ship-script | designing — consumed contracts pass; reading the design record, the forge adapters and the outside-writes helper before writing the ship script
2026-10-27 22:19 | execute | 0007-ship-script | decision(D-45) — the ground for the ship seams held by re-reading the lines INV-025 cites; the ship script's proof comment is marked change-proof so it never collides with the bug mode's proof step
2026-10-27 22:19 | execute | 0007-ship-script | developing — the ship script (open, proof, ready, land) and its tests are written; GitLab change-reviewers now adds a reviewer; SAFETY.md carries the feature-branch sentence
2026-10-27 22:24 | execute | 0007-ship-script | pushed 2cfd96b..e5dff91 (1 commits) — the ship script, its tests, the GitLab reviewer fix and the SAFETY sentence are on the pull request
2026-10-27 22:27 | execute | 0007-ship-script | verifying — plugin-source gates pass, the declared function is in place, 48 ship tests and 117 forge adapter tests pass on Windows; the full suites run in the pull request's checks
2026-10-27 22:32 | execute | 0007-ship-script | reviewing — round 1, full slice
2026-10-27 23:15 | execute | 0007-ship-script | review round 1 — 13 findings (1 high: no test proved the push is never forced), all fixed in place; decision(D-47) records the proof step's inputs, the tracked-job duty on 0008 and the GitLab conformance note
2026-10-27 23:52 | execute | 0007-ship-script | reviewing — round 2, the round-1 fixes
2026-10-28 00:40 | execute | 0007-ship-script | blocked — run ended in review round 2: 7 findings (2 high: base-branch auto not resolved; land lists a push for a branch with no fix commit) not yet posted or fixed; resume at Step 10 round 2 post
2026-10-28 00:08 | autopilot | 0007-ship-script | parked — blocked: run ended in review round 2 with 7 findings unposted (high: the default auto base branch is never refused, so land can push onto main); adversary and wiring checks not run
2026-10-28 00:08 | autopilot | 0008-standalone-fix | parked(waiting on 0004-diagnose-rewrite, 0006-fix-procedure, 0007-ship-script)
2026-10-28 00:08 | autopilot | run | 5/13 done, starting 0013-config-contract
2026-10-28 00:10 | execute | 0013-config-contract | designing — the reader that resolves developer settings is being changed to keep the promises the settings documentation makes
2026-10-28 00:18 | execute | 0013-config-contract | developing — ground re-read instead of re-scripted (the scripted search stops at its hit cap, as D-4 and D-26 record): since INV-026 the reader, the setup script and the H6 probe changed only through 0002 and 0003, and every reader of the five keys still resolves through the one reader; tests first
2026-10-28 00:37 | execute | 0013-config-contract | pushed 98e54f17..e5b86bea (1 commits) — the reader change, its setup and probe counterparts, the documentation and tests are on the branch
2026-10-28 00:37 | execute | 0013-config-contract | verifying — plugin-source gates pass, the declared refusal is in place, 193 focused tests pass on Windows; the full suites run in the pull request's checks
2026-10-28 00:37 | execute | 0013-config-contract | reviewing — round 1, full slice
2026-10-28 00:46 | execute | 0013-config-contract | review advisory crit=0 high=0 med=2 low=6 — round 1: the separate-git-folder promise is wider than the code and untested, a blank misspelled key escapes validate, and five smaller gaps; all posted on the pull request, fixing in place
2026-10-28 00:51 | execute | 0013-config-contract | decision(D-48) — one stale comment line in the worktree script joins this slice so its review finding can be fixed and closed
2026-10-28 01:05 | execute | 0013-config-contract | pushed 51bf4ae — round-1 fixes for all eight findings
2026-10-28 01:32 | execute | 0013-config-contract | review advisory crit=0 high=0 med=0 low=1 — round 2: a separate git folder that is itself named .git still derived a worktree base; fixed in 7b432e5 and pushed
2026-10-28 01:58 | execute | 0013-config-contract | review advisory crit=0 high=0 med=2 low=0 — round 3: CONFIG.md named the wrong mechanism for a linked worktree, and linked worktrees had no test; fixed in f004ed4 and pushed
2026-10-28 02:20 | execute | 0013-config-contract | review advisory crit=0 high=0 med=1 low=2 — round 4: the round-2 guard made one repository's worktrees disagree and its test branched on the case; guard removed, docs say where a .git-named separate folder derives, tests split; fixed in 13b21d8 and pushed
2026-10-28 02:35 | execute | 0013-config-contract | decision(D-49) — a second stale comment line in the worktree script joins this slice so its review finding can be fixed and closed
2026-10-28 02:40 | execute | 0013-config-contract | review advisory crit=0 high=0 med=0 low=2 — round 5: a stale comment in the worktree script and loop-shaped tests; fixed in 1cfdabd and pushed
2026-10-28 02:50 | execute | 0013-config-contract | review clean — round 6: delta sweep, test veracity and scope found nothing; this commit adds the Settles trailers the round 2-5 fix commits lacked

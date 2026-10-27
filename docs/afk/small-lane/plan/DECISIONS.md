# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — which states the diagnosis check script derives
- 2026-10-20 · decided by execute (0001-diagnosis-format)
- Options: the check script derives only the states its file holds, and `/afk:fix` reads Fixed and the grill return vs the script also reading git history, tier results and a grill log
- Chosen: file-borne states only. SDD §8 gives the script one input ("path in → accept or refuse with the missing parts; state"). Fixed is read from commits and tiers, and the grill return from a size-call row whose grammar slice 0004 defines; neither is in the file.
- Supersedes: none (narrows SDD §6 "Read from" to the rows a file can answer)
- To reverse: add those inputs to `check_diagnosis.py` and its format-file state table

## D-2 — which passage D-1 supersedes
- 2026-10-20 · decided by execute (0001-diagnosis-format, review fix)
- Options: D-1 stands with `Supersedes: none` vs record the passages its narrowing overrides
- Chosen: record them. D-1 drops two §6 rows from the check script, so the contract bullet citing that table no longer holds as written; a ledger entry overrides only the passage it quotes.
- Supersedes: 0001-diagnosis-format Acceptance "The check script derives the state from the file per the §6 \"Read from\" table and nothing stores it (design ADR-0002)" and SDD §6 "Read from" rows Fixed and the grill return, for the check script only; `/afk:fix` reads both
- To reverse: as D-1

## D-3 — what the adversary gate probes for a slice with no running app
- 2026-10-20 · decided by execute (0001-diagnosis-format, Step 10.5)
- Options: skip the gate as not applicable vs probe the slice's runtime surface — the check script's command line and the helper's public functions — from the contract and the format file alone
- Chosen: probe the runtime surface. The gate is on by default and only a human may skip it; the slice's promises are observable by running the script and calling the helper, and the format file is the published contract the script reads.
- Supersedes: none
- To reverse: skip Step 10.5 for script-only slices and rerun nothing

## D-4 — how the developer-settings slice reads "the assignee", and where the bug pipeline's own stop rules stay
- 2026-10-20 · decided by execute (0002-developer-settings, Step 4)
- Options: (a) `none` reads as unset for `mrAssignee` and `mrReviewer` only vs for all three person keys, `trackerAssignee` included; (b) move the bug pipeline's per-operation stop table into `CONFIG.md` vs leave it on the bug skill's page until that skill is removed
- Chosen: (a) all three person keys — ADR-0010 names a ticket filed unassigned and a change opened unassigned, so "the assignee" covers both assignees, and a recorded `none` passed to the tracker as a user name can never resolve; (b) leave it — the table describes `/afk:bug`'s own operations, not the keys, and moving it would change that skill's behaviour outside this slice. The key definitions, the resolution order and the general missing-value rule move. The scripted ground check could not run (`seed_map` stops at its 20000-hit class cap on INV-026's declared aliases); every line INV-026 cites for this seam was re-read at the current head and still holds, and every reader of the three keys resolves through `afk-config.py resolve`.
- Supersedes: none
- To reverse: map `none` only for the two forge keys in `developer_value`; move the stop table with the keys

## D-5 — how the tracker slice's ground is re-taken when the scripted check cannot run
- 2026-10-20 · decided by execute (0003-tracker-attach, Step 4)
- Options: run a fresh /afk:investigate over the INV-024 ground vs diff the seam files INV-024 cites against its head
- Chosen: diff the cited files. The 8-root seed map stops at its 20000-hit class cap (22798, grown by this feature's own plan and investigation files), and a per-root split searches other patterns, so ground_diff reports moved for every root without measuring drift. `git diff d346cfb..HEAD` over every file INV-024 cites for this seam (tracker adapters, MCP server, ADAPTERS.md, registry check, gate, publishers, CONFORMANCE.md, .mcp.json, comment gate, the four seam tests, CI) changes only test_plugin_source_gates.py, which gained behavior-registry fixtures from main; its check-E tests shift lines but are unchanged. The ground held.
- Supersedes: none
- To reverse: run /afk:investigate Q3 on the five seam symbols at the current head and re-plan from its ledger

## D-6 — the H6 probe's test file joins the developer-settings slice's scope
- 2026-10-20 · decided by execute (0002-developer-settings, review round 1)
- Options: stop `blocked` for a re-slice vs add `scripts/tests/test_setup_h6_probe.py` to this slice's Scope
- Chosen: add it. `skills/afk/setup/MANIFEST.md` is in Scope and its H6 probe had to change with the `none` rule; that test file runs the probe block verbatim and is the only place its branches can be pinned. A re-slice would move one test file into an identical contract.
- Supersedes: 0002-developer-settings ## Scope, for this one file
- To reverse: revert the test additions in that file; the probe change stays covered only through `developer_values.py status`

## D-7 — the 0002 adversary's contract gaps become a new slice, and the developer-settings anchor names its heading line
- 2026-10-22 · decided by the human (0002-developer-settings, Step 10.5)
- Options: (a) record the high finding as pre-existing, file an issue and finish 0002 vs fix it in this change outside any slice vs add a slice for it; (b) leave the anchor `Developer settings (K1–K5)`, which also matches the pointer in the `developer` row of `CONFIG.md`, vs anchor on the heading line
- Chosen: (a) add slice `0013-config-contract` for adversary findings F1, F2, F4 and F5 — each breaks a promise `CONFIG.md` states, and each behaves the same on main 82c3db8, so none was caused by 0002; 0002 is finished with them routed there, and `0012-sync-harness` waits for 0013. F3, F6 and the low findings stay advisory in the adversary report. (b) anchor on `## Developer settings (K1–K5)` in 0002's Produces and in the Consumes of 0005, 0007, 0011 and 0013, so a removed heading cannot pass on the pointer.
- Supersedes: PLAN.md progress tracker (row 13 added); 0012-sync-harness ## Blocked by; the anchor text in those five contracts
- To reverse: delete 0013 and its tracker row, restore 0012's Blocked by, and restore the bare anchor

## D-8 — the tracker loader's verb count joins the tracker slice's scope
- 2026-10-24 · decided by execute (0003-tracker-attach, Step 8)
- Options: stop `blocked` for a re-slice vs add `scripts/tracker_api.py` to this slice's Scope
- Chosen: add it. Acceptance bullet 1 requires every home that counts the tracker verbs to name ten, and line 4 of that file's docstring says nine; the edit is that one word. `providers/PARITY.md:148`, `providers/CONFORMANCE.md:24` and the 1.x CHANGELOG entry stay: they record what a dated run saw.
- Supersedes: 0003-tracker-attach ## Scope, for this one file
- To reverse: restore "nine" on line 4 of `scripts/tracker_api.py`

## D-9 — how the tracker adapters settle the cases the contract left open
- 2026-10-24 · decided by execute (0003-tracker-attach, Step 5)
- Options: (a) Jira create with an opening state: check the state before create vs after; (b) GitHub write access: probe once per call vs per file; (c) a listed file missing on disk: refuse the call vs attach the rest; (d) the GitHub attachable types: the image and video types the gh docs list vs any file
- Chosen: (a) after create, answered as `status_warning` — Jira lists transitions per issue, so none exist to check before the issue does; `tracker_transition`, the in-review move, checks before its write. (b) one `gh repo view --json viewerPermission`; READ, TRIAGE or NONE marks every file unsupported. (c) refuse the whole call before any write, so a proof comment is never posted half-filled. (d) the image and video types only; every other file is named in the comment.
- Supersedes: none
- To reverse: (a) read the project's workflow statuses before create; (c) attach the files that exist and name the missing ones

## D-10 — how the diagnose slice's ground is re-taken when the scripted check cannot finish
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 4)
- Options: wait on the scripted seed map over INV-022's six roots vs diff the files INV-022 cites for both seams against its head
- Chosen: diff the cited files. The seed map over INV-022's roots and declared aliases (`diagnose`, `grill-requirements`, `grill-solution`, `skills/afk/fix`, `/fix`, `afk-toolkit:fix`) ran 25 minutes without an answer and was stopped; inferred cause: the same hit growth D-4 and D-5 record. `git diff d346cfb..HEAD` over the cited files: the diagnose skill, the fix skill, both grill skills, `GRILL-LOG-FORMAT.md`, `to-sdd/SKILL.md` and `test_skill_frontmatter.py` are unchanged; `BEHAVIORS.md` only gained the `ci-parity-before-push` row, so line 47 still names the "Phase 2.5 — Trace the path" doctrine home; `behavior_registry.py` still refuses a missing doctrine section and a row changed without a revision bump. The ground held.
- Supersedes: none
- To reverse: run /afk:investigate Q3 on the two seam symbols at the current head and re-plan from its ledger

## D-11 — where diagnose works, and how a caller with no person present answers the starting-branch question
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 5)
- Options: (a) diagnose always cuts its own worktree vs an invoker may hand over a worktree it already cut for the bug in owned mode; (b) with no person present and no answer, start from the base branch vs end `blocked`
- Chosen: (a) an invoker may hand one over, and its branch is the Diagnosis branch; otherwise diagnose cuts one with `create-worktree --name <work id, lower-cased> --base <Base>`. SDD §7 has the out-of-slice caller cut the second worktree and then run diagnose in it, and §4 has `/afk:fix` retire the diagnosis worktree, so a caller-cut worktree must be usable. (b) `blocked`, and an invoker may give the answer up front: §3 makes the starting branch a question and lists `blocked` for missing input; a guessed base would put the failing test on the wrong code.
- Supersedes: none (closes a case SDD §3 leaves open)
- To reverse: drop the handed-worktree sentence and the up-front answer from diagnose Phase 0 steps 4 and 5

## D-12 — what "before any tracker or forge call" binds for diagnose, and the size-call bar
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 5)
- Options: (a) read PRD AC-008 as every tracker call, so diagnose writes a file before it reads the ticket, vs every tracker or forge write, with the ticket read as input validation; (b) leave "still small" to the grill's judgement vs give it a bar
- Chosen: (a) every write: SDD §3 makes the input "a ticket key the tracker returns", which needs the read before any file, and §3 also says diagnose writes nothing when its input is missing. Diagnose itself makes no write, and the file is on disk before any writer runs. (b) a bar in the size-call file: still small is one change to existing behaviour that one `/afk:fix` run can make test-first, with no new requirement past the settled answer, no new or changed public contract, no persisted-data change and no decision that needs a design record; anything else is too big. G-1 names the two routes and no test between them.
- Supersedes: none
- To reverse: (a) write the diagnosis skeleton before `tracker_get`; (b) drop the bar and let the grill judge

## D-13 — how `/afk:fix` applies the proposal until its rewrite lands
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 5)
- Options: leave `/afk:fix` delegating the fix to diagnose until slice 0008 vs fix applies the diagnosis's proposal itself now
- Chosen: fix applies it now, the smallest change that keeps every caller working: run diagnose (a light diagnosis when the caller holds the reproduction), read the verdict, and for V-1 bring the diagnosis's failing test into the checkout the bug is fixed in and apply the proposal test-first. A feature-building session fixes in its own worktree, starting diagnose from the branch tip; any other session fixes in the diagnosis worktree. V-2, V-3 and V-4 stop with no code change as `blocked`, V-5 as `cannot_reproduce`, because the fix's status set and its approval step belong to slice 0008.
- Supersedes: none
- To reverse: slice 0008 rewrites the fix skill whole

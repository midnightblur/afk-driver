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

## D-14 — where diagnose and fix work when fix runs inside a worktree it was given, and what fix reads back from a grill
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 10 round 1, findings r-001 to r-006)
- Options: (a) a handed-over worktree only when it was cut for the bug from the Base tip (D-11), with ad-hoc fixes landing in a new diagnosis worktree, vs any linked worktree fix runs in, handed to diagnose with the answer `branch tip`; (b) fix re-runs diagnose for any input, vs fix also takes a `DIAGNOSIS.md` path and acts on a `still small` size-call row now
- Chosen: (a) any linked worktree. Callers run fix inside their own worktree with no person present (an autonomous fixer limited to its worktree, the in-place gates in a feature worktree). A second worktree broke the fixer's write limit, left a worktree behind on every in-place call and blocked on the starting-branch question. In a handed worktree diagnose commits nothing; the invoker owns that branch. (b) take the path now: diagnose offers `/afk:fix <path>` and a still-small grill sends the bug back with that path, so without it both hand-offs dead-end at this commit. A V-2 or V-3 with a `still small` row applies the row's `settled:` answer; the latest row across both grill sections wins.
- Supersedes: D-11 "an invoker may hand over a linked worktree already cut for this bug from the Base tip in owned mode"; D-13 "A feature-building session fixes in its own worktree, starting diagnose from the branch tip; any other session fixes in the diagnosis worktree"
- To reverse: restore D-11's narrower hand-over and drop the path input and size-call routing from fix Phase 1; slice 0008 rewrites the fix skill whole

## D-15 — the ticket read before the diagnosis file
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 10 round 1, finding r-017)
- Options: write a diagnosis skeleton before reading the ticket, vs read the ticket first and write the file before any tracker or forge write
- Chosen: read first. SDD §3 makes the input "a ticket key the tracker returns", and diagnose writes nothing when its input is missing, so the read must come before any file. AC-008 guards recovery of outside writes, and diagnose makes none. This records D-12 (a) against the passage it narrows.
- Supersedes: contract 0004 Acceptance "`DIAGNOSIS.md` is written per the diagnosis format file into the bug's spec folder before any tracker or forge call (PRD AC-008)" — read as "before any tracker or forge write"
- To reverse: write the diagnosis skeleton before `tracker_get`

## D-16 — a stale pointer outside the slice's Scope, and how callers treat fix's `blocked`
- 2026-10-26 · decided by execute (0004-diagnose-rewrite, Step 10 round 1, findings r-005, r-008)
- Options: (a) leave the workflow-feedback pointer at diagnose's removed post-mortem for slice 0006 vs repoint it now; (b) edit the in-place callers to route fix's `blocked` vs leave caller routing to its owning slice
- Chosen: (a) repoint `skills/afk/fix/WORKFLOW-FEEDBACK.md` at the diagnosis's `DIAGNOSIS.md` now, one line outside Scope: this slice removed the post-mortem, and 0006 rewrites the file whole later. (b) leave it to slice 0009, which owns execute, preflight and autopilot's fix points. Fix now restores `design_conflict` for a wrong binding SDD or ADR decision, so execute's existing route still fires. A `blocked` from fix reaches a gate as an unfixed finding, which the settle loop can dispute or park.
- Supersedes: none
- To reverse: (a) revert the one line; (b) slice 0009

## D-17 — a handed worktree's Base and the SDD rows it narrows, the workflow-feedback line in Scope, and D-14's quote
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 2, findings r-004, r-005, r-009)
- Options: (a) a handed worktree's Base is only its tip commit vs its branch and that tip, with SDD §4's diagnosis-branch and diagnosis-worktree rows narrowed for the handed case vs refusing a handed worktree; (b) revert the one workflow-feedback line vs add the file to this slice's Scope; (c) leave D-14's Supersedes quote vs correct it
- Chosen: (a) the handed branch and its tip: the diagnosis format needs a branch and a commit for Base, and the handed branch is where the reproduction starts. That branch belongs to the invoker, so diagnose commits nothing there, fix never pushes or retires it, and fix cuts a worktree onto the Diagnosis branch only when fix runs outside any linked worktree, which a handed case never does. (b) add it: D-16 (a) repointed the line because this slice removed what it pointed at. (c) correct it: D-14 quoted wording D-11 does not contain, so D-11's own passage is superseded here.
- Supersedes: SDD §4 "Diagnosis branch | local git branch from the branch template, made from the Base tip | one per diagnosis | pushed only by `/afk:fix`" and "Diagnosis worktree | a linked worktree off the Base branch, made in the owned mode (name and base given)" — not for a worktree the invoker hands over; contract 0004 "## Scope" list — adds `skills/afk/fix/WORKFLOW-FEEDBACK.md`; D-11 "an invoker may hand over a worktree it already cut for the bug in owned mode" — by D-14 (a)
- To reverse: (a) drop the handed-worktree step from diagnose Phase 0; (b) revert the one line; (c) none needed

## D-18 — a re-run whose worktree is gone, and the handed branch's name rows
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 3)
- Options: (a) find a re-run whose worktree is gone before the starting-branch question, by working out the branch the template makes, vs let `create-worktree` name the existing branch after the question; (b) leave the branch-name rows binding a handed worktree's branch vs narrow them as D-17 narrowed the resource rows
- Chosen: (a) after the question. The filled branch depends on placeholders only `create-worktree` resolves, so diagnose finds a re-run by the owner record or a worktree folder named for the work id, and a gone worktree by `create-worktree`'s refusal. The answer goes unused on a re-run, and step 5 keeps the recorded Base. With no person present and no answer, such a re-run ends `blocked`, as D-11 (b) chose; agent invokers give the answer up front. (b) narrow them: an invoker's branch is not made from the template, and diagnose never names it.
- Supersedes: SDD §4 "| Diagnosis branch | branch name | no | from the branch template, made from the Base tip | — | lower-cased; passes `git.branch-pattern` |" and DIAGNOSIS-FORMAT.md "branch name from the branch template, made from the Base tip" — not for a worktree the invoker hands over
- To reverse: (a) detect the branch before the question in diagnose Phase 0 step 3; (b) drop the handed-worktree step

## D-19 — fix works where the diagnosis is
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 4)
- Options: fix works in the linked worktree it runs in (D-17) and brings the diagnosis's files over, vs fix works in the worktree that holds the diagnosis
- Chosen: where the diagnosis is: the worktree its `DIAGNOSIS.md` lies in, else the worktree on the Diagnosis branch, cut only when that branch holds the diagnosis. When fix hands its own worktree to diagnose, the diagnosis lies there, so D-14 (a) still holds. For a path input, the diagnosis's worktree holds the diagnosed code, the failing test and the file; any other worktree may sit on different code, and copying uncommitted files across sessions has no safe source.
- Supersedes: D-17 "fix cuts a worktree onto the Diagnosis branch only when fix runs outside any linked worktree, which a handed case never does"
- To reverse: fix in the linked worktree it runs in and bring the files over with `git checkout <Diagnosis branch> -- <paths>`

## D-20 — what makes a re-run, and its Base when no diagnosis was written
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 5)
- Options: (a) any worktree folder named for the work id marks a re-run vs only one whose spec folder holds a `DIAGNOSIS.md` for this Work id; (b) a re-run found by its owner record with no `DIAGNOSIS.md` takes the base branch as Base vs the worktree's HEAD commit with the starting-branch answer as the Base branch
- Chosen: (a) only with the diagnosis: a folder name alone can be a person's own worktree, and diagnose would then commit onto a branch it does not own. The owner record still marks a re-run on its own, since only diagnose's `--name` cut writes it. (b) HEAD and the answer: diagnose commits nothing before its end, so HEAD is where the first run started, and the answer names the branch, which the record does not store. A guessed base branch would put the reproduction on the wrong code.
- Supersedes: D-18 "diagnose finds a re-run by the owner record or a worktree folder named for the work id"
- To reverse: drop the `DIAGNOSIS.md` condition and the record-only Base rule from diagnose Phase 0 step 3

## D-21 — what lets fix cut a worktree onto the Diagnosis branch
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 5)
- Options: cut only when the branch holds `DIAGNOSIS.md` (D-19) vs when it holds the failing test, or the diagnosis has none
- Chosen: the failing test. A notes store outside the repository keeps `DIAGNOSIS.md` off every branch, while diagnose commits the failing test on the Diagnosis branch, so the test is the one thing a cut needs. The diagnosis worktree is the listed worktree whose folder holds the `DIAGNOSIS.md` path, so a notes folder that is its own git repository is never taken for it.
- Supersedes: D-19 "else the worktree on the Diagnosis branch, cut only when that branch holds the diagnosis"
- To reverse: gate the cut on `DIAGNOSIS.md` again

## D-22 — a re-run is proved by its diagnosis
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 6)
- Options: mark a re-run by a worktree record, a folder name or an existing branch, giving a Base to one with no diagnosis, vs only by a `DIAGNOSIS.md` for this Work id
- Chosen: only by the diagnosis. The harness writes an owner record for every session worktree, so a record, a folder name and a branch name can each belong to a person's own work, and a re-run there would commit onto a branch diagnose does not own. A worktree or branch with no diagnosis carries no recorded Base either, so guessing one would put the reproduction on the wrong code. A matching worktree with no diagnosis goes on to a fresh cut, and an existing branch with no diagnosis ends `blocked`. Fix picks the diagnosis worktree by the longest listed folder that holds the `DIAGNOSIS.md` path, because linked worktrees can sit inside the main checkout.
- Supersedes: D-20 "The owner record still marks a re-run on its own, since only diagnose's `--name` cut writes it." and "(b) HEAD and the answer"; D-21 "The diagnosis worktree is the listed worktree whose folder holds the `DIAGNOSIS.md` path"
- To reverse: restore record-only re-runs with the HEAD-and-answer Base in diagnose Phase 0 step 3, and the unconditional recut in step 4

## D-23 — a worktree for the work id with no diagnosis
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 7)
- Options: reuse a worktree named for the work id that holds no `DIAGNOSIS.md` vs cut a fresh one vs end `blocked` naming it
- Chosen: end `blocked` naming its path. Diagnose writes the file only at its end, so a stopped run leaves exactly such a worktree, but a session worktree named for the ticket looks the same, and `create-worktree` refuses a fresh cut under a taken name. The person removes it or hands it over, and nothing is committed onto a branch diagnose cannot prove is its own.
- Supersedes: D-22 "A matching worktree with no diagnosis goes on to a fresh cut"
- To reverse: reuse the worktree when its owner record proves diagnose made it

## D-24 — how the person clears a worktree with no diagnosis
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 8)
- Options: name no removal vs name `git worktree remove` vs name `${AFK_PLUGIN_ROOT}/scripts/remove-worktree.py --path <path> --force`
- Chosen: the blocked reason names `remove-worktree.py --path <path> --force`. A plain `git worktree remove` leaves the owner record, which makes `create-worktree --name` refuse the name as taken, and the branch, which ends the next run `blocked` (branch exists). The plugin script drops the worktree, its record, and the branch when that branch holds no commit of its own.
- Supersedes: D-23 "The person removes it or hands it over"
- To reverse: drop the command from the blocked reason in diagnose Phase 0 step 3

## D-25 — clearing a worktree with no diagnosis, with or without a record
- 2026-10-27 · decided by execute (0004-diagnose-rewrite, Step 10 round 9)
- Options: name the plugin script alone vs name what must go plus a command per case
- Chosen: the blocked reason says a retry needs the folder, the owner record and the worktree's branch gone, warns that clearing discards all work on them, and names `afk-python ${AFK_PLUGIN_ROOT}/scripts/remove-worktree.py --path <path> --force` where the record exists, else `git worktree remove --force <path>`, then `git branch -D <branch>` while the branch remains. The plugin script touches only a worktree with an owner record, and with `--force` it skips its own uncommitted-work and other-session checks.
- Supersedes: D-24 "the blocked reason names `remove-worktree.py --path <path> --force`."
- To reverse: restore the single script command in diagnose Phase 0 step 3

## D-26 — how 0005-bug-mode re-takes its ground
- 2026-10-27 · decided by execute (0005-bug-mode, Step 4)
- Options: run the scripted ground check vs re-read the lines the seam investigations cite at the current head
- Chosen: re-read them, as D-4 and D-5 did. The scripted seed map stops at its 20000-hit class cap. The `/afk:to-ticket` files are unchanged since the head INV-024 closed at; the tracker adapters changed only through 0003-tracker-attach (this slice's producer) and `CONFIG.md` only through 0002-developer-settings. The ground holds.
- Supersedes: none
- To reverse: rerun the scripted ground check once the seed map's cap allows it

## D-27 — what the bug and ad-hoc mode decides inside its own script
- 2026-10-27 · decided by execute (0005-bug-mode, Step 4)
- Options: add tracker verbs for type lists, label lists and marker search vs keep a per-kind table in `publish_bug_mode.py` over the existing verbs
- Chosen: a per-kind table (jira, github-issues), because `tracker_search` takes the tracker's own query language, no verb lists issue types or labels, and the adapters are outside this slice's Scope. (a) Jira checks the type and the fix version with a `tracker_search` on the value; a 400 answer refuses. GitHub checks the type label through the adapter's own `gh label list`. (b) The type defaults to bug on a ticket this run creates and is applied only there. The Jira name comes from `jira.issue-types.<type>`, else the capitalised type; the GitHub label is the type itself. (c) The folder moves, and the Work id becomes the key, only for a diagnosis input after a create; a description input keeps its folder and its work id is the folder name. (d) The fix version has no Outside-writes kind, so the step reads the ticket's versions first and adds the new one to them; GitHub refuses `--fix-version`. (e) A refused or 4xx write ends the retries. (f) Consent is declared with `--consent person|prior`; Approval is not checked (design ADR-0008). (g) Proof files upload under `{work id}-{kind}-proof-{file name}` from a temporary folder removed after the run.
- Supersedes: none
- To reverse: add the missing verbs to each tracker adapter and drop the table

## D-28 — two one-line edits outside the bug mode's Scope globs
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 1)
- Options: stop `blocked` for two out-of-Scope lines vs edit them in the remediation commit
- Chosen: edit them. `README.md`'s to-ticket summary still said "meeting + spinoff modes" after the AGENTS.md catalog row this slice changed; a review finding on that line cannot close while it has no inline location, and only an edit gives it one. `.claude/wiring-ious.md` names this slice as the owner of the spinoff wording it fixed, so the IOU line is ticked in the same commit. Both are one-line, reversible text edits that change no behaviour.
- Supersedes: 0005-bug-mode Scope, for `README.md` (the to-ticket summary line) and `.claude/wiring-ious.md` (the jira create IOU line) only
- To reverse: revert those two lines

## D-29 — when the in-review match runs, and what a marker is keyed on
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 1)
- Options: (a) refuse `--in-review` on a run that creates the ticket vs match its transition right after the create; (b) key markers on the diagnosis work id vs on the key of a ticket this mode created
- Chosen: (a) match right after the create and before any other write; no match ends the run with exit 2, and the created ticket stays for a re-run. A ticket that does not exist yet offers no transitions, so SDD §3's "match a transition, else refused with no write" can hold only for an existing ticket. (b) A ticket this mode created keys its markers and proof names on its key from the first run, so a folder move on a later run changes neither; a later different key adds `-{key}` to the step, so its evidence is not mistaken for the first ticket's. A description input's work id is `{folder}-{file stem}`, so two descriptions in one folder file two tickets.
- Supersedes: SDD §3 bug-mode row "the in-review key must be configured and match a transition (name or id), else refused with no write", for a ticket the run creates only
- To reverse: refuse `--in-review` without a key; key markers on the work id

## D-30 — the diagnosis file swap waits out a held file, in one shared helper
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 1)
- Options: retry only in the bug mode's own copy vs make `outside_writes.py`'s swap public, retry there, and drop the copy
- Chosen: the shared helper. On Windows the temporary-file swap fails with "Access is denied" while a scanner holds the diagnosis open; the focused suite failed about one run in five on this. Both `publish_bug_mode.py` and `append_outside_write` swap the same file, so one `replace_text` retries a refused swap up to 20 times, 50 ms apart, then raises. Removing the copy also keeps the file mode, which the copy did not.
- Supersedes: 0005-bug-mode Scope, for `skills/utils/diagnose/scripts/outside_writes.py` (`_replace` renamed `replace_text`, retry added) and `scripts/tests/test_outside_writes.py` (two tests) only
- To reverse: restore `_replace` in both files without the retry

## D-31 — what "already in review" can mean, one spelling per key, a description work id that cannot collide
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 2)
- Options: (a) for an existing ticket with no matching transition, read the changelog to guess whether it reached review vs accept only a state named by the configured value and name the way out; (b) compare keys as typed vs in each tracker's canonical spelling; (c) keep `{folder}-{stem}` vs slugs joined by `_`
- Chosen: (a) the configured value is often a transition id, and no answer from the ticket ties that id to a state name, so "already in that state" holds only for a state of that name; the refusal now says to re-run without `--in-review` when the ticket is already in review. (b) a given key is put in the tracker's spelling (Jira upper case, GitHub the issue number) and, when it names the recorded ticket, takes the recorded spelling, so `#5` and `5` are one ticket. (c) the description work id is `{slug(folder)}_{slug(file stem)}`: a slug holds only `a-z0-9-`, so `_` cannot occur inside either half, a name with a space is filed, and two folders no longer join alike.
- Supersedes: D-29 (b), for the description work id format only; BUG-MODE.md "unless the ticket is already in that state"
- To reverse: revert the `key_of` field, the work id line and the refusal text in `publish_bug_mode.py`

## D-32 — D-30's out-of-Scope edits widened by round 2
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 3)
- Options: revert the round 2 edits to `outside_writes.py` and its tests vs record them
- Chosen: record them. Round 2 found that `replace_text(tries=0)` returned without writing and left its temporary file, and that the retry tests did not pin the pause or the default bound. The fix makes the swap always try at least once and adds a third test, and the two D-30 tests now assert the pauses and the default 20 tries. These edits touch only the helper D-30 already moved out of Scope, and change no caller's behaviour: both callers use the default.
- Supersedes: D-30 "two tests only" and "rename and retry only", for `skills/utils/diagnose/scripts/outside_writes.py` (the at-least-once bound) and `scripts/tests/test_outside_writes.py` (three tests)
- To reverse: drop the `max(tries, 1)` bound and the third test

## D-33 — a description work id carries a hash of its exact names
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 3)
- Options: refuse a folder or file name the slug would change vs add a short hash of the exact names to the slugs
- Chosen: the hash. The id is `{slug(folder)}_{slug(file stem)}-{first 8 hex of sha1 of "folder/file name"}`, so names that slug alike (case, spaces, `_`, `.`, or no ASCII letters at all) still get distinct ids, and no name is refused. A re-run of the same file gets the same id; a renamed file gets a new one. A `--key` that names no ticket once put in the tracker's spelling (`#`) is refused. `run_bug_mode` looks the folder resolver up at call time, so a test can replace it for the command line too.
- Supersedes: D-31 (c)
- To reverse: drop the digest from the work id line in `publish_bug_mode.py`

## D-34 — the description work id hashes the names the file system holds
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 4)
- Options: hash the names as the caller typed them vs hash the names of the resolved path
- Chosen: the resolved path. On a file system that ignores letter case, `Export/DESCRIPTION.md` and `export/description.md` are one file, so they must give one work id; the resolved path carries the stored spelling. A given `--key` that is empty once put in the tracker's spelling is refused, including `""`.
- Supersedes: D-33 "a hash of the exact folder and file name", for which spelling is hashed
- To reverse: hash `source.parent.name` and `source.name` instead of the resolved names in `publish_bug_mode.py`

## D-35 — the description work id hashes the names as their folders list them
- 2026-10-27 · decided by execute (0005-bug-mode, Step 10 round 5)
- Options: rely on the resolved path for the stored spelling vs read each name from its folder listing
- Chosen: the folder listing. A resolved path carries the stored letter case on Windows only; on macOS it keeps the typed case. The folder and file names are now taken from their folders' listings, matched by the same file when the typed name is not listed, so every case-blind file system gives one work id.
- Supersedes: D-34 "the resolved path carries the stored spelling"
- To reverse: hash the resolved path's names again in `publish_bug_mode.py` and drop `_stored_name`

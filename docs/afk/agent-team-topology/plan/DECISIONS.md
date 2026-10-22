# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — Slice although the seam gate refuses 11 rows
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — refuse to slice and bounce to /afk:grill-solution vs B — slice, with the 11 refused rows carried as rows the plan must prove
- Chosen: B — the human's exception "Write SDD, gaps in §13 (Recommended)" (GRILL-LOG.md:711) says each open load-bearing claim becomes a §13 row the plan proves with a live probe or a test subtask, which needs a plan; the gate refuses exactly those 11 rows and nothing else (inferred reading: the exception reaches slicing for these rows only)
- Supersedes: SKILL.md step 2 "exit 1 refuses" — for the 11 excepted rows only
- To reverse: delete plan/ and re-slice after the 11 investigations close

## D-2 — Harness sync delegates to /afk:claude-md
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — /afk:agents-md, as the installed 1.12.0 template says vs B — /afk:claude-md, the steward skill this branch ships
- Chosen: B — this branch is at plugin 1.3.0 and has skills/afk/claude-md and no agents-md skill
- Supersedes: HARNESS-SYNC.md "delegates the write to /afk:agents-md" — for this plan only
- To reverse: rename the skill in 0026-sync-harness once the branch takes the rename from main

## D-3 — Names the SDD left to the executor
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — leave file and symbol names open in the contracts vs B — fix them now so Produces and Consumes anchors can be checked
- Chosen: B — SDD §0 gives the executor latitude on layout, and cross-subtask anchors need one name; picked: package scripts/team/, entry script scripts/afk-team.py, records scripts/team/patterns/BP-1-solo.json to BP-5-afk-lite.json, pattern standard scripts/team/patterns/STANDARD.md, kinds adapters/transport/{subagent,headless,multiplexer,desktop}/, recipes multiplexer/herdr.md and desktop/1devtool.md, wait script hooks/inbox-wait.sh, handlers hooks/pane-rule-notice.sh and hooks/charter-pointer.sh, skill skills/afk/team/, dashboard section mc/sections/team.py, launch-only value AFK_CHARTER_FILE; records stay outside the folders SDD §14 row "Built-in pattern records BP-1 to BP-5 and their charters" forbids
- Supersedes: none
- To reverse: the executor renames through a new D-n here and updates every Produces and Consumes line naming the old name

## D-4 — 26 subtasks, above the aim of 4 to 10
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — bounce to split the PRD vs B — slice along SDD §8 and §14 into 26 subtasks
- Chosen: B — the plan brief requires every §13 check, the charter subtasks, the status-set subtask and the provider fix to be owned, and SDD §8 holds 15 module rows plus 17 changed stage-skill surfaces; splitting the PRD is the human's call
- Supersedes: SKILL.md step 3 "Aim for 4–10 subtasks"
- To reverse: the human splits the PRD and the plan is re-sliced

## D-5 — Seams the plan cannot carry as ## Seams bullets
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — write them as ## Seams bullets and fail the validator vs B — write each as an Acceptance bullet with its §13 checks as Verification rows
- Chosen: B — the 11 excepted §14 rows stand on partial investigations, which the validator's seam-ground check refuses, and 13 SDD §9b rows have no §14 row to name; each still has an owner, its seam test and a seam-register row
- Supersedes: SKILL.md step 3 "Every ## Seams row copies the id of the investigation" — for these rows only
- To reverse: once an investigation closes, move its Acceptance bullet into the owning subtask's ## Seams

## D-6 — Slice on agent-decided rows still owed a human audit
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — park until the human audits SDD §13 Q23, Q28, Q29, Q32 to Q50 and Q53 vs B — slice on the agent-decided answers as they stand, each cited and labelled agent-decided in its contract
- Chosen: B — the hands-off grant of 2026-09-30 (GRILL-LOG.md:707) covers going with the agent's recommendation, and no human-settled or signed row is reversed; the audits stay open and can change a contract before its subtask runs
- Supersedes: SDD §13 rows that say "human (audit of the agent-decided row) before slicing"
- To reverse: the human audits a row; a changed answer edits the owning contract before /afk:execute runs it

## D-7 — Long suite and build runners keep the stall watchdog
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep the existing runner arm of DELEGATION.md:34 vs B — drop the watchdog for runners
- Chosen: A — runners stay helpers (PRD AC-043), and a helper gains no new watchdog duty, so leaving the line as it is is the smaller change (SDD §13 Q32)
- Supersedes: none
- To reverse: edit 0014-delegation-doctrine's Acceptance before it runs

## D-8 — afk-lite reads driven mode from its caller
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — add a new input that tells afk-lite a run is driven vs B — afk-lite reads driven mode from its caller's invocation, as /afk:execute does
- Chosen: B — /afk:execute already decides driven mode from how it was invoked (skills/afk/execute/SKILL.md:26), and no new input is needed (SDD §13 Q37)
- Supersedes: none
- To reverse: edit 0021-fix-afk-lite's Acceptance before it runs

## D-9 — Seven §14 rows the plan validator cannot read
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — edit SDD §14 to cite one investigation per parenthesis vs B — carry those 7 seams as Acceptance bullets naming their closed investigation
- Chosen: B — validate_plan.py reads only `(INV-NNN)` alone in parentheses, while check_sdd_investigations.py reads any `INV-NNN`; the 7 rows group theirs as `(INV-005, INV-001)`, and the SDD is not this skill's to edit; their investigations are closed with frontier, so the ground holds (plugin defect, reported in the slicing report)
- Supersedes: none
- To reverse: once the validator reads grouped citations, move the 7 bullets into ## Seams

## D-10 — Minimal smoke gate rows with no declared tiers
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — drop every row, since the repository declares no verification.tiers vs B — keep compile and regression with the repository's own checks, and drop app-start, e2e and api
- Chosen: B — SMOKE-GATE.md says a plan never ships gate-less, and CLAUDE.md names the checks this plugin runs (hook tests and gates, no build step); the plugin has no app, browser suite or api suite
- Supersedes: SMOKE-GATE.md "A row whose tier the repository does not declare is dropped" — rows 1 and 3 only
- To reverse: declare verification.tiers in .afk/config.yaml and re-seed the gate

## D-11 — Ledgers checked with this branch's coverage validator
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — the installed 1.12.0 coverage validator vs B — this branch's skills/utils/investigate/scripts, through AFK_INVESTIGATE_SCRIPTS
- Chosen: B — the installed validator calls every branch ledger structurally broken over a field the branch format allows (also_found_by); the ledgers were written and closed by the branch's investigate skill
- Supersedes: none
- To reverse: run validate_plan.py without AFK_INVESTIGATE_SCRIPTS once the branch takes the ledger format from main

## D-12 — The review-gate subtask owns check V23
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep V23 in 0017-spawn-steps and block it on 0018-review-gate-pane-workers vs B — move V23 to 0018-review-gate-pane-workers
- Chosen: B — SDD §13 V23 is proven once "the review subtask states the inline run", which 0018 writes; 0018 already edits skills/afk/review/SKILL.md, and B keeps rank order unchanged
- Supersedes: SDD §13 V23's owner, "spawn-step" — the check, not its text
- To reverse: move the V23 Verification row and its Acceptance bullet back to 0017 and add 0018 to 0017's Blocked by, re-ranking 0018 first

## D-13 — Re-slice the plan in place against 1210110
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — slice a new plan with new ids vs B — rewrite contracts 0001 to 0026 in place, keeping each id and rank where its slice still holds
- Chosen: B — the SDD changed after the main merge only in the rows GRILL-LOG.md:744 and :745 name, and no slice changed its intent; every contract's cites, Context excerpts, Acceptance, Seams, Consumes, Produces and Verification now match the SDD at 1210110, with no file added, removed or renamed
- Supersedes: none
- To reverse: restore plan/ from before this re-slice and re-run /afk:to-subtasks

## D-14 — More §14 rows the plan validator cannot read
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — leave these rows without an owner check vs B — carry each as a "Seam (plan D-14)" Acceptance bullet naming its closed investigation, as D-9 does
- Chosen: B — 8 §14 rows cite their ledger as `(INV-059 c-…)` or a grouped form, which validate_plan.py does not read, and a ## Seams bullet naming one fails "names no SDD §14 seam": Step 10 and PF-3 (INV-059), GLOSSARY.md:319 (INV-062), afk-lite (INV-060), S-208's spawn steps and DELEGATION.md's spawn rules (INV-061), progress.py (INV-063) and the status set (INV-064); each investigation is closed, so the ground holds
- Supersedes: none
- To reverse: once the validator reads these citation forms, move the 8 bullets into ## Seams

## D-15 — D-2 is void: harness sync uses /afk:agents-md
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep /afk:claude-md per D-2 vs B — follow HARNESS-SYNC.md and delegate to /afk:agents-md
- Chosen: B — this branch now ships skills/afk/agents-md/ and has no claude-md skill, and CLAUDE.md is a one-line pointer to AGENTS.md; 0026 now edits AGENTS.md and skills/afk/AGENTS.md
- Supersedes: D-2
- To reverse: none needed; D-2's premise no longer holds

## D-16 — D-11 is void: no AFK_INVESTIGATE_SCRIPTS
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep pointing the validator at the branch scripts through AFK_INVESTIGATE_SCRIPTS vs B — run validate_plan.py with no override
- Chosen: B — validate_plan.py:191-196 loads the coverage validator beside itself, and that validator reads also_found_by, so the default path checks every branch ledger
- Supersedes: D-11
- To reverse: set AFK_INVESTIGATE_SCRIPTS again if a later plugin moves the validator

## D-17 — D-1 now covers 5 refused rows
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep D-1's count of 11 vs B — narrow it to the 5 rows the seam gate still refuses
- Chosen: B — check_sdd_investigations.py refuses 5 rows at 1210110, all under the human's exception (GRILL-LOG.md:711): Step 10.5 (INV-035), the report-file writers (INV-036), the lesson id mint (INV-034) and both /afk:bug rows (INV-038); the other 6 rows now cite closed ledgers INV-051 to INV-064, and D-5's excepted Acceptance rows shrink to these 5
- Supersedes: D-1 "the gate refuses exactly those 11 rows" and D-5 "the 11 excepted §14 rows"
- To reverse: none needed; the count follows the gate

## D-18 — D-7 is void: the runner arm of DELEGATION.md:34 is removed
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — keep the runner arm, as D-7 chose vs B — remove it, as SDD §13 Q32 builds S-162
- Chosen: B — SDD §13 Q32 says the design builds S-162 as settled: a runner is a helper, so it gets no watchdog and the runner arm goes; D-7 left the plan contradicting that row; Q32's owner is "human (confirm)", so the confirmation stays open
- Supersedes: D-7
- To reverse: if the human's Q32 confirmation keeps the runner arm, restore it in 0014 and drop its absence check

## D-19 — The short form is a BEHAVIORS.md entry on 0014
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — a subtask of its own vs B — Acceptance bullets and a seam test on 0014, which owns DELEGATION.md
- Chosen: B — GRILL-LOG.md:744 makes the short form one BEHAVIORS.md entry (scope configured-repos, doctrine DELEGATION.md) in the setup-installed block, and its doctrine home is the file 0014 already edits; no SessionStart handler prints it, so hooks/pane-rule-notice.sh and its handler and trust entries are dropped from 0016
- Supersedes: D-3 "handlers hooks/pane-rule-notice.sh and hooks/charter-pointer.sh" — only the first name
- To reverse: move the BEHAVIORS.md bullets and their test row from 0014 into a new subtask

## D-20 — The V6 fix moves to agent-start
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — 0013 keeps the codex.sh marker detection vs B — 0010 sets AFK_PROVIDER for the launched kind and owns V6, V39 and §9b row "Provider marker variables in a pane agent"
- Chosen: B — SDD §13 V6 and V39 name agent-start's AFK_PROVIDER as the fix route, which also covers the protected-branch backstop (GRILL-LOG.md:745 (8)); 0013 drops codex.sh, provider.sh, hook-smoke.sh and the envelope fixtures from its Scope
- Supersedes: none
- To reverse: move the AFK_PROVIDER bullets and the V6 row back to 0013 and restore its codex.sh scope

## D-21 — Owners of V17 and V37 to V41
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — one new probe subtask vs B — each check on the subtask whose change it proves
- Chosen: B — V37 and V39 on 0010 (agent-start), V38 on 0006 (the transport), V40 on each subtask that changes a Stop-path source (0002 adapter_registry_check.py, 0019 stop-gates.sh, 0023 native-contract-gate.sh), V41 on 0018 (PF-3), and V17's answer gets its test row on 0023
- Supersedes: none
- To reverse: move the Verification rows to the subtask a new owner names

## D-22 — The DELEGATION.md:50 carve-out
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — carve out DELEGATION.md:50 as the old 0014 did vs B — add one carve-out sentence over :45, :49 and :50 while :47, :48 and :50 keep their text
- Chosen: B — the §14 spawn-rules row (INV-061) says :50 stands, and the doctrine row names :45, :49 and :50 as the absolute rules; one added sentence meets both rows (inferred reconciliation)
- Supersedes: none
- To reverse: rewrite the 0014 carve-out bullet if an SDD row names another line set

## D-23 — One owner per changed line
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — leave lines that two §14 rows name to both subtasks vs B — give each line one owner
- Chosen: B — two subtasks editing one line would conflict; PROVIDERS.md:23, :126 and :131 go to 0014, investigate/SKILL.md:44 with its tracer arm to 0017, every settle-change line to 0018, execute :90 and :94 to 0019, the bug lines to 0022, and afk-config.py:581-582 to 0002
- Supersedes: none
- To reverse: move the Acceptance bullet to the other subtask that names the line

## D-24 — The C15 register line changes with the team skill
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — 0006 edits all of row C15 vs B — 0006 edits the note fields, and 0015 changes the line 'No skill invokes it'
- Chosen: B — the §14 setup register row says that line changes in the commit of the first skill invoker, and 0006 adds no skill; 0015 adds skills/afk/team
- Supersedes: none
- To reverse: move the MANIFEST.md:596-597 bullet back to 0006

## D-25 — 0016 keeps its id with one handler
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — rename 0016 to a singular slug vs B — keep the id 0016-sessionstart-handlers and change only its title
- Chosen: B — a rename changes the id that 0026's Blocked by and the tracker name, and the slice still holds the SessionStart work; the title now reads "SessionStart: the charter pointer after a compaction"
- Supersedes: none
- To reverse: rename the file and every line that names its id

## D-26 — Owners of the main-checkout and Draft-reuse rules
- 2026-10-07 · decided by /afk:to-subtasks
- Options: A — a new subtask for GRILL-LOG.md:745 (6) and (7) vs B — Acceptance bullets on the subtasks that write the manifest and the briefs
- Chosen: B — the run-directory rule (GL:745 (7)) sits on 0003, which writes the manifest, and on 0015, whose briefs tell agents how to write; the Draft-reuse rule for a subtask agent's rationale-post (GL:745 (6)) sits on 0015; afk-lite's pending operation ids (GL:745 (6)) sit on 0021 with a test
- Supersedes: none
- To reverse: move the bullets to a new subtask

## D-27 — D-18 is void: the runner arm of DELEGATION.md:34 stays
- 2026-10-13 · decided by /afk:to-subtasks
- Options: A — keep D-18 and remove the runner arm vs B — keep the arm, as the human's answer to SDD §13 Q32 says
- Chosen: B — GRILL-LOG.md:746 (human, 2026-10-07): a long suite or build runner keeps the stall watchdog, the one exception to S-162; 0014 keeps the arm, its absence check becomes a presence check, and its excerpts quote the SDD rows that now say so
- Supersedes: D-18
- To reverse: a new human row that removes the arm; then restore D-18's edits in 0014

## D-28 — The short-form entry has scope all-repos
- 2026-10-13 · decided by /afk:to-subtasks
- Options: A — scope configured-repos, as 0014 said vs B — scope all-repos, as the human's row says
- Chosen: B — GRILL-LOG.md:747 (human, 2026-10-13) sets the BEHAVIORS.md short-form entry to all-repos, so AC-047 stands; 0014's Seams, Acceptance, Produces and CHANGELOG bullet say all-repos, and a repository with no .afk/config.yaml gets the short form; the block is 2795 bytes before the entry at 13bec6d
- Supersedes: none
- To reverse: a new human row; then set the scope back in 0014

## D-29 — Re-anchor the plan to main 4b17f1e
- 2026-10-13 · decided by /afk:to-subtasks
- Options: A — re-slice the plan vs B — keep the slices and correct the facts and cites main moved
- Chosen: B — main's #97 moved every plugin gate off Stop to agent commits and CI (hooks/plugin-source-gates.sh:97) and inserted /afk:execute Step 11, so: 0019 drops hooks/stop-gates.sh from its Scope and changes no Stop runner, and leaves V40 to 0002, 0016 and 0023, which still change gate sources; 0016 appends the charter pointer at index 7 after protected-branch-occupancy.py, so the group ends with 8 handlers and H12 gains a sixth hook, SessionStart:0:7; 0021 names the rationale receipt Step 12 (execute/SKILL.md:106); 0024 names the status table Step 14 (execute/SKILL.md:122-131) and the tooltip seed scripts/lavish/tips.json; 0006's V38 checks parallel Step 11 wiring scans, not Stops; 0023 names the gate walks native-contract-gate.sh:98, :536; every Python launch runs as afk-python; every SDD excerpt is re-quoted from the current SDD
- Supersedes: none
- To reverse: revert the delta-2 change to plan/

## D-30 — The park sentences join the status-set change
- 2026-10-13 · decided by /afk:to-subtasks
- Options: A — leave GLOSSARY.md:207 and README.md:57, :456-457 as they are vs B — change them with autopilot step 4
- Chosen: B — INV-072 found that the team-park rule makes these 3 sentences false, since each says a park lets independent work continue; 0024 changes them in the same commit as step 4, and the Park entry also changes the page tooltip
- Supersedes: none
- To reverse: drop the 0024 bullet and the SDD clause; the 3 sentences then contradict step 4

## D-31 — 0001 writes the root glossary directly
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-03)
- Options: A — route the write through /afk:glossary, as SDD §13 Q1's owner cell says vs B — the 0001 executor writes GLOSSARY.md directly as plugin author
- Chosen: B — /afk:glossary stewards domain glossaries only, routes through a GLOSSARY-MAP.md this repository lacks and writes only after approval (skills/utils/glossary/SKILL.md:3-8, :38); FRESHNESS.md:44 names the plugin author as the root GLOSSARY.md steward; the SDD's Q1 owner cell waits for the human
- Supersedes: SDD §13 Q1 owner cell "`/afk:glossary`" — for 0001 only
- To reverse: restore 0001's /afk:glossary bullet once that skill can write the root glossary

## D-32 — agent-stop's entry logic is in the team entry script
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-01)
- Options: A — leave agent-stop's entry checks with no owner, or to cleanup vs B — 0010 builds them in scripts/team/entry.py, and 0012 consumes them
- Chosen: B — SDD §3's agent-stop row (SDD.md:228) gives the verb the entry check, the identity check and the answers 'already gone', 'identity unknown' and 'nothing recorded', and the transport never reads the manifest (ADR-0001); 0012 consumes `def agent_stop(` and is blocked by 0010
- Supersedes: none
- To reverse: move the agent-stop bullets out of 0010 and drop 0012's Consumes line and Blocked-by entry

## D-33 — agent-start appends the pane agent to the owner record
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-02)
- Options: A — call `worktree_owner.py record`, as 0010 said vs B — append the pane agent's process id and creation time to the record's owners list
- Chosen: B — `record` writes a new record with one owner from the caller's own ancestry and drops earlier owners (scripts/worktree_owner.py:211-233); adopt() keeps earlier owners but also reads the caller's ancestry (scripts/remove-worktree.py:410-420); so scripts/worktree_owner.py becomes writable in 0010 for an append that takes the process id and creation time as arguments
- Supersedes: 0010 Scope "read only: agent-start calls its record command"
- To reverse: rely on the SessionStart adopt instead, once a probe shows that a pane agent's harness adopts itself

## D-34 — Owners of the reporting duties and the progress line form
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-04)
- Options: A — leave PRD AC-069 and AC-070 in Context excerpts only vs B — Acceptance bullets on 0005 (built-in role parts and the moderator part) and 0015 (one-off charters the contact agent writes)
- Chosen: B — no Acceptance bullet made a charter's role part name milestones, the report-up and report-down duties or the line `progress: MILESTONE — SENTENCE`; 0005 adds a resolver-test case on each built-in role part, and 0015 a grep of the team skill
- Supersedes: none
- To reverse: drop the 0005 and 0015 bullets and their checks

## D-35 — Order two subtask pairs that change one line
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-06)
- Options: A — give each line one owner vs B — keep both changes and order the subtasks
- Chosen: B — 0017 and 0024 both change autopilot/SKILL.md:39, and 0018 and 0019 both change execute/SKILL.md:143, each for its own §14 row; 0024 is now blocked by 0017 and 0019 by 0018, and the later subtask finds the line by its text
- Supersedes: D-23 "One owner per changed line" — for autopilot/SKILL.md:39 and execute/SKILL.md:143 only
- To reverse: move one subtask's bullet on the line to the other and drop the added Blocked-by entry

## D-36 — Seam-tests for the Step 10.5 row and the doctrine row
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-08)
- Options: A — greps and the V4 and V5 probes only vs B — a live Step 10.5 run on 0019, and 0014's text checks named as the doctrine row's seam-test
- Chosen: B — VALIDATION.md (d) asks for a seam-test that asserts on real output; the Step 10.5 row's output is the verdict read from the report file after finished arrives, and the doctrine row's output is DELEGATION.md's text
- Supersedes: none
- To reverse: drop the 0019 row and the 0014 label

## D-37 — 0008 alone implements "Background job at session end"
- 2026-10-15 · decided by /afk:to-subtasks (plan audit fix A-09)
- Options: A — 0008 and 0012 both implement the row vs B — 0008 implements it and 0012 uses it
- Chosen: B — the seam register names 0008 (PLAN.md:101); 0012's test of the row becomes a cleanup case
- Supersedes: none
- To reverse: mark the row as implemented in 0012's Seams note again and restore its Verification label

## D-38 — The transport kinds' agent-stop takes what the script gives it
- 2026-10-15 · decided by /afk:to-subtasks (plan re-check fix A-13)
- Options: A — each kind's agent-stop takes §3's agent-id vs B — each kind takes the process id, the pane handle and the TR-4 terminal identifier from the script
- Chosen: B — a kind never reads the manifest (0006), so it cannot resolve an agent-id; D-32 puts the entry logic and §3's agent-id contract in the script
- Supersedes: none
- To reverse: drop the 0006 bullet and the 0007 clause, and give the kinds a manifest read

## D-39 — agent-stop also stops a process entry
- 2026-10-15 · decided by /afk:to-subtasks (plan re-check fix A-14)
- Options: A — agent-stop accepts a process entry by its process id vs B — cleanup kills a process entry itself through a shared helper
- Chosen: A — SDD:228 runs the identity check "for an agent entry as for a process entry" inside agent-stop, so one path holds the check; cleanup calls agent-stop for process entries too
- Supersedes: none
- To reverse: limit agent-stop to agent entries and give 0012 the identity check for process entries

## D-40 — The adversary gate's running system is the plugin's command line
- 2026-10-19 · decided by /afk:execute (0001-glossary-terms, Step 10.5)
- Options: A — pass `cli:C:/Users/mvu/PersonalProjects/afk-driver-agent-teams` as the app base URL; the adversary runs the scripts and hooks the contract names in a scratch copy vs B — park the gate as `env_unreachable`, since the plugin has no app, api tier or browser tier
- Chosen: A — the plugin has no app; its scripts and hooks are its running surface, and the invoker named this target for the run
- Supersedes: none
- To reverse: re-run Step 10.5 against a provisioned app instance once one exists

## D-41 — Review round 2 re-reviews the slice's own commits at the moved head
- 2026-10-19 · decided by /afk:execute (0001-glossary-terms, Step 10)
- Options: A — a full lean-roster review of the `[0001-glossary-terms]` commits at head ade8ab1 vs B — a delta round over 52ada6a..ade8ab1, whose only change is the non-slice `.gitattributes` commit
- Chosen: A — no remediation landed in round 1, and the head moved only by a commit outside this slice, so a delta round would review work this slice does not own
- Supersedes: none
- To reverse: run a delta round with `--base 52ada6a` and drop round 2's summary note

## D-42 — Re-take the ground of the three Acceptance-carried seams with one fresh investigation
- 2026-10-19 · decided by /afk:execute (0002-config-transport-and-pattern-keys, Step 4)
- Options: A — no ground diff, since ## Seams holds no row in validator form (D-9) vs B — run the ground diff on INV-001, INV-002 and INV-005, and on drift run one fresh Q3+Q2 investigation (INV-076) at d9e1569 with one tracer then a blind counter-search tracer, in sequence
- Chosen: B — the three Acceptance bullets are §14 seams that name their ledgers; all three ground diffs exit 1 (scripts/afk-config.py, CONFIG.md and the tests changed since 9d9fce6 and 7e9c87a); the run allows one child at a time, so the fan-out runs in sequence
- Supersedes: none
- To reverse: drop INV-076 and cite INV-001, INV-002 and INV-005 again

## D-43 — Literal names and shapes of the new configuration keys
- 2026-10-19 · decided by /afk:execute (0002-config-transport-and-pattern-keys, Step 4)
- Options: A — `transport: <kind>` as a scalar, like `tracker` vs B — `transport` is the transport settings map: `transport.kind` (the kind override, one of subagent, headless, multiplexer, desktop per D-3) and `transport.pane-switch` (pane or subagent); one top-level settings block per kind (`subagent`, `headless`, `multiplexer`, `desktop`, no child keys yet); `stage-map` (stage name to one pattern name or a list); `patterns` (a map keyed by pattern name, fields name, description, charter, schema-version, record-version, roles, edges, steps, includes; role fields model, lifespan, count, report-target, hub, charter)
- Chosen: B — the SDD puts the pane switch "under the transport settings" and the plan's family-row anchor is `transport.kind`; with B no configuration ever sets AFK_CFG_TRANSPORT, so the probe's handed-in kind is never overwritten by a config load (SDD §14 dispatcher row); family_enum reads the `transport.kind` row; kebab-case follows every existing key
- Supersedes: none
- To reverse: rename the keys in scripts/afk-config.py, CONFIG.md and the tests in one commit before any configuration uses them

## D-44 — The reader holds the built-in pattern names until 0005 ships the records
- 2026-10-19 · decided by /afk:execute (0002-config-transport-and-pattern-keys, Step 4)
- Options: A — read the names from records that do not exist yet vs B — one tuple in scripts/afk-config.py: solo, debate, build-verify, review-panel, afk-lite (PRD.md:67-71)
- Chosen: B — AC-062 needs the built-in names now, and 0005, which writes the records and consumes `_validate_saved_patterns`, can switch the reader to the records or pin the tuple to them
- Supersedes: none
- To reverse: read the names from scripts/team/patterns/*.json in 0005 and delete the tuple

## D-45 — The reader checks pattern field names and types; the resolver checks field values
- 2026-10-19 · decided by /afk:execute (0002-config-transport-and-pattern-keys, Step 4)
- Options: A — the reader also checks lifespan values, counts, hub limits, edge and step entries vs B — the reader refuses unknown pattern and role fields, wrong container types, name collisions and names that name no pattern; value checks stay with the resolver
- Chosen: B — the resolver must check a one-off pattern that never passes the reader, so value checks in both would be two homes; SDD:1508 gives presence checks to the resolver
- Supersedes: none
- To reverse: add the value checks to `_validate_saved_patterns`

## D-46 — The issue template shows the collector's transport field
- 2026-10-19 · decided by /afk:autopilot (orchestrator, under the human's standing autonomous grant; resolves the 0002-config-transport-and-pattern-keys needs_decision park on review findings f001 and f003)
- Options: A — widen 0002's Scope to skills/utils/report-issue/ISSUE-TEMPLATE.md and add `transport <transport>` to its Adapters row, plus `transport` in the collector field set that publish-smoke.sh:237 checks vs B — give that row to a later subtask and leave the collector field without a reader until then
- Chosen: A — no other subtask touches ISSUE-TEMPLATE.md, the edit is one table cell, and without it the field collect_env.sh:74 writes reaches no issue
- Supersedes: 0002-config-transport-and-pattern-keys.md ## Scope — the list gains skills/utils/report-issue/ISSUE-TEMPLATE.md and skills/utils/report-issue/scripts/tests/publish-smoke.sh for this run; the contract file is not edited
- To reverse: revert the Adapters-row and need-set edits, and route findings f001 and f003 to the subtask that takes the row

## D-47 — Drop a hostile test host from the INV-076 ledger's quoted evidence
- 2026-10-19 · decided by /afk:execute (0002-config-transport-and-pattern-keys, Step 10 round 2 re-verification)
- Options: A — replace the literal `git.corp.acme.local` in the evidence string of node `B12:scripts/tests/test_report_issue.py:732` of INV-076 COVERAGE.json with `<hostname>` vs B — change skills/utils/report-issue/scripts/redact.py so its plugin inventory skips investigation ledgers
- Chosen: A — redact.py:351-353 counts every dotted token in tracked non-test text as public, so the ledger's verbatim quote made test_a_machine_named_like_a_config_key_still_goes fail; the ledger is already in this slice's diff (review finding f007 withdrawn), the evidence field needs only non-empty text (validate_coverage.py:263, still valid after the edit), and B is outside Scope
- Supersedes: none
- To reverse: restore the quoted host in that evidence string, after redact.py stops reading investigation ledgers

## D-48 — The manifest module's call shape beyond record, move and read
- 2026-10-19 · decided by /afk:execute (0003-manifest-module, Step 4)
- Options: A — only record_entry, move_entry and read_manifest, with adoption and process removal folded into record vs B — the three verbs take the ignored agent directory and the feature as arguments, plus adopt_manifest (create or take over a run: owner session rewritten, generation + 1), remove_process (cleanup's removal of a killed process entry), manifest_path and checkpoint_path; layout <root>/<feature>/manifest.json, lock folder manifest.lock beside it, checkpoints/<role>.json
- Chosen: B — SDD §8 passes dependencies as arguments (S-53), AC-015 needs an explicit takeover, and 0010's Acceptance says cleanup removes a process entry through this module; folding them into record would let any record take over a run or delete a kill-list line
- Supersedes: none
- To reverse: fold the extra functions into record_entry before 0010, 0012 or 0025 consume them

## D-49 — An unknown manifest version is refused on every call and reported once per process
- 2026-10-19 · decided by /afk:execute (0003-manifest-module, Step 4)
- Options: A — persist a marker beside the foreign file so the report happens once across processes vs B — every read and write raises ForeignManifest and leaves the file untouched; the module writes one stderr line the first time a process meets that file and version
- Chosen: B — SDD §4 says "not read, not deleted, reported once" and names no store for the report; a marker file would be a write beside a file the module must not touch
- Supersedes: none
- To reverse: add a marker file next to the manifest and check it before the stderr line

## D-50 — The manifest module's later callers are held by one wiring IOU
- 2026-10-19 · decided by /afk:execute (0003-manifest-module, Step 10 round 1, review findings f005, f006 and f012)
- Options: A — add Consumes lines for adopt_manifest, remove_process and checkpoint_path to the 0010, 0012 and 0015 contracts vs B — one anchored line in .claude/wiring-ious.md naming each public function and the contract row or plan decision whose step will call it
- Chosen: B — the contracts belong to the human and round-trip verbatim, while /afk:execute Step 11 names an anchored IOU in .claude/wiring-ious.md as the answer to a symbol whose consumer comes later
- Supersedes: none
- To reverse: add the Consumes lines to 0010, 0012 and 0015 and close the IOU line

## D-51 — The manifest module's later callers get one wiring IOU each, keyed by function
- 2026-10-19 · decided by /afk:execute (0003-manifest-module, Step 10 round 2, review finding f021)
- Options: A — keep D-50's one line keyed by the file, which the wiring gate closes on its next run because other files already name `manifest` vs B — one line per function, keyed `scripts/team/manifest.py#<function>(`, which the file-name scan never matches, closed by hand when the call lands
- Chosen: B — the gate keys a line by the exact file path and closes it on any file-name hit, so only a function key keeps the three owed callers tracked until /afk:verify-seams final
- Supersedes: D-50 (its one file-keyed line, not its choice of an IOU over contract edits)
- To reverse: put back one file-keyed line, or add Consumes lines to 0010, 0012 and 0015 and close the three lines

## D-52 — The knowledge store module's call shape, layout and entry identity
- 2026-10-19 · decided by /afk:execute (0004-knowledge-store, Step 4)
- Options: A — the three verbs only, each finding the store by itself vs B — write_entry, mark_finished and read_finished take the ignored agent directory and the feature as arguments, plus store_path for the cleanup step that deletes the store; layout <root>/<feature>/knowledge/<YYYYMMDDTHHMMSSZ>-<author>.json, one JSON file per entry with format_version 1; a second entry with the same author and second is refused, and mark_finished takes the author and time that identify the entry
- Chosen: B — SDD §8 passes dependencies as arguments (S-53), SDD §4 makes author and time the entry's identity, and cleanup (0012) deletes the store, so one function owns its path; the file name drops the colons of the ISO time, which Windows refuses in a name
- Supersedes: none
- To reverse: drop store_path and let 0012 build the path, before 0012 consumes it

## D-53 — The read filter takes the reader's stages and each work item's debater roles as arguments
- 2026-10-19 · decided by /afk:execute (0004-knowledge-store, Step 4)
- Options: A — the module learns the stage order and the debater roles itself vs B — read_finished takes the stages the reader may read (its own and the earlier ones, in the caller's order) and a map from work-item id to that item's debater roles; an entry whose work item is in the map is read whatever its stage; a draft is returned only when every listed role has a finished draft for its item, and a draft whose item is not in the map is withheld
- Chosen: B — the knowledge store module depends on nothing (SDD §8), the debater roles live in the resolved pattern, and the rule counts roles, so a role that has written nothing yet must still hold the release back; withholding an unmapped draft keeps AC-007 when a caller forgets the map
- Supersedes: none
- To reverse: have the module read the resolved pattern and the stage map, which adds a dependency SDD §8 does not list

## D-54 — Re-take the ground of both seams with one fresh investigation
- 2026-10-19 · decided by /afk:execute (0005-pattern-resolver-and-builtin-records, Step 4)
- Options: A — build on INV-074 and INV-075 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-077) at b33b6d0 over the union of both ledgers' subjects and name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — both ground diffs exit 1: scripts/afk-config.py, CONFIG.md, GLOSSARY.md, AGENTS.md and .claude/wiring-ious.md changed since 13bec6d; the run allows one child at a time, so the two tracers run in sequence, as D-42 did
- Supersedes: none
- To reverse: drop INV-077 and cite INV-074 and INV-075 again

## D-55 — The resolver's call shape and the record fields the SDD leaves open
- 2026-10-19 · decided by /afk:execute (0005-pattern-resolver-and-builtin-records, Step 4)
- Options: A — the resolver finds the run directory, the fill rule, the transport's abilities and the moderator's model itself vs B — resolve_pattern(root, feature, pick, session, can_fill, abilities, moderator_model, saved) writes `<root>/<feature>/pattern.json` and returns the path, the file's content and each role's charter text; refusals raise PatternRefused, exit code 2 on the command line; record keys are the configuration reader's kebab-case keys; an edge is {from, to, kinds}, a step {name, roles, debate}, where `debate: true` marks a debate step; a role's model is `<tier>@<provider>`; a pattern with roles needs worker-to-contact, exit-signal and limit-signal, plus worker-to-worker when any edge joins 2 roles; an added moderator is the role `moderator`, lifespan Step, on `moderator_model`
- Chosen: B — SDD §8 passes dependencies as arguments (S-53) and I6 takes the abilities from each transport's trial record; the SDD names no debate marker and no model form, and the team entry script (0010) needs the charters, which the resolved file must not carry; one key set serves a saved pattern and a built-in record
- Supersedes: none
- To reverse: change the signature, the field names and the records in one commit before 0010 or 0021 consumes them

## D-56 — Two readings the SDD leaves to the resolver
- 2026-10-19 · decided by /afk:execute (0005-pattern-resolver-and-builtin-records, Step 4)
- Options: A — a pick of 2 or more names keeps each pattern's own step names, and its file names the first pattern vs B — a pick of 2 or more names combines as a pattern with no steps of its own that includes them (SDD §13 Q35 (1)), so every step is named pattern-name/step-name, the file's pattern name joins the names with "+", its record version is empty and its source is "combined", while `sources` keeps each pattern's name, version and source; a one-off pattern may not take a built-in or saved name
- Chosen: B — it follows the Q35 (1) reading to its end, keeps step names unique across the list, and keeps the name and version of each source (S-229); a one-off pattern under a taken name would make an include of that name ambiguous
- Supersedes: SDD §4 resolved pattern "source: one of built-in, saved, one-off" — for a pick of 2 or more names only
- To reverse: give the list's first pattern the top-level fields and drop "combined"

## D-57 — Re-take the ground of both seams with one fresh investigation
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 4)
- Options: A — build on INV-057 and INV-065 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-078) at cedb959 over the union of both ledgers' subjects (MANIFEST, install_block, afk_adapter) and declared name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — both ground diffs exit 1 (the register, the dispatcher's callers and the docs that name them moved since 1210110 and 13bec6d); the run allows one child at a time, so the two tracers run in sequence, as D-42 and D-54 did
- Supersedes: none
- To reverse: drop INV-078 and cite INV-057 and INV-065 again

## D-58 — Kind payloads and one shared launch builder
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — each kind builds its own harness command vs B — one `adapters/transport/launch.py` builds every start command (interactive for panes, no-terminal for headless) with the update-off switch on that launch only, and shared `contract.py` (verbs, budgets, answers, payload checks) and `process.py` (tree list then kill by id); answer fields in snake_case as `scripts/team/manifest.py` names them (pid, handle, started_at, pane_label, agent_name, session_id)
- Chosen: B — the SDD §9b update-check row binds every kind to the same switches, and the script (0010) copies kind answers into manifest fields without a rename; payload field names the SDD leaves open are named in each kind's CONTRACT.md
- Supersedes: none
- To reverse: inline launch.py into each kind and rename the answer fields in the kinds and their CONTRACT.md files

## D-59 — The subagent kind answers every verb unsupported
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — the subagent kind starts a harness child itself vs B — every verb answers exit 3 with a reason naming the harness's own spawn tool
- Chosen: B — a subagent is spawned, messaged and ended by the harness inside the calling session, so no script can perform any of the six verbs (SDD §3 "implements all six verbs or answers unsupported")
- Supersedes: none
- To reverse: give the kind a cli entry that drives a harness child, if a harness exposes one

## D-60 — Headless runs: a job owner process and a log-file read
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — Popen the harness directly vs B — a detached `job.py` owns the run: on Windows it creates a job object with kill-on-job-close, joins it, then starts the agent; elsewhere it leads its own session; it writes a status file (pid, start time, exit code); agent-read reads the log by byte offset with a 1 MiB cap; agent-send and agent-list answer unsupported
- Chosen: B — the contract binds the headless kind to an operating-system job, and a job outlives the caller only when a process of its own holds it; a no-terminal run takes no message after its start and has no pane id
- Supersedes: none
- To reverse: drop job.py and spawn the harness from headless.py

## D-61 — V31 proven by the register's own probe after a stub installer
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — a live `/afk:setup` agent run vs B — a test runs a stub installer that creates part of herdr's layout and exits 1, then runs the C15 Probe line parsed from MANIFEST.md and asserts it still fails, and pins setup step 5's rule that such a fix "is not fixed"
- Chosen: B — setup is agent-run prose with no script of its own, so the deterministic parts are the probe line and the step 5 rule; setup/SKILL.md is outside Scope
- Supersedes: none
- To reverse: replace the test with a recorded live setup run

## D-62 — herdr's removal line and the no-human skip in C15's note
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — leave the uninstall unstated vs B — print one removal line per platform for the layout seen (`Remove-Item -Recurse -Force "$env:USERPROFILE\.herdr"` on Windows, where `.herdr` held only `packages/`; `rm -f "$(command -v herdr)"` elsewhere), say herdr ships no uninstall command and that what the line leaves stays unverified (SDD §13 Q3); with no human, the row stays deselected in setup step 3's election and reports `skipped (user choice)`
- Chosen: B — the contract asks for the tool's one-line uninstall in the note; herdr.dev/docs/install/ names none (checked 2026-10-20), and setup step 6 has no no-human status, so the note reuses its existing label rather than invent one setup cannot report
- Supersedes: none
- To reverse: replace the lines with the vendor's uninstall command once one ships; add a no-human status to setup step 6 and use it here
- Surfaced gap: setup/SKILL.md step 6 has no status for an opt-in row skipped because no human is present (outside Scope)

## D-63 — The empty `transport:` section cannot blank the handed-in kind
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — make validate refuse an empty `transport:` section vs B — the probe's shell loads the configuration first and then sets AFK_CFG_TRANSPORT, drops an inherited AFK_CFG_LOADED so the load always runs, and pins AFK_PLUGIN_ROOT to its own plugin; a test with an empty section, no section and a `transport.kind` section proves the kind survives, and fails when the order is swapped
- Chosen: B — `scripts/afk-config.py` is outside Scope, and the order makes the empty export harmless for every caller that goes through the probe (INV-078: config.sh:31, adapter.sh:29-49); the carried 0002 finding (D-43) is closed for the probe
- Supersedes: D-43's premise that no configuration sets AFK_CFG_TRANSPORT — an empty `transport:` section sets it to '' (INV-078 c-a6fd17be)
- To reverse: move the assignment before the load and add the validate refusal in the config subtask
- Surfaced gap: export-shell still prints `AFK_CFG_TRANSPORT=''` for an empty section, and adapter.sh:41's advice says to set `transport:`, which a scalar value fails validate for (INV-078; files outside Scope)

## D-64 — Detection's fixable setting is herdr's agent integration
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — report herdr fixable only when its server is down vs B — herdr is usable when it is on PATH, this session runs inside a herdr pane, `herdr status` shows running and `herdr integration status` shows each started harness current; a missing integration is the named fixable setting `herdr integration for <harness>` with its fix command; outside a pane is `outside`, a silent server `broken`
- Chosen: B — without the integration herdr reports no agent state and no session id, so starts and resumes cannot work (PRD AC-026, AC-027); the probe offers the fix in its answer and resolves the subagent kind until it is applied
- Supersedes: none
- To reverse: drop the integration check from herdr.detect

## D-65 — The contact inbox and lifecycle copies stay with the team entry script
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — the multiplexer kind writes the contact agent's inbox file and the lifecycle copy vs B — the kind delivers only into panes and states in its detection answer that the contact agent's way is the inbox; the inbox write (temporary name, then rename) and the same-id lifecycle copy belong to the team entry script (0010)
- Chosen: B — SDD §3 row "Delivery to the contact agent", §6 I13 and ADR-0007 name the script as the only writer of message files; the kind has no run directory
- Supersedes: none
- To reverse: give the kind an inbox path in its agent-send payload

## D-66 — Plugin prose drops the transport catalog ids
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — keep the catalog ids (TR, a dash, a number) in CONTRACT.md headings and comments vs B — name the kinds by folder name only in plugin files
- Chosen: B — the ticket shape in hooks/lib/sensitive-patterns.tsv matches those ids, so the genericity gate and the comment gate would block it (INV-078); the plan and SDD keep the ids
- Supersedes: none
- To reverse: add `TR` to the notation prefixes in sensitive-patterns.tsv

## D-67 — FRESHNESS.md and CHANGELOG.md stay untouched by the transport slice
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 5)
- Options: A — add a FRESHNESS.md registry row for adapters/transport/ and scripts/team/probe.py and a CHANGELOG line, outside Scope vs B — keep to Scope: the dependency half of the same-commit rule is met here (MANIFEST.md C15 and the env rows HERDR_*, AFK_CFG_TRANSPORT, DISABLE_AUTOUPDATER), and the registry row and the changelog line are left for a slice that owns those files
- Chosen: B — Scope excludes both files; no developer reaches the transport before the team skill (0015) invokes it, so a changelog line now would announce nothing usable
- Supersedes: none
- To reverse: add the row and the line in this slice's commit
- Surfaced gap: no plan contract names a FRESHNESS.md row for the transport family or the probe; the human adds it to 0015 or 0026

## D-68 — Re-take the ground of both seam roots with one fresh investigation
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 4)
- Options: A — build on INV-058 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-079) at 80b6f50 over INV-058's roots (stall-watchdog, run_in_background) and its declared name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — the ground diff exits 1: hooks/README.md, CAPABILITIES.md, providers/CONFORMANCE.md, AGENTS.md, CHANGELOG.md, hooks/tests/hook-smoke.sh and the gates that read them moved since 1210110; the run allows one child at a time, so the two tracers run in sequence, as D-42, D-54 and D-57 did
- Supersedes: none
- To reverse: drop INV-079 and cite INV-058 again

## D-69 — The wait script's exit codes, file test and argument checks
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 5)
- Options: A — leave exit codes and the file test to the arming step vs B — exit 0 on a file, 3 once park-until passes, 2 on a usage error, each after one `INBOX-WAIT:` line; a file is a regular file directly in the inbox, so a subfolder for handled envelopes never wakes the job; a missing folder, a third argument or a time other than `YYYY-MM-DDTHH:MM:SSZ` (manifest.py:42) is a usage error; park-until is parsed in shell arithmetic, and the last sleep before it is shortened to end on time; the usage, codes and the 10-second check live in the hooks/README.md row and the usage line, since the comment gate caps a new script's header at 2 lines
- Chosen: B — SDD §8 binds the 2 arguments and the 2 exits but names no codes; the watchdog's never-0 rule does not fit a job whose normal end is a message, and exit 3 keeps the two ends apart for the contact agent (SDD §7 sequence: a file → handle the inbox; park-until → move the parked agent back to working)
- Supersedes: none
- To reverse: change the codes in hooks/inbox-wait.sh, its README row and the hook-smoke case

## D-70 — The harness probes run headless, one session at a time
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 8)
- Options: A — write the two probe rows and leave them not run, since this run may open no pane vs B — run both probes now in headless sessions (`claude -p` print mode, `codex exec`), one child session at a time in the foreground, the Codex one with `-s danger-full-access` so the job is visible to the operator's process list; interactive sessions and a subagent contact stay unprobed and are named in providers/CONFORMANCE.md
- Chosen: B — a headless session is a real harness session and needs no pane; it answers the wake (pass on Claude Code 2.1.304; Codex 0.163.0 exec has no later turn) and V25 (pass on both) on today's versions
- Supersedes: none
- To reverse: re-run both probes in interactive pane sessions and replace the rows' results
- Surfaced gap: on Claude Code 2.1.304 a killed headless session's wait job outlived it as an orphan, where SDD §9b row "Background job at session end" records the job's shell killed; the fallback holds either way, since no wake arrives and the next turn recovers

## D-71 — Wiring IOUs for the wait script and its capability row
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 11)
- Options: A — no IOU, since the plan files already name the script vs B — one IOU each for `hooks/inbox-wait.sh#park_until_utc` (consumers: 0010 and 0014 ## Consumes) and `CAPABILITIES.md#background_job_wake` (reader: 0015's AC-065 run-start notice), in `.claude/wiring-ious.md`, outside this slice's Scope
- Chosen: B — no runtime caller exists until 0010 and 0015 land, and the human's rule is that an artifact without a consumer carries an anchored IOU; execute Step 11 names `.claude/wiring-ious.md` as the place for one
- Supersedes: SKILL.md hard rule "Stay inside Scope globs" — for these two IOU lines only
- To reverse: delete the two lines

## D-72 — Which inbox files are writes in flight
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 10, review key 0008-inbox-wait-script/f002)
- Options: A — count every regular file and leave the temporary name to the sender vs B — skip a name starting with `.` or ending in `.tmp`, the two shapes the plugin's write-then-rename helpers use (scripts/team/knowledge.py:144, resolver.py:383 `.{name}.{id}.tmp`; manifest.py:277 `{name}.{pid}.{id}.tmp`)
- Chosen: B — SDD §3 "Delivery to the contact agent" writes the envelope into the inbox under a temporary name, so under A a half-written envelope or a crashed writer's leftover would wake the contact agent
- Supersedes: none
- To reverse: drop the two `! -name` tests in hooks/inbox-wait.sh and the in-flight files in the hook-smoke case
- Surfaced gap: 0010-team-entry-script must name its inbox temporary file in one of these two shapes; its contract does not say so yet

## D-73 — A lost inbox ends the wait with exit 2
- 2026-10-20 · decided by /afk:execute (0008-inbox-wait-script, Step 10, review key 0008-inbox-wait-script/f001)
- Options: A — a new exit code for an inbox that disappears mid-wait vs B — the same exit 2 as a bad folder at start, with its own stderr line, checked only when find saw no message file
- Chosen: B — it is the start-time check repeated, so no new code reaches the README row or the arming step; checking only on an empty scan keeps a file renamed away mid-scan from ending the wait
- Supersedes: D-69 — for the meaning of exit 2 only (usage error, or an inbox folder gone or unreadable)
- To reverse: remove the folder check in the loop, the "is gone" smoke case and the README wording

## D-74 — Re-take the ground of the setup-row seam with one fresh investigation
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 4)
- Options: A — build on INV-068 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-080) at 53d1586 over INV-068's roots (MANIFEST, set_instruction_files) and its declared name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — the ground diff exits 1: the cited ledger ran in another worktree at 13bec6d, and scripts/team/manifest.py, its tests, the plan files and the review files that name MANIFEST were added since; the run allows one child at a time, so the two tracers run in sequence, as D-68 did
- Supersedes: none
- To reverse: drop INV-080 and cite INV-068 again

## D-75 — The spawn rule names the plugin-root variable, so one text survives plugin updates
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 5)
- Options: A — a rule on the installed, versioned path of scripts/afk-team.py, changed at every plugin update vs B — a wildcard before the script, `Bash(afk-python *afk-team.py *)` vs C — `Bash(afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py" *)`, matching the command text the contact agent writes for each verb, `afk-python "${AFK_PLUGIN_ROOT}/scripts/afk-team.py" <verb> '<json>'`
- Chosen: C — a Bash rule matches the command text as written and `*` stands for any text (code.claude.com/docs/en/permissions, "Wildcard patterns", read 2026-10-20); A goes stale at every update; B draws the documented startup warning for a `*` before the subcommand and matches any script named afk-team.py; C settles SDD §13 Q11 for the rule text, and the run check still catches a stale entry
- Supersedes: none
- To reverse: change AFK_SPAWN_ALLOW_RULE and INVOCATION in scripts/team/permission.py together
- Surfaced gap: 0010-team-entry-script and 0015-team-skill-and-manifests must write every entry-script call in exactly the form `permission.INVOCATION <verb> …`, with AFK_PLUGIN_ROOT set in the contact agent's shell; neither contract says so yet. Whether the harness lets a `${…}` reference in an allowed command run without asking is unverified until the live trial in SDD §9b row "Claude Code auto-mode classifier" is repeated with the rule present

## D-76 — The provider adapter owns the rule, the settings files and the lists; the check holds no harness fact
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 5)
- Options: A — scripts/team/permission.py reads the Claude settings files itself vs B — claude.sh answers three functions (afk_claude_spawn_allow_rule, afk_claude_spawn_rule_files, afk_claude_spawn_rule_lists), codex.sh answers afk_codex_spawn_allow_rule with nothing, and permission.py calls them by name in a bash child sourcing hooks/lib/provider.sh, as scripts/team/probe.py does
- Chosen: B — AGENTS.md "Harness-agnostic by default" puts provider behaviour in hooks/lib/providers/<name>.sh, and Scope holds no claude_*.py helper; provider.sh has no dispatcher for these names (INV-080) and is outside Scope, so the check builds `afk_<provider>_spawn_*` itself
- Supersedes: none
- To reverse: move the file list and list keys into permission.py and drop the two Claude functions
- Surfaced gap: the add-harness checklist in providers/CONFORMANCE.md:402-408 does not list the new adapter functions (INV-080); 0010 holds that file in its Scope

## D-77 — What the check accepts and refuses
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 5)
- Options: A — reimplement the harness's wildcard matcher and accept any allow entry that matches all six verb commands vs B — ok only when the constant itself is in an allow list of a readable settings file and in no block list (deny, ask); an allow entry naming afk-team.py in another text is `stale`, none is `missing`, the constant in a block list is `blocked`; unreadable files are skipped; a provider whose adapter prints no rule, and an `unknown` provider, answer ok with a reason
- Chosen: B — ADR-0005 has setup print one exact rule and confirm it, so the constant is what the human adds; exact text keeps the harness's matcher out of the plugin, and a start-only or old-path entry still refuses. `unknown` answers ok because a Codex agent shell detects `unknown` (providers/CONFORMANCE.md:434, INV-080); refusing it would stop every Codex-contact run, which needs no rule
- Supersedes: none
- To reverse: add a wildcard matcher to permission.py and accept matching entries; refuse `unknown`

## D-78 — An IOU carries the spawn rule's command form to the entry script and the team skill
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 1, review key f005)
- Options: A — leave the requirement in D-75's surfaced gap only vs B — one anchored line in `.claude/wiring-ious.md` keyed on `scripts/team/permission.py#INVOCATION`, naming 0010 and 0015 as the callers that must write every entry-script call as `INVOCATION <verb> …` with AFK_PLUGIN_ROOT set
- Chosen: B — the plan contracts are the human's, and the run's IOU file is where an artifact's not-yet-built consumer is tracked (D-71 precedent); without it the check can answer ok while the harness still asks at the first verb
- Supersedes: SKILL.md hard rule "Stay inside Scope globs" — for this one IOU line only
- To reverse: delete the line

## D-79 — A detected harness whose adapter has no spawn functions refuses
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 1, review key f006)
- Options: A — keep D-77: an adapter with no `afk_<provider>_spawn_allow_rule` answers ok vs B — answer ok only when the function exists and prints no rule (as codex.sh does); a detected provider missing it gets a `provider-layer` refusal pointing at PROVIDERS.md "Spawn allow rule"
- Chosen: B — A lets a new harness that asks before shell commands ship without the functions and pass silently; only claude.sh and codex.sh exist and both define the function, so B refuses nothing today; `unknown` still answers ok per D-77
- Supersedes: D-77 — the clause "a provider whose adapter prints no rule … answer ok", for an adapter that lacks the function
- To reverse: exit 0 again when the function is undefined

## D-80 — The setup register's new row gets its changelog line in this slice
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 1, review key f008)
- Options: A — leave it to a later slice vs B — one line under `## [Unreleased]` in CHANGELOG.md now
- Chosen: B — FRESHNESS.md's CHANGELOG row requires the line in the same commit as a dev-visible change, and no later contract that holds CHANGELOG.md names row H15
- Supersedes: SKILL.md hard rule "Stay inside Scope globs" — for this one CHANGELOG line only
- To reverse: delete the line

## D-81 — The check leaves organization-managed settings out and says so
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 1, review key f004)
- Options: A — read the three per-OS `managed-settings.json` paths vs B — read no managed source; PROVIDERS.md states that a managed deny or ask rule, or `allowManagedPermissionRulesOnly`, can still make the harness ask after an ok
- Chosen: B — managed settings come from server-managed settings, an MDM plist or HKLM registry value, `managed-settings.json` plus `managed-settings.d/`, and an HKCU registry value, and the harness selects among them by rank (code.claude.com/docs/en/managed-settings, "How Claude Code combines managed sources", read 2026-10-20); a read of one file would answer for a source the harness may not select, and the live trial owed to providers/CONFORMANCE.md stays the proof
- Supersedes: none
- To reverse: add the managed sources to `afk_claude_spawn_rule_files` with block lists

## D-82 — The add-harness checklist names the spawn functions now
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 2, review key f018)
- Options: A — leave it to 0010, which holds providers/CONFORMANCE.md in its Scope but names no such task vs B — add the three `afk_<name>_spawn_*` functions to step 2 of "Add harness #N" in providers/CONFORMANCE.md now, pointing at PROVIDERS.md "Spawn allow rule"
- Chosen: B — D-79 makes the functions required for any detected harness, so the checklist must name them; no contract or IOU tracks the step, and one added sentence is easy to undo
- Supersedes: SKILL.md hard rule "Stay inside Scope globs" — for this one sentence only; D-76's surfaced gap is closed
- To reverse: delete the sentence

## D-83 — Correct where D-75's rule text lives
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 4, review key f030)
- Options: A — leave D-75's "To reverse" line, which places AFK_SPAWN_ALLOW_RULE in scripts/team/permission.py vs B — record that the rule text is the variable AFK_SPAWN_ALLOW_RULE local to afk_claude_spawn_allow_rule in hooks/lib/providers/claude.sh, and the command form is INVOCATION in scripts/team/permission.py
- Chosen: B — the round 1 fix for f007 moved the rule into the adapter function; the ledger is append-only, so this entry corrects D-75 instead of editing it
- Supersedes: D-75 — its "To reverse" line: change AFK_SPAWN_ALLOW_RULE in afk_claude_spawn_allow_rule (hooks/lib/providers/claude.sh) and INVOCATION in scripts/team/permission.py together
- To reverse: delete this entry

## D-84 — A provider-layer refusal reports needs-human even with no human present
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 5, review key f034)
- Options: A — skip row H15 with no human present in every case, as SDD §14 C19 says vs B — skip it with no human present except on a `provider-layer` refusal, which reports `needs-human: <cause>` whether or not a human is present
- Chosen: B — a `provider-layer` refusal is no missing rule a human can add: its cause (an adapter without the spawn functions, no POSIX shell, a provider layer that did not answer) blocks every team run, and a skip would hide it in the setup summary; the opt-in tier paragraph of skills/afk/setup/MANIFEST.md lets an entry's probe name that status
- Supersedes: SDD §14 row "Setup register `MANIFEST`: the spawn allow-rule offer" (C19) and 0009 Acceptance bullet 1 — the clause "skipped with no human present", for a `provider-layer` refusal only
- To reverse: remove the provider-layer clauses from row H15 and the exception from the opt-in tier paragraph

## D-85 — The check's ok does not cover organization-managed settings
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 5, review key f035)
- Options: A — leave SDD §8 promising that the check confirms the harness will let the contact agent run the script vs B — record that D-81 narrows that promise: an ok means the rule is in a user, project or local allow list and in no block list of those files; a managed deny or ask rule, or `allowManagedPermissionRulesOnly`, can still make the harness ask
- Chosen: B — D-81 left managed settings unread and PROVIDERS.md "Spawn allow rule" states the gap; the ledger must mark the spec passage it narrows
- Supersedes: SDD §8 row "Spawn permission check" and 0009 Acceptance bullet 5 — "confirm the harness will let the contact agent run the team entry script … refuse … when it will not", for organization-managed settings only
- To reverse: read the managed sources (D-81's option A) and drop this entry

## D-86 — A provider-layer refusal carries the rule only when the adapter printed one
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 5, review key f036)
- Options: A — every refusal names the rule vs B — a refusal names the rule the check knows; a `provider-layer` refusal raised before the adapter prints a rule (no POSIX shell, a provider layer that did not answer, an adapter without `afk_<name>_spawn_allow_rule`) carries an empty `rule` and still names `/afk:setup`
- Chosen: B — with no adapter answer there is no rule text to name; inventing one would put a harness fact back in the check (D-76)
- Supersedes: SDD §8 row "Spawn permission check" and §9b row "Claude Code auto-mode classifier" — "naming the rule", for a `provider-layer` refusal raised before the adapter prints a rule
- To reverse: give the check a fallback rule text per provider
- Surfaced gap: 0015-team-skill-and-manifests Acceptance (line 37) says a refusal "names the rule and /afk:setup"; the team skill built from it must name the rule only when the refusal's `rule` is not empty — the human narrows that bullet

## D-87 — D-86 also narrows the contract's and the team skill's "names the rule"
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 6, review keys f040 and f041)
- Options: A — leave D-86 superseding SDD §8 and §9b only vs B — extend it to every plan passage that promises a refusal names the rule
- Chosen: B — the same empty rule on an early `provider-layer` refusal reaches every reader of these passages; one entry keeps the narrowing in one home
- Supersedes: SDD §8 row "Spawn permission check" interface column "a refusal carrying the rule text"; 0009 Goal "refuses naming the rule when it will not", Acceptance bullets 4, 5 and 7 and the Produces line "a refusal naming the rule"; 0015 Acceptance line 37 "names the rule and /afk:setup" — each for a `provider-layer` refusal raised before the adapter prints a rule, which carries an empty `rule` and still names `/afk:setup`
- To reverse: give the check a fallback rule text per provider, then drop D-86 and this entry

## D-88 — D-85 also narrows ADR-0005's "ok, every verb runs under the rule"
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 7, review key f045)
- Options: A — leave D-85 superseding SDD §8 and 0009 Acceptance bullet 5 only vs B — extend it to the design record that promises the same ok
- Chosen: B — the same unread managed settings reach every reader of ADR-0005's sequence; one entry keeps the narrowing in the ledger
- Supersedes: ADR-0005 (`adr/design/0005-human-granted-spawn-rule.md`) sequence line "ok, every verb runs under the rule" — for organization-managed settings only: a managed deny or ask rule, or `allowManagedPermissionRulesOnly`, can still make the harness ask after an ok
- To reverse: read the managed sources (D-81's option A), then drop D-85 and this entry

## D-89 — D-85 reaches every plan copy of SDD §8's "confirm the harness will let"
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 8, review key f049)
- Options: A — extend D-85 one passage at a time vs B — extend it to every plan passage that restates SDD §8's promise
- Chosen: B — the same unread managed settings reach each restatement; one entry closes the set (searched 2026-10-20 for "will let" and "would ask" across the SDD, PRD, ADR-0005 and the 0009, 0010 and 0015 contracts)
- Supersedes: 0009 Goal "the check confirms, through the provider layer, that the harness will let the contact agent run the team entry script for all six transport verbs"; the SDD §8 quotations in 0009 Context excerpts and 0015 Context excerpts — each for organization-managed settings only: an ok means the rule is in an allow list and in no block list of the settings files the adapter names
- To reverse: read the managed sources (D-81's option A), then drop D-85, D-88 and this entry

## D-90 — A block-list entry outranks the rule's presence in ADR-0005's sequence
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 round 9, review key f053)
- Options: A — leave ADR-0005's `alt rule present` → ok and `else missing or stale` branches as written vs B — record that the check refuses with `blocked` when the rule is in a deny or ask list, whatever the allow lists hold
- Chosen: B — deny and ask rules resolve before allow rules (PROVIDERS.md "Spawn allow rule"), so a rule present in an allow list and in a block list still makes the harness ask
- Supersedes: ADR-0005 (`adr/design/0005-human-granted-spawn-rule.md`) sequence branches "alt rule present … ok" and "else missing or stale … refuse" — for a rule that is also in a block list, which answers `blocked`
- To reverse: drop the block-list read (D-77) and this entry

## D-91 — A start whose first turn outlasts herdr's wait counts a working agent as started
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 8 live probe row V38)
- Options: A — pass the whole start budget to `herdr agent start` and refuse on its `timeout` vs B — pass the budget less a 40 s reserve, and on `timeout` read `agent get`: working, idle or done is started, blocked is a dialog, no agent is refused and closed
- Chosen: B — `agent start` waits for idle, so a launch prompt's long first turn failed two live starts and an expired budget left a pane behind
- Supersedes: none
- To reverse: drop `START_RESERVE_S` and `_started` in `adapters/transport/multiplexer/herdr.py`

## D-92 — The Windows tree kill adds MSYS children from Git for Windows' `ps`
- 2026-10-20 · decided by /afk:execute (0006-transport-family-and-herdr, Step 8 live probe row V28)
- Options: A — list the tree from Windows parent ids only vs B — also map each MSYS parent's Windows id to its children's Windows ids from `ps -e`, when Git's `ps` is found
- Chosen: B — a Git Bash child's Windows parent is a gone fork stub, so a live `sleep` outlived agent-stop while it answered `stopped` true
- Supersedes: none
- To reverse: drop `_msys_ps` and `_msys_children` in `adapters/transport/process.py`

## D-93 — Round 11 closes the slice review with a clean summary and no new review pass
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10 resume after the round cap)
- Options: A — run an 11th review pass at ed074e6 before the summary vs B — write the round 11 summary at ed074e6 with `clean=true` and no new pass, after f055 to f061 take `deferred gate=feature`
- Chosen: B — the human decision of 2026-10-20 ("for nitpicking, let them slip") makes the 7 round-cap findings non-actionable; the commits from d824640 to ed074e6 are slice 0006's and change no file in this slice's Scope; the closure gate needs a summary that names the forge head
- Supersedes: SETTLEMENT.md "Termination" stalemate path and execute Step 10 "Stalemate → review_fail" — for this slice's round cap only
- To reverse: reopen f055 to f061 with a new review round on this slice and mark the row blocked(review_fail)

## D-94 — A block-list entry that matches any verb command refuses, by the adapter's own matcher
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10.5 adversary finding F1, high)
- Options: A — keep D-77's exact-text block check, so `Bash`, `Bash(afk-python *)` or a one-verb deny entry answers ok vs B — the Claude Code adapter adds `afk_claude_spawn_rule_blocks`, which matches a block-list entry against the six verb commands (`*` is any text, other characters literal, a trailing `:*` reads as ` *`), and the check refuses `blocked` on the first match, naming the entry and the verb command
- Chosen: B — Acceptance "refuses, naming the rule, when it will not" and SDD §9b "nothing is started"; Claude Code resolves deny, then ask, then allow, and a broad deny blocks every command it matches (Claude Code documentation, "Configure permissions", as quoted in plan/review/0009-spawn-permission-check-adversary.md), so a one-verb deny lets agent-start run and stops a later verb; the allow side stays exact text, so the plugin still holds no matcher that grants
- Supersedes: D-77 "the constant in a block list is `blocked`" — any block-list entry the adapter matches against a verb command is `blocked`; D-90 "when the rule is in a deny or ask list" — the same widening
- To reverse: drop `afk_claude_spawn_rule_blocks`, `_BLOCKS` and `_blocks` in scripts/team/permission.py, and restore the exact-text block check

## D-95 — The r3 adversary verdict stands although the check's own refusal printed part of its bash text
- 2026-10-20 · decided by /afk:execute (0009-spawn-permission-check, Step 10.5 adversary re-run 2)
- Options: A — count the printout as a diet breach and spend the last re-run vs B — keep the `findings` verdict
- Chosen: B — the adversary diet forbids reading the slice diff, tests, review findings and branch commits; this text came from running the check, every scenario was designed before it appeared, and no later scenario used it (plan/review/0009-spawn-permission-check-adversary.md, "Diet disclosure")
- To reverse: re-run the gate in a fresh session without the long block-list probe and treat its verdict as the gate's

## D-96 — Re-take the ground of both seams with one fresh investigation
- 2026-10-21 · decided by /afk:execute (0013-provider-layer-codex, Step 4)
- Options: A — build on INV-067 and INV-013 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-081) at ecf0fd5 over the subjects `Model tiers`, `afk-reader` and `afk-afk-reader` with INV-067's declared name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — both ground diffs exit 1: PROVIDERS.md, providers/CONFORMANCE.md, hooks/native-contract-gate.sh, CHANGELOG.md and the SDD changed since 13bec6d and 7e9c87a; INV-013's other roots (`DELEGATION`, `spawn`, `subagent`) are the spawn doctrine, which this slice does not change; the run allows one child at a time, so the two tracers run in sequence, as D-74 did
- Supersedes: none
- To reverse: drop INV-081 and cite INV-067 and INV-013 again

## D-97 — The equivalence rule follows the in-harness fallback and covers only a provider failure
- 2026-10-21 · decided by /afk:execute (0013-provider-layer-codex, Step 5)
- Options: A — the cross-provider equivalent first, the in-harness fallback after it vs B — the in-harness fallback first, for a model the active harness cannot drive, then the equivalent model from another provider when a provider fails a call
- Chosen: B — a provider failure fails every model that provider serves, so a model in the same harness column cannot replace it, while a model the harness cannot drive is a configuration gap the same column can still close (PROVIDERS.md:138; SDD §8 row "Model equivalence": "Same tier row, another harness column")
- Supersedes: none
- To reverse: reword the appended sentence at PROVIDERS.md:138

## D-98 — A single-model role with no reachable equivalent waits like a debate role
- 2026-10-21 · decided by /afk:execute (0013-provider-layer-codex, Step 10 review round 1, key f003)
- Options: A — leave the case unstated vs B — the sentence says a single-model role waits when no other column names a model for its tier or that model's provider fails too
- Chosen: B — PRD AC-022 limits the switch to "where the tier map supplies one" and AC-023 forbids a reduced shape, so the only path left is the wait that already parks past the provider's limit; without it a role whose substitute also fails would switch back and forth
- Supersedes: none
- To reverse: drop the clause after "a role in a debate pattern waits" at PROVIDERS.md:138 and in the CHANGELOG.md entry

## D-99 — Claude probe panes use launch flags and read-only commands, never a settings change
- 2026-10-21 · decided by /afk:execute (0006-transport-family-and-herdr, Step 8 live probe rows, Claude cells)
- Options: A — answer the permission prompts in the probe panes vs B — pass `--allowedTools`, `--permission-mode default` and `--add-dir` on the probe launch only, and give the main checkout read-only commands
- Chosen: B — the run may not accept a dialog or change a harness setting; the installed guard runs only provably read-only commands in a main checkout, and Claude Code 2.1.305 refuses a foreground `sleep` and an outside script under auto mode
- Supersedes: none
- To reverse: re-run the Claude cells with the other launch, recorded in `providers/CONFORMANCE.md` "Transport kind probes"

## D-100 — The herdr recipe records that a busy Claude pane takes queued messages before its Stop handlers
- 2026-10-21 · decided by /afk:execute (0006-transport-family-and-herdr, Step 8 live probe rows V34 and V35)
- Options: A — keep the recipe's sentence that a busy `claude` pane waits for its turn and Stop handlers vs B — state that `claude` 2.1.305 takes all queued messages when the running tool call ends, in the same turn
- Chosen: B — the V35 re-run showed one Stop mark for the busy turn and its three queued answers; SDD §9b row "Busy pane message order" still holds: a delay, never a reorder
- Supersedes: SDD §9b row "Stop gates in a pane session" — "A message to a busy pane waits for the repository's Stop handlers", for `claude` 2.1.305 and `codex` 0.163.0
- To reverse: restore the delivery-way sentence and the busy-pane trap row in `adapters/transport/multiplexer/herdr.md`

## D-101 — A stop with no process id whose pane close fails answers stopped false
- 2026-10-21 · decided by /afk:execute (0006-transport-family-and-herdr, Step 10 review round 3, key f036)
- Options: A — answer `stopped` true for every failed close, as the settled row words it vs B — keep `stopped` true only when a process id was killed; a stop given only a pane id whose close fails answers `stopped` false with a reason naming the pane
- Chosen: B — with no process id nothing was killed, so the agent still runs in its open pane; the contact agent marks the line unkillable on `stopped` false or `pane_closed` false alike (SDD §11 lifecycle row A7), and the no-tool path already answers the same way
- Supersedes: GRILL-LOG.md S-234 — "When the close fails, 'stopped' stays true", for a stop given no process id
- To reverse: drop the `pid is None and not closed` branch in `adapters/transport/multiplexer/herdr.py` agent_stop and its contract-row clause

## D-102 — agent-stop reaches an orphan through the consoles or sessions its tree uses, and states what it cannot reach
- 2026-10-21 · decided by /afk:execute (0006-transport-family-and-herdr, Step 10.5 adversary finding A-1, review round 11 keys f048, f058)
- Options: A — sweep the consoles (Windows) or sessions (POSIX) that tree members use for processes whose parent ended, answer `stopped` false when the search is incomplete, and state that on Windows a process alone in a console no live member uses is out of reach vs B — also make agent-start put each pane agent in a named job object so every descendant stays traceable
- Chosen: A — B changes agent-start for both harnesses and needs live proof that a job outlives the process that made it; A fixes both adversary repros and every live V28 case, and the stated limit keeps a `stopped` true from being read as complete
- Supersedes: SDD §7 row E2 "Kill an agent's whole process tree", for a Windows descendant alone in a console no live tree member uses
- To reverse: add job-object tracking at agent-start and drop the "Not reached" clause from `adapters/transport/multiplexer/CONTRACT.md` and the herdr.md trap row

## D-103 — Re-take the ground of both seams with one fresh investigation
- 2026-10-22 · decided by /afk:execute (0014-delegation-doctrine, Step 4)
- Options: A — build on INV-055 and INV-069 as cited vs B — one fresh Q1+Q2+Q3 investigation (INV-082) at 83372fd over the subjects `DELEGATION`, `stall-watchdog` and `BEHAVIORS` with the cited ledgers' declared name forms, one tracer then a blind counter-search tracer, in sequence
- Chosen: B — both ground diffs exit 1: AGENTS.md, CAPABILITIES.md, PROVIDERS.md, CHANGELOG.md, hooks/README.md, hook-smoke.sh and the SDD changed since 1210110 and 13bec6d; the run allows one child at a time, so the two tracers run in sequence, as D-96 did
- Supersedes: none
- To reverse: drop INV-082 and cite INV-055 and INV-069 again

## D-104 — The pane-agent probes run as headless top-level sessions and their rows go to the journal
- 2026-10-22 · decided by /afk:execute (0014-delegation-doctrine, Step 8)
- Options: A — run providers/CONFORMANCE.md:439 and :440 in herdr panes and edit those rows vs B — run them as headless top-level sessions (`claude -p`, `codex exec`), the same process kind a pane agent is, and record the result rows in plan/JOURNAL.md
- Chosen: B — this run's resource rule forbids herdr panes, and providers/CONFORMANCE.md is outside this slice's Scope; 0013 ran the :439 Codex probe the same way
- Supersedes: 0014 Verification row "environment-gated on both harnesses with herdr" — the herdr part and "record the result rows" in CONFORMANCE.md only
- To reverse: re-run both probes in herdr panes and record the rows in providers/CONFORMANCE.md under the subtask that owns that file

## D-105 — At the main merge, the pane-agent-rule inventory row survives and the id-set hunk goes
- 2026-10-22 · decided by /afk:execute (0014-delegation-doctrine, Step 10)
- Options: A — keep `"pane-agent-rule"` in EXPECTED_INVENTORY_IDS at the merge vs B — take main's scripts/behavior_registry.py, which no longer has EXPECTED_INVENTORY_IDS (origin/main 82c3db8), and keep the hooks/behavior-dispositions.tsv row `pane-agent-rule` and the BEHAVIORS.md entry beside main's appended `ci-parity-before-push` entry
- Chosen: B — main checks inventory ids against the base revision's dispositions, not that constant (origin/main scripts/behavior_registry.py:390-404), so the TSV row is what keeps the gate green after the merge
- Supersedes: 0014 Acceptance bullet "EXPECTED_INVENTORY_IDS in scripts/behavior_registry.py gains that id", from the main merge on only
- To reverse: none needed before the merge; after it, re-add the id only if main restores the constant

## D-106 — A wiring IOU for the /afk:team pointer in DELEGATION.md
- 2026-10-22 · decided by /afk:execute (0014-delegation-doctrine, Step 10)
- Options: A — no IOU, since 0015's contract already produces skills/afk/team/SKILL.md vs B — one IOU line in `.claude/wiring-ious.md`, outside this slice's Scope, for DELEGATION.md "Stall watchdog" On fire's pointer "follows `/afk:team` for an agent that dies or stops early", anchored to 0015 ## Produces and its Acceptance
- Chosen: B — the pointer names a skill that does not exist until 0015 lands, and the human's rule is that a reference without a reachable consumer carries an anchored IOU; D-71 took the same exception for 0008
- Supersedes: SKILL.md hard rule "Stay inside Scope globs" — for this one IOU line only
- To reverse: delete the line

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

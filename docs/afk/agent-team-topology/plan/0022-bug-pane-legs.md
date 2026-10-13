## Goal
Make the /afk:bug publisher, fixer and retester pane agents (agents in their own terminal panes) that return their result lines through result files, while /afk:bug's rules stay: only the main session writes the bug ledger, and at most one fixer is live. Give the fixer afk-lite's design stop: the fixer returns `BUGFIX: blocked` with the design, the bug moves to blocked (S5), the developer gets a push notification, and the answer resumes the same fixer with its context. Both §14 rows are signed (packet HL6-8); this slice never changes the signed text's meaning. The bug skill, both prompts and the bug ledger format change in one commit. The slice ends at /afk:bug, its prompts, its ledger format and the glossary lines that name its legs; /afk:fix's own team entry is another subtask.

## Complexity
complex

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "/afk:bug publisher, fixer and retester" and "/afk:bug fixer: afk-lite's design stop"
- SDD: SDD.md#§9b External Seams & Failure Affordance — rows "Plugin tracker server in a pane agent" and "herdr harness session id" (use)
- SDD: SDD.md#§13 Open Questions — V8, V9, V10, V21, Q31
- ADR: adr/requirements/0017-bug-agents-keep-their-grants.md — the /afk:bug publisher and fixer keep today's grants as pane agents
- ADR: adr/design/0015-a-change-that-only-adds-keeps-the-contract.md — the design stop row's extends verdict

## Scope
- skills/afk/bug/SKILL.md
- skills/afk/bug/*.md
- FRESHNESS.md
- GLOSSARY.md
- AGENTS.md (:9, :195, :208)
- README.md (:119)
- agents/afk-implementor.md (:18)

## Seams
- (none — both §14 rows this slice changes are excepted (partial INV-038); listed under ## Acceptance)

## Acceptance
- [ ] Excepted seam §14 row "/afk:bug publisher, fixer and retester" (partial INV-038, human exception of 2026-10-02, GRILL-LOG.md:711): before this subtask merges, §13 V8, V9, V10 are proven at build as listed in ## Verification, and the change follows the row's Planned change cell (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] Excepted seam §14 row "/afk:bug fixer: afk-lite's design stop" (partial INV-038, human exception of 2026-10-02, GRILL-LOG.md:711): before this subtask merges, §13 V8, V9, V10, V21 are proven at build as listed in ## Verification, and the change follows the row's Planned change cell (SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The publisher, fixer and retester do role work and become pane agents, started as role spawns at bug/SKILL.md:54, :55, :68, :78, :87, :88; the fixer edits code, so it keeps writing its files under the subagent fallback (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] /afk:bug's rules stay: only the main session writes the bug ledger, each role agent returns its result line through its result file, and at most one fixer is live (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The result-line grammar does not change; only the channel moves from the spawn call's result to a file (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] A pane publisher gets a result-line grammar that names the line carrying the key, which capture step 3 records and backfill and the publish retry read (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] FIXER-PROMPT.md:20 (write only inside the worktree) and RETEST-PROMPT.md:12 (any file write is a failure) gain a carve-out for the result file (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The lines that name the legs as subagents whose return is the channel change: bug/SKILL.md:30, :38-40, :42, :54, :55, :68, :69, :76, :78, :87, :88, :98; LEDGER-FORMAT.md:15, :84; FIXER-PROMPT.md:3, :5; RETEST-PROMPT.md:3; and the text that calls the legs subagents: AGENTS.md:9, :195, :208; README.md:119; GLOSSARY.md:269, :272, :275 (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The one-live-fixer lane, the S1 to S10 moves and publish_bug.py stay unchanged (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The publisher creates 1 bug ticket, moves it once to Dev-Pending and adds evidence comments to that ticket; the fixer commits, pushes, opens 1 Draft change request and marks it ready, only on its own fix branch, and never merges; both grants hold by convention (PRD AC-060)
- [ ] Conforms to requirement ADR-0017 — the grants of /afk:bug do not change, and every other spawned agent stays denied (requirement ADR-0017)
- [ ] agents/afk-implementor.md:18, which makes the final message the return value, gains the pane fixer's result file as its channel (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The retester runs in the dev's checkout with the fix and the publisher in the main session's checkout, as today; bug/SKILL.md:87 and :30 gain the retester's result-file carve-out, as RETEST-PROMPT.md:12 does (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] bug/SKILL.md:29 counts a blocked bug as holding the lane; GLOSSARY.md:278, which names only the fixing (S4) lane, changes to match (inferred, SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The retester writes only its result file; the main session copies the evidence into the bug directory and sets retest.evidencePath (agent-decided, SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] The bug skill, both prompts and LEDGER-FORMAT.md change in one commit, as FRESHNESS.md:76 requires for a change to the result grammars or an edge (SDD §14 row "/afk:bug publisher, fixer and retester")
- [ ] Inside the /afk:bug fixer, a stop after afk-lite's design step moves the bug to blocked, carrying the design, and sends the developer a push notification; the developer's answer resumes the same fixer with its context; the fixer keeps its lane while blocked (PRD AC-063)
- [ ] The fixer is a Turn agent, so its blocked result is its finished; the contact agent stops it and closes its pane, and the S5 ledger state, not a live pane, holds the lane (agent-decided, SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The answer resumes the fixer's harness session in a new pane after the old agent is stopped, and arrives as data; the resume reads the session id from the run manifest and is written as a pane start; when the id is empty or the resume fails, a fresh fixer gets the bundle, the design and the answer in its brief (agent-decided, SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The changed text is the blocked row of the `BUGFIX:` format and the notification line (bug/SKILL.md:108, :117), the fixer prompt (FIXER-PROMPT.md:29 and its result section :43-46, which gain the design stop's path), the meaning of state S5 in the bug ledger format (LEDGER-FORMAT.md:52), GLOSSARY.md, and a resume step the skill lacks today (SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The spawner parses only the result token (FIXER-PROMPT.md:45); the bug states S1 to S10 and their moves do not change, and no ledger entry changes shape (SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] Conforms to ADR-0015 — the design stop row is extends: every existing caller keeps the contract it has today and the change only adds (ADR-0015)
- [ ] The fixer keeps this stop in every run; driven mode's needs_decision route does not apply to it (agent-decided, SDD §13 Q34)
- [ ] The fixer's team starts in the fixer worktree, and the contact agent starts every pane agent, so the team adds no nesting level (agent-decided, SDD §14 row "/afk:bug fixer: afk-lite's design stop")
- [ ] The slice uses the tracker seam as the §9b row states it; the Codex gap for the fixer's /afk:fix Jira intake stays open under §13 Q31 (SDD §13 Q31)
- [ ] The resume follows the §9b session-id seam: an empty session id makes recovery skip the resume and start a fresh agent that reads the checkpoint, and on Codex the resume is typed with herdr pane run (SDD §9b row "herdr harness session id")
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "/afk:bug fixer: afk-lite's design stop")

## Produces
- skills/afk/bug/SKILL.md#design stop resumes the same fixer — the fixer's design stop row and its resume step

## Consumes
- 0020-subagent-fallback-report-writers skills/utils/investigate/SKILL.md#starter writes the file — the fallback rule the fixer's file writes follow
- 0021-fix-afk-lite skills/afk/fix/SKILL.md#afk-lite pattern — the afk-lite team the fixer runs

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'design stop resumes the same fixer' skills/afk/bug/SKILL.md`; `grep -n 'starter writes the file' skills/utils/investigate/SKILL.md`; `grep -n 'afk-lite pattern' skills/afk/fix/SKILL.md` | Produces and consumed anchors present |
| static | `git diff -U0 main -- skills/afk/bug FRESHNESS.md GLOSSARY.md \| grep -E '^\+[^+]' \| grep -e 'mcp__' -e CLAUDECODE -e SendMessage -e subagent_type -e 'Claude Code' -e Codex -e '[^A-Z_]PLUGIN_ROOT'` prints nothing | no provider word added to skill prose |
| static | `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | skill frontmatter still valid |
| unit | `python -m pytest scripts/tests/test_publish_bug.py -q` | publish_bug.py unchanged in behaviour |
| unit | V9: probe providers/CONFORMANCE.md:440 (passed on both harnesses), plus a new plan test (file named by the executor): a fixer that blocks, is cleaned up, then gets the answer resumes its recorded session, or a fresh fixer gets the bundle, the design and the answer when the id is gone or the resume fails | V9 |
| integration | V8, environment-gated on Codex CLI and a session whose permission classifier allows the full-access launch: the full-access probe of V7 runs each shell step of a Codex publisher, fixer and retester pane (publish_bug.py, builds, git, the reproduction) and reads the bundle in the main checkout; recorded as a probe row | V8 |
| integration | Environment-gated on herdr and each harness: start the /afk:bug publisher as a pane agent and list the tools in its turn; Claude Code holds the tracker tools, and a Codex publisher's missing tools are reported as the §13 Q31 gap, never a silent pass; recorded as a probe row in providers/CONFORMANCE.md | seam-test of §9b row "Plugin tracker server in a pane agent" |
| integration | V10, environment-gated on each harness: a new probe row in providers/CONFORMANCE.md in which the session that runs /afk:bug sends a push notification and the developer receives it | V10 |
| integration | V21, environment-gated on both harnesses with herdr: probe providers/CONFORMANCE.md:440 re-run through agent-start's resume path, a blocked fixer pane resumed with its context; on Codex the resume is typed with herdr pane run; recorded as a probe row | V21; seam-test of §9b row "herdr harness session id" |

## Context excerpts
> (SDD §14 row "/afk:bug publisher, fixer and retester", Planned change) The publisher, fixer and retester do role work, so they become pane agents. All 3 are role spawns in the spawn-step list (S-208). The fixer edits code, so it keeps writing its files under the fallback (S-209) (S-165) (signed, HL6-8). Settled in round 46, not part of that signature: the publisher writes the tracker only within today's grant, 1 bug ticket, one move to Dev-Pending and evidence comments on that ticket; the fixer commits, pushes, opens 1 Draft change request and marks it ready, only on its own fix branch, and never merges; both rights hold by convention (S-238). The retester writes only its result file (S-165, D-18); agent-decided: the main session copies the evidence into the bug directory and sets retest.evidencePath, a key the schema has and no step writes today (D-18; INV-038 c-37fbfa59, inference); the fixer is a Turn agent (D-02)

> (SDD §14 row "/afk:bug publisher, fixer and retester", Impacted flows) /afk:bug dispatch, record and retest steps (bug/SKILL.md:55-69, 87-88); FIXER-PROMPT.md and RETEST-PROMPT.md result sections (signed, HL6-8). From INV-038: 19 lines name the legs as subagents whose return is the channel: bug/SKILL.md:30, :38-40, :42, :54, :55, :68, :69, :76, :78, :87, :88, :98; LEDGER-FORMAT.md:15, :84; FIXER-PROMPT.md:3, :5; RETEST-PROMPT.md:3 (c-db08912d, inference). FIXER-PROMPT.md:20, write only inside the worktree, and RETEST-PROMPT.md:12, any file write is a failure, need a carve-out for the result file (c-aa4962c4, c-37fbfa59, inference). Text that calls the legs subagents goes stale: AGENTS.md:9, :195, :208; README.md:119; GLOSSARY.md:269, :272, :275 (c-70816999, inference). Unchanged: the one-live-fixer lane, the S1 to S10 moves (c-e72e71e7, inference) and publish_bug.py (c-593149fc) (INV-038)

> (SDD §14 row "/afk:bug publisher, fixer and retester", Conventions / landmines) /afk:bug's rules stay: only the main session writes the bug ledger, each role agent returns its result line through its result file, and at most one fixer is live (S-165). Compatibility: Result-line grammar unchanged; only the channel moves from the spawn call's result to a file (signed, HL6-8). From INV-038, not signed: the publisher has no result-line grammar, so a pane publisher needs one that names the line carrying the key, which capture step 3 records and backfill and the publish retry read (c-5ce5dfa9; c-fc785d9e, inference). bug/SKILL.md:87 and :30 bar the retester's write too (row Report-file writers). FIXER-PROMPT.md:20 is the pane fixer's whole write fence, held by convention under the team's full-access launch flags (D-31); a Codex stub's sandbox setting fences no pane agent (providers/CONFORMANCE.md:437; c-6c919e83, inference). agents/afk-implementor.md:18 makes the final message the return value, against a pane fixer's result file (c-55cada64, inference). The retester runs in the dev's checkout with the fix, not in the fixer worktree, and the publisher's start directory decides which configuration its tracker reads; S-152 and AC-008 name neither start directory (c-5ccca71d, c-5a61c237, inference). Today both run in the main session's checkout, the only checkout root at publish time, and the retester takes the dev's checkout as its repo path (bug/SKILL.md:87; inferred). The publisher calls no tracker MCP tool, so the Codex tracker gap misses it, but the fixer runs /afk:fix, whose Jira intake may call one (fix/SKILL.md:23; c-0f7baaa7, c-3bdf5d0e, inference; §13 Q31). A Codex contact takes the finished message at its next turn, so the record, the queue promotion and the notifications wait for the developer's next message (S-166; c-f1102ed7, inference). Codex pane legs: §13 V6 to V8; the session id at the answer: V9; push delivery: V10. No test pins a planned break: test_publish_bug.py pins publish_bug.py, and the frontmatter and create-worktree smoke tests pin what the plan keeps (c-593149fc, c-5bae5ba8). FRESHNESS.md:76: a change to the result grammars or an edge touches the bug skill, both prompts and LEDGER-FORMAT.md in one commit. Rollback: The one key that sets role agents back to subagents (S-201); the AGENTS.md and GLOSSARY.md wording stays true only with that key set back (c-70816999, inference). Source: S-165, S-201, S-208, S-209, BUG-1; signed in round 41 (packet HL6-8); S-238 (round 46, added after the R-45 signature); D-02, D-18 (agent-decided); D-31 restates C5 and S-136 (AC-060, ADR-0016); INV-038.

> (SDD §14 row "/afk:bug fixer: afk-lite's design stop", Planned change) The fixer returns 'BUGFIX: blocked' with the design for your review. The bug moves to blocked (S5), you get a push notification, and your answer resumes the same fixer with its context (blocked to fixing). The fixer keeps its lane (the one slot for a live fixer) while blocked (S-164) (signed, HL6-8). Not signed: the fixer is a Turn agent, so its blocked result is its finished; the contact stops it and closes its pane, and the S5 ledger state, not a live pane, holds the lane (D-02, agent-decided; S-192). The answer resumes the fixer's harness session in a new pane after the old agent is stopped (S-213, S-242) and arrives as data (S-150); the resume reads the session id from the run manifest, since state.json has no such key, and is written as a pane start (INV-038 c-be71894c, inference). When the id is empty or the resume fails, a fresh fixer gets the bundle, the design and the answer in its brief (D-02, agent-decided; S-219). The fixer keeps this stop in every run; driven mode's needs_decision route does not apply to it (agent-decided, Q34)

> (SDD §14 row "/afk:bug fixer: afk-lite's design stop", Impacted flows) In the /afk:bug skill: the blocked row of the BUGFIX: format and the notification line. The fixer prompt. The meaning of state S5 (blocked) in the bug ledger format. GLOSSARY.md (S-202) (signed, HL6-8). From INV-038: bug/SKILL.md:108 and :117 and LEDGER-FORMAT.md:52 (c-e72e71e7, inference); FIXER-PROMPT.md:29 and its result section :43-46, which gain the design stop's path (c-7f8cad70, inference); a resume step the skill lacks today (c-73e5c753, c-be71894c) (INV-038)

> (SDD §14 row "/afk:bug fixer: afk-lite's design stop", Conventions / landmines) The spawner parses only the result token (FIXER-PROMPT.md:45) (signed, HL6-8). Compatibility: The bug states S1 to S10 and their moves do not change: the cause uses the same S5 state, lane and notification. No ledger entry changes shape, and nothing needs migration (S-202) (signed, HL6-8). From INV-038, not signed: the moves and the lane hold (c-e72e71e7, inference), and no ledger entry changes shape only while the session id lives in the run manifest (c-be71894c, inference). The design cannot ride the result line: the summary is one plain clause and the session parses only the trailing line, so the design sits in a file the summary names, or the parse rule widens for blocked (c-7f8cad70, inference). The resume held on both harnesses (providers/CONFORMANCE.md:440); on Codex only a resume typed with herdr pane run worked, and herdr agent start with resume left no pane (c-72834296). Whether the session id still exists at the answer is unproven: it may be empty, a Codex id at start is a trial still owed, and cleanup deletes the manifest (c-4e801d33; §13 V9). No file names how a push notification reaches the developer; REPORTING.md:28 owns its content only (c-0bb7298f; §13 V10). A Codex contact takes the finished message at its next turn, so the S5 notification waits for the developer's next message (S-166; c-f1102ed7, inference). Codex pane fixer: §13 V6 to V8. S-202's 4-file list omits RETEST-PROMPT.md, which FRESHNESS.md:76 adds to the commit if the blocked row counts as a result-grammar change (c-36836ea6, inference). The fixer's team starts in the fixer worktree (D-27) under the team's full-access launch flags, its fence held by convention (D-31), and the contact starts every pane agent, so the team adds no nesting level (D-25). Rollback: Revert the commit that adds the cause; it touches 4 files. A bug in S5 for this cause at rollback time resumes through the unchanged move from S5 to S4 (fixing), on the developer's answer. The fixer's use of afk-lite rolls back with the /afk:fix team entry (S-202) (signed, HL6-8). The move exists (c-e72e71e7), but no step runs it today (c-73e5c753). Source: S-164, S-202, STOP-1, BRB-1; signed in round 41 (packet HL6-8); S-150, S-166, S-192, S-213, S-219, S-242 (added after the R-45 signature); D-02, D-25 (agent-decided); D-27 restates AC-008 and S-152, and D-31 restates C5 and S-136; INV-038.

> (SDD §9b row "Plugin tracker server in a pane agent") Claude: the pane agent held the tracker tools. Codex: the server is registered and connected, but its tools are absent from the agent's turn | A Codex pane agent that needs the tracker, such as the /afk:bug publisher, fails (§13) | The probe's Codex cell after a fix |

> (SDD §9b row "herdr harness session id") herdr 0.9.1, observed 2026-09-29 for a Claude pane | Records a Claude pane agent's session id, read back from the pane's details. Not verified: that it records a Codex session the same way; that a resume from the id works after a kill in the middle of a turn. On Codex, herdr agent start with --kind codex -- resume left no pane, and only the same command typed with herdr pane run worked (providers/CONFORMANCE.md:440), so agent-start's resume path takes that form there (§13 Q21, V21) | Empty session id → recovery skips the resume and starts a fresh agent that reads the checkpoint (S-219) | Probe 2026-09-30 (providers/CONFORMANCE.md:440): a blocked pane agent took a relayed answer, and a session resumed in a new pane kept its context, on both harnesses. Still owed before the design binds (S-213): Codex session id at start, resume after a mid-turn kill (§13 Q21)

> (SDD §13 Q31) Q31: A Codex pane agent gets no tracker tools in its turn, though the server is registered and connected (providers/CONFORMANCE.md:433). The /afk:bug publisher and the Jira intake of /afk:fix fail in a Codex pane agent. No settled row routes tracker work away from a Codex pane agent

> (SDD §13 V8) V8: Whether a Codex CLI publisher, fixer or retester pane can run its shell steps (publish_bug.py, builds, git, the reproduction) or read the bundle in the main checkout. … Proven at build by: the full-access probe of V7, running each shell step

> (SDD §13 V9) V9: Whether the fixer's harness session id still exists when the developer answers. The manifest may hold it empty (S-233), a Codex session id at start is a trial still owed (Q21), cleanup deletes the manifest (S-198), and no file says when a /afk:bug fixer run's cleanup runs relative to its S5 wait. INV-038 c-4e801d33; the three §14 rows /afk:fix team entry, /afk:bug publisher, fixer and retester, and afk-lite's design stop. Proven at build by: the probe 'A blocked pane agent stays live and takes a relayed answer; a resumed session keeps its context' (providers/CONFORMANCE.md:440, passed on both harnesses), and a test the plan carries: a fixer that blocks, is cleaned up, then gets the answer resumes its recorded session, or a fresh fixer gets the bundle, the design and the answer when the id is gone or the resume fails (D-02, agent-decided)

> (SDD §13 V10) V10: How a push notification reaches the developer. No repository file names the delivery; REPORTING.md:28 owns only its content (subject, status, plain-terms sentence). … Proven at build by: a new probe row in which the session that runs /afk:bug sends a push notification on each harness and the developer receives it (INV-031, INV-038 at skills/afk/bug/SKILL.md:115)

> (SDD §13 V21) V21: Whether a blocked fixer pane agent stays live to be resumed with its context; S-165 does not state the fixer's lifespan. D-02 (agent-decided): the fixer is a Turn agent, its blocked result is its finished, the S5 ledger state holds the lane, and the answer resumes its harness session in a new pane. … Proven at build by: probe :328 (passed on both harnesses), re-run through agent-start's resume path; on Codex the resume is typed with herdr pane run (:328)

> (PRD AC-060) The `/afk:bug` publisher and fixer keep today's grants as pane agents (ADR-0017). The publisher creates 1 bug ticket, moves it once to Dev-Pending, and adds evidence comments to that ticket. The fixer commits, pushes, opens 1 Draft change request and marks it ready, only on its own fix branch. The fixer never merges. Both grants hold by convention (ADR-0016).

> (PRD AC-063) Inside the `/afk:bug` fixer, a stop after afk-lite's design step moves the bug to blocked, carrying the design, and sends the developer a push notification. The developer's answer resumes the same fixer with its context. The fixer keeps its lane (the one slot for a live fixer) while blocked.

> (requirement ADR-0017) As pane agents, the `/afk:bug` publisher and fixer keep the rights they have today, as 2 stated exceptions to the spawned-agent rules. … The grants of `/afk:bug` do not change, and every other spawned agent stays denied.

> (FRESHNESS.md:76) | `skills/afk/bug/SKILL.md` + `FIXER-PROMPT.md` + `RETEST-PROMPT.md` | `/afk:bug` | the subcommand set, the `BUGFIX:`/`RETEST:` result grammars, or the S1-S10 ledger machine's allowed edges change — update both prompt siblings + `LEDGER-FORMAT.md` in the same commit |

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
0020-subagent-fallback-report-writers, 0021-fix-afk-lite

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

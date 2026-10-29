# Grill log — afkv2 (GitHub issue #153)

Checkpoint of interactive grill sessions. Working state, updated as decisions lock;
superseded when the synthesized artifacts (PRD / SDD / plan) land.

## Requirements grill

- Ledger: `claude plugin eval` exists in Claude Code 2.1.312 → verified (probe 2026-10-29, `claude plugin eval --help`)
- Ledger: `codex exec --json` and `codex exec -p <profile>` exist in codex-cli 0.164.0 → verified (probe 2026-10-29, `codex exec --help`)
- Ledger: plugin name `afkv2` passes Claude manifest validation → verified (probe 2026-10-29, `claude plugin validate`)
- Ledger: Claude enables plugins per project (`enabledPlugins`) → verified (PROVIDERS.md:11,20)
- Ledger: Codex enables plugins in the global config; a profile can turn a plugin off for one session → refuted for the config flag (probe 2026-10-29: `codex plugin list -c 'plugins."<id>".enabled=false'` still listed it enabled); per-session switch unverified-external → H-2 global switch
- Ledger: Claude plugin hooks run only while the plugin is enabled → verified (Claude docs, plugin hooks 'When plugin is enabled'); Codex stop-on-disable + re-injection after compaction on both → unverified-external, owner acknowledged W-5 2026-10-29; probed in the seam design pass (H-4)
- Ledger: v1 forge contract covers GitHub + GitLab with JSON answers → verified (adapters/forge/github/CONTRACT.md:6-19)
- Ledger: v1 has GitHub-issue read code → verified (adapters/tracker/github-issues/api.py, 388 lines)
- Ledger: v1 release gate checks version agreement across manifests, marketplace, changelog, tag → verified (hooks/release-gate.sh, 106 lines)
- Ledger: v1 review settle cap is 10, hard-coded → verified (skills/afk/review/SETTLEMENT.md)
- Ledger: v1 lavish kit is Python + JS + CSS, no bash, about 3.5k lines → verified (wc -l scripts/lavish_render.py scripts/lavish_show.py scripts/lavish/)
- Staples: none — no STAPLES.md in the repository; no new-staple candidate
- Settled: decisions 1-98 of issue #153 are binding input; not reopened
- Settled: Jira read goes into subtask 09 as a read-only tracker port using acli · decided-by agent R-1 · accepted 2026-10-29 · spec: #153 P0 lists Jira read, no subtask held it; decision 40 makes acli the Jira tool · reverse: move the read verbs to their own subtask
- Settled: GitHub-issue read is in the beta, same tracker port (S-2, accepted)
- Settled: release gate port goes into subtask 01, rewritten in Python · decided-by agent R-1 · accepted 2026-10-29 · spec: decision 74 no bash; v1 release-gate.sh is the only version-agreement check · reverse: delete the script and its CI step
- Settled: redaction port moves to 2.1 with report-issue (S-4, accepted)
- Settled: beta ships the medium lane only; lane-choice rule is 2.1 · decided-by agent R-1 · accepted 2026-10-29 · spec: #153 map week-1 target medium lane only · reverse: grill the lane rule and add a lane step
- Settled: evals are not for AFK skills for now; they prove contextual instructions and information (core behaviors, a repo's AGENTS.md and nested AGENTS.md) (S-6 write-in, human)
- Settled: one shared eval case set runs on Claude and Codex, for contextual instructions (S-7 accepted with the S-6 note)
- Settled: chain smoke run uses a toy repository and a written test ticket (S-8, accepted)
- Settled: chain smoke passes when one ticket reaches a Draft change with green local tests on Claude and Codex, human answering the grill and approving the plan (S-9, accepted)
- Settled: v2 takes over the user instruction files; v2 setup removes the v1 block (C-1 write-in, human)
- Settled: v2 uses its own names: plugin afkv2, config folder .afkv2, env prefix AFKV2_, own plugin data folder · decided-by agent R-1 · accepted 2026-10-29 · spec: #153 map W1 gap "never collide with v1"; `claude plugin validate` accepts afkv2 · reverse: rename in setup and config reader
- Settled: v2 setup offers a one-time copy of v1 config values; never changes the v1 file (C-3, accepted)
- Settled: one of v1 or v2 on per session (Claude per-project enabledPlugins, Codex profile) (C-4 accepted; owner question on plugin-scoped hooks open)
- Settled: v2 does not run v1 plans; a v1 feature finishes on v1 or is sliced again with v2 (C-5, accepted)
- Settled: K-1 setup, K-2 core behaviors text ≤ 200 lines, K-3 grill input/reading/rounds (presentation part reopened by the R-1 page-level steer), K-8 to-subtasks, K-9 autopilot, K-10 code-review, K-11 create-change-request, K-12 CI watch, K-15 forge port · decided-by agent R-1 · accepted 2026-10-29 · spec: decisions cited on each card (40, 3, 18, 62, 63, 21, 22, 26, 68, 23, 45, 25, 46, 31, 28, 20, 74) · reverse: per card
- Settled: K-7 critical-aspect list (entities, relations, keys, constraints, cascade, then API contract + compatibility, data migration, authorization, entity life cycle, other teams' modules, large data) (accepted)
- Settled: K-13 agent marks the change Ready at ship (review settled, CI green); human merges (accepted)
- Settled: K-14 gc keeps the run branch, deletes worktree + local and remote feature branches (accepted)
- Settled: A-1 four actors; A-2 agent allowed/denied actions; A-3 ownership-graded scope · decided-by agent R-1 · accepted 2026-10-29 · spec: #153 Expected, decision 31, interim rules, decisions 32, 57 · reverse: per card
- Settled: A-4 ownership from repo config, CODEOWNERS as suggestion, unlisted = not owned (accepted)
- Settled: A-5 plan check must pass and division approved before autopilot · decided-by agent R-1 · accepted 2026-10-29 · spec: decision 26; v1 validate_plan checks (a)(b) · reverse: make the check a warning
- Settled: terms T-1, T-4..T-18 accepted as drafted; T-2 renamed "core behaviors", T-3 renamed "interim behaviors"; T-19 void (v1 artifact names kept); glossary home afkv2/GLOSSARY.md (T-0)
- Settled: visualize moves into P0 as a port of the v1 page kit; gc and the release gate move to P1 (P-4 port-cut, human)
- Settled: grill shows rounds on the page; terminal only on render failure or opt-out · decided-by agent R-2 · accepted 2026-10-29 · spec: R-1 steer point 4; LAVISH.md primary-path rule · reverse: terminal rounds
- Settled: P0 division with visualize as S1 subtask 05 (P-7 accepted; reopened by the R-2 engine scope → re-derived R-3)
- Settled: v2 keeps the v1 artifact set, names and split (GRILL-LOG, PRD + requirement ADRs, SDD + design ADRs, plan/, VERIFICATION-PLAN in P1) · decided-by agent R-2 · accepted 2026-10-29 · spec: owner K-5/K-6/T-19 notes · reverse: merge the files again
- Settled: to-spec writes PRD.md + requirement ADRs from the settled grill, no new questions (F-2) · decided-by agent R-2 · accepted 2026-10-29 · spec: F-1; #153 P0 · reverse: change the PRD template
- Settled: propose-solution: critical-aspect questions (with rendered context to provoke notes, owner F-3 note), top-down draft, fork cards on the page, writes SDD.md + design ADRs (F-3) · decided-by agent R-2 · accepted 2026-10-29 · spec: decisions 14, 49, 94, 97 · reverse: split into two skills
- Settled: rename to-spec → to-prd (F-4); keep INDEX.md (F-5)
- Settled: worked examples use the picture that fits (flow chart, table, more than one) (F-6) · decided-by agent R-2 · accepted 2026-10-29 · spec: owner K-4 note · reverse: fix one format
- Settled: Jira write in P0 inside to-prd (J-1 p0-in-spec, human) → mechanics re-derived R-3
- Settled: core behaviors load from a plugin session-start hook; setup only removes the v1 block (H-1 plugin-hook, human: "clearly a superior solution")
- Settled: Codex switch is global (one of afk/afkv2 enabled) until a live probe proves per-session (H-2)
- Settled: eval harness proves contextual instructions (core behaviors, repo root + nested AGENTS.md), with vs without, Claude + Codex; it is part of the contextual-instruction writing capability, exercised in the sync-harness subtask or the adopt process (E-1 + note) · decided-by agent R-2 · accepted 2026-10-29 · spec: owner S-6 note; decision 34 · reverse: add skill cases
- Settled: harness runs on any repo from one command, cases in that repo; week-1 set core behaviors + toy-repo nested AGENTS.md; case-drafting skill 2.1 (E-2)
- Settled: T-21 steer accepted; T-20 → no single map, as many maps as the content needs (write-in); T-22 → a clear, unambiguous note can settle a point (write-in)
  owner R-2 P-1 note (source of V-1..V-11, verbatim):
    P-1 reopen | I can tell you what I liked about the wayfinder page
    - each round has a color code and it's clear what's new/changed in this round and what belong to previous rounds
    - via the use round's chip it also indicate which cards and which info needs my attention in this round
    - my own annotations and agents' responses at the top. this is good because while my mind is still fresh about what I said, I can read the responses
    - would be better if each round's responses is collapsible
    - the scope map is great. in grill and propose session we need this (or several of this depending on the content needing visualization) to keep high level vision. the color code shows where is settled, where is open, where is the current focus, and whatnot
    - then each node in the map get dedicated card. content and presentation in each card is good too
    - different styling to present meanings: strikethrough, chips, color, dashed line, etc
    - the page does not need to be too rigid on how a point is settled though. through a comment, agents can see if human settled the point, not necessarily answer the question. human still can answer the question, but it's not the only way to settle a point. of course if conflicting info, then it's not settled
    - the structure map is great as we can visualize the modules. this shows that depending on the need, we can have different visualization together. it's all depends on the need, we don't need to be rigid on having 1 map or 2 maps, etc
    - the simulated run I also like, again another visualization doing good job and in the right place
    - I like the fact that everything just accumulate and I see the whole history of the session, and I also can annotate to anything, so I can go back correct myself, or something I did not notice before, now I do, I still have a chance to address it
    
    overall, I like the freedom and flexibility, and I emphasize enough that the content and presentation medium needed depends on the topics at hand. so I don't want it to be too rigid. however, it might contradict, that I also want rendering the page become as fast and effortless as possible, ideally without agents having to generate the page, but only fill in a data structure (eg JSON) and the render engine take that in and render it beautifully like what we have now. I think that means the data structure must be very well defined, with component is composable, so agents can put a chip into a cell, apply styling to text, having diagrams in cards, etc. each component can define its styling, etc. there will also be "freestyle" component where agents can render whatever as they see fit in case what we have does not support what agents want to do. agents should have full understanding of how to use this render engine and how to make the most of it for the most intuitive presentation
    
    the engine and the data structure can be durable too, so we can always reopen prev sessions and audit it (eg if there's a gap in the impl, we can see if that aspect was talked about in the discussion or not, if yes what was the decision, etc). that brings a lot of visibility
    
    needless to say, as this is UI, agents should live test as part of verification
    
    I need this engine in P0
- Settled: one page engine; the agent writes only a JSON page document, never page HTML (V-1) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner R-2 P-1 note · reverse: let skills write HTML
- Settled: composable components, any may hold others, each owns its styling; semantic styling (removed / kept / new / proposed) (V-2) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note · reverse: flat card list
  owner note on V-2: "obviously we want to fully support what HTML can render, not limited to what style and components listed here" → settled by note: any HTML/CSS renders (freestyle + an open style field on every component)
- Settled: freestyle component for any HTML/SVG; each use marked so a repeat can become a component (V-3) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note · reverse: remove freestyle
- Settled: page order: round banner, notes + replies on top (newest first, collapsible per round), maps (as many as needed, coloured settled/open/focus), one card per map node; round colours + round chips; history accumulates (V-4) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note · reverse: kit order
- Settled: a note on anything; a point settles by a mark or by a clear, unambiguous note; the reply states the reading; 'settled by note' has its own state and chip; conflicting signals stay open (V-5) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note, T-22 write-in · reverse: marks only
- Settled: page documents are durable; the engine reopens any past session to read or continue; every schema version stays readable; real grill documents become test fixtures (V-6) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note · reverse: throwaway pages
  owner note on V-6: "not as run files though, in the feature's specs folder instead (along with other artifacts like PRD)" → storage moves to the spec folder; which branch holds the spec folder vs the run files → R-4
- Settled: agents get an authoring guide, loaded before any page document is written (V-7) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-1 note · reverse: schema only
  owner note on V-7: "the guide could be the lavish skill itself" → settled by note: the guide is the visualize skill (SKILL.md + component pages)
- Settled: deterministic tests + a live agent browser test of what users see (hidden content, every action, many notes, note delete, long text, wide tables, many rounds, big diagrams, re-render keeps unsent notes) (V-8) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner P-8 note, decision 70 · reverse: tests only
- Settled: grill and propose-solution render context pictures before critical-aspect questions (V-9) · decided-by agent R-3 · accepted 2026-10-29 · spec: owner F-3 note · reverse: text-only questions
- Settled: all 4 diagram kinds in P0: graphs (maps, flows, module structure), tables, sequence diagrams, simulated-run strips (V-10 all-p0, human)
- Settled: engine grows out of the v1 kit (wrapper, send runtime, drafts, audit fixes, tooltips kept; fixed components → component registry; round cards become registry components) (V-11) · decided-by agent R-3 · accepted 2026-10-29 · repo: v1 scripts/lavish/ · reverse: new engine
- Settled: pay the larger P0 with one day: chain smoke moves from day 3 to day 4, P1 gets 2 days (X-1 slip-day, human)
- Settled: X-2 division void (it was provisional on X-1 move-evals) → re-derived R-4
- Settled: to-prd publishes into the ticket: preview, write after the human's yes, only inside the AFK-managed block, read-back check; refuses if the ticket changed since the preview; first publish appends the block (J-2) · decided-by agent R-3 · accepted 2026-10-29 · spec: J-1 pick, interim rules, v1 to-ticket · reverse: no Jira write
- Settled: the whole PRD is published into the ticket, not a summary (J-3 whole-prd, human)
- Settled: the agent writes Jira only in that managed block, only via to-prd, only after the yes; create, transition, comment denied in the beta (J-4) · decided-by agent R-3 · accepted 2026-10-29 · spec: J-1 pick, A-2 · reverse: deny again
- Settled: core behaviors from a plugin session-start hook on both providers; the hook prints one file, < 50 ms, no shell parsing (H-3) · decided-by agent R-3 · accepted 2026-10-29 · spec: H-1 pick, #153 design rules · reverse: user-file blocks
- Settled: setup guides the Codex hook trust review; the seam design pass probes stop-on-disable and post-compaction reload before the plan locks (H-4) · decided-by agent R-3 · accepted 2026-10-29 · spec: Codex hook docs · reverse: skip the probe
- Settled: K-8 holds in P0 (no sync-harness subtask); the sync-harness subtask and the eval harness both arrive in P1 (E-3 p1-both, human)
- Settled: the adopt process stays 2.1 (E-4, human)
- Settled: no v1 plugin update during the build; each session checks the friction switches at start (D-1, human)
- Settled: setup removes the v1 block only after the afkv2 hook proved it fired, with a backup and a switch-back step (D-2) · decided-by agent R-3 · accepted 2026-10-29 · spec: C-1, Codex trust review, decision 75 · reverse: remove first
- Settled: no ownership config → setup asks once; skipped → the agent asks at its first edit outside the ticket's files (D-3, human)
- Settled: the chain smoke run publishes to a throwaway Jira test ticket in a project the owner names (D-4, human); the project name is parked → R-4 header
- Settled: eval 'without' arms use isolated Claude and Codex home folders, never the owner's settings (D-5, human; isolated Codex home unverified → design pass)
- Settled: terms T-23 page engine / page document, T-24 freestyle component, T-25 map accepted
- Settled: X-1 + E-3 read together: eval harness + sync-harness subtask in P1, everything else in P0, chain smoke on day 4 (W-1, human)
- Settled: P0 division S1 01 skeleton/manifests/hook, 02 core behaviors, 03 engine core + schema v0, 04 diagram components, 05 notes/replies/settle-by-note/reopen + live browser test; S2 06 visualize skill, 07 grill, 08 to-prd + Jira publish, 09 propose-solution, 10 to-subtasks; S3 11 setup, 12 forge + tracker port, 13 autopilot + execute, 14 code-review, 15 change request + CI watch; S4 16 chain smoke day 4; P1 days 5-6 eval harness + sync-harness, gc, release gate (W-2) · decided-by agent R-4 · accepted 2026-10-29 · spec: X-1, E-3, W-1 · reverse: setup back to S1
- Settled: spec folder (grill log, PRD + requirement ADRs, SDD + design ADRs, page documents, INDEX) on the feature branch, merges with the change; run branch holds only plan folder, journal, decision ledger, review telemetry (W-3) · decided-by agent R-4 · accepted 2026-10-29 · spec: owner V-6 note · reverse: spec folder on run branch
- Settled: the ticket gets a summary of the PRD, not the whole PRD (W-4 note reverses J-3); premise correction: W-4 said diagrams go in as code blocks, but v1 attaches them as images (skills/afk/to-ticket/scripts/publish_prd.py:8-13) → Y-1
  owner note on W-4: "I see the problem is the diagrams. then I think a summarized PRD is fine. we need to work on what is the structure of PRD, and how it could be summarized to ensure critical info is preserved. I know for sure Acceptance Criteria as well as worked use cases/scenarios are critical"
- Settled: 3 Claude/Codex premises stay unverified-external until the seam design pass probes them; the PRD marks each as an open premise (W-5, human acknowledgement)
- Settled: the ticket gets the whole PRD with its diagrams as pictures; J-4 widens to upload and replace the diagram pictures on that one ticket (Y-1 whole-images, human; supersedes W-4 summary)
- Settled: v2 PRD keeps the v1 sections and adds Worked examples after the acceptance criteria; every acceptance criterion and worked example carries a stable id (Y-2) · decided-by agent R-5 · accepted 2026-10-29 · repo: v1 skills/afk/to-prd/PRD-TEMPLATE.md · reverse: drop the section and ids
- Settled: publish check refuses when an acceptance-criterion id or worked-example id is missing from the published text; preview before the yes (Y-3, read with Y-1: no separate summary; owner confirmed 2026-10-29: "there's no summary, diagrams as images as of now") · decided-by agent R-5 · accepted 2026-10-29 · spec: owner W-4 note · reverse: agent-judged
- Settled: exit gate passed 2026-10-29 — no pending ledger row, terms verified, access policies (A-1..A-4, J-4), staples none, devil's-advocate pass resolved (D-1..D-5, V-11)
  steer: Steer, page-level, binding for this grill and for propose-solution and propose-verification: 1. Presentation change, logic unchanged. Keep the grill's rules as they are: the round model, decided/confirm/debate cards, explicit marks, the claim ledger, the exit gate. Change how a round is shown. The page must show the whole picture, like the wayfinder scope page from the v2 scoping rounds earlier in this session. Find my prompts that produced that page in this session's transcript. Search for "wayfinder" and "lavish", and for the scratchpad page/r*_build.py / r*_gen.py scripts. Summarize what I asked for and what that page showed. Then base the requirement on it. 2. Page shape I want: - A persistent big-picture map on top, updated in place each round: the scope or requirement tree, decisions so far, open items, and a diagram of how the parts connect. - The current round's cards below the map. Each card links to the map node it settles. - Free annotation on anything: map nodes, settled items, diagrams, not only the current cards. A note on a settled item reopens it, and a note on the map is a steer. - Decisions still need explicit marks. Free notes never stand in for an accept. 3. The same page model for all 3 skills. grill-requirements uses the requirement tree. propose-solution uses the design layers and fork cards. propose-verification uses the scenarios. Only the map content differs. 4. Scope change: move visualize up. Move a minimal visualize (the big-picture page plus rounds and annotation) from P1 into P0, so the day-3 chain already uses it. Re-derive these: K-3 (grill shows rounds in the terminal), K-6 (propose-solution), the P0 division (which session builds visualize, and its seams with the grill and propose-solution), the eval scope for the page. Challenge this if the week-1 target breaks. Say what it costs and what you would cut to pay for it. 5. Record this as a steer: line in GRILL-LOG.md, and bring the re-derived cards back in round 2.

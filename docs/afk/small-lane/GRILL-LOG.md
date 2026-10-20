# Grill log — small-lane

Checkpoint of interactive grill sessions. Working state, updated as decisions lock;
superseded when the synthesized artifacts (PRD / SDD / VERIFICATION-PLAN) land.

## Requirements grill

- Ledger: to-ticket today publishes PRD, meeting and spinoff modes only, no bug create/transition/comment path → verified (digest: skills/afk/to-ticket/SKILL.md:10-17,75-99)
- Ledger: /afk:bug publisher is the second tracker writer under ADR-0001; ADR-0001 has no file → verified (digest: AGENTS.md Tracker boundary; adr/ holds 0002-0007)
- Ledger: /afk:fix never commits/pushes; execute Step 8/10 and preflight PF-3 call it and ship themselves → verified (digest: skills/afk/fix/SKILL.md:107; skills/afk/execute/SKILL.md:67,77; skills/afk/preflight/SKILL.md:99)
- Ledger: /afk:diagnose is user-invocable standalone and fixes in Phase 5 → verified (skills/utils/diagnose/SKILL.md:1-4,119-133)
- Staples: none — no STAPLES.md in this repository
- Settled: diagnose never fixes; owns intake, verify-real, spec comparison, reproduction, root cause, proposed fix; usable standalone
- Settled: fix = diagnose + approval + fix + verification (incl. re-test) + proof + MR + ticket update
- Settled: shared behaviour = pointed-at markdown; new skill only when a human must run it
- Settled: retire /afk:bug; /afk:to-ticket publishes bug and ad-hoc tickets
- Settled: approval before fixing is default unless explicit instruction or approval given beforehand
- Settled: complex / no obvious fix / product-owner call → grilling
- Settled: only the small lane in this feature; other lanes and wayfinder later
- Settled: diagnose leaves a failing test as reproduction proof (agent proposal, not objected under standing rule)
- Settled: five diagnosis verdicts (agent proposal, not objected under standing rule)
- Settled: fix modes in-place vs standalone (agent proposal, not objected under standing rule)
- Settled: hands-off run start = prior approval; decision protocol applies (agent proposal, not objected under standing rule)
- Settled: diagnose/fix lane covers bugs only (any size); to-ticket also files ad-hoc enhancement tickets; enhancements are never small and always grilled
- Settled: a grill a bug was sent to ends with a size call — back to fix if small, else full chain
- Settled: diagnosis = file in the ticket's spec folder, published to ticket, linked from MR; evidence-bundle sections + spec comparison + verdict + proposal; standalone diagnose writes no ticket, offers fix
- Settled: diagnose reproduces on a clean copy of the base branch · decided-by agent R-2 · accepted 2026-10-13 · repo: bug fixer re-reproduces on clean base (skills/afk/bug/FIXER-PROMPT.md) · reverse: drop the clean-base step
- Settled: diagnosis file written to disk before any tracker/forge call · decided-by agent R-2 · accepted 2026-10-13 · repo: never-lost invariant (skills/afk/bug/SKILL.md:24-30) · reverse: reorder the write
- Settled: one approval on the proposal covers code, ticket writes, MR; a steer returns to diagnose
- Settled: proof = failing→passing test + output, every tier run, before/after live-app capture or API request/response
- Settled: standalone fix files ticket after approval before fix; at MR posts link + proof, moves ticket to in review
- Settled: standalone fix ends at MR with tests passing, Ready + reviewer when configured, never merged
- Settled: in-place fix never commits/pushes/opens MR/writes ticket · decided-by agent R-2 · accepted 2026-10-13 · repo: execute ships after fix (skills/afk/execute/SKILL.md:67) · reverse: fix ships in both modes
- Settled: background fix dropped; one-at-a-time queue dropped; local-merge shortcut dropped (agent R-2, accepted 2026-10-13, pattern: SAFETY.md)
- Settled: /afk:bug removed now, no alias, major release
- Settled: to-ticket gains bug/ad-hoc mode (create/update from diagnosis, configured states, evidence comments; Jira + GitHub Issues; human-present); to-ticket is the only tracker writer; fix-version ask/backfill in that mode, Jira only
- Settled: ticket state changes use configured states/transitions · decided-by agent R-2 · accepted 2026-10-13 · repo: adapters/tracker/jira/CONTRACT.md:23-29 · reverse: restore fixed number
- Settled: tracker writes only from human-present to-ticket; unscoped data; validation rules (no fix without real-bug diagnosis + approval; no verdict without reproduction or recorded attempt; works-as-specified stops fix)
- Settled: glossary terms Small lane, Diagnosis, Diagnosis verdict, Fix proposal, Proof, Prior approval, In-place/standalone fix → GLOSSARY.md "Small lane"
- Settled: caller approves the fix proposal; agent caller approves under DECISIONS.md, stops for the human otherwise; fix never self-approves
- Settled: tracker writes allowed under prior approval that covers ticket writes (amends the human-present-only rule for to-ticket's bug mode)
- Settled: verdict routes — human caller: obvious→approval; several/spec gap→grill; works as specified→stop + post diagnosis with approval; cannot reproduce→post attempts with approval. Agent caller: obvious→protocol; several→pick or stop; spec gap→needs decision; works as specified→new outcome (test/finding wrong); cannot reproduce→as today
- Settled: standalone diagnosis in its own worktree off base; failing test on a local branch named in the diagnosis file
- Settled: mid-task capture = to-ticket from a description; diagnose later
- Settled: no push notifications · decided-by agent R-3 · accepted 2026-10-13 · spec: R-2 dropped background fixes · reverse: add notifications
- Settled: fix keeps escape analysis, spec reconciliation, workflow lesson · decided-by agent R-3 · accepted 2026-10-13 · repo: skills/afk/fix/SKILL.md:57-80 · reverse: move them
- Settled: removal complete only with zero references outside CHANGELOG + setup audit pass · decided-by agent R-3 · accepted 2026-10-13 · pattern: FRESHNESS.md same-commit rule · reverse: restore refs
- Settled: old-pipeline tickets fixed by key, no migration; developer settings keep names (agent R-3, accepted 2026-10-13); release notes give in-flight cleanup
- Settled: user stories US-1..3, US-5..8 accepted
- Spinoffs: deferred · medium and large lanes, incl. known limit that a grilled bug grown too large goes to the full chain → candidate — pain: mid-size work has only the heavy chain · why-out: small lane only in this feature — links: relates small-lane (no ticket) → filed #108
- Settled: no diagnosis for a bug found inside a bigger job; caller fixes inline as today (R-4 Q-6 = C)
- Settled: own-code failure → build loop, one targeted retry; flaky → reported with both runs, never fixed; human tester's bug on a feature branch → full diagnosis, in place, that human approves
- Settled: one spinoff ticket for medium + large lanes carrying the known limit, filed at grill end
- Settled: in-feature (red after retry, review finding, adversary finding, smoke gate) → in-place fix, no diagnosis step; regression test, tiers, escape analysis, lesson still run; wrong finding disputed in settle loop
- Settled: in-place fix returns today's outcomes, no verdict; R-3 agent-caller verdict routes and works-as-specified outcome dropped
- Settled: US-4 restated — agent fixes in place without diagnosis, approves under DECISIONS.md, ships with the feature
- Settled: blocking out-of-slice defect → diagnosis (full or light) so the ticket stands alone with evidence + proof; fix on own branch + MR linked to ticket; same fix on feature branch; human merges both
- Settled: non-blocking out-of-slice defect → ticket, no fix
- Settled: hands-off start = prior approval for those ticket writes and separate MRs; merges stay human
- Settled: non-blocking out-of-slice defect → diagnosis (light when a reproduction is held) before its ticket, so the ticket stands alone; not fixed (R-6 SC-10, supersedes the R-5 "ticket, no fix" row's no-diagnosis reading)
- Settled: glossary term Light diagnosis → GLOSSARY.md "Small lane" (R-6 T-8)
- Settled: devil's-advocate pass ran (R-3); findings resolved in R-3..R-5
- Open: none — requirements tree exhausted 2026-10-13; next /afk:to-prd
  steer: SC-6 "if it slice, agents should aim for being autonomous, so it can make the fix to unblock itself, create a ticket to track the issue, along with a separate MR (also attached to the created ticket). that way human will still be in the loop and making merge decision, while not slowing down the autonomous job"
  steer: US-4 "it might be frequent that an on-going feature development will hit lots of bugs, and if we run this workflow it seems to be very heavy and costly ... we need to think through this more carefully about different scenarios of a bug found in an autonomous or semi-autonoomous bigger workflow"
  steer: A-1 "the caller of the skill. if the fix is inside a bigger job (eg implementing a new feature), then the agents implementing the feature can approve the fix"
  steer: Q-1 "bugs can be of any size. enhancement can never be small, it is at least medium and always need careful consideration, so proper grilling is always necessary"
  steer: "if I don't mention something, it means I agree with you"
  steer: "do not create a skill if not needed (eg don't need it to be invocable). create just a markdown and refer to it only instead"

## Solution grill

- Ledger: INV-001 worktree/branch/forge verbs · INV-002 fix + callers · INV-003 diagnose · INV-004 proof capture · INV-005 out-of-slice defects · INV-006 bug removal · INV-007 to-ticket + tracker verbs → partial, gap acknowledged R-1 GAP-1 "gap accepted" (no `investigation:` block; alias forms unsearched; 3 runs non-blind counter-search)
- Locked: L1 inherited — skills run by an agent in the current session; no new process; detached fixer removed (gap acknowledged: INV-001..007 partial)
- Locked: L2 no new skill — diagnose stays a utility, fix becomes standalone only, to-ticket gains bug mode; in-place fix = shared fix procedure markdown in the fix folder read by fix + execute Steps 8/10/10.5, preflight PF-3, smoke gate (R-1 Q-1 = B); diagnosis file is the hand-off by path; to-ticket bug mode uses tracker adapter verbs from one new script; B-9 run by the executor as a standalone fix in a second owned worktree off base, carried by cherry-pick after the fix change opens, dependency named in a managed change-description block + ticket comment (INV-001, INV-002, INV-003, INV-005, INV-007; gap acknowledged)
- Ledger: INV-008 artifact storage + retention · INV-009 consent enforcement · INV-010 re-run safety + tracker config/identity → partial, gap acknowledged R-2 GAP-2 (accept mark, no note) (same reasons as R-1; Jira comment read unchecked)
- Ledger: GitHub Issues has no official upload API → refuted 2026-10-16 (R-3 Q-4 asked to verify): the REST API has none, but GitHub CLI v2.99.0 (2026-09-01) `--attach` on `gh issue create|edit|comment` uploads images and videos — docs.github.com/en/github-cli/github-cli/attaching-files-with-github-cli; github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments. Image/video only (PNG, JPEG, GIF, WebP, SVG, MP4, MOV, WebM), push access, not on GitHub Enterprise Server. Local gh 2.92.0 (live run pending: needs ≥2.99.0) → verified-external, acknowledged R-4 GAP-4 (accept mark, no note)
- Ledger: INV-011 read-back + upload verbs → partial (4 live behaviours unchecked), gap acknowledged R-3 GAP-3 (accept mark, no note); its "no upload in github-issues" holds for plugin code only
- Settled L3: diagnosis = DIAGNOSIS.md in the bug's own spec folder, committed with the failing test on a local diagnosis branch off base, never pushed by diagnose; fix continues on it (R-2 D-7 accept)
- Settled L3: no-ticket work id bug-{slug}; bug mode re-resolves the spec folder with the new key, git-moves it if the path differs, records the key (R-2 D-8 accept)
- Settled L3: proof is attached to the ticket only — text, images and other files — never committed to git (R-2 D-9 reverse:attach + Q-2 write-in)
- Settled L3: diagnosis file merges with the fix and stays (R-2 Q-2 write-in addressed proof only; diagnosis retention follows the recommendation under steer "if I don't mention something, it means I agree with you")
- Settled L3: bug mode sets one named state, in review, through jira.transitions / github-issues state-labels; code starts reading jira.transitions; 3 docs corrected (R-2 D-10 accept)
- Settled L3: diagnosis file lists every outside write done (ticket key, change link, evidence comment markers); comments carry a visible marker (R-2 D-11 accept)
- Settled L4: approval enforced by skill text only; no script check (R-2 Q-3 = A)
- Settled L4: bug mode takes any ticket key it is given (R-2 D-12 reverse:any)
- Settled L4: a failed outside write may be retried, but each retry first checks whether the earlier attempt took effect (R-2 D-13 reverse:retry, note: "as long as before retrying, check if the previous \"supposedly failed attempt\" actually produce something that we should not do again")
- Settled L4: proof carries no credentials; credential rules of the existing redaction script, shared (R-2 D-14 accept)
- Settled L4: writes run as the developer; no new log, no feature flag (R-2 D-15 accept)
- Settled L3: GitHub Issues image proof goes on the ticket through `gh --attach` (R-3 Q-4 write-in: "I do not know but I don't think Github does not support images upload to issue (seems like a very basic necessity), so please verify / if it's truly not supported, then text only and devs attach files manually"; verified supported, so the text-only fallback does not apply; mechanics R-4 D-21)
- Settled L4: tracker family gains `attach`; Jira sends the real file type (R-3 D-16 accept; its GitHub "unsupported" clause superseded by Q-4, re-decided R-4 D-21)
- Settled L4: read-back before each retry, at most 2 retries after 5 s and 20 s, no read-back → no retry (R-3 D-17 accept)
- Settled L3: diagnosis file keeps an approval section (who, words or prior approval, scope, date); nothing checks it (R-3 D-18 accept)
- Settled L4: a given ticket key gets the write; recorded when the file's key is empty, else listed in outside writes (R-3 D-19 accept)
- Settled L4: executor runs change-fetch before change-update-body for the dependency block (R-3 D-20 accept)
- Signoff: HL-3 authz and scoping → signed 2026-10-16 "I sign" — covers HL-3b: who may diagnose, approve, change code, write tickets, open changes; skill-text enforcement; ticket-write scope incl. any given key
- Signoff: HL-1 persistence → signed 2026-10-19 "sign" (R-9 HL-1e) — covers DIAGNOSIS.md fields + other stored items as R-6 HL-1d plus R-8 C-14/C-16/C-17 and R-9 C-34 (proof names carry diagnosis id; Jira read-back), C-39 (owned worktree), C-40 (K1-K5 ids kept)
- Settled L4: GitHub Issues attach = one evidence comment with images/videos inline via `gh issue comment --attach`; other types named for manual add (R-4 D-21 accept)
- Settled L4: GitHub Issues attach read-back = ticket comments, evidence marker (R-4 D-22 accept)
- Settled L4: dependency register gh row gains ≥2.99.0 when tracker github-issues, setup probes it; older gh → attach unsupported, files named, run continues (R-4 D-23 accept)
- Signoff: HL-2 API surface → signed 2026-10-19 "sign" (R-9 HL-2e) — covers R-6 HL-2d plus R-8 Q-6, C-9, C-10, C-15..C-20 and R-9 Q-7 (flaky = passed + journal line), Q-8 (created ticket gets description; existing: comments only), C-36 (GitLab reviewer adds), C-37 (lookup by number), C-38 (unavailable/empty key = failed write)
- Locked: L3 diagnosis = DIAGNOSIS.md on a local diagnosis branch, merges with the fix; provisional bug-{slug} work id re-resolved after the ticket exists; proof on the ticket only (Jira attachments, GitHub Issues gh --attach, else named for manual add), never git; one in-review state via jira.transitions / state-labels; outside-writes list + visible markers; approval section, unchecked (INV-008, INV-010, INV-011; gaps acknowledged R-2 GAP-2, R-3 GAP-3, R-4 GAP-4; HL-1 signed)
- Locked: L4 approval by skill text only; writes as the developer, no log, no flag; any given ticket key; credential-only redaction; read-back before each retry, ≤2 retries at 5 s / 20 s, none without a read-back; tracker attach verb; executor reads the description before rewriting it; gh ≥2.99.0 floor (INV-009, INV-010, INV-011; HL-2 and HL-3 signed)
- Ledger: INV-012 park + decision mechanics · INV-013 CI wait + ready flip · INV-014 feature-branch fix + concurrency → partial, gap acknowledged R-5 GAP-5 (accept mark, no note) (alias forms unsearched; no-method classes; live forge unchecked)
- Settled L5: bug state derived from diagnosis fields (verdict, approval, outside writes); no state field (R-5 D-24 accept)
- Settled L5: one writer per diagnosis part — diagnose: work id..fix proposal; fix: approval; bug mode: ticket key while empty; outside-writes list append-only by bug mode (ticket writes) + fix (change writes) (R-5 D-25 accept)
- Settled L5: diagnosis check script (required parts per verdict, verdict needs reproduction or attempt, certainty marks); run by diagnose at end, fix at start; approval unchecked (R-5 D-26 accept)
- Settled L5: diagnose re-run rewrites verdict/root cause/proposal and empties approval; keeps ticket key + outside writes; steer = re-run (R-5 D-27 accept)
- Settled L6: standalone order — ticket if none → local fix + tiers → push + Draft change → proof on ticket + change → ticket in review → CI wait → ready + reviewer (R-5 D-28 accept)
- Settled L6: CI wait = forge ci-wait as tracked background job, 5400 s / 180 s; green → ready + reviewer; red / timeout / unreadable (incl. no CI) → Draft + reason; outcome stays fixed; re-run resumes at the wait (R-5 D-29 accept)
- Settled L6: out-of-slice verdict routes — blocking: V-1 undoable + clear → fix; V-2/V-3 → ticket + park; V-4 → no ticket, design conflict park; V-5 → no ticket, park; non-blocking: V-1..V-3 ticket, V-4/V-5 nothing, slice continues (R-5 D-30 accept)
- Settled L6: hands-off separate change stays Draft, no CI wait in the slice; named in end report + dependency block; no plan dependency model; feature preflight does not wait (R-5 D-31 accept)
- Settled L6: B-8 — fix commits on the feature branch and pushes, no ticket, no new change (R-5 Q-5 = A)
- Signoff: HL-4 domain invariants → signed 2026-10-19 "sign" (R-9 HL-4c) — covers R-6 HL-4b plus R-8 C-9, C-18, C-19, C-26 and R-9: landing by plain git push, several GitLab changes on a branch stop the run, a flaky check never parks
- Signoff: HL-5 irreversible side effects → signed 2026-10-19 "sign" (R-9 HL-5c) — covers R-6 HL-5b plus R-8 Q-6, C-6, C-7, C-17..C-19 and R-9: description written only on a created ticket, Jira upload read-back, reviewer added on both forges
- Ledger: INV-015 adding a tracker verb → partial (B14 live Jira/GitHub; Jira non-PNG handling unchecked) · INV-016 skill files, scripts, gates → closed-with-frontier , gap acknowledged R-7 GAP-6 (accept mark, no note)
- Settled L6: diagnose off the base branch asks once: that branch's tip or the base branch; records it (R-6 D-32 accept)
- Settled L6: feature-branch landing = fast-forward push, never forced; moved tip → one rebase + every tier again + push; else blocked, commits stay on the diagnosis branch; person pulls (R-6 D-33 accept)
- Settled L6: feature-branch fix proof = one comment on that branch's open change, else the run report; no ticket, no CI wait, no ready (R-6 D-34 accept)
- Locked: L5 derived bug state; one writer per diagnosis part, append-only outside writes; diagnosis check script; re-run empties approval (INV-012, INV-014; gap acknowledged R-5 GAP-5; HL-4 signed)
- Locked: L6 standalone write order; background CI wait, Draft unless green; out-of-slice verdict routes; hands-off separate change stays Draft; feature-branch landing by fast-forward push with proof on the feature change (INV-012, INV-013, INV-014; gap acknowledged R-5 GAP-5; HL-5 signed; HL-1, HL-2 re-signed R-6)
- Locked: L7 no new skill; files beside their owner (diagnose: skill + DIAGNOSIS format + check script; fix: skill + shipping sibling + shared fix procedure + ship script open/ready/land; execute: out-of-slice sibling; to-ticket: bug-mode sibling + one script; grill-requirements: size-call file pointed at by grill-solution; tracker adapters + server: tracker_attach); one outside-writes helper (lockstep: format file ↔ helper ↔ check script); procedure results all routed by every caller; developer settings + fail-closed rule to CONFIG.md; tests in scripts/tests, stub tracker/forge, both OS; dependency direction inherited (INV-015, INV-016; gap acknowledged R-7 GAP-6; R-7 D-35..D-40, C-2, C-3 accept)
- Locked: L8 table-driven check script with derived state; named-step scripts skipping listed writes, helper retry; tracker/forge kind differences stay in adapters; tracker_attach = one comment carrying files, exact-match registry check (R-7 D-38, D-41..D-43 accept)
- Ledger: INV-017 diagnose/fix/lesson/grill seams · INV-018 fix callers · INV-019 to-ticket/tracker · INV-020 forge/worktree/helper · INV-021 removal/registries → partial (alias/wire forms unsearched; no-method classes; live forge + Jira behaviours unchecked) , gap acknowledged R-8 GAP-7 (accept mark, no note)
- Settled L9: red smoke gate → autopilot runs the shared fix procedure per failing scenario between two gate runs; gate stays report-only; one re-run, second red ends the run red (R-8 Q-6 = A)
- Settled L9: hands-off run start = prior approval for out-of-slice ticket + separate-change writes; merge, force push, ready stay forbidden (DECISIONS.md:23,25; autopilot:24,64; SUBAGENT-PROMPT:28-29; execute:12,30,142) (R-8 C-4 accept)
- Settled L9: execute keeps step numbers + caps; procedure results → existing statuses; V-4 → design_conflict cited / needs_decision uncited; "only execute commits" rewritten (R-8 C-5 accept)
- Settled L9: dependency note inside execute's afk:subtasks block; change-fetch before every rewrite (R-8 C-6 accept)
- Settled L9: cherry-pick carries the bug work id, not the slice prefix; second worktree via create-worktree; reasons posted on the separate change; slice re-runs from Step 8 (R-8 C-7 accept)
- Settled L9: three journal events (ticket written, separate change, defect parked) + one autopilot report line (R-8 C-8 accept)
- Settled L9: procedure re-runs a failure once first; seventh result flaky (CHANGED D-39) (R-8 C-9 accept)
- Settled L9: procedure records caller, input, failing path from the reproduction (R-8 C-10 accept)
- Settled L9: diagnose keeps "§Phase 2.5 — Trace the path" verbatim (behavior_registry.py:283-298), investigate + rationale-read, name, description, language pointer; hitl template stays; dead hand-off dropped (R-8 C-11 accept)
- Settled L9: lesson-capture links move to the procedure file (AGENTS.md:153, LEDGER-FORMAT:79-88); WORKFLOW-FEEDBACK uses slice/finding id (R-8 C-12 accept)
- Settled L9: grills accept DIAGNOSIS.md; grill-solution runs without a PRD; size call names fix only as bounce target (R-8 C-13 accept)
- Settled L9: fix retires the diagnosis worktree via remove-worktree.py; lower-case name, fetch base; pattern refusal → ask, or needs_decision hands-off (R-8 C-14 accept)
- Settled L9: Jira adapter converts markdown → ADF for create/comment/attach; attach embeds media (R-8 C-15 accept)
- Settled L9: one in-review key on both trackers, name or id, checked against transitions, refused when unconfigured; Jira refuses unknown fix version; scaffold key renamed (R-8 C-16 accept)
- Settled L9: missing assignee/reviewer → ask when a person is present; hands-off → unassigned + reported; literal none = unset (CHANGED: narrows fail-closed) (R-8 C-17 accept)
- Settled L9: tracker/forge none probed before the first write; then fix locally and stop (R-8 C-18 accept)
- Settled L9: ship script opens the change before rationale-post, routes ci-wait on exit + stdout, refuses empty id + protected target; landing fetches, checks fast-forward, sets -u (R-8 C-19 accept)
- Settled L9: to-ticket bug mode files only from a file on disk, never imports publish_prd (tracker_api.load(("call",))), writes comments or its own region, keeps dry-run + publish_bug safeguards, lists gh ≥2.99.0 (R-8 C-20 accept)
- Settled L9: remove /afk:bug in one commit (manifests, test, references); mrReviewer + change-reviewers land with fix's ready step (R-8 C-21 accept)
- Settled L9: adr/0008 supersedes ADR-0001; report-issue stays a separate egress (R-8 C-22 accept)
- Settled L9: new commit check refuses /afk:bug + /afk-toolkit:bug outside CHANGELOG and spec folders (R-8 C-23 accept)
- Settled L9: glossary commit goes with PRD.md; remove 8 bug-pipeline terms + One-live-fixer (R-8 C-24 accept)
- Settled L9: major release (bump is the human's call); Migration line; remove to-demo-plan + settle-mr aliases (R-8 C-25 accept)
- Settled L9: feature-branch fix lands through the feature's Draft change; one SAFETY sentence, no BEHAVIORS change (R-8 C-26 accept)
- Signoff: HL-6 changes to existing behaviour → signed 2026-10-19 "sign" (R-9 HL-6b) — covers the 19 R-8 seam rows as changed by INV-022..INV-026 and R-9 (diagnose description, flaky, journal forms, commit rule, size call, PRD-less grill exit, spinoff ADF, GitLab reviewer, worktree ownership, none value), compatibility posture, rollback = pin the previous plugin version
- Ledger: INV-022 diagnose/fix · INV-023 callers · INV-025 forge/worktree · INV-026 removal/registries → closed-with-frontier (B14 only); INV-024 ticket/tracker → partial on 3 claims, delta D3 after R-9 Q-8 + C-34 (accepted as ground R-9 GAP-8)
- Settled L9: flaky = passed for that run + one journal line (check, both runs); no new execute status (R-9 Q-7 = A)
- Settled L9: bug mode writes the diagnosis summary as the description only on a ticket it creates; existing ticket → comments only; no marked region (R-9 Q-8 = A)
- Settled L9: diagnose description rewritten (CHANGED C-11); heading, name, language pointer verbatim (R-9 C-27 accept)
- Settled L9: size call "still small" recorded as a new row shape in the grill's own GRILL-LOG section; fix reads it before code (R-9 C-28 accept)
- Settled L9: PRD-less grill-solution ends at the size call: small → fix; too big → grill-requirements; never to-sdd (R-9 C-29 accept)
- Settled L9: PRD M2 in-place return = the shared fix procedure file (R-9 C-30 accept)
- Settled L9: journal events use the park form, a subject commitjoin does not join, never `pushed` for the separate change (insights.py:23-24, commitjoin.py:65-78, understand:80) (R-9 C-31 accept)
- Settled L9: JOURNAL-FORMAT park reasons gain V-2, V-3, V-5 out-of-slice reasons (R-9 C-32 accept)
- Settled L9: "only execute commits" widens to autopilot's and preflight's fix helpers (autopilot:24, execute:142) (R-9 C-33 accept)
- Settled L9: Jira uploads read back stored name + type; proof names carry the diagnosis id (R-9 C-34 accept)
- Settled L9: spinoff stubs inherit ADF + unknown-fix-version refusal; to-ticket existing-modes row → extends (R-9 C-35 accept)
- Settled L9: GitLab change-reviewers adds (`+` prefix) like GitHub (R-9 C-36 accept)
- Settled L9: fix records its change number, looks up by number after opening; several GitLab MRs on a branch → stop, never a second change (R-9 C-37 accept)
- Settled L9: unavailable or empty created key = failed write in the helper (github-issues/api.py:95,321-326) (R-9 C-38 accept)
- Settled L9: fix creates its worktree with --name + --base, removes from outside, reads stderr/kept.json (R-9 C-39 accept)
- Settled L9: none = unset for reviewer and assignee; K1-K5 ids kept in CONFIG.md (R-9 C-40 accept)
- Settled L3/L6: standalone change gets one proof comment (ship script proof step, change-comment): P-1 + P-2 as text + link to the ticket evidence comment; P-3 files on the ticket only; reconciles AC-018 + R-5 D-28 with ADR-0004 (plan adversary review A-11, 2026-10-19, human: "Text + link (Recommended)"; covers this added outside write under HL-5)
- Settled plan: standalone write order proven by a walk check of SHIPPING.md against the SDD §7 diagram, not a driver script; replay safety rests on the bug-mode and ship-script skips (plan adversary review A-11 final disagreement, 2026-10-19, human: "Walk check (Recommended)")
- Locked: L9 seam rows (the 19 signed in HL-6) — reworked: diagnose never fixes; fix standalone + in-place; execute fix points + limits (Steps 8/10/10.5/14, out-of-slice sibling); hands-off rules; smoke gate + autopilot (Q-6 A); bug skill removed; registries + FRESHNESS + MANIFEST; extends: shared fix procedure; preflight PF-3/PF-4 + description blocks; journal + run report; lesson capture links; grills; to-ticket bug mode; tracker adapters (tracker_attach, ADF, states/versions); registry check E exact match; forge + worktree script; developer settings → CONFIG.md; one tracker writer; new commit check; extends since R-9 C-35: to-ticket existing modes (spinoff); fits (no sign-off): feature-branch landing (plain git push), outside-writes helper, release gate (INV-022..INV-026 closing INV-017..INV-021; R-9 GAP-8; HL-6 re-signed R-9)
- Open: none — L9 exhausted; HL-1..HL-6 signed (R-9); INV-024 re-closed (D3); SDD.md + 11 design ADRs written 2026-10-19 after to-sdd gates 7/7b/7c/8/8b passed (gh 2.99.0 floor verified: github.blog changelog 2026-09-01). Next: /afk:to-design-brief, then /afk:to-subtasks
  out of scope, existing drift to report: AGENTS.md:179 + README:838 omit preflight-evidence block; JOURNAL-FORMAT:51-55 omits unhomed_product_debt; GLOSSARY.md:337 5 miss classes vs 6; providers PARITY:75 + CONFORMANCE:44 list diagnose missing; diagnose:147 hands off to unshipped skill; gc/SKILL.md:76 + settle-change:102 raw worktree remove; check E config-key first-segment match; PARITY:70 claims to-subtasks proved tracker_create; github-issues CONTRACT:54 stale; overlapping tracer fragments cannot fold; validate_coverage rejects irrelevant read site
  out of scope, to report: git push unguarded; update-ref moves another worktree's branch; --ignore-other-worktrees (INV-014); merge_fragments seed-node conflict (INV-010..014)
  R-9 response: "GAP-8 accept · Q-7 A · Q-8 A · C-27..C-40 accept · HL-1e sign | sign · HL-2e sign | sign · HL-4c sign | sign · HL-5c sign | sign · HL-6b sign | sign"
  R-8 response: "GAP-7 accept · Q-6 A · C-4..C-26 accept · HL-6 sign | sign"
  R-7 response: "GAP-6 accept · D-35..D-40 accept · C-2 accept · C-3 accept · D-41..D-43 accept"
  R-6 response: "D-32 accept · D-33 accept · D-34 accept · HL-1d sign · HL-2d sign · HL-4b sign · HL-5b sign"
  R-5 response: "GAP-5 accept · D-24..D-31 accept · Q-5 A · HL-4 sign · HL-5 sign"
  R-4 response: "GAP-4 accept · D-21 accept · D-22 accept · D-23 accept · HL-1c sign | I sign · HL-2c sign | I sign"
  R-3 response: "GAP-3 accept · Q-4 write-in | I do not know but I don't think Github does not support images upload to issue (seems like a very basic necessity), so please verify / if it's truly not supported, then text only and devs attach files manually · D-16 accept · D-17 accept · D-18 accept · D-19 accept · D-20 accept · HL-1b sign | I sign · HL-2b sign | I sign · HL-3b sign | I sign"
  glossary: "In-place fix / standalone fix" reworded for Q-1 = B (uncommitted)
  steer: "if I don't mention something, it means I agree with you"
  steer: "do not create a skill if not needed (eg don't need it to be invocable). create just a markdown and refer to it only instead"

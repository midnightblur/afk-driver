# L9 compatibility audit — findings

Read-only auditors over the settled design (GRILL-LOG `## Solution grill`, PRD.md). Each finding gets its resolution in GRILL-LOG round R-8.

## Chain skills (execute, autopilot, preflight, smoke-test, DECISIONS, journal)

1. **Blocks.** Hands-off ticket writes and a separate change off base contradict autopilot's boundary: `autopilot/SKILL.md:24,64`, `SUBAGENT-PROMPT.md:28-29`, and execute driven mode, which allows "this branch" only (`execute/SKILL.md:30`). The AGENTS.md Tracker boundary lists execute and autopilot as "not Jira".
2. **Blocks.** DECISIONS.md's two-way-door test excludes outside writes (`:23`) and hard boundaries, which include Jira and branches beyond the feature branch (`:25`). B-9 therefore always parks unless AC-028's prior approval is written into it. The ledger assumes `plan/DECISIONS.md` exists (`:35`), and no plan exists for B-1 or B-8.
3. **Changes behaviour.** fix today never commits (`fix/SKILL.md:14,107`), delegates to a diagnose that fixes (`:12,31`), and reads the ticket via `tracker_get` (`:23`). Execute calls itself "the only context where the agent commits autonomously" (`execute/SKILL.md:142`).
4. **Changes behaviour.** Execute Steps 8, 10 and 10.5 (`:67,77,93`) and preflight (`:99,125`) route to `/afk:fix`, and the `test_fail` text names "/afk:fix pass" (`:123`). The adversary corpus ratchet is in `fix/SKILL.md:51-53`. Phase 2 higher-tier tests are at `:42-55`.
5. **Blocks.** B-6 contradicts the smoke gate: "not by patching here" (`smoke-test/SKILL.md:53`), "Never patches to green" (`:80`), autopilot's "No patching to green at the gate" (`autopilot/SKILL.md:67`). Smoke-test owns only its gate cells (`:77`).
6. **Changes behaviour.** B-7 (re-run, report flaky) contradicts "no silent retry; the human re-runs deliberately" (`smoke-test/SKILL.md:53`). The only flake concept today is PF-7 `forge_flake`.
7. **Blocks.** B-9 breaks execute's limits:
   - Scope globs (`:49,147`).
   - The single-writer list (`:151`).
   - Push "to the parent branch" (`:63`).
   - AGENTS.md's MR-description invariant, which allows only the `afk:subtasks` block.
   - "Writes no tracker" (`:12`).
   - The one-worktree precondition (`:16`).
8. **Changes behaviour.** The journal grammar has no event for a separate change opened, a ticket written, or a defect parked (JOURNAL-FORMAT event table). Execute `:37` requires a journal line per push and decision.
9. **Nit.** `design_conflict` is cited-mode only (`execute/CITED-MODE.md:132-148`). The V-4 route needs `needs_decision` in uncited mode.
10. **Changes behaviour.** to-ticket spinoff mode never mints in a driven run (`to-ticket/SKILL.md:99`; SPINOFF-TICKET.md). AC-028 inverts that for bug mode.
11. **Nit.** The CI-wait numbers match preflight PF-6 (`preflight/SKILL.md:192,200`).

## Doctrine and gates

1. **Changes behaviour.** A tenth tracker verb breaks "the same nine on every kind" (`ADAPTERS.md:42-48`). The count is repeated in the CONTRACTs, `adapter.json`, `OPERATIONS` and `CONFORMANCE.md:95-96`. Upload already has a route outside the nine, via `tracker_api.py` (`ADAPTERS.md:50-53`).
2. **Blocks AC-038.** FRESHNESS rows `:77-80` must be rewritten, not only deleted. `:86` names `publish_bug.py` as a `jira/api.py` caller, and row 80 lists `/afk:bug` as a worktree-provision consumer.
3. **Blocks AC-038.** References beyond the removal list: `CAPABILITIES.md:65`, `SPINOFF-TICKET.md:20`, `gc/SKILL.md:90`, `to-meeting-d/SKILL.md:114` (routes defects to `/afk:bug capture`, a dead end), MANIFEST, `create-worktree:63`, `afk-config.py:69`, `test_tracker_create_assignee.py:3`, `hooks/README.md:123`, README, skills/afk/AGENTS.md "Bug pipeline", and the AGENTS.md catalog and Tracker boundary.
4. **Changes behaviour.** `CONFIG.md:136` and `afk-config.py:69` point at `bug/CONFIG.md` for the fail-closed rule. MANIFEST `:126-127,913-914` cite its keys (`ideBinary`). The keys that `create-worktree:63` reads lose their documented owner. What `ideBinary` and the "open fixer worktrees" use mean without the detached fixer is undefined.
5. **Blocks if mishandled.** BEHAVIORS.md:47 `prove-reachability-before-fix` has its doctrine home at `diagnose/SKILL.md §Phase 2.5 — Trace the path` (`:86`). Keep the heading, or change BEHAVIORS, setup, tests and changelog together.
6. **Changes behaviour.** The `change-landing` managed behavior and `SAFETY.md:18-21` say work lands through one Draft change. The design has a feature-branch fix with no change, a standalone fix that flips its change to ready (today preflight's job), and a fast-forward landing. SAFETY needs an explicit exception.
7. **Changes behaviour.** A diagnosis branch must pass `git.branch-pattern` and be named from `git.branch-template` (`create-worktree:19-23,143-168,230-234`; `branch-name-gate.sh`). `bug-{slug}` is a work id, not a branch name.
8. **Changes behaviour.** The feature-branch push sits outside the guard (`SAFETY.md:28-30`), so the landing rests on skill text only. Cite this in HL-5.
9. **Changes behaviour.** The fix contract inverts at `fix/SKILL.md:3,10,12,14,23,29-38,107`. The status table `:90-97` has no V-4 status.
10. **Nit.** Registry lines `AGENTS.md:117,130` and `README.md:741,787-788` need new text. The `CAPABILITIES.md:68` change_rationale row needs a check. The lesson capture points at fix Phase 2.5/3.5 (`lessons/LEDGER-FORMAT.md:79-80`) break if renumbered.
11. **Nit.** A major release passes `release-gate.sh` (changelog, manifests, marketplace, tag); a skill removal trips skill-registry-gate through the catalog rows.
12. **Nit.** The MANIFEST C3b probe is auth-only (`:426-442`); a version probe that applies only to `tracker: github-issues` is new.

## Adapters, to-ticket, config

1. **Changes behaviour.** The fail-closed rule for `trackerAssignee` (`CONFIG.md:136`; bug/CONFIG.md) stops hands-off B-9 and B-10 ticket writes. to-ticket `:96` treats an unset assignee as no assignee. Made general, it would silently change spinoff mode.
2. **Changes behaviour.** No code reads `jira.transitions`. The key names disagree:
   - the scaffold has `ready-for-review: Ready for Review`, a name (`afk-config.py:1031-1032`);
   - the test has `dev-pending: "12463"`, an id (`test_afk_config.py:67-75`);
   - GitHub has `in-review` (`:1048`).
   Jira `tracker_transition` takes an id (`jira/api.py:530-532`), while create's `status` matches by name (`:604`).
3. **Changes behaviour.** The adapters do not refuse a transition missing from the config. Jira accepts any id (`:530-532`); GitHub always allows open, closed, close and reopen (`github-issues/api.py:212-218`). The refusal must live in the bug-mode script.
4. **Changes behaviour.** Jira `_op_comment` wraps the text in one ADF paragraph (`jira/api.py:495-499,540-542`), which flattens a diagnosis. Rich ADF is reachable only via `tracker_api.load(required=…)`, which exits on github-issues (`tracker_api.py:44-49`).
5. **Changes behaviour.** The "nine verbs" invariant (as in Doctrine 1). Jira attachments attach to the issue (`:193`), not to a comment, so "one comment carrying files" needs the media-UUID embed (`:199-211`).
6. **Changes behaviour.** GitHub `tracker_attachments` is partial: it regex-scans URLs (`github-issues/api.py:251-265`). The read-back must use `tracker_get` comments, as D-22 settled.
7. **Changes behaviour.** Tracker `none` and forge `none` are not designed for. With forge none, D-28 writes the ticket before a change that can never open. Fix: probe both before the first write.
8. **Nit.** With no CI, `ci-wait` exits 3 after about 360 s (inferred from `forge.sh:700-713`). On native Windows the payload goes through the environment (github CONTRACT).
9. **Nit.** Dangling references (as in Doctrine 3). to-ticket `SKILL.md:3,8,10,29` frames the skill as Jira-only with S1; the GitHub bug mode needs a gh ≥2.99.0 prerequisite row.

# Review — 0004-diagnose-rewrite round 3

- policy: lean · delta round 3 (d22496e..b6b4c0b) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: fix-owner specialists (no critical or high in round 2), scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 1 high, 3 medium, 4 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: b6b4c0b5ddc6c2a7d4060fda7abe56ecb4768bb4
- counts: crit=0 high=1 med=3 low=4

## r-001 · high · correctness · `skills/utils/diagnose/SKILL.md:34`
Re-run detection now keys only on the owner record, but the step-4 recut (`create-worktree --branch --dir`) writes no record, so a second re-run hits an unhandled `already exists` refusal

- Why: create-worktree writes the owner record only on the `--name` path (scripts/create-worktree:509-523), so after one recut the next re-run skips step 3. At step 4, `--name` refuses because the branch exists (:474). The `--branch --dir` recut then refuses because the worktree folder exists (:296). Step 4 routes neither refusal. The removed step-3 text caught this case by the local branch.
- Fix: Restore branch-based re-run detection in step 3 (find the worktree on the template-filled branch via `git worktree list`; cut one only when none is checked out), or record the recut worktree
- Concern: refactor-safety,delta-sweep (reworked control flow in an existing method — behaviour-preservation risk)

## r-002 · medium · correctness · `skills/utils/diagnose/SKILL.md:35`
A re-run whose worktree is gone now reaches the recut only through step 4, after the starting-branch question, so with no person present and no answer it ends `blocked`

- Why: The recut now sits behind 'On any other branch, ask once ... No person present and no answer → blocked'. The removed step 3 cut onto the existing branch directly. SDD §3 says a re-run keeps the recorded starting branch, so asking again is a regression.
- Fix: Detect the existing Diagnosis branch before the starting-branch question (in step 3), and cut onto it without asking
- Concern: refactor-safety,delta-sweep (reworked control flow in an existing method — behaviour-preservation risk)

## r-003 · medium · correctness · `skills/afk/fix/SKILL.md:39`
Fix step 3 now fixes in whatever linked worktree it runs in, even for a handed `DIAGNOSIS.md` path where fix handed nothing to diagnose. Nothing checks that this worktree is on the Diagnosis branch or holds the Base commit No route either when the brought-in test passes or does not build there.

- Why: The removed text used the caller's worktree only when fix had handed it to diagnose. The diagnose and size-call hand-backs (`/afk:fix <path>`, SIZE-CALL.md:24) now apply the proposal on any branch the session is on. That breaks the format's Fixed state, 'fix commits on the diagnosis branch'. The proposal's file:line was also diagnosed against a different Base.
- Fix: For a path input, work in the linked worktree only when its branch is the diagnosis's Diagnosis branch (or contains its Base commit); otherwise use or cut the Diagnosis-branch worktree
- Concern: refactor-safety,delta-sweep (changed defaults — behaviour-preservation risk)

## r-004 · medium · correctness · `skills/afk/fix/SKILL.md:39`
The bring-in step `git checkout <Diagnosis branch> -- <paths>` fails for a handed-worktree diagnosis, whose failing test and DIAGNOSIS.md were never committed on that branch, when fix later runs with the path from a different linked worktree.

- Why: Diagnose leaves both files uncommitted in a handed worktree, so the checkout's pathspec does not match. A still-small grill returns exactly such a path to `/afk:fix`, and fix now always works in its own linked worktree, so this path is reachable. D-17's claim that a handed case never reaches the cut is about the cut only; this checkout breaks too.
- Fix: When the Diagnosis branch does not hold the files, copy them from the worktree that holds DIAGNOSIS.md; failing that, stop `blocked` and name that worktree.
- Concern: delta-sweep (New defect in the change)

## r-005 · low · correctness · `skills/afk/fix/SKILL.md:43`
Step 2 now routes on the latest size-call row, but the Phase 1 exit gate still accepts any V-2/V-3 with a `still small` row. The rule is fixed in one place and the sibling keeps the old behaviour.

- Why: If an earlier `still small` row is followed by a later `too big` row, step 2 stops, yet the exit gate as written still passes.
- Fix: Reword the exit gate to 'a V-2/V-3 whose latest size-call row is `still small`'.
- Concern: delta-sweep (New defect in the change)

## r-006 · low · correctness · `skills/afk/grill-solution/SKILL.md:14`
The stop with no size call (a verdict SIZE-CALL.md leaves with no open question) is covered only for the no-PRD case. The with-PRD sentence, grill-solution Next (line 117) and grill-requirements Next (line 95) still route that grill onward.

- Why: With a PRD, or in the requirements grill, a handed V-1/V-4/V-5 stops with no call per SIZE-CALL.md:10. The Next sections cover only 'ends at its size call' or 'still small', so 'Otherwise ... run /afk:to-sdd' or 'everything below binds every other grill' (glossary commit, /afk:to-prd) applies.
- Fix: State the no-call stop once for every diagnosis grill: in both Next sections, or in the with-PRD sentence plus grill-requirements line 95.
- Concern: delta-sweep (New defect in the change)

## r-007 · low · spec · `docs/afk/small-lane/plan/DECISIONS.md:119`
D-17 supersedes the two SDD §4 resource rows but not the §4 DIAGNOSIS.md entity row or the consumed format's Diagnosis branch row. Both still require a branch 'from the branch template, made from the Base tip', and the SDD row adds 'lower-cased; passes `git.branch-pattern`', which an invoker's handed branch need not meet.

- Why: A ledger entry supersedes only the passage it quotes, so SDD line 133 and DIAGNOSIS-FORMAT.md:17 still bind the handed case that D-17 means to narrow.
- Fix: Add SDD §4 entity row 'Diagnosis branch | branch name | no | from the branch template, made from the Base tip | — | lower-cased; passes `git.branch-pattern`' to D-17's Supersedes for the handed case. Note the format row too.
- Concern: delta-sweep (Documented-rule breach in changed lines)

## r-008 · low · compliance · `skills/utils/diagnose/SKILL.md:35`
The new re-cut instruction runs the plugin script as a bare `create-worktree`, not through `${AFK_PLUGIN_ROOT}/scripts/create-worktree`; the removed step 3 text used the full path.

- Why: The plugin is installed rather than checked out beside the work, so a bare script name does not resolve.
- Fix: Write `${AFK_PLUGIN_ROOT}/scripts/create-worktree --branch <branch> --dir <work id, lower-cased> --no-open`.
- Concern: delta-sweep (Documented-rule breach in changed lines)

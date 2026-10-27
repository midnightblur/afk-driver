# Review — 0004-diagnose-rewrite-f86eb43-r1

- policy: lean · full-unit round · activated: spec-fidelity, scope-and-impact, test-veracity, logic-correctness (slice 0008 consumes this one), refactor-safety (modified lines), api-contract (public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 1 upheld / 1 downgraded / 0 dropped (r-016 upheld; r-014 downgraded to low)
- verdict: blocking — 2 high, 15 medium, 7 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- mutation probe not run (tests run in CI on the human's call)
- head: ac7bb38c841ec9c6003d72e505eb2e9df7eeecb4
- counts: crit=0 high=2 med=15 low=7

## r-001 · high · correctness · `skills/afk/fix/SKILL.md:37`
The live /afk:bug fixer calls /afk:fix inside its own worktree with no person present. At this commit, diagnose either ends `blocked` on the starting-branch question, or cuts a second worktree where fix applies the change, outside the fixer's only allowed write location.

- Why: Fix answers diagnose's branch question only in a feature-building session, and otherwise fixes 'in the diagnosis worktree'.
- Fix: Have fix hand diagnose the caller's current worktree and the starting-branch answer whenever it already runs in a worktree, and fix there.
- Concern: logic-correctness,refactor-safety,scope-and-impact (partial-failure handling (caller compatibility))

## r-002 · high · spec · `skills/utils/diagnose/SKILL.md:31`
Phase 0 resolves the spec folder (step 2) and checks it for an existing DIAGNOSIS.md (step 3) before the diagnosis worktree exists (step 5). `notes resolve` returns an absolute path under the invoking checkout's toplevel, so a diagnosis committed only on the unpushed Diagnosis branch is never seen there and the re-run is not detected. Phase 7 step 2 also writes DIAGNOSIS.md outside the worktree where step 4 commits it.

- Why: The re-run contract cannot be reached, and ADR-0002 requires the file committed with the failing test on a local diagnosis branch.
- Fix: Resolve the spec folder from inside the diagnosis worktree after step 5. Detect a re-run by an existing Diagnosis branch or worktree for the work id, then read DIAGNOSIS.md there.
- Concern: spec-fidelity,logic-correctness (Acceptance: re-run keeps ticket key, Outside writes and Base (SDD §3); DIAGNOSIS.md written into the bug's spec folder (PRD AC-008, ADR-0002))

## r-003 · medium · spec · `skills/utils/diagnose/SKILL.md:161`
Diagnose offers `/afk:fix <path>`, and SIZE-CALL.md sends a still-small bug back to /afk:fix with the diagnosis path. At this commit, fix's Argument accepts only a key, a description or nothing, and it always re-runs diagnose.

- Why: The hand-off this slice adds does not work at this commit. Fix treats the path as a description and starts a new diagnosis, or re-runs the existing one and gets V-2/V-3 again, which ignores the settled answer in the size-call row and ends `blocked`.
- Fix: Have fix accept a diagnosis path and skip re-diagnosis now, or hold the offer and the bounce until slice 0008 lands that input.
- Concern: refactor-safety,api-contract,scope-and-impact,logic-correctness (open-question)

## r-004 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
Every fix call from an in-place caller (execute tier-red and review routing, preflight) now cuts a new linked worktree and local branch, and no one removes them. Diagnose never removes the worktree, and fix at this commit does not retire it.

- Why: A behaviour that used to need no resources now leaks a worktree, a branch and an owner record on every autopilot remediation. A repeat name also fails create-worktree's 'name already taken' / 'branch already exists' check.
- Fix: Until slice 0008, have fix retire the diagnosis worktree after a feature-session fix (remove-worktree from outside it), or have diagnose skip cutting one when the invoker supplies its own worktree.
- Concern: refactor-safety,scope-and-impact (medium — in-module refactor reworking behaviour-bearing code (control flow) with thin coverage)

## r-005 · medium · correctness · `skills/afk/fix/SKILL.md:35`
Fix now ends `blocked` on the common V-2, V-3 and V-4 verdicts, and on diagnose's new setup ends (spec folder unresolved, branch-pattern refusal, no answer to the starting-branch question). The in-place callers route only `design_conflict`.

- Why: Execute's review and adversary remediation (Steps 10 and 10.5) and preflight PF-3 expect /afk:fix to fix. A `blocked` result reaches them unrouted, so findings fix used to clear now park or stall the settle loop.
- Fix: State in the callers, or in D-13's interim note, how a fix `blocked` is routed (for example, dispute or park), or pin the behaviour with a test of the caller route.
- Concern: refactor-safety,scope-and-impact,logic-correctness (medium — changed outcomes of a symbol whose callers live outside the home module)

## r-006 · medium · correctness · `skills/afk/grill-requirements/SIZE-CALL.md:24`
A 'still small' call sends the bug to `/afk:fix` with the diagnosis path. At this commit, fix accepts no path and never reads the size-call row, so the bug loops between grill and fix.

- Why: Fix re-runs diagnose, gets V-2/V-3 again and stops `blocked`.
- Fix: Have fix read the 'still small' row for a V-2/V-3 diagnosis path and apply its `settled:` clause, or say the return is not yet consumed.
- Concern: logic-correctness,scope-and-impact,api-contract (concurrency/ordering (state round-trip))

## r-007 · medium · correctness · `skills/afk/fix/SKILL.md:58`
Two checks from diagnose's old Phase 5 and Phase 6 did not move into fix: re-running the original, un-minimised scenario, and confirming a UI-visible bug fixed in the running UI. Fix now re-runs only the diagnosis's reproduction (the minimised failing test).

- Why: In-place callers (execute Step 8/10/10.5, preflight) now accept a fix proven only at the test seam, which the old diagnose rule says gives false confidence for UI bugs.
- Fix: Add both checks to fix's Phase 2 Verify step.
- Concern: refactor-safety (medium — logic moved between modules with behaviour dropped)

## r-008 · medium · correctness · `skills/afk/fix/WORKFLOW-FEEDBACK.md:31`
WORKFLOW-FEEDBACK.md still points the lesson's Bug line at diagnose's post-mortem, which this diff removes along with the old 'Phase 6 — Cleanup + post-mortem'.

- Why: Every Phase 3.5 workflow lesson now cites an artifact that no longer exists. The diagnosis record that replaces it is DIAGNOSIS.md.
- Fix: Point at the DIAGNOSIS.md path from the diagnose run instead of 'the post-mortem'.
- Concern: refactor-safety,scope-and-impact (high — call sites not all updated after a removal)

## r-009 · medium · correctness · `skills/utils/diagnose/SKILL.md:42`
A light diagnosis must 'run it once' on the handed reproduction, but a review finding id cannot be run. And when the reused check passes in the diagnosis worktree, the skill gives no next step.

- Why: A static review finding has no command; a check that comes back green skips Phase 2's gate and never reaches V-5.
- Fix: For a finding with nothing to run, build a failing test from it (Phase 1). For a reused check that does not fail, fall back to Phase 1 or end V-5 with the run in Attempts.
- Concern: logic-correctness (empty/null/missing inputs)

## r-010 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The only create-worktree failure handled is a branch-pattern refusal. 'branch already exists' and 'name already taken' end in an unhandled ERROR, and asking for a new name can never satisfy a pattern the template's --name filling cannot match.

- Why: create-worktree --name refuses an existing branch; with no non-{user} placeholder it yields `worktree-<name>`.
- Fix: Handle an existing branch or name: ask for another name, or end `blocked` with no person present.
- Concern: logic-correctness (error and rollback paths)

## r-011 · medium · correctness · `skills/afk/grill-solution/SKILL.md:14`
A solution grill handed a diagnosis ends at the size call 'with or without a PRD'. For a too-big bug that went through the requirements grill and /afk:to-prd, the design grill again stops and never reaches /afk:to-sdd.

- Why: SDD §7 ends the grill only for the no-PRD case.
- Fix: End at the size call only when no PRD exists; with a PRD, after a 'too big' call, continue to /afk:to-sdd.
- Concern: logic-correctness (concurrency/ordering (loop termination))

## r-012 · medium · correctness · `skills/utils/diagnose/SKILL.md:161`
Diagnose's only declared terminal line is `DIAGNOSIS: <verdict> <path>` with `<verdict>` = V-{n}. Its four `blocked` exits (input missing, ticket unreadable, spec folder unresolved, no branch answer) print no defined line, and fix routes only on V-1..V-5.

- Why: An agent caller such as /afk:fix Phase 1 step 2 has nothing it can parse when diagnose ends blocked, so the failure path of the invocation contract is undefined.
- Fix: Declare a blocked headline, e.g. `DIAGNOSIS: blocked(<reason>) — <one line>` with the SDD §3 reason set, and add a route for it to fix Phase 1 step 2.
- Concern: api-contract,scope-and-impact (Error contract absent)

## r-013 · medium · design · `skills/utils/diagnose/SKILL.md:159`
In one run, diagnose emits two different grammars under the same `DIAGNOSIS:` prefix: the check script's `DIAGNOSIS: accept — verdict …` / `DIAGNOSIS: refuse` / `DIAGNOSIS: unreadable` (Phase 7 step 3), then the run's own `DIAGNOSIS: <verdict> <path>` (step 5).

- Why: A caller that matches the `DIAGNOSIS:` headline can take `refuse` or `accept` for the verdict token, which makes the status line easy to misparse.
- Fix: State that the status line is `DIAGNOSIS: V-[1-5] <path>` and that callers match that form; or give the check script's output its own prefix in a 0001 follow-up.
- Concern: api-contract,logic-correctness (Vocabulary drift)

## r-014 · low · compliance · `skills/utils/diagnose/SKILL.md:161`
When diagnose runs as a step of fix, it prints the plain-terms sentence after the status line, so the status line is not the trailing line. Fix's routing says 'Diagnose ends with `DIAGNOSIS: …`'.

- Why: REPORTING.md requires the headline to stay last when an orchestrator parses the trailing line, and the diagnose and fix texts disagree on where the line sits.
- Fix: In driven mode (run as a step of another skill), put the `In plain terms:` line before the `DIAGNOSIS:` line, per REPORTING.md.
- Concern: api-contract (Wrong protocol semantics)

## r-015 · medium · design · `skills/utils/diagnose/SKILL.md:23`
Diagnose's Input demands exactly one of a ticket key or a description, but defines nothing for both together. Its only in-repo caller, fix, hands over the key and the intake's repro steps and symptom.

- Why: Every ticketed fix run sends an input combination the contract calls invalid but does not reject or resolve, so key-vs-description precedence and the Work id derivation are left to guesswork.
- Fix: Either define a key plus context as valid (key wins for Work id, the description is repro context), or reject both at intake; align fix Phase 1 step 1 to match.
- Concern: api-contract,logic-correctness (Easy to misuse)

## r-016 · medium · design · `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md:109`
Size-call rows for one diagnosis can sit in both the requirements-grill and the solution-grill sections. The overwrite rule only works inside one section, and the row carries only a date, so nothing says which call wins.

- Why: The planned reader, fix (0008 AC-011), can act on a call that a later grill overturned.
- Fix: State one cross-section rule, e.g. the latest row wins across sections, or a later grill marks the earlier row superseded.
- Concern: api-contract (Easy to misuse)

## r-017 · medium · spec · `skills/utils/diagnose/SKILL.md:158`
The skill calls `tracker_get` at Input before it writes any file, and narrows the bullet from 'call' to 'write'. D-12 makes that reinterpretation but records 'Supersedes: none', so the AC-008 passage is not overridden on the record.

- Why: DECISIONS.md says a Supersedes line overrides only the exact passage it quotes; the literal bullet still binds.
- Fix: Append a new decision entry whose Supersedes line quotes the contract bullet 'before any tracker or forge call', or meet the literal text.
- Concern: spec-fidelity (Acceptance: DIAGNOSIS.md is written ... before any tracker or forge call (PRD AC-008))

## r-018 · medium · test · `scripts/tests/test_behavior_registry_gate.py:78`
The no-fix pin only matches the literal, case-sensitive substrings of the old description, so a description that still promises a fix in other words passes.

- Why: The test is named 'promises_no_fix', but a description such as 'reproduce → root cause → fix. Use when…' or '… → Fix → …' gives no problems, so the acceptance bullet 'the description no longer promises a fix or a regression test' is only pinned against the old wording.
- Fix: Fold case and also flag a fix step anywhere in the arrow chain (for example the regex r'→\s*fix\b' plus 'fix\s*→' with re.I), and add a negative case for a trailing '→ fix.' description.
- Concern: test-veracity (Happy-path-only)

## r-019 · low · design · `skills/afk/grill-requirements/SIZE-CALL.md:10`
Both grills accept any DIAGNOSIS.md. The procedure defines an open question only for V-2 and V-3, so a V-1, V-4 or V-5 diagnosis gives undefined grill behaviour.

- Why: The grill can be handed an input it has no question for, and nothing tells it to refuse or bounce that input.
- Fix: Add one line: a diagnosis whose verdict is not V-2 or V-3 is not a grill input; name the verdict and stop.
- Concern: api-contract (Easy to misuse)

## r-020 · low · design · `skills/utils/diagnose/SKILL.md:34`
Two invoker inputs appear only inside Phase 0 steps and are missing from ## Input: a handed-over owned worktree (D-11) and an up-front starting-branch answer.

- Why: A caller reading the Input section cannot learn these inputs exist or what form they take.
- Fix: List both optional inputs under ## Input with their form.
- Concern: api-contract (Undocumented surface)

## r-021 · low · correctness · `skills/utils/diagnose/SKILL.md:33`
Step 4 records the Base commit id before step 5 fetches the Base.

- Why: A fetch that advances the Base leaves the worktree on a different commit from the recorded one, and Phase 7.1's diff check fails.
- Fix: Fetch first, then record the Base commit as the commit the worktree is cut from.
- Concern: logic-correctness (concurrency/ordering)

## r-022 · low · correctness · `skills/utils/diagnose/SKILL.md:32`
A re-run reuses the recorded diagnosis worktree, but fix (ad-hoc) applies its uncommitted product change there; Phase 7.1's 'product code is unchanged' check then fails.

- Why: Fix:37 makes the diagnosis worktree the fix checkout outside feature sessions.
- Fix: Name how a re-run treats fix edits in the worktree.
- Concern: logic-correctness (concurrency/ordering (re-run state))

## r-023 · low · test · `scripts/tests/test_behavior_registry_gate.py:98`
The negative test asserts only the number of problems (3), not which checks fired.

- Why: A count can stay at 3 when one check breaks and another starts firing wrongly, and a failure does not say which pin regressed.
- Fix: Assert the exact list: ['description promises \'fix →\'', 'description promises \'regression-test\'', 'names removed text \'Phase 6 reports\''].
- Concern: test-veracity (Assertion roulette)

## r-024 · low · test · `scripts/tests/test_behavior_registry_gate.py:96`
Two of the five pinned strings, 'regression test' and 'Phase 5 — Fix', have no negative case, so a typo in either goes unnoticed.

- Why: The fixture contains only 'fix →', 'regression-test' and 'Phase 6 reports', so a check that never matches anything still passes both tests.
- Fix: Add parameterized negative cases, one fixture per pinned string, and assert the matching problem message for each.
- Concern: test-veracity (Happy-path-only)

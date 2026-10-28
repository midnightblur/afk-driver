# Review — 0006-fix-procedure round 4

- policy: lean · delta round 4 (e3718b2..63c4b00), scope-escalated (rounds 2 and 3 each left a sibling passage stale) · activated: delta-sweep, consistency-sweep (scope escalation, 41 fixed keys), test-veracity (delta edits test code) · skipped: fix-owner specialists (round 3 had no critical or high finding), logic-correctness (delta 39 lines in 3 files), scope-and-impact (inline Scope grep: every path is in Scope or added by D-41), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 13 upheld / 0 downgraded / 0 dropped (each finding re-read against the cited lines)
- verdict: advisory — 0 high, 6 medium, 7 low
- shape: copies of corrected facts outside the delta (fix skill status table and intake, ledger format, decision ledger and spec cells); one sweep closes them
- Gate outcome: all 13 fixed in place (f042-f054); D-43 records the spec, contract and ledger corrections
- head: 63c4b00c36683033e8325ec54a17c67a098029c7
- counts: crit=0 high=0 med=6 low=7

## r-001 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:223`
The new Live tiers rule applies 'in any step', and step 6 runs a live api or e2e scenario red-then-green, so step 6 can now return `blocked`. The results table still limits `blocked` to steps 1-5, the Record rows Runs and Edits leave out step 6's runs and its in-place scenario edit, and fix Phase 2.5 has no route for a `blocked` return from step 6.

- Why: This is the sibling-passage pattern the round escalated for: skills/afk/fix/IN-PLACE-FIX.md:43-46 now says a live check in any step with no instance or restart command returns `blocked`, but the results table (:223), the Record (:201, :203) and the caller's step-6 phase (skills/afk/fix/SKILL.md:51) still describe the procedure from before the delta, when step 6 could not stop it.
- Fix: Change the `blocked` row to 'steps 1-6' (or 'any step under Live tiers'). Set Runs to 'steps 1, 4, 6' and Edits to 'steps 3, 4, 6'. In fix Phase 2.5 add: 'A `blocked` return → report `blocked`, naming it.'
- Concern: delta-sweep

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:14`
The delta makes the invoker the only source of the running instance and restart command. But the skill's Argument and Phase 0 intake never take or ask for either one. A human who runs `/afk:fix <KEY>` names neither, so every live tier ends `blocked`, including step 5's required check in the running UI for any UI-visible bug. That is the same dead end f037 reported, now reached through a different source.

- Why: An instruction the agent cannot carry out is a defect (brief). Before this slice, fix Phase 2 confirmed a UI-visible bug in the running UI with no restart input. Now skills/afk/fix/IN-PLACE-FIX.md:142-143 requires that check and :45-46 blocks it without a restart command, and skills/afk/fix/SKILL.md:18-27 gives the invoker no place to name one.
- Fix: Add a Phase 0 intake item: 'Running instance — the instance a live tier runs against and the command that restarts it on the working tree; ask the invoker when the bug class needs a live tier and none was named.' Or reword line 14 to name where the values come from in a human invocation.
- Concern: delta-sweep,consistency-sweep

## r-003 · medium · correctness · `skills/afk/fix/SKILL.md:55`
Phase 1 still sends a diagnose-time design conflict to 'route per Phase 3', but Phase 3 now only routes what procedure step 7 records and, on design_conflict, keeps a fix in the tree and names it. At Phase 1 there is no fix and no step 7 record, and the routing target (grill-solution, to-sdd) now lives only in the procedure's step 7 table.

- Why: Fixed keys f028/f010 rewrote Phase 3's design_conflict branch: skills/afk/fix/SKILL.md:55 "Its `design_conflict` → keep the fix in the tree (skip the procedure's revert), run Phase 3.5, then report `design_conflict`, naming the kept fix"; the sibling pointer that lands there was not updated.
- Fix: In Phase 1 step 2 replace 'route per Phase 3' with the target itself, e.g. 'report `design_conflict`, naming the decision; a superseding ADR comes from `/afk:grill-solution` → `/afk:to-sdd`' (no fix to keep, no step 7 to run).
- Concern: consistency-sweep

## r-004 · medium · spec · `skills/afk/fix/IN-PLACE-FIX.md:17`
Fixed keys f005/f029 added the running instance and its restart command to what the caller hands over, and a live check without them returns `blocked`. The specs still give the procedure's input as the failure alone, and the contract requires the SDD §8 interface unmodified. No decision entry (D-40..D-42) records the wider interface. A later caller built from the SDD will hand over no restart command, and every live tier will end `blocked`.

- Why: docs/afk/small-lane/plan/0006-fix-procedure.md:34 "Implements the public interface of SDD §8 row \"shared fix procedure (beside fix)\" unmodified (SDD §8)"; plugin-root DECISIONS.md protocol: a spec passage is overridden only by a Supersedes line quoting it.
- Fix: Add a decision entry that supersedes SDD §3's 'Input and validation' cell and SDD §8's interface cell, naming the extra hand-over (paths, tiers, spec folder, running instance and restart command), or edit those SDD cells under the decision protocol.
- Concern: consistency-sweep

## r-005 · medium · test · `scripts/tests/test_fix_procedure.py:75`
Possible false green: the cited-step test only checks that each cited number is some heading number in IN-PLACE-FIX.md, so the likely drift (a step inserted and the rest renumbered) leaves every pointer citing an existing but wrong step and the suite stays green. Mutation probe: a new step 2 was inserted into a copy and steps 2-9 renumbered to 3-10, so 'step 6' now names Run every tier and 'step 8' names Find stale artifacts. All 19 non-hook tests still passed.

- Why: The test's own comment states the contract it guards: scripts/tests/test_fix_procedure.py:55-56 "A cited procedure step: ... every cited number must be a procedure step." The pointers it protects send readers to a step by number (skills/afk/fix/SKILL.md:51 "Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 6." under '## Phase 2.5 — Escape analysis'). Checklist: test-veracity.md 'Assertion strength' — assert the behaviour, not a weaker proxy.
- Fix: Pin the step list so any renumbering fails: assert re.findall(r"^### (\d+)\. (.+)$", PROCEDURE text, re.M) equals the exact ordered list [("1","Re-run once"), ("2","Record the failing path"), ... ("9","Return")]. Or map each pointer citation to the heading it must name (for example SKILL.md Phase 2.5 -> 'Escape analysis', LEDGER-FORMAT.md 'escape-analysis step' -> 'Escape analysis') and assert the heading of the cited number matches.
- Concern: test-veracity

## r-006 · medium · test · `scripts/tests/test_fix_procedure.py:95`
Possible false green: the flaky check uses re.DOTALL with '.*', so it matches when 're-run passes' appears anywhere before any `flaky` in step 1. It does not tie the `flaky` return to the pass branch. Mutation probe: the two branches were swapped in a copy (pass -> step 2; fail -> record disabled/flaky, run step 8, return `flaky`), which inverts acceptance bullet 1, and the test still passed. It also never asserts the D-41 (c) parts of that branch: the miss class `disabled/flaky` and the step 8 run.

- Why: docs/afk/small-lane/plan/0006-fix-procedure.md:27 "a failure that passes on that re-run returns `flaky` and changes no product code (PRD AC-029)"; docs/afk/small-lane/plan/DECISIONS.md:286 D-41 "(c) record and run". Checklist test-veracity.md 'Assertion strength'.
- Fix: Assert on the single pass bullet, not across the step. Take the line block that starts with '- The re-run passes' and runs up to the next '- ' bullet, then check that it holds `flaky`, `disabled/flaky`, 'step 8' and 'Change no code'. Also check that the '- The re-run fails' bullet holds 'step 2' and no `flaky`.
- Concern: test-veracity

## r-007 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:172`
The fix skill's Phase 4 status table still defines design_conflict as any change to a frozen SDD/ADR decision. Fixed key f007 narrowed it to a one-way door or a tie (a two-way door is recorded and the fix goes on), and f028 made the skill keep the fix uncommitted until the superseding ADR lands; the table states neither.

- Why: Corrected text: skills/afk/fix/IN-PLACE-FIX.md:172-174 "Classify a change to a frozen SDD decision by `DECISIONS.md` as in step 3: a one-way door or a tie → return `design_conflict`; a two-way door is recorded, and the SDD goes into the record as stale."
- Fix: Reword the row: 'The fix needs a frozen SDD/ADR decision changed, and that change is a one-way door or a tie; the fix stays uncommitted in the tree until the superseding ADR from `/afk:grill-solution` lands.'
- Concern: consistency-sweep

## r-008 · low · correctness · `skills/afk/lessons/LEDGER-FORMAT.md:80`
The miss-class mapping section still says the miss class comes from the escape-analysis step (step 6) and that every fix lesson's class derives from it. After fixed keys f014/f031 step 1 also names `disabled/flaky`, and after f008 a lesson from a stale artifact alone takes `wrong-design` with no miss class. That rule lives only in WORKFLOW-FEEDBACK.md, not in the file that calls itself the one home for the mapping.

- Why: Corrected facts: skills/afk/fix/IN-PLACE-FIX.md:205 "| Miss class | steps 1, 6 |"; skills/afk/fix/WORKFLOW-FEEDBACK.md:58-59 "a lesson from a stale artifact alone takes `--class wrong-design` and no `--miss`". LEDGER-FORMAT.md:3-5 "The **one home** for ... class enum, miss-class mapping ... Every other file points here and restates nothing."
- Fix: Change LEDGER-FORMAT.md:79-82 to 'The shared fix procedure (`skills/afk/fix/IN-PLACE-FIX.md` steps 1 and 6) names a miss class ...', add a row or sentence 'a stale artifact alone, no miss class → `wrong-design`', and have WORKFLOW-FEEDBACK.md point at it.
- Concern: consistency-sweep

## r-009 · low · spec · `scripts/tests/test_fix_procedure.py:198`
Fixed key f015 showed that hook-smoke.sh does not touch the lesson scripts, and f022 showed that the wiring gate does not prove each pointer. Both were fixed by adding pytest checks. The contract's Verification cells still credit hook-smoke.sh with 'lesson append and digest' and credit the static wiring gate with pointer reachability.

- Why: Fixed keys f015 and f022 (fix locators scripts/tests/test_fix_procedure.py:38 and :55) moved the proof into this test file. The contract text a reader checks against still names the old tools.
- Fix: Edit contract 0006 '## Verification' (or record it in the decision ledger): drop '(lesson append and digest)' from the hook-smoke.sh cell and credit `scripts/tests/test_fix_procedure.py` with the lesson lockstep and the pointer checks.
- Concern: consistency-sweep

## r-010 · low · spec · `docs/afk/small-lane/plan/DECISIONS.md:295`
D-42's undo line says to 'add the catalog clause back' to the Caller's paths rule. After fixed key f038 the rule still has a catalog clause, now saying the opposite ('is no exception'). The undo cannot be followed as written.

- Why: Root DECISIONS.md protocol: the To reverse line must let a reader undo the decision. The current rule is skills/afk/fix/IN-PLACE-FIX.md:28-30.
- Fix: This is an append-only ledger, so add a short entry (or amend in the next one): 'D-42 To reverse (a): replace the sentence "A catalog scenario that step 4 or step 6 calls for outside those paths is no exception." with D-41's exemption.'
- Concern: consistency-sweep

## r-011 · low · spec · `skills/afk/fix/IN-PLACE-FIX.md:29`
Possible uncorrected copy: D-42 made an in-place fix return `blocked` when it needs a catalog scenario outside the caller's paths, which includes an adversary finding whose catalog sits outside them. PRD row B-5 and AC-025 still promise an in-place fix for every adversary finding, and D-42's Supersedes line quotes only D-41.

- Why: docs/afk/small-lane/PRD.md:113 "AC-025 For every row of catalog B, the diagnosis, fix, approver and ticket columns hold for a bug found that way."; plugin-root DECISIONS.md: a Supersedes line overrides only the passage it quotes.
- Fix: Add PRD B-5's fix cell and AC-025 to D-42's Supersedes in a follow-up ledger entry, for the case of a catalog outside the caller's paths. Alternatively, state in the caller contract that such a finding leaves the in-place lane.
- Concern: consistency-sweep

## r-012 · low · spec · `skills/afk/fix/IN-PLACE-FIX.md:158`
Fixed key f010 changed who reconciles: the procedure now runs no owning skill and only records stale artifacts, and the caller routes them. No decision entry records this split. D-40 (c) still frames the procedure as reconciling some artifacts and leaving others 'it cannot reconcile'.

- Why: Corrected text: skills/afk/fix/IN-PLACE-FIX.md:157-159 "record each stale artifact with its owning skill from the table below; run no owning skill here." The slice's specs (contract Acceptance AC-023 bullet, SDD §14 'spec reconciliation') carry no statement that in-place callers must route the record's stale artifacts.
- Fix: Record the split in the ledger: 'the procedure records stale artifacts and runs no owning skill; every caller routes the Stale artifacts field', superseding D-40 (c)'s 'a stale artifact it cannot reconcile' wording, so the later caller slice inherits it.
- Concern: consistency-sweep

## r-013 · low · test · `scripts/tests/test_fix_procedure.py:57`
Possible gap: CITED_STEP still misses a bare 'step N' that follows a procedure citation in the same sentence. Examples: WORKFLOW-FEEDBACK.md 'procedure steps 1 and 6 named no miss class and step 7 recorded', and SKILL.md 'the step 1 failure'. A wrong number there passes. Mutation probe: 'step 7' was changed to 'step 12' in a copy of WORKFLOW-FEEDBACK.md and the suite stayed green.

- Why: scripts/tests/test_fix_procedure.py:55-56 "every cited number must be a procedure step"; skills/afk/fix/WORKFLOW-FEEDBACK.md:10 names a procedure step the pattern does not reach.
- Fix: Cover the continuation form: after a CITED_STEP match, also scan the rest of that sentence for '\bsteps?\s+(\d+)'. Or reword the two passages to 'procedure step 7' / 'procedure step 1 failure' so the existing pattern reaches them, and add a mutation-style case to the test for the bare form.
- Concern: test-veracity

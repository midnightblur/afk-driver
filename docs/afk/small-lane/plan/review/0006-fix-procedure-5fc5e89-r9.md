# Review — 0006-fix-procedure round 9

- policy: lean · delta round 9 (5fc5e89..f54f672), scope-escalated (copies again in round 8) · activated: delta-sweep, consistency-sweep (scope escalation), test-veracity (escalated roster; read the whole test file), logic-correctness (delta touches 2 skill files) · skipped: fix-owner specialists (round 8 had no critical or high finding), scope-and-impact (every path is in Scope or added by a ledger entry), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 10 upheld / 0 downgraded / 0 dropped (12 raw findings, 2 merged: delta-sweep-001 and logic-correctness-002 into r-001)
- verdict: advisory — 0 high, 5 medium, 5 low
- shape: siblings of round 8 fixes left partial (the second ask covered steps 4 and 5 only and needed both inputs missing; the Decisions row had no writer and no reader; the reuse rule matched any entry on the decision; the drop sentence read as covering step 4's temporary revert; two phases still stated optional values unconditionally); three test assertions weaker than the facts they pin (results in the step prose, callers named in plain words, the trace row's stage)
- Gate outcome: 10 fixed in place (f085-f094); the Decisions row is dropped rather than wired, since no caller reads it and the ledger itself is the record of a decision
- head: f54f672072dd2b00ec499c1d59830be518d7f04e
- counts: crit=0 high=0 med=5 low=5

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:28`
Fixed key f081 made the fix skill ask the present human for the instance and restart command before a live check runs with none named, but the ask-again names only procedure steps 4 and 5. Phase 1 step 3 also runs a live check under "Live tiers" (the diagnosis's failing test, which line 33 steers toward an api or e2e/browser loop), and procedure step 6 (Phase 2.5) re-runs an api or e2e scenario red-then-green; with none named, both still end `blocked` with no ask.

- Why: f081 fix: "ask for the instance and restart command whenever procedure step 4 or 5 is about to run a live check and the invoker named none. End `blocked` only when the invoker cannot supply them." The same rule applies at every site that runs a check under IN-PLACE-FIX.md "Live tiers" (IN-PLACE-FIX.md:43 "A check that runs against the running instance runs, in any step, only after the caller's restart command has restarted that instance"). Pattern used: enumerated every site in skills/afk/fix/*.md naming `live`, `running instance` or `Live tiers` (grep -i), instead of the "step 4 or 5" phrase.
- Fix: In SKILL.md:28 replace "when procedure step 4 or 5 is about to run a live check the invoker named neither for" with "whenever a live check (Phase 1 step 3, or procedure step 4, 5 or 6) is about to run and the invoker named neither".
- Concern: consistency-sweep,delta-sweep,logic-correctness
- Key: 0006-fix-procedure/f085 — fixed

## r-002 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:181`
The new reuse rule fires when plan/DECISIONS.md holds any entry 'for that decision', not only an entry recording this same change. A fix that changes a frozen SDD decision an earlier slice already superseded in another direction then reuses the old entry and writes no entry for the new change. Example: D-3 changed SDD section 8 row X to return 404; this fix, a two-way door, changes the same row to return 410; step 7 finds D-3 'for that decision', reuses it, and the 410 change reaches neither the ledger nor the end-of-run audit.

- Why: DECISIONS.md:52 "A `Supersedes:` line overrides the exact spec passage it quotes — build on the recorded call; a new fork on the same ground gets a new entry, never an edit." DECISIONS.md:31 "An auto-taken decision is a recommendation the human never saw — record it as one they can audit and reverse." The case the reuse targets is narrower: fixed key f073 names the entry fix Phase 1 step 2 recorded for this same fork.
- Fix: Narrow the condition: 'when plan/DECISIONS.md already holds an entry that records this same change (the caller recorded it before the procedure ran), reuse it instead of writing a new entry; a different change to that decision gets a new entry.'
- Concern: logic-correctness
- Key: 0006-fix-procedure/f086 — fixed

## r-003 · medium · spec · `skills/afk/fix/IN-PLACE-FIX.md:214`
Fixed key f078 added a Decisions field to the record the procedure publishes to its callers, but no caller reads it, and no step text writes it: the delta removed step 7's "put its id into the record", and step 3 never had it. Consumers checked: the fix skill (Phase 4 report names only miss class and lesson id), contract 0009 Acceptance with the D-53 and D-55 additions (Stale artifacts and hand-over only), contract 0008 (consumes the results table only).

- Why: f078: "no caller reads that id"; its fix asked to "write the id there in both cases". Every other record field is written by an explicit step sentence (IN-PLACE-FIX.md:156 "Put the miss class into the record.", :195 "Put the lesson id into the record."). Root AGENTS.md wiring rule via user CLAUDE.md: "Anything you create ... is not done until its consumer is named and verified to exist." Pattern used: grep of `Decisions` and `DECISIONS` over skills/afk/fix/*.md and plan contracts 0008, 0009.
- Fix: Either add "put its id into the record's Decisions field" to the two-way-door sentences of step 3 (IN-PLACE-FIX.md:102-103) and step 7 (:179-181) and name a reader (a fix SKILL.md Phase 4 line, or a 0009 Acceptance bullet through a ledger entry like D-53), or drop the Decisions row.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f087 — fixed

## r-004 · medium · test · `scripts/tests/test_fix_procedure.py:127`
Possible false green: the seven-results test reads only the result table, so a step that returns an eighth result in its prose passes. Mutation probe on a scratch copy: adding "→ return `cannot_reproduce`" to step 1 left the test green.

- Why: docs/afk/small-lane/plan/0006-fix-procedure.md:29 "returns exactly one of `fixed`, `fail`, `blocked`, `design_conflict`, `needs_decision`, `adversary_fail`, `flaky` (SDD §3)"; the steps, not the table, are what an agent follows when it returns (skills/afk/fix/IN-PLACE-FIX.md:199 "Return the result with the record.").
- Fix: Also collect every result returned in the step prose (e.g. re.findall(r"return\s+`([a-z_]+)`", text before "## Record")) and assert that set is a subset of RESULTS; keep the table-equality assert.
- Concern: test-veracity
- Key: 0006-fix-procedure/f088 — fixed

## r-005 · medium · test · `scripts/tests/test_fix_procedure.py:134`
Possible false green: the no-callers test matches only the slash-command spellings in CALLERS, so naming a caller in plain words passes. Mutation probe on a scratch copy: adding "Report the result to execute's Step 10 and to autopilot." to step 1 left the test green.

- Why: docs/afk/small-lane/plan/0006-fix-procedure.md:32 "The procedure names none of its callers (SDD §8)"; AGENTS.md:25 "Downstream is blind to upstream. A skill invoked later must not name the skill/stage calling it".
- Fix: Match each caller by its bare name as a word as well (e.g. r"\b(execute|preflight|autopilot|smoke-test)\b" plus the slash forms), with an allow-list only for owning-skill names the procedure legitimately routes to.
- Concern: test-veracity
- Key: 0006-fix-procedure/f089 — fixed

## r-006 · low · correctness · `RATIONALE.md:63`
Possible wrong drop. The new RATIONALE.md wording allows a drop for any uncommitted line 'a revert removed'. Step 4 of the procedure reverts the fix for a while and then restores it, and the Record's Rationale row says steps 3–4 set the entries 'a revert dropped'. An agent can read this as: drop the entries at step 4's revert. The restored comment lines then have no rationale, and verify still passes. The final drops happen only at the revert before `design_conflict`, `needs_decision` and `flaky` (steps 1, 3 and 7), and that row does not name those steps.

- Why: D-54 (docs/afk/small-lane/plan/DECISIONS.md) limits the widening to the procedure's revert "before `design_conflict`, `needs_decision` and `flaky`"; IN-PLACE-FIX.md:219-222 "`design_conflict`, `needs_decision` and `flaky` leave no edit of the fix in the working tree, tests included: before returning, revert each edit and run `rationale-drop`"; RATIONALE.md:64 "Verify passes without a dropped entry".
- Fix: In RATIONALE.md step 6, write "or whose uncommitted line a revert discarded for good". In the IN-PLACE-FIX.md Rationale row, set 'Set by' to "steps 3–4; the revert before `design_conflict`, `needs_decision` or `flaky`".
- Concern: delta-sweep
- Key: 0006-fix-procedure/f090 — fixed

## r-007 · low · correctness · `AGENTS.md:119`
The reworded catalog row gets the order wrong. It puts the workflow lesson before spec reconciliation. The fix skill runs reconciliation (Phase 3, procedure step 7) before the workflow lesson (Phase 3.5, procedure step 8).

- Why: skills/afk/fix/SKILL.md:57 "Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 7, then route each stale artifact it records to its owning skill" (Phase 3) precedes SKILL.md:61 "Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 8." (Phase 3.5).
- Fix: Reword the row: "diagnose, then the shared fix procedure (`IN-PLACE-FIX.md`, read in place by agent callers) for coverage and escape analysis, spec reconciliation of the stale artifacts it records, then the workflow lesson".
- Concern: delta-sweep
- Key: 0006-fix-procedure/f091 — fixed

## r-008 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:46`
Possible misclassified result: the new restart-failure exit returns `blocked` in every step, including a restart on the fixed tree in step 4's restored run or step 5. When the fix itself stops the app from starting (for example, it adds a dependency the unit tier never wires), the procedure reports `blocked`, which tells the caller the procedure could not go on and the failure stays unfixed, instead of `fail`, which tells it the fix did not hold. The fix's edits stay in the tree either way.

- Why: skills/afk/fix/IN-PLACE-FIX.md:230-231 "`fail` | a check other than an adversary reproduction stays red after the fix (step 5) | The fix did not hold"; "`blocked` | the procedure cannot go on ... | The failure stays unfixed". A restart that succeeded on the reverted tree and fails on the fixed tree is evidence against the fix, not an environment blocker.
- Fix: Split the exit: a restart that fails on a tree without the step 3 fix → restore the fix, then `blocked`; a restart that fails on a tree with the fix → `fail`, naming the restart and its output.
- Concern: logic-correctness
- Key: 0006-fix-procedure/f092 — fixed

## r-009 · low · correctness · `skills/afk/fix/SKILL.md:81`
Fixed keys f075 and f079 made Phase 4 add the miss class and the lesson id only when the record holds them, because procedure step 6 can name no miss class and step 8 can record no lesson. Phase 2.5 and Phase 3.5 still state both unconditionally.

- Why: f079: "Phase 2.5 runs procedure step 6, which skips a pure unit or logic bug and names no miss class ... an agent must either make one up or ignore the rule." WORKFLOW-FEEDBACK.md:9-11 skips step 8 when "the procedure's record holds no miss class and no stale artifact". Pattern used: grep of "Phase 4" in skills/afk/fix/SKILL.md, reading each sentence that hands a value to the report.
- Fix: SKILL.md:53 "Carry the miss class, when step 6 named one, into Phase 4's report."; SKILL.md:61 "Report the lesson id, when step 8 recorded one, in Phase 4."
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f093 — fixed

## r-010 · low · test · `scripts/tests/test_fix_procedure.py:59`
Possible weak check: the stale-artifact trace test asserts only that each row's first-cell label exists, not the stage or skill the row routes to, so the pairing lives only in the test's own STALE_TRACE dict. Mutation probe: routing the PRD row to architecture / grill-solution left it green.

- Why: skills/afk/fix/WORKFLOW-FEEDBACK.md:20-22 "Map the miss class ... (or a stale artifact the record holds) to the AFK stage that under-specified the guard" — the stage is the fact the row carries; the label alone is never read by an agent.
- Fix: Pin each stale-artifact row whole: assert the expected stage cell beside each label (e.g. STALE_TRACE maps name -> (label, stage)), matching what step 7's owning-skill column names.
- Concern: test-veracity
- Key: 0006-fix-procedure/f094 — fixed

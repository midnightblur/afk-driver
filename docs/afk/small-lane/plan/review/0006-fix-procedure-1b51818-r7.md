# Review — 0006-fix-procedure round 7

- policy: lean · delta round 7 (1b51818..b24fe99), scope-escalated (copies again in round 6) · activated: delta-sweep, consistency-sweep (scope escalation, 70 fixed keys), test-veracity (delta edits test code), logic-correctness (delta touches 5 files) · skipped: fix-owner specialists (round 6 had no critical or high finding), scope-and-impact (every path is in Scope or added by D-41 or D-44), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 6 upheld / 0 downgraded / 0 dropped (6 raw findings, 0 merged)
- verdict: advisory — 0 high, 1 medium, 5 low
- shape: siblings of round 6 fixes left stale (the Live tiers exit while the fix is reverted, step 7's one-way door, the Phase 4 lesson-id condition, a second ledger entry for one decision); one consumer contract (0009) missing duties D-43 gave the callers
- Gate outcome: 5 fixed in place (f072-f075, f077; D-53 records 0009's duties); f076 (low compliance) deferred to the feature gate under the lean policy
- head: b24fe995fdaa12683244cdb262899874bfebc889
- counts: crit=0 high=0 med=1 low=5

## r-001 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:118`
The delta made the two red-then-green exits of step 4 and step 6 restore the step 3 fix before returning `blocked`, but a third `blocked` exit can fire on the same reverted run and still leaves the fix out. The test that step 4 adds at a live tier runs first with the fix reverted, under "Live tiers". When the caller handed over no instance or no restart command, "Live tiers" returns `blocked` at that point, and nothing says to restore the fix first. The same applies to a live scenario in step 6.

- Why: Delta-sweep item: "a fix applied at one site while a sibling path keeps the old behaviour" (skills/afk/review/checklists/delta-sweep.md:8). The procedure's record rule says `blocked` keeps the fix in the tree: skills/afk/fix/IN-PLACE-FIX.md:218-219 "`fail`, `adversary_fail` and `blocked` leave the edits made so far, listed under Edits." On this path the Edits field names a fix that is no longer in the working tree.
- Fix: State the restore once, for every exit: "Any return while the step 3 fix is reverted (step 4, step 6, or the Live tiers rule) restores the fix first." Alternatively, check in step 4 and step 6 that the instance and the restart command were handed over before reverting the fix.
- Concern: delta-sweep
- Key: 0006-fix-procedure/f072 — fixed

## r-002 · low · correctness · `skills/afk/fix/SKILL.md:37`
The new two-way-door branch in Phase 1 records the wrong binding SDD decision in plan/DECISIONS.md, applies it, and later Phase 3 runs procedure step 7, which classifies the same frozen-SDD change again and records it again. Example: a feature-session V-3 whose cause is a wrong SDD section 8 decision, classified a two-way door, ends with two ledger entries (D-n at Phase 1, D-n+1 at Phase 3) for one fork.

- Why: DECISIONS.md:52 "a new fork on the same ground gets a new entry" covers only a new fork, and the ledger is append-only (DECISIONS.md:35 "Append-only: never edit or delete a prior entry"), so the duplicate cannot be removed; the human's end-of-run audit (DECISIONS.md:53) lists the same decision twice.
- Fix: In IN-PLACE-FIX.md step 7, record a two-way door only when plan/DECISIONS.md holds no entry for that decision yet (an existing entry: put its D-id into the record), or have fix Phase 3 hand step 7 the D-id Phase 1 recorded.
- Concern: logic-correctness
- Key: 0006-fix-procedure/f073 — fixed

## r-003 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:177`
Fixed key f069 made step 3's one-way-door branch put the SDD or ADR into the record as a stale artifact before it runs step 8, so step 8's skip rule (no miss class and no stale artifact) cannot drop the lesson. Step 7's sibling branch says only 'run step 8, then return design_conflict' and attaches 'the SDD goes into the record as stale' to the two-way door alone. After the No-fix revert, 'stale only when the fix changed something it asserts' lets an agent leave the record empty, and step 8 then skips whenever step 6 named no miss class.

- Why: The corrected fact (IN-PLACE-FIX.md:102-104): "A one-way door or a tie that changes a binding SDD or ADR decision → put that SDD or ADR into the record as a stale artifact (owning skill: step 7's table), run step 8, then return `design_conflict`." Step 8's gate (WORKFLOW-FEEDBACK.md:9-11): "Skip also when the procedure's record holds no miss class and no stale artifact". Fix Phase 3 (SKILL.md:57) promises "the lesson id step 8 recorded" on this path.
- Fix: Reword IN-PLACE-FIX.md:176-178 to match step 3: 'a one-way door or a tie → put the SDD into the record as stale, run step 8, then return `design_conflict`; a two-way door is recorded, and the SDD goes into the record as stale.'
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f074 — fixed

## r-004 · low · correctness · `skills/afk/fix/SKILL.md:57`
Fixed key f066 made Phase 3 skip Phase 3.5 on a design_conflict, because procedure step 7 already ran step 8. Step 8 can therefore record a lesson without Phase 3.5 running. Phase 4 still keys the OUTCOME line's lesson id on 'Phase 3.5 ran', the old equivalence, so the `[lesson: L-NNNN]` bracket is not required on that path.

- Why: Corrected fact, SKILL.md:57: "skip Phase 3.5 (procedure step 7 already ran procedure step 8), and report `design_conflict`, naming the kept fix and the lesson id step 8 recorded". Stale sibling, SKILL.md:81: "Phase 3.5 ran → append the **lesson id** so the workflow-improvement lesson isn't lost".
- Fix: Change SKILL.md:81 to key on the record: 'procedure step 8 recorded a lesson → append the **lesson id**'.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f075 — fixed

## r-005 · low · compliance · `AGENTS.md:119`
Fixed keys f010, f053 and f063 (D-43 (b), D-44 (b)) corrected who reconciles specs: the procedure records each stale artifact and runs no owning skill, and its caller reconciles. The AGENTS.md skill-catalog row that this slice rewrote still lists spec reconciliation as part of the shared fix procedure that agent callers read in place.

- Why: IN-PLACE-FIX.md:162-163 "record each stale artifact with its owning skill from the table below; run no owning skill here"; DECISIONS.md:308 restates contract 0006 as "The procedure keeps escape analysis and the workflow lesson, and records each stale artifact for its caller to reconcile (PRD AC-023)".
- Fix: Reword the row: '... diagnose, then the shared fix procedure (`IN-PLACE-FIX.md`, read in place by agent callers): coverage, escape analysis, the workflow lesson; the skill reconciles the stale specs the procedure records'.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f076 — deferred gate=feature

## r-006 · medium · spec · `skills/afk/fix/IN-PLACE-FIX.md:163`
Fixed keys f010 and f053 (D-43 (b)) moved stale-artifact reconciliation from the procedure to every caller. Fixed keys f025, f038 and f052 (D-43 (c)) limited B-5's in-place fix to the caller's paths. Contract 0009, the consumer contract of the in-place callers, consumes only the results table. It has no bullet that routes the record's Stale artifacts field, and its B-5 bullet still promises the adversary reproduction as a permanent test with no caller's-paths limit. No wiring IOU names either change, and D-43 names 0009 only for its hand-over part (a).

- Why: D-43 (b), DECISIONS.md:300 "Every stale artifact goes to the caller; no artifact is one the procedure 'cannot reconcile'."; D-43 Supersedes (DECISIONS.md:301) PRD B-5 "inside the caller's paths; a catalog scenario outside them returns `blocked`"; the user's wiring rule requires a later consumer to carry an IOU anchored to its plan step.
- Fix: Add a ledger entry (or an IOU in .claude/wiring-ious.md) anchored to contract 0009. It names the Stale artifacts record field that each in-place caller must route to the owning skill, and it supersedes 0009's B-5 acceptance wording with D-43 (c)'s caller's-paths limit.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f077 — fixed

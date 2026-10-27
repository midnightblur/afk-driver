# Review — 0006-fix-procedure round 3

- policy: lean · delta round 3 (5693ac2..e3718b2) · activated: delta-sweep, test-veracity (delta edits test code), logic-correctness (delta touches 7 files) · skipped: fix-owner specialists (round 2 had no critical or high finding), scope-and-impact (inline Scope grep: every path is in Scope or added by D-41), api-contract, domain-alignment (no trigger), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level concern ran)
- verdict: advisory — 0 high, 5 medium, 1 low
- shape: a round 2 fix again left a sibling passage stale (the restart rule, the lesson gate); round 4 runs with scope escalation
- Gate outcome: all 6 fixed in place (f036-f041); a Live tiers section now holds the restart rule for every step
- head: e3718b2a9f7b0345accd7be3848325e7d536c008
- counts: crit=0 high=0 med=5 low=1

## r-001 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:108`
Step 4 makes the agent watch each added test fail with the fix reverted and pass with it restored, but the new sentence defers the instance restart to step 5. A live-tier (api/e2e) test cannot give a valid red or green in step 4 without a restart on each tree state, and step 4 has no restart rule.

- Why: The delta rule says a live-tier test runs only on a restarted instance, yet the restart instruction exists only in step 5 (skills/afk/fix/IN-PLACE-FIX.md:133-135), after the revert and restore runs of step 4.
- Fix: State the restart once for every live-tier run in steps 4 and 5 (before each run, including the reverted-fix and restored-fix runs), and make the no-instance or no-restart-command blocked result apply from step 4.
- Concern: delta-sweep

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:14`
The fix skill says the running instance is restarted the way the diagnosis started it, but DIAGNOSIS-FORMAT has no part that records how an instance was started (Reproduction holds test path, command and failing output). With a handed-over DIAGNOSIS.md the restart command cannot be found, so step 5 returns blocked for every live tier.

- Why: skills/afk/fix/IN-PLACE-FIX.md:17-18 requires the caller to hand over the command that restarts the instance; skills/utils/diagnose/DIAGNOSIS-FORMAT.md:23 defines Reproduction as test path, command and failing output, with no start or restart field.
- Fix: Name the source of the restart command (the Reproduction command, else intake context, else ask the human), or add a diagnosis part for it in the same commit.
- Concern: delta-sweep

## r-003 · medium · compliance · `skills/afk/fix/IN-PLACE-FIX.md:28`
The rewritten rule says: Change only the paths the callers work may change, catalog scenarios included. That sentence parses as adding catalog scenarios to the allowed set, the opposite of D-42 (an out-of-paths catalog scenario returns blocked). Only the second sentence disambiguates.

- Why: LANGUAGE.md:19-25 (one instruction per sentence, no ambiguity the reader must guess); docs/afk/small-lane/plan/DECISIONS.md D-42 Chosen (a) blocked.
- Fix: Reword: Change only the paths the callers work may change. A catalog scenario outside them is not such a path; a fix that needs one, or any other path, returns blocked, naming the path.
- Concern: delta-sweep

## r-004 · medium · test · `scripts/tests/test_fix_procedure.py:56`
CITED_STEP is case-sensitive and needs the words "IN-PLACE-FIX.md ... step" or "procedure step". It skips real citations: "Procedure step 7" (capital P), "steps 4 to 8 of the shared fix procedure", "then its step 5". A wrong number there passes, and a file with no match passes as an empty set.

- Why: The delta comment says "the cited numbers must be procedure steps" (scripts/tests/test_fix_procedure.py:55) but the pattern does not reach every citation; checklist assertion strength (skills/afk/review/checklists/test-veracity.md:8-11).
- Fix: Use re.IGNORECASE, also match "steps? N" after "fix procedure" and "its", and assert a non-empty cited set per file. A mutation of "Procedure step 7" to "Procedure step 12" must fail the test.
- Concern: test-veracity

## r-005 · medium · correctness · `skills/afk/fix/IN-PLACE-FIX.md:109`
Step 4 requires each added test to fail with the step 3 fix reverted and pass with it restored. The delta adds that a live-tier test runs only on a restarted instance, but the restart rule and the blocked exit for a missing instance or restart command sit only in step 5, after step 4. A live-tier test in step 4 has no instruction to restart on the reverted tree, so its fails-with-fix-reverted run can hit the stale fixed instance and pass.

- Why: skills/afk/fix/IN-PLACE-FIX.md:106-109 makes the revert and restore watch binding; IN-PLACE-FIX.md:133-136 scopes the restart to step 5 runs. An agent cannot carry out the step 4 watch for a live tier as written.
- Fix: Move the restart clause into step 4 (restart with the caller restart command before each live-tier run, in the reverted and the restored state), or make the step 5 rule cover every live-tier run in steps 4 and 5.
- Concern: logic-correctness

## r-006 · low · correctness · `skills/afk/fix/WORKFLOW-FEEDBACK.md:7`
Step 8 gate now reuses the Unreleased feature signals, but that section still says only that step 7 runs for an unreleased feature, and the Lesson hard rule still says unconditionally to record a workflow lesson (step 8). Both contradict D-42, which narrows the lesson to unreleased-feature fixes.

- Why: docs/afk/small-lane/plan/DECISIONS.md D-42: a shipped feature or a failure from outside the feature own verification records no lesson; AGENTS.md one-fact-one-home rule.
- Fix: Change the section lead to say steps 7 and 8 run only for a fix on an unreleased feature, and add the same condition to the Lesson hard rule or point it at the WORKFLOW-FEEDBACK.md gate.
- Concern: delta-sweep

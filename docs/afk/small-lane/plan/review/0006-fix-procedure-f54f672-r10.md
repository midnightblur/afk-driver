# Review — 0006-fix-procedure round 10

- policy: lean · delta round 10 (f54f672..3810623), scope-escalated (copies again in round 9) · activated: delta-sweep, consistency-sweep (scope escalation), test-veracity (delta edits test code), logic-correctness (delta touches 2 skill files) · skipped: fix-owner specialists (round 9 had no critical or high finding), scope-and-impact (every path is in Scope or added by a ledger entry), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 7 upheld / 0 downgraded / 0 dropped (11 raw findings, 4 merged: delta-sweep-001 and logic-correctness-001 into r-001; delta-sweep-003 and logic-correctness-004 into r-002)
- verdict: advisory — 0 high, 1 medium, 6 low
- shape: siblings of round 9 fixes left stale (the new `fail` exit not routed in Phase 2.5 nor named in the record; the narrowed reuse rule; one unconditional lesson id); two test assertions still narrower than the facts they pin
- Gate outcome: stalemate — round 10 is the cap; f095-f098, f100, f101 stay open with no remediation; f099 (low compliance) deferred to the feature gate under the lean policy
- head: 3810623fcfbd483a71a2ab2f673e6c1edf1ddecc
- counts: crit=0 high=0 med=1 low=6

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:53`
The delta (f092) made a restart that fails on a tree holding the fix return `fail` in any step, and gave fix Phase 2 a route for that `fail`. Phase 2.5 runs procedure step 6, whose live scenario re-run (red, then green with the fix restored) falls under the same rule, but it still routes only a `blocked` return, so a `fail` from step 6 has no route and the skill can go on to Phase 3 and report `fixed`.

- Why: skills/afk/fix/IN-PLACE-FIX.md:43-49 "A check that runs against the running instance runs, in any step, only after the caller's restart command has restarted that instance ... A restart that fails on a tree holding the fix → return `fail`, naming the restart and its output."; IN-PLACE-FIX.md:211 "| Runs | steps 1, 4, 6 |"; SKILL.md:28 lists "procedure step 4, 5 or 6" as live-check sites.
- Fix: SKILL.md:53: "Run [IN-PLACE-FIX.md](IN-PLACE-FIX.md) step 6. A `fail` or `blocked` return → report `blocked`, naming it. ...", the same route Phase 2 got; or state the route once for every phase that runs a procedure step.
- Concern: consistency-sweep,delta-sweep,logic-correctness
- Key: 0006-fix-procedure/f095 — open (stalemate)

## r-002 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:232`
The delta widened the `fail` row's 'Returned when' cell to cover a restart that fails on a tree holding the fix, but the same row's caller-meaning cell still says the record names the red check, and the Record's Reason field lists no restart. For the new case no check ran red; Live tiers says the record names the restart and its output.

- Why: IN-PLACE-FIX.md:48-49 "A restart that fails on a tree holding the fix → return `fail`, naming the restart and its output." Consumers read this row: contract 0009 Produces-consumer "skills/afk/fix/IN-PLACE-FIX.md#In-place fix results — the seven results each caller maps" (docs/afk/small-lane/plan/0009-in-place-callers.md:49) and 0008 (0008-standalone-fix.md:63).
- Fix: Row 232 meaning cell: "The fix did not hold; the record names the red check, or the restart and its output." Record Reason row (line 219): "the blocker, the red check or reproduction, the failed restart and its output, or the fork ...".
- Concern: consistency-sweep,delta-sweep,logic-correctness
- Key: 0006-fix-procedure/f096 — open (stalemate)

## r-003 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:183`
The narrowed reuse rule names only an entry the caller wrote before the procedure ran. Step 3 itself records a two-way door that changes a binding SDD decision, and step 7 then classifies that same SDD change again. Read as the condition, the parenthetical excludes step 3's own entry, so step 7 writes a second ledger entry for one change. Failing input: an in-place caller hands over a failing check; step 3 changes an SDD section 8 row as a two-way door and records it; step 7 finds that entry, which the caller did not write, and records the change again.

- Why: IN-PLACE-FIX.md:104-105 "Classify each fork by `DECISIONS.md` (plugin root). A two-way door is decided, recorded, and the fix goes on." with :105-107 limiting design_conflict to a one-way door or a tie on a binding SDD or ADR decision, so a two-way door on that decision is recorded at step 3; fixed key f073 established that one change gets one ledger entry.
- Fix: IN-PLACE-FIX.md:182-184: "when `plan/DECISIONS.md` already holds an entry recording this same change (written at step 3, or by the caller before the procedure ran), reuse it instead of writing a new entry."
- Concern: logic-correctness
- Key: 0006-fix-procedure/f097 — open (stalemate)

## r-004 · low · correctness · `skills/afk/fix/SKILL.md:57`
The delta made Phase 3.5 report the lesson id only when step 8 recorded one, but Phase 3's design_conflict branch still names "the lesson id step 8 recorded" unconditionally. Step 8 can record none on that path: the capture protocol says not to capture when unsure, and `LESSON_LEDGER_DISABLE=1` makes the append exit without writing. The agent is then told to name an id that does not exist.

- Why: SKILL.md:61 (this delta) "Report the lesson id, when step 8 recorded one, in Phase 4."; IN-PLACE-FIX.md:217 Record row "Lesson | step 8 | the lesson id, when one was recorded"; skills/afk/lessons/CAPTURE.md:23 "When unsure, don't capture."; hooks/lesson-append.sh:21 `[ "${LESSON_LEDGER_DISABLE:-0}" = "1" ] && exit 0`
- Fix: SKILL.md:57: "report `design_conflict`, naming the kept fix and the lesson id, when step 8 recorded one".
- Concern: logic-correctness
- Key: 0006-fix-procedure/f098 — open (stalemate)

## r-005 · low · compliance · `RATIONALE.md:64`
The added words "for good" are an idiom, and they carry the one distinction the sentence needs: a final revert drops the entry, the temporary step 4 revert does not.

- Why: LANGUAGE.md:24 "No idioms, no metaphors, no filler, no rhetorical questions."
- Fix: Write "or whose uncommitted line a revert removed and no later step restored" (or "removed permanently").
- Concern: delta-sweep
- Key: 0006-fix-procedure/f099 — deferred gate=feature

## r-006 · low · test · `scripts/tests/test_fix_procedure.py:131`
Possible false green: the new returned-results check only collects a result written right after the word 'return', so a bad result in the procedure's arrow form, or a second result joined by 'or', passes. Mutation probes on a scratch copy: changing IN-PLACE-FIX.md:29 '→ `blocked`' to '→ `blocked_path`' left the test green, and so did changing step 1 to 'return `flaky` or `cannot_reproduce`'; a typo in the new 'return `fail`' (Live tiers) went red as intended.

- Why: The test is named test_the_procedure_returns_exactly_the_seven_results, and the procedure hands a result back in the arrow form too: IN-PLACE-FIX.md:28-29 "A
fix that needs another path → `blocked`, naming the path."
- Fix: Collect every backticked lower-case token that follows 'return' or '→' in the text before '## Record', including tokens joined by 'or' or ',' (for example re.findall(r"(?:return|→)\s+`([a-z_]+)`(?:\s*(?:,|or)\s*`([a-z_]+)`)*" ...) or a scan of every backticked token in a 'return …' / '→ …' clause), and keep the subset assert.
- Concern: test-veracity
- Key: 0006-fix-procedure/f100 — open (stalemate)

## r-007 · low · test · `scripts/tests/test_fix_procedure.py:138`
Possible weak check: the new bare-name caller check matches 'smoke-test' only with its hyphen, so naming that caller in plain words, as prose would, passes. Mutation probe on a scratch copy: adding 'hand the result to the smoke test.' to step 1 left the test green.

- Why: AGENTS.md "Downstream is blind to upstream. A skill invoked later must not name the skill/stage calling it"; the test exists to enforce that for the procedure, and CALLERS lists /afk:smoke-test as a caller (scripts/tests/test_fix_procedure.py:18).
- Fix: Match the smoke-test caller with a space or a hyphen, e.g. r"\b(?:execute|preflight|autopilot|smoke[- ]test)\b".
- Concern: test-veracity
- Key: 0006-fix-procedure/f101 — open (stalemate)

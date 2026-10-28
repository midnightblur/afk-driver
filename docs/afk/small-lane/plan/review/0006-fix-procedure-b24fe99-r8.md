# Review — 0006-fix-procedure round 8

- policy: lean · delta round 8 (b24fe99..5fc5e89), scope-escalated (copies again in round 7) · activated: delta-sweep, consistency-sweep (scope escalation), test-veracity (no test code in the delta; kept on the escalated roster), logic-correctness (delta touches 2 skill files) · skipped: fix-owner specialists (round 7 had no critical or high finding), scope-and-impact (every path is in Scope or added by a ledger entry), api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 7 upheld / 0 downgraded / 0 dropped (9 raw findings, 2 merged: logic-correctness-001 into r-001; consistency-sweep-002 restates deferred key f076)
- verdict: advisory — 0 high, 0 medium, 7 low
- shape: siblings of round 7 fixes left stale (where a reused decision id lands, the Phase 4 miss-class condition, a failed restart, a second ask for the instance); the owning file of `rationale-drop`; two ledger-only findings on contracts 0006 and 0009 (issue #152 pattern)
- Gate outcome: 7 fixed in place (f078-f084; D-54 widens one `RATIONALE.md` sentence, D-55 quotes contract 0006's input lines and gives 0009 the hand-over duty); deferred key f076 fixed too (the `AGENTS.md` row puts reconciliation on the skill)
- head: 5fc5e8935ae51a2217dce75a1adda96c11c3e547
- counts: crit=0 high=0 med=0 low=7

## r-001 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:181`
The delta tells step 7 to put an existing plan/DECISIONS.md entry id into the record, but the Record table has no field that holds a decision id and no step sets one. A new two-way-door entry's id is never put into the record, so only the reused case reaches it, and no caller reads that id.

- Why: The Record section is the procedure's output contract: skills/afk/fix/IN-PLACE-FIX.md:203 "The caller keeps the record in its own report." and its table (IN-PLACE-FIX.md:205-216) lists every field with the step that sets it. A field set by step 7 but missing from that table is a drifted twin of the contract.
- Fix: Either add a Record row such as "| Decisions | steps 3, 7 | each `plan/DECISIONS.md` entry id the fix recorded or reused |" and write the id there in both cases, or drop "put its id into the record" and say only "record no new entry".
- Concern: delta-sweep,logic-correctness
- Key: 0006-fix-procedure/f078 — fixed

## r-002 · low · correctness · `skills/afk/fix/SKILL.md:81`
The delta changed the lesson half of this sentence to depend on what the record holds, but left the miss-class half depending on whether Phase 2.5 ran. Phase 2.5 runs procedure step 6, which skips a pure unit or logic bug and names no miss class. So 'Phase 2.5 ran' can hold when there is no class to add, and an agent must either make one up or ignore the rule.

- Why: Delta-sweep item (skills/afk/review/checklists/delta-sweep.md:8): "a fix applied at one site while a sibling path keeps the old behaviour". skills/afk/fix/ESCAPE-ANALYSIS.md:9-11 "Run only for **standing-suite tier** bugs ... Skip a pure unit/logic bug that never had a higher-tier scenario"; IN-PLACE-FIX.md:212 "| Miss class | steps 1, 6 | the escape-analysis class, when one was named |".
- Fix: Make both halves depend on the record: "the record holds a miss class → add the **miss class** to the summary; procedure step 8 recorded a lesson → append the **lesson id** ...".
- Concern: delta-sweep
- Key: 0006-fix-procedure/f079 — fixed

## r-003 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:46`
Possible missing branch. The delta made the Live tiers exit restore a reverted fix, but that exit fires only when no instance or no restart command was handed over. Nothing covers a restart command that was handed over but fails, for example when the instance will not start on the reverted tree in step 4 or step 6. The check then can never run, because it runs 'only after' a restart that never happened, and no exit, result or restore is stated.

- Why: The brief treats an instruction an agent cannot carry out, or a missing branch, as a defect. IN-PLACE-FIX.md:43-45 makes a live check conditional on a completed restart, and IN-PLACE-FIX.md:220-222 says `blocked` keeps the edits made so far, which holds only when the fix is restored before the return.
- Fix: Widen the exit's condition to every case where a live check cannot run: "A live check with no instance or no restart command handed over, or whose restart fails → restore the step 3 fix when a step reverted it, then return `blocked`, naming the check and the restart's output."
- Concern: delta-sweep
- Key: 0006-fix-procedure/f080 — fixed

## r-004 · low · correctness · `skills/afk/fix/SKILL.md:28`
Phase 0 step 5 decides at intake, before diagnosis, whether to ask for the running instance and restart command. It asks only when the reported bug is one a live tier must prove. Phase 2 can still add a live test later, through procedure step 4's Contract row (api) or its user-visible-flow row (e2e/browser), once the diagnosis shows the bug's class. Example: a ticket reporting a wrong total is diagnosed as a status-code bug, so step 4 adds an api test. No instance was asked for at intake, so the Live tiers rule ends the run `blocked`, and the skill has no instruction to ask then, though a human is present to answer.

- Why: SKILL.md:14 "Its running instance and restart command are the ones Phase 0 step 5 takes; with none, a live tier ends the procedure `blocked`." The only re-ask covers a worktree change (SKILL.md:28 "Ask again when Phase 1 step 3 puts the fix in a worktree the named command does not serve."), not a live tier first needed after diagnosis.
- Fix: In Phase 0 step 5 (or Phase 2), ask for the instance and restart command whenever procedure step 4 or 5 is about to run a live check and the invoker named none. End `blocked` only when the invoker cannot supply them.
- Concern: logic-correctness
- Key: 0006-fix-procedure/f081 — fixed

## r-005 · low · correctness · `skills/afk/fix/IN-PLACE-FIX.md:220`
Fixed key f009 makes the procedure run `rationale-drop` on every pending entry when a revert removes the fix's uncommitted edits. RATIONALE.md, the one home for the drop verb, still says to use it for an entry whose line a later commit rewrote or deleted, and names no revert of uncommitted edits.

- Why: AGENTS.md 'DRY - one fact, one home': the owning file states when a verb applies, and a pointer that widens the use leaves the owner stale. RATIONALE.md:62-63 is the passage the f009 finding quoted as too narrow, and it did not change. Pattern used: grep of the identifier `rationale-drop` in RATIONALE.md and IN-PLACE-FIX.md, then read both in context.
- Fix: Widen RATIONALE.md:62-63 to 'Use it for an entry whose line a later commit rewrote or deleted, or whose uncommitted line a revert removed', and record the edit outside the 0006 Scope in the decision ledger.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f082 — fixed

## r-006 · low · spec · `docs/afk/small-lane/plan/DECISIONS.md:301`
D-43 (a) widened the procedure's input, adding the caller's paths, tiers, spec folder, running instance and restart command, and supersedes the SDD §3 and §8 cells. Contract 0006 still carries the narrow input in three places D-43 does not quote: an Acceptance bullet, the 'unmodified' §8 interface bullet, and the verbatim Context excerpts the executor works from.

- Why: Plugin-root DECISIONS.md protocol: a Supersedes line overrides only the exact passage it quotes. D-43 (d) and D-44 (b) show that this ledger supersedes contract 0006 lines one by one, so a fidelity check against the contract can still flag the wider hand-over. Pattern used: grep of the original cell wording 'failing check, finding or scenario' across PRD, SDD, ADR-0001 and the plan contracts.
- Fix: Add a ledger entry whose Supersedes line quotes contract 0006 '## Acceptance' "The procedure takes the failing check, finding or scenario the caller holds" and "Implements the public interface of SDD §8 row ... unmodified", plus the two Context excerpt cells, each read as widened by D-43 (a).
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f083 — fixed

## r-007 · low · spec · `docs/afk/small-lane/plan/DECISIONS.md:371`
D-53 (fixed key f077) wrote contract 0009 Acceptance wording for two of the three caller duties D-43 created: stale-artifact routing (b) and the caller's-paths limit (c). The third, D-43 (a), requires each caller to hand over its paths, tiers, spec folder, running instance and restart command. It has no 0009 Acceptance bullet, and 0009 consumes only the results table.

- Why: IN-PLACE-FIX.md:45-47 returns `blocked` for every live check when no instance or restart command is handed over. A 0009 review that checks its Acceptance can pass callers that hand over neither, so every live tier ends `blocked`. D-53 chose Acceptance wording over the bare ledger mention for exactly this reason. Pattern used: enumerated D-43 (a) to (e) against D-53's Supersedes, and grepped 0009 for 'hand', 'restart' and 'instance' (no hits).
- Fix: Extend D-53, or add an entry, so contract 0009 ## Acceptance gains: '- [ ] Each in-place caller hands the procedure its paths, declared tiers, spec folder, and the running instance with its restart command when a live tier applies (`skills/afk/fix/IN-PLACE-FIX.md` intake; D-43 (a))'.
- Concern: consistency-sweep
- Key: 0006-fix-procedure/f084 — fixed

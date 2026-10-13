## Goal
Put the lesson ledger's id mint and its append in hooks/lesson-append.sh under a folder lock, so 2 lesson appends that run at once never get the same id now that several pane agents can append together. The lock is a folder made with mkdir beside the ledger, taken over when stale with an atomic mv, and freed by a trap on exit. The same change ships 2 walker fixes, so the native contract gate's walks and scripts/create-worktree do not fail on the lock folder. The id format, the ledger grammar and the digest do not change. The slice ends at the mint, its lock and the 2 walkers.

## Complexity
standard

## Design refs
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — row "Lesson ledger id mint in hooks/lesson-append.sh"
- SDD: SDD.md#§13 Open Questions — V17 (answered), V18, V40

## Scope
- hooks/lesson-append.sh
- hooks/native-contract-gate.sh
- scripts/create-worktree*
- scripts/tests/test_lesson_filing.py

## Seams
- (none — the one §14 row this slice changes is excepted (partial INV-034); listed under ## Acceptance)

## Acceptance
- [ ] Excepted seam §14 row "Lesson ledger id mint in hooks/lesson-append.sh" (partial INV-034, human exception of 2026-10-02, GRILL-LOG.md:711): before this subtask merges, §13 V18 is proven at build as listed in ## Verification (V17 is answered by the re-probe of 2026-10-06), and the change follows the row's Planned change cell (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] The id step and its append run under a folder lock made with mkdir beside the ledger, with an atomic mv to take over a stale lock and a trap that frees it on exit, so 2 parallel appends never get the same id (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] The lock reads its folder's age with GNU `stat -c %Y`, else BSD `stat -f %m`, and never takes over a lock whose age it cannot read; a lock is stale after 10 s, a mint waits at most 30 s and polls the lock every 0.2 s, and a timeout exits 0 with a stderr note (agent-decided, SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] The lock keeps silent stdout, acquire-or-bail, and a lock path derived from the ledger path; maven-lock.sh keeps its code and is not copied (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] The native contract gate's walks (native-contract-gate.sh:90, :425) skip an entry that vanishes mid-walk, and scripts/create-worktree (:318, :340) skips the lock folder; both fixes ship in the same change as the lock (agent-decided, SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] The id format, the grammar and the digest do not change, so the lesson ledger lockstep (LEDGER-FORMAT.md, lesson-append.sh, lesson-digest.sh) is not triggered (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] No new upper-case setting with a self-default is added to the lock, since one makes skill-registry-gate.sh block Stop until skills/afk/setup/MANIFEST.md gains its row (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")
- [ ] A lock left by a pane closed with no trap stays until the stale test takes it over, as V17's answer gives (SDD §13 V17)
- [ ] Other walkers do not fail on the lock folder: lesson appends run in parallel with the native contract gate's walk and with scripts/create-worktree, on Python before and after 3.12 (SDD §13 V18)
- [ ] The changed native-contract-gate.sh, a Stop-path source, passes native check M: any new walk goes through bounded_scan.py (SDD §13 V40)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh")

## Produces
- hooks/lesson-append.sh#lesson-append.lock — the folder lock around the id mint and append

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'lesson-append.lock' hooks/lesson-append.sh`; `bash -n hooks/lesson-append.sh`; `bash -n hooks/native-contract-gate.sh`; `bash -n scripts/create-worktree` | Produces anchor present; the changed scripts parse |
| unit | `python -m pytest scripts/tests/test_lesson_filing.py -q`, with a new case in which 8 parallel appends get 8 distinct ids | the lock: 2 parallel appends never get the same id |
| unit | V18: a new case in scripts/tests/test_lesson_filing.py in which lesson appends run in parallel with the native contract gate's walk and with scripts/create-worktree, on Python before and after 3.12 | V18 |
| unit | `bash scripts/tests/create-worktree-smoke.sh` | scripts/create-worktree still works after its walker fix |
| integration | V17, answered by the re-probe of 2026-10-06 (providers/CONFORMANCE.md:442): a new case in scripts/tests/test_lesson_filing.py leaves a lock folder older than 10 s with no owner, as a pane closed with no trap does, and shows the next mint takes it over and gets a fresh id | V17's answer: a lock left by a closed pane stays until the stale test takes it over |
| static | `python -m pytest scripts/tests/test_native_contract_events.py -q`; the native contract gate run on the change (`GATE_CACHE_DISABLE=1 gate_native_contract`, sourced as scripts/tests/test_native_contract_events.py:25-28 does) reports no check M finding | V40 for the changed gate |

## Context excerpts
> (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh", Existing contract) An opened event without --id mints its id (lesson-append.sh:63) as the highest id plus 1 (:64-66), makes the folder (:73) and appends (:98); nothing orders 2 writers between :64 and :98. The id format, the grammar and the digest do not change (:66, :95; lesson-digest.sh:38, :56, :65) (INV-034)

> (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh", Planned change) The id step and its append run under a folder lock made with mkdir beside the ledger, with an atomic mv to take over a stale lock and a trap that frees it on exit, so 2 parallel appends never get the same id (S-203). The lock reads its folder's age with GNU stat -c %Y, else BSD stat -f %m, and never takes over a lock whose age it cannot read; a lock is stale after 10 s, a mint waits at most 30 s and polls the lock every 0.2 s, and a timeout exits 0 with a stderr note (D-06, agent-decided; the 0.2 s poll: audit L64, agent-decided, where INV-034 c-0414cafb measured 8 of 8 ids in 3 of 3 trials). maven-lock.sh keeps its code (D-06). The same change ships 2 walker fixes: the native contract gate's walks skip an entry that vanishes mid-walk, and scripts/create-worktree skips the lock folder (corrected D-08, agent-decided). Until each harness reloads, an older installed copy may mint a duplicate id, and the digest merges the 2 lines into 1 lesson (D-07, agent-decided)

> (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh", Impacted flows) Every lesson capture site; several pane agents can now append at once. Without the walker fixes: on Python 3.8 to 3.11 a lock folder that vanishes mid-walk makes native-contract-gate.sh (:90, :425) exit 2, so stop-gates.sh:122 blocks Stop and precommit-gates.sh:123, :133 refuses the commit, where the plugin loads from its main checkout (INV-034 c-bb3f8660); scripts/create-worktree (:318, :340) exits 1 when a lock owner file vanishes under set -eE (c-2c077446). A pane closed from a plain shell sends no signal a trap catches, so its lock stays until the stale test takes it over (providers/CONFORMANCE.md:442; c-e60b26f3) (INV-034)

> (SDD §14 row "Lesson ledger id mint in hooks/lesson-append.sh", Conventions / landmines) maven-lock.sh is not safe to copy: :34 takes over a live lock when stat fails, 2 waiters can take over one stale lock, :40 skips the wait cap, and at its 10 s poll 4 of 8 captures gave up with exit 0 and no id (INV-034 c-699010c5, c-439a5ff6, c-f8a33743, c-0414cafb). An upper-case setting with a self-default, as maven-lock.sh:22 has, makes skill-registry-gate.sh (:157, :230) block Stop until skills/afk/setup/MANIFEST.md gains its row (c-b194ce90). Keep silent stdout, acquire-or-bail, and a lock path derived from the ledger path (c-a1ebd14a, inference). A sandboxed Codex agent may not be able to create the lock folder (providers/CONFORMANCE.md:427; the ledger's frontier). The lesson ledger lockstep (LEDGER-FORMAT.md, lesson-append.sh, lesson-digest.sh) is not triggered: the grammar does not change. Compatibility: same ids and grammar; installed copies mint without the lock until refreshed, and a duplicate folds into 1 lesson (providers/CONFORMANCE.md:422; c-75ffec35, inference; D-07). Rollback: revert the commit that adds it, or install the previous plugin version; the lock keeps the ids and the format of the lesson ledger, so no data migration (S-200). Source: S-159, S-200, S-203, FIX-2; D-06, D-07, D-08, audit L64 (agent-decided); INV-034

> (SDD §13 V17) V17: For Codex, the run-time limit of a capture command and the signals a pane close sends. Answered by the re-probe of 2026-10-06, Codex CLI 0.160.0 (providers/CONFORMANCE.md:442): a shell call with no timeout argument returns after 10 s; asked for 900000 ms the agent set at most 30000 ms, and the screen then showed a background terminal. A pane close killed the agent's bash with no signal a trap catches, and its child stayed alive with no live parent (§13 V28). A lock the mint holds when a pane closes stays behind on both harnesses (inferred: no trap runs). INV-034 c-cdff8cb9; §14 row Lesson ledger id mint

> (SDD §13 V18) V18: Whether other walkers fail on the lock folder in the ledger's ignored folder. … The corrected D-08 (agent-decided) adds the native contract gate's walk and scripts/create-worktree, which do fail, and ships 2 walker fixes with the lock. INV-034 c-5ffc6a70; §14 row Lesson ledger id mint. Proven at build by: a test the plan carries: lesson appends in parallel with the native contract gate's walk and with scripts/create-worktree, on Python before and after 3.12

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

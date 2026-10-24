## Goal
Write the out-of-slice sibling file beside `/afk:execute` for a defect outside the slice (B-9, B-10): diagnose it in a second worktree off the base branch, route by verdict, file its own ticket, and — when it blocks — fix it on its own Draft change, cherry-pick the fix onto the feature branch and name the dependency in the feature change's `afk:subtasks` block. Make the start of a hands-off run the prior approval for those writes, and add the journal events, park reasons and run-report line that make them visible.

## Complexity
complex

## Design refs
- SDD: SDD.md#§7 L6 — Process & Coordination — "Blocking defect outside the slice"; out-of-slice verdict table; failure row "Dependency note rewrite"
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — Idempotency row "Dependency note"; Observability rows for journal events and the run report
- SDD: SDD.md#§8 L7 — Module Decomposition — row "out-of-slice sibling file (beside execute)"
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "Forge change description"
- ADR: adr/design/0005-blocking-defect-outside-the-slice.md — second worktree, separate change first, cherry-pick, dependency note, journal forms

## Scope
- skills/afk/execute/OUT-OF-SLICE.md
- skills/afk/execute/SKILL.md
- skills/afk/execute/scripts/*.py
- skills/afk/autopilot/SKILL.md
- skills/afk/autopilot/SUBAGENT-PROMPT.md
- skills/afk/preflight/SKILL.md
- skills/afk/to-subtasks/JOURNAL-FORMAT.md
- DECISIONS.md
- README.md
- AGENTS.md
- scripts/tests/test_dependency_note.py
- CHANGELOG.md

## Seams
- implement: hands-off rules: `DECISIONS.md`, `/afk:autopilot` — the run's start is the prior approval for out-of-slice writes (INV-023)
- implement: `/afk:preflight` PF-3/PF-4 and the `afk:subtasks` block — the dependency note, §9b boundary "Forge change description"; owns its stub-forge seam-test (INV-023)
- implement: `JOURNAL-FORMAT` events and `/afk:autopilot` report — the three out-of-slice events, three park reasons and the report line (INV-023)
- use: `/afk:execute` fix points and limits — the out-of-slice route out of Step 8 and the V-4 park statuses (INV-023)

## Acceptance
- [ ] The sibling file routes an out-of-slice diagnosis by verdict and blocking, per the §7 table: V-1 easy to undo with a clear winner → fix when blocking, ticket and continue when not; V-2/V-3 → ticket, park when blocking; V-4 → no ticket, park `design_conflict` (cited) or `needs_decision` (uncited) when blocking; V-5 → no ticket, park when blocking (SDD §7)
- [ ] The diagnosis runs in a second worktree off the base branch through the plugin's create-worktree script (SDD §7)
- [ ] B-9: the fix sits on its own branch off the base branch with its own Draft change linked to its own ticket, opened first; the feature branch carries the same commit by cherry-pick with the bug's work id in the subject; the feature change names the separate one as a dependency; neither change is merged by an agent (PRD AC-026)
- [ ] B-9 and B-10 tickets hold the diagnosis and the proof, so a reader can act without the feature's context (PRD AC-027)
- [ ] In a hands-off run, B-9 and B-10 write their tickets and B-9 opens its separate change without stopping; B-10 opens no change; the run's start is that prior approval; merge, force push and marking the separate change ready stay forbidden; each automatic decision gets a `D-{n}` entry and a journal line (PRD AC-028)
- [ ] `DECISIONS.md` no longer calls every outside write a never-two-way door for these writes, and `README.md` and `AGENTS.md` state the same rule (SDD §14 row "hands-off rules: `DECISIONS.md`, `/afk:autopilot`")
- [ ] The executor reads the change description through `change-fetch` (from its metadata file) before every rewrite, replaces only its `afk:subtasks` block, and keeps all text outside the block (SDD §9b row "Forge change description")
- [ ] `JOURNAL-FORMAT.md` defines three events in the park form — ticket written, separate change opened, defect parked — and three new park reasons; the separate change's push never uses the `pushed` token (SDD §5)
- [ ] The autopilot run report carries one line listing the separate changes and tickets for the person's follow-up (SDD §5)
- [ ] After the cherry-pick the slice re-runs from Step 8 (SDD §7)
- [ ] Implements the public interface of SDD §8 row "out-of-slice sibling file (beside execute)" unmodified (SDD §8)
- [ ] Conforms to ADR-0005 design — no silent pattern substitution (design ADR-0005)

## Produces
- skills/afk/execute/OUT-OF-SLICE.md#Out-of-slice verdict routes — the verdict × blocking table and each route's steps
- skills/afk/execute/OUT-OF-SLICE.md#Dependency note — the `afk:subtasks` block rewrite rule
- skills/afk/to-subtasks/JOURNAL-FORMAT.md#separate change opened — one of the three new park-form events

## Consumes
- 0008-standalone-fix skills/afk/fix/SHIPPING.md#Standalone write order — the separate change follows it, never ready hands-off
- 0009-in-place-callers skills/afk/to-subtasks/JOURNAL-FORMAT.md#Flaky check line — journal grammar this subtask extends in the same file

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; `bash hooks/wiring-gate.sh`; grep each ## Produces anchor | prose gates pass; the sibling file is reachable from execute |
| static | method: walk `OUT-OF-SLICE.md` through all ten cells (V-1..V-5 × blocking, not blocking) and both write outcomes (B-9 ticket + separate change; B-10 ticket only); each cell names exactly the action the §7 table gives | the route matrix matches the SDD |
| unit | `afk-python -m pytest skills/afk/mission-control/scripts/tests -q` — the journal fixture with the three new events still parses, and the commit join still works | journal readers accept the new events |
| integration | `afk-python -m pytest scripts/tests/test_dependency_note.py -q` — stub forge whose `change-fetch` writes the body only to the metadata file; the rewrite keeps every line outside the `afk:subtasks` block and the stub's `change-update-body` receives the whole body | the §9b "Forge change description" seam as the forge answers |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §7)
> | Out-of-slice verdict | Blocking | Not blocking |
> |----------------------|----------|--------------|
> | V-1, easy to undo, clear winner | fix (above) | ticket, slice continues |
> | V-2, V-3 | ticket, park | ticket, slice continues |
> | V-4 | no ticket; park `design_conflict` (cited) or `needs_decision` (uncited) | nothing |
> | V-5 | no ticket; park | nothing |
> (SDD §7)
> **Blocking defect outside the slice** (B-9; ADR-0005).
>
> ```mermaid
> sequenceDiagram
>   participant E as /afk:execute slice
>   participant W as Second worktree off base
>   participant T as /afk:to-ticket bug mode
>   participant G as Forge
>   E->>W: create-worktree, run /afk:diagnose
>   W->>W: verdict route per D-30
>   W->>T: ticket under prior approval
>   W->>G: push, Draft change, reasons on that change
>   E->>E: cherry-pick fix commit with bug work id
>   E->>G: change-fetch, rewrite afk:subtasks block with dependency note
>   E->>E: re-run from Step 8
> ```
>
> Caption: the separate change opens first, then the feature branch carries the same commit and names the dependency.
> (SDD §7) | Dependency note rewrite | change-fetch before update | none | remove the block | `/afk:execute` |
> (SDD §9b) | Forge change description | `change-fetch` / `change-update-body` | update replaces the whole body; fetch writes it only to the metadata file, never stdout, on both forges (INV-023) | read the metadata file before every rewrite | stub-forge test: rewrite keeps text outside the block |
> (SDD §5) three journal events: ticket written, separate change opened, defect parked — in the journal's park form, with three new park reasons, never the `pushed` token for the separate change, and a commit subject carrying the bug's work id | out-of-slice flows in hands-off runs |
> (SDD §5) | autopilot run-report line for separate changes and tickets | the person's follow-up list |
> (SDD §5) | `plan/DECISIONS.md` entry + `decision(D-{n})` journal line | every automatic approval |
> (SDD §14 row "hands-off rules: …") INV-023: `DECISIONS.md:23` external write never a two-way door; `:25` hard boundaries; autopilot `:24,64`; subagent prompt `:28-29` | a hands-off run's start is the prior approval for out-of-slice ticket and separate-change writes; merge and force push stay forbidden, and so does marking the separate change ready (the feature change still goes ready through preflight, `preflight/SKILL.md:215`) | INV-023: `README.md:127,860-861`; `AGENTS.md:195`; no test pins | each automatic decision gets `D-{n}` + journal line
> (SDD §14 row "`/afk:preflight` PF-3/PF-4 and the `afk:subtasks` block") one block per writer (`:181-186`); `change-update-body` replaces the whole body; body only from `change-fetch` | … dependency note inside execute's `afk:subtasks` block; `change-fetch` before every rewrite | INV-023: no test names `change-update-body`, `afk:subtasks`, `preflight-evidence` | V-2, V-3, V-5 need park reasons
> (SDD §14 row "`JOURNAL-FORMAT` events and `/afk:autopilot` report") INV-023: events `JOURNAL-FORMAT.md:31-37`; report `autopilot/SKILL.md:49-58` | three events in the park form, three new park reasons (`JOURNAL-FORMAT.md:51-54`), a `flaky` line, one report line; the separate change's push never uses `pushed` (`understand/SKILL.md:80`) | INV-023: mission-control parser generic (`mc/journal.py:10-13`); journal fixture `test_contract.py:90-97`, commit join `:306`
> (PRD AC-026) B-9: the fix is on its own branch off the base branch with its own merge request, linked to its own ticket. The same change is on the feature branch, and the feature's merge request names the separate one as a dependency. Neither merge request is merged by an agent.

> (PRD §Where a bug is found (B) — what runs) | B-10 | a defect outside the slice that does not block it | K-1 or K-2 | none | — | ticket only |
> (PRD §Acceptance Criteria) - [ ] AC-028 In a hands-off run, B-9 and B-10 write their tickets, and B-9 opens its separate merge request, without stopping for the human. Starting the run is the prior approval.

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
0008-standalone-fix, 0009-in-place-callers

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

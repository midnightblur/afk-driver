# Phase 3.5 — Workflow feedback (AFK-delivered features only)

Phase 3 fixed *this feature's* artifacts. This step asks the next question:
**which AFK stage let the bug through, and what should change so the next feature
doesn't repeat it.** Run **only** when the feature was built with AFK assistance
(Phase 0 feature-building signals: AFK branch + `plan/PLAN.md`). Ad-hoc/maintenance
bugs have no AFK workflow to improve → skip.

The lesson is **recorded, not self-applied.** Do **not** edit the AFK skills
here and do **not** run a retro — improving a workflow skill is a separate,
reviewed change applied via `/afk:lessons apply` from the lesson ledger
(format: `skills/afk/lessons/LEDGER-FORMAT.md`).

1. **Trace the miss to a stage.** Map the Phase 2.5 miss class (or the Phase 3
   stale artifact) to the AFK stage that under-specified the guard:

   | Phase 2.5 miss class / Phase 3 gap | Stage that under-specified it | Skill(s) to revisit |
   |------------------------------------|-------------------------------|---------------------|
   | `no-scenario` — gate had no journey/contract for this path | verification design | `/afk:grill-verification` → `/afk:to-verification-plan` |
   | `weak-assertion` — subtask Acceptance/Verification too loose | slicing | `/afk:to-subtasks` |
   | `wrong-path` — seam/fixture not pinned | architecture | `/afk:grill-solution` → `/afk:to-sdd` (§9b seams) |
   | `excluded` — env-tag policy hid a real regression | gate policy | `/afk:smoke-test` + `VERIFICATION-PLAN.md` tagging |
   | `disabled/flaky` — a built guard was left skipped/quarantined | execution TDD discipline | `/afk:execute` (TDD step) + `tdd` skill |
   | `dodged-failure` — an authoring dodge survived review | review gate | `skills/afk/review/checklists/` (test concern) |
   | PRD asserted the wrong behavior | requirements | `/afk:grill-requirements` → `/afk:to-prd` |

2. **Write the structured lesson** (the ledger payload — facts only, reference
   don't duplicate):
   - **Bug** — one line + ticket key; point at `/afk:diagnose`'s post-mortem by
     path, don't restage it.
   - **Miss class** — from Phase 2.5.
   - **Implicated stage + skill** — from the table.
   - **Proposed change** — the concrete edit to that skill (new grill question,
     tighter slice-time check, a seam the SDD must pin, a narrower exclusion rule)
     that would have forced the guard to exist.
   - **Evidence** — the existing scenario file + the assertion that whiffed
     (`path:line`), so the next agent can confirm before changing the skill.

3. **Record it.** Append the lesson to the lesson ledger as `opened`, from the
   repo root:

   ```
   bash tools/payable/ai-agents/plugins/workflow/hooks/lesson-append.sh opened \
     --class <mapped> --miss <phase-2.5 class> --target <implicated skill file> \
     --summary "<the Bug line>" --draft "<the Proposed change>" \
     --source <ticket key> --evidence <path:line> --writer fix
   ```

   `--class` maps from the miss class per the mapping table in
   `skills/afk/lessons/LEDGER-FORMAT.md`; the `draft` must stand alone. The
   draft is applied later — reviewed against `/afk:writing-great-skills` — via
   `/afk:lessons apply`, never in this session. Report the minted lesson id in
   Phase 4.

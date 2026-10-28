# Workflow feedback (AFK-delivered features only)

Procedure step 7 (a step of the shared fix procedure,
[IN-PLACE-FIX.md](IN-PLACE-FIX.md)) recorded *this feature's* stale artifacts.
This step asks the next question: **which AFK stage let the bug through, and
what should change so the next feature doesn't repeat it.** Run **only** for
a fix on an unreleased feature built with AFK assistance (signals:
[IN-PLACE-FIX.md](IN-PLACE-FIX.md) "Unreleased feature"). Ad-hoc/maintenance
bugs have no AFK workflow to improve → skip. Skip also when
procedure steps 1 and 6 named no miss class and procedure step 7 recorded no
stale artifact: there is no miss to trace.

The lesson is **recorded, not self-applied.** Do **not** edit the AFK skills
here and do **not** run a retro — improving a workflow skill is a separate,
reviewed change applied via `/afk:lessons apply` from the lesson ledger
(format: `skills/afk/lessons/LEDGER-FORMAT.md`). A miss traced to the plugin
itself routes per `skills/afk/lessons/CAPTURE.md` "A plugin defect is an
issue".

1. **Trace the miss to a stage.** Map the miss class from procedure step 1 or 6
   (or the stale artifact from procedure step 7) to the AFK stage that
   under-specified the guard:

   | Miss class / stale artifact | Stage that under-specified it | Skill(s) to revisit |
   |------------------------------------|-------------------------------|---------------------|
   | `no-scenario` — gate had no journey/contract for this path | verification design | `/afk:grill-verification` → `/afk:to-verification-plan` |
   | `weak-assertion` — subtask Acceptance/Verification too loose | slicing | `/afk:to-subtasks` |
   | `wrong-path` — seam/fixture not pinned | architecture | `/afk:grill-solution` → `/afk:to-sdd` (§9b seams) |
   | `excluded` — env-tag policy hid a real regression | gate policy | `/afk:smoke-test` + `VERIFICATION-PLAN.md` tagging |
   | `disabled/flaky` — a built guard was left skipped/quarantined or passes only on a re-run | execution TDD discipline | `/afk:execute` (TDD step) + `tdd` skill |
   | `dodged-failure` — an authoring dodge survived review | review gate | `skills/afk/review/checklists/` (test concern) |
   | PRD asserted the wrong behavior | requirements | `/afk:grill-requirements` → `/afk:to-prd` |
   | A frozen SDD decision was wrong or infeasible | architecture | `/afk:grill-solution` → `/afk:to-sdd` |
   | No verification scenario would catch the bug | verification design | `/afk:grill-verification` → `/afk:to-verification-plan` |
   | An in-flight subtask contract shifted | slicing | `/afk:to-subtasks` |

2. **Write the structured lesson** (the ledger payload — facts only, reference
   don't duplicate):
   - **Bug** — one line + the slice id or finding id (a ticket key when the fix
     has neither); point at the diagnosis's `DIAGNOSIS.md` by path when there
     is one, else at the procedure's record — don't restage either.
   - **Miss class** — from procedure step 1 or 6.
   - **Implicated stage + skill** — from the table.
   - **Proposed change** — the concrete edit to that skill (new grill question,
     tighter slice-time check, a seam the SDD must pin, a narrower exclusion rule)
     that would have forced the guard to exist.
   - **Evidence** — the existing scenario file + the assertion that whiffed
     (`path:line`), so the next agent can confirm before changing the skill.

3. **Record it.** Append the lesson to the lesson ledger as `opened`, from the
   session's linked worktree (the script finds the main checkout's ledger):

   ```
   bash $AFK_PLUGIN_ROOT/hooks/lesson-append.sh opened \
     --class <mapped> --miss <miss class> --target <implicated skill file> \
     --summary "<the Bug line>" --draft "<the Proposed change>" \
     --source <slice or finding id, else ticket key> --evidence <path:line> --writer fix
   ```

   `--class` comes from `skills/afk/lessons/LEDGER-FORMAT.md` "Miss-class
   mapping"; a lesson from a stale artifact alone takes no `--miss`. The `draft` must stand alone. The
   draft is applied later — reviewed against `/afk:writing-for-agents` — via
   `/afk:lessons apply`, never in this session. Put the minted lesson id into
   the procedure's record.

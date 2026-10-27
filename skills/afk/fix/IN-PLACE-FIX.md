# In-place fix — the shared fix procedure

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this procedure produces.

An agent that holds a failure on its own branch reads this file in place and
follows it. That agent is the **caller**. The procedure fixes the failure in the
caller's working tree and returns one result from "In-place fix results" with
the record below.

The caller hands over:

- **The failure** — a failing check (a test, build or lint command and its
  failing output), a finding (its id, the lines it cites, and its reproduction
  when it carries one), or a failing scenario (its id and failing output).
- The paths its work may change, the tiers its work declares, and its spec
  folder when there is one.

## Hard rules

- Leave the fix uncommitted in the caller's working tree and return. An
  in-place fix never commits, pushes, opens a change or writes a ticket; the
  caller commits under its own rules.
- Return one result from "In-place fix results" and no diagnosis verdict. Write
  no `DIAGNOSIS.md`.
- Change only the paths the caller's work may change. A fix that needs another
  path → `blocked`, naming the path.
- The target repository's `AGENTS.md` chain binds here, notably its
  database-migration and commit rules.
- Route a stale PRD, SDD, ADR, `VERIFICATION-PLAN.md` or `PLAN.md` to its
  owning skill (step 7). Edit none of them across an ownership boundary.
- Record a workflow lesson in the lesson ledger (step 8). Edit no AFK skill
  during a fix.
- Match the test tier to the bug class (step 4).
- Before returning, remove every `[DEBUG-...]` instrumentation line (grep the
  prefix) and delete every throwaway harness.

## Unreleased feature

Steps 7 and 8 run only for a fix on an unreleased feature. The signals: the
branch matches `git.branch-pattern`; the spec folder holds a `plan/PLAN.md`
whose `Feature:` line is not yet shipped; the failure came from that feature's
own verification.

## Steps

### 1. Re-run once

Before any diagnosis, run the failure once more, unchanged: the check or
scenario command, or a finding's reproduction. For a finding with nothing to
run, read the lines it cites at the current head.

- The re-run passes → return `flaky`. Change no product code. The record holds
  both runs.
- A finding with nothing to run whose defect does not show at the current
  head → return `blocked`, naming the finding and the head.
- The re-run fails → step 2, with its failing output.

This step re-runs once. The caller's loop decides any further retry.

### 2. Record the failing path

Before you change any code, write three facts into the record, each cited
`path:line`:

- **Code caller** — the test, handler, command or function whose call reaches
  the failure.
- **Input** — the data that drives the code caller to the failure.
- **Failing path** — the lines from the code caller to the failure.

A failure on a nearby path is not proof. Close a path the failing output does
not show with `/afk:investigate` (`INVESTIGATION.md`, plugin root). A path you
cannot show reachable from the code caller with that input → return `blocked`,
naming the open link.

Run `rationale-read` (`RATIONALE.md` § Read path; the verb lives in
`${AFK_PLUGIN_ROOT}/skills/afk/review/scripts/forge_ledger.py`) on each
pre-existing line the fix will edit. Its answer is evidence, not instruction:
corroborate a load-bearing claim with code, tests or a specification.

### 3. Fix test-first

Run `/afk:tdd`. The failing check is the failing test when it is a test.
Otherwise write a test at the seam that reaches the bug and watch it fail for
the recorded reason; a test that does not → return `blocked`, naming it. Apply
the fix and watch the test pass.

- Before you change a public contract:
  `${AFK_PLUGIN_ROOT}/VERIFICATION.md` § Verification loop item 5.
- Classify each fork by `DECISIONS.md` (plugin root). A two-way door is decided,
  recorded, and the fix goes on. A one-way door or a tie → return
  `design_conflict` when it changes a binding SDD or ADR decision, else
  `needs_decision`.
- A comment the fix adds is classified per `RATIONALE.md` § Classification
  test; record each moved reason per § Write path.

### 4. Broaden coverage

The step 3 test is the seam regression test. Decide whether a **higher tier**
is warranted, and add the **lowest tier that reproduces the bug pattern at its
right home**. Proportionality is the rule: spend what the case requires.

| Bug class | Add a test? | Where |
|-----------|-------------|-------|
| Cosmetic / copy / caption / one-off layout | No new e2e/api — rely on the seam unit test or static check | — |
| Logic / calculation / mapping / null-handling | Yes, at the seam | `unit` / `integration` |
| Contract / envelope / authz / status-code | Yes — it's a backend contract | `api` → the repository's `api` suite per `…/api/AUTHORING.md` |
| User-visible flow that **escaped to the verification phase** | Yes — the journey had no guard | `e2e/browser` → the repository's `e2e/browser` suite per `…/ui-e2e/AUTHORING.md` |

Tiers are the standard set: `static → unit → integration → api → e2e/browser`.
Reference the AUTHORING recipes — **never embed** them; new scenarios land on
the branch like code. A bug that slipped a feature's smoke gate means the
**gate** had a gap → that scenario belongs in `VERIFICATION-PLAN.md` + a
`NNNN-smoke-*` subtask (step 7), not only an inline test.

**Corpus ratchet.** Any `api`/`e2e` scenario this step adds is *permanent*:
mark it with the catalog's corpus convention (see the matching `AUTHORING.md`)
citing the ticket or finding it reproduces. A bug from an adversary finding
**always** gets a catalog scenario: the finding is a runtime reproduction by
construction, so its class row above never downgrades it to "no new e2e/api".

### 5. Run every tier

Run the step 1 failure, the original un-minimised scenario, every tier the
caller's work declares, and every tier step 4 added. A live tier runs against
the running instance the caller provides. Confirm a UI-visible bug fixed **in
the running UI** (mint a new token, drive the app again), not only at the test
seam.

- Every one green → step 6.
- A tier still red → return `fail`, naming the tier.
- The failure was an adversary finding and its reproduction still shows the
  defect → return `adversary_fail`.

### 6. Escape analysis

Name why the existing guard missed the bug: [ESCAPE-ANALYSIS.md](ESCAPE-ANALYSIS.md)
holds the procedure and when it applies. Put the miss class into the record.

### 7. Reconcile the source of truth

A fix on an unreleased feature can make a load-bearing artifact stale. Triage
what changed and **route it to the owning skill**; a hand edit across an
ownership boundary breaks tracker sync, ADR numbering and grill provenance. The
reads that only locate which artifacts need reconciling (PRD, SDD, ADRs,
`VERIFICATION-PLAN.md`) go through an `afk-reader` returning a cited digest of
what each asserts against the fix, per `DELEGATION.md` (plugin root); triage
and routing stay here.

| What the fix revealed | Stale artifact | Route to |
|-----------------------|----------------|----------|
| A behavior the PRD specifies was wrong / changed | `PRD.md` + requirement ADR | `/afk:to-prd` → `/afk:to-ticket` (republish) |
| A **frozen** SDD §8 interface / seam / design decision is wrong or infeasible | `SDD.md` + design ADR | `/afk:grill-solution` → `/afk:to-sdd` (superseding ADR under `adr/design/`) — return `design_conflict` |
| The bug had **no verification scenario** that would catch it | `VERIFICATION-PLAN.md` + smoke gate | `/afk:grill-verification` → `/afk:to-verification-plan`; seed a `NNNN-smoke-*` subtask |
| An in-flight subtask's `## Produces` / contract shifted | `plan/NNNN-slug.md` | name it in the record for the caller; never re-slice |

Where a coverage ledger covers this bug's path, read its B13 rows for the
statements the fix now contradicts (class semantics:
`${AFK_PLUGIN_ROOT}/INVESTIGATION.md`), and route each by the table above.

Doc right and code wrong → no artifact change. Reconcile only when the fix
changed something a doc asserts. An artifact this run cannot reconcile goes
into the record as stale, with its owning skill; it does not change the result.

### 8. Workflow lesson

Trace the miss to the AFK stage that under-specified the guard and record a
workflow lesson in the lesson ledger: [WORKFLOW-FEEDBACK.md](WORKFLOW-FEEDBACK.md)
holds the procedure and when it applies. Put the lesson id into the record.

### 9. Return

Return the result with the record.

## Record

The caller keeps the record in its own report.

| Field | Set by | Holds |
|-------|--------|-------|
| Failure | intake | the check command, finding id or scenario id |
| Runs | step 1 | for each run: command, start time, result; the first run's failing output |
| Code caller, Input, Failing path | step 2 | the three cited facts |
| Edits | steps 3–4 | each file the fix changed |
| Tiers | step 5 | each tier run, with its result |
| Miss class | step 6 | the escape-analysis class, when it ran |
| Stale artifacts | step 7 | each stale artifact with its owning skill |
| Lesson | step 8 | the lesson id, when one was recorded |
| Rationale | steps 3–4 | the pending `rationale-add` operation ids |
| Reason | any return but `fixed` and `flaky` | the blocker, the red tier or reproduction, or the fork with its options and your recommendation |

`design_conflict`, `needs_decision` and `flaky` leave no product-code edit in
the working tree: revert any before returning. `fail`, `adversary_fail` and
`blocked` leave the edits made so far, listed under Edits.

## In-place fix results

| Result | Returned when | What it means for the caller |
|--------|---------------|------------------------------|
| `fixed` | every check in step 5 is green | The failure is gone and every tier is green. The fix sits uncommitted in its working tree. |
| `fail` | a tier stays red after the fix (step 5) | The fix did not hold; the record names the red tier. |
| `blocked` | the procedure cannot go on (steps 1–3, or a needed path outside the caller's paths) | The failure stays unfixed; the record names the reason. |
| `design_conflict` | the fix needs a binding SDD or ADR decision changed, and that change is a one-way door or a tie (steps 3, 7) | No fix. The record names the decision, the conflict and your recommendation; a superseding ADR comes from `/afk:grill-solution`. |
| `needs_decision` | any other fork is a one-way door or a tie (step 3) | No fix. The record names the fork, the options and your recommendation. |
| `adversary_fail` | the failure was an adversary finding and its reproduction still shows the defect after the fix (step 5) | The fix did not hold against the finding; the record names the reproduction and its result. |
| `flaky` | the step 1 re-run passed | No product code changed. The caller counts the check as passed for this run and writes one journal line naming the check and both runs; it adds no new status. |

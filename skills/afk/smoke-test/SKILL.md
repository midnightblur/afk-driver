---
name: smoke-test
description: The feature-level completion gate — after every subtask in a local plan is done, run the feature's already-built verification suites (the browser UI journeys `ui-e2e` and direct-REST API contracts `api` under `11700-payable/verification`) against a running app and, only on green across both, stamp the feature complete in `PLAN.md`. Use when every subtask in a local plan is `done` and `PLAN.md` carries a `## Feature smoke gate` (full) or `## Feature smoke gate (minimal)` section, or to manually re-verify a feature's sanity. This skill only EXECUTES already-built verification suites — it authors nothing. It verifies the integrated whole, not one slice. Touches no Jira and merges nothing.
---

# afk:smoke-test — the feature-level smoke gate (runs, never authors)

Each subtask's own `## Verification` tiers prove that **one slice** works in isolation, in a dev worktree — a per-subtask `api` row when it exposes an endpoint, an `e2e/browser` row when it touches UI, each green before that subtask is `done`.

This skill is the **integrated feature smoke gate**: it runs the feature's verification suites — cross-subtask UI journeys (`ui-e2e`) and direct-REST API contracts (`api`) — against a **real running app**, and stamps the feature **complete** only when **both** modalities pass. "All subtasks `done`" ≠ "feature works".

Those suites then live on permanently under `11700-payable/verification` (`ui-e2e` Gherkin catalog + `api` `node:test` files), so CI, scheduled jobs, and ad-hoc human sanity runs invoke them directly. This skill is the **AFK-facing gate** plus a **manual runner** — not the only way the suites ever run.

## When it applies

Every feature has one of two gates:

- **Full gate** — a `## Feature smoke gate` section in `PLAN.md` (scenarios ↔ sources, suite paths, run commands, target env) plus a terminal build subtask **per modality** (`NNNN-smoke-e2e` and/or `NNNN-smoke-api`) that **built** the specs.
- **Minimal gate** — a `## Feature smoke gate (minimal)` section (features that skipped verification design): four fixed rows — compile, app-start, regression, existing suites — run as-is, no scenario table, no build subtasks. Green ⇒ stamp `Feature: complete (minimal gate, {YYYY-MM-DD})`; the stamp names the gate kind so "complete" is never mistaken for scenario-verified.

Neither section in `PLAN.md` → the plan predates the minimal-gate rule; report `no_gate` and point the human at re-running the slicing skill's gate seeding.

**This skill never authors or edits specs.** The specs are built by the terminal `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks (reviewed in an MR like any code); this skill only **executes** the already-implemented scenarios as the gate.

## Argument

- `plan_path` *(or `ticket_id`)* — locates `…/{TICKET-ID}/plan/PLAN.md`.
- `target` *(optional)* — the running app both suites hit (browser navigates it; API client calls its REST surface): `local` (default — dev server), `staging`, or an explicit base URL. Never silently default to a target the human didn't pick when release-gating; `local` is for dev sanity, `staging` for acceptance.
- `scope` *(optional)* — run a named subset of scenarios (manual spot-check), or a single modality (`ui-e2e` | `api`); default is both whole suites. A scoped run never stamps the feature complete.

## Process

1. **Locate the gate.** Read `PLAN.md`. Find `## Feature smoke gate` or `## Feature smoke gate (minimal)`; neither → `no_gate` (see "When it applies"). **Minimal gate:** run its rows in order after the Step 2 precondition (Step 3's env checks apply to the app-start and existing-suite rows); record each row's `Status` cell + the section's `Last run` line (this section is part of the gate surface this skill owns — see Boundary); any red row → `smoke_fail` naming the row, all green → stamp `Feature: complete (minimal gate, {YYYY-MM-DD})` and report — Steps 4–6 below are the full-gate path only. **Full gate:** read the suite paths, run command **per modality**, and the scenario table — each row carries its `Modality` (`ui-e2e` | `api`) and traces to its source (UI → a PRD User Story; API → an SDD §3 row / PRD Acceptance Criterion).

2. **Precondition — feature fully built.** Every row in the `## Progress tracker` (including terminal build subtasks `NNNN-smoke-e2e` and, when present, `NNNN-smoke-api`) must be `done`. Any subtask not `done` → refuse with `preconditions_unmet`, naming the laggards. A smoke gate on a half-built feature is meaningless — integrated scenarios can't pass until every slice has landed.

3. **Precondition — app reachable + suite env set.** Confirm the `target` app instance is up (hit its base/health URL). Not reachable → `env_unreachable`; tell the human to start the app / bring up the env. Also confirm **each modality's** run env is configured — the browser suite's auth token / base URL per `11700-payable/verification/ui-e2e/README.md`, and the API suite's token / base URL per `11700-payable/verification/api/AUTHORING.md` (API client mints via `../core`). A green build never compensates for a missing token at gate time. This gate requires a **real running app** — unlike the per-subtask tiers, which may run against a stub or a transient dev server.

4. **Run the suites.** Execute each present modality's run command against `target`, skipping a modality only if `scope` named the other:
   - **ui-e2e** — `cd 11700-payable/verification/ui-e2e && npm run smoke`, which already excludes the env-limited tags the gate declared (the same journeys marked `env-limited`; `@sap` is the common one but the exclusion set is whatever the run command carries, not a fixed list). (`npm run smoke:all` is the everything-incl-env-limited variant — not what the gate runs.)
   - **api** — `cd 11700-payable/verification/api && node --test`, likewise skipping the scenarios the plan marked `env-limited`. All in-scope scenarios across both suites — or the `scope` subset. Do not modify the app or the specs to coax a pass (Hard rules).

   Each modality's run goes through an `afk-runner` subagent, which returns per-scenario/per-test verdicts + failure digests and saves the raw suite output to an evidence file — that file's path is what Step 5 attaches to `fail` rows and the `Run history` line, per `DELEGATION.md` (plugin root). Verdict interpretation and every PLAN.md stamp stay with this skill (single-writer).

5. **Record per scenario.** Update each scenario row's `Status` in the `## Feature smoke gate` table (`pass` / `fail`), keyed by its `Modality`, and stamp the gate's `Last run` (date + target). A row pre-marked `env-limited` (a scenario that can't go green on `target` by design — either modality) stays `env-limited` — **not** run as pass/fail, never blocks the verdict. Attach the failure trace/artifact path on any `fail` row so the human can open it.

   **Keep the run history.** Append one line to the gate section's `Run history` list (create the list under the gate section if missing; append-only, both gate shapes): `- {YYYY-MM-DD} {target} — {verdict}, failing: {scenario names | none}`. The `Last run` line shows only the latest state; the history is what shows a gate that went red four times before green. Also append the run's journal line to `plan/JOURNAL.md` (format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`).

6. **Verdict.** Computed over the **runnable** scenarios of **both** modalities — every row not marked `env-limited`.
   - **All runnable green across both modalities** (full run, not a `scope` subset) → stamp the `PLAN.md` header `Feature: complete (smoke green {YYYY-MM-DD}, target={env})`. This is the completion milestone — a green UI suite with a red (or unrun) API suite is **not** complete, and vice versa. If any `env-limited` rows were skipped, note them in the report so "green" isn't read as "everything ran".
   - **Any runnable red** (either modality) → set `Feature: smoke-failing`; do **not** stamp complete. List failing scenarios + modality + source (User Story / §3 row) + artifact path. **No silent retry** — a flaky run is the human's to re-run deliberately; a real failure is fixed via a new/re-opened subtask or `/afk:grill-solution`, not by patching here. (An `env-limited` scenario going red is expected, not a gate failure — don't confuse the two.)

6b. **Update the ticket index.** Upsert the `Smoke gate` row in the ticket folder's `INDEX.md` (`red {date}` / `green {date} ({full|minimal} gate)`) per `skills/afk/to-prd/INDEX-FORMAT.md`; create the file per that format if missing.

7. **Report the structured outcome.** End with the status line plus one plain-terms sentence per the reporting protocol (`REPORTING.md` at the plugin root):

   ```
   OUTCOME: <status> — <one-line summary> [target: <env>] [failing: <n>]
   In plain terms: <one jargon-free sentence — is the feature shippable, and if not, what broke>
   ```

   | Status | Meaning / next action |
   |---|---|
   | `smoke_green` | Every runnable scenario across both modalities passed on a full run (env-limited rows skipped by design); the feature is stamped complete in `PLAN.md`. Note any skipped env-limited scenarios. (MRs remain the human's to merge — see Boundary.) |
   | `smoke_fail` | ≥1 scenario red (either modality). Name each + its modality + its source (User Story / §3 row) + artifact path; the feature is **not** complete. |
   | `env_unreachable` | The `target` app was not up. No scenarios were run. |
   | `preconditions_unmet` | Not every subtask is `done`; name the laggards. |
   | `no_gate` | `PLAN.md` carries neither gate section — a legacy plan from before the minimal-gate rule. Re-seed the gate via the slicing skill, then re-run. |
   | `other` | Unexpected failure. |

## Boundary (Hard rules)

- **Owns only the gate's surface in `PLAN.md`** — the gate section's table `Status` cells (full or minimal shape), its `Last run` line, its append-only `Run history` list, and the header `Feature:` line. Everything else in `PLAN.md` round-trips verbatim (the `## Progress tracker` status column stays `/afk:execute`'s). Outside `PLAN.md` it appends to `plan/JOURNAL.md` (append-only) and upserts the `Smoke gate` row of the ticket `INDEX.md` — nothing else.
- **Merges nothing, touches no Jira.** It stops at the human's lane: a green gate does not merge the Draft MRs and does not write to the tracker. The human merges out of band.
- **Authors no specs.** Spec code is the terminal `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks' reviewed work, built per the canonical recipes `11700-payable/verification/ui-e2e/AUTHORING.md` and `11700-payable/verification/api/AUTHORING.md`. A scenario needing a new/changed spec is a subtask edit (re-run `/afk:execute` on it) — or a scenario redesign (`/afk:grill-verification`) — not an edit from inside the gate. If a suite is missing or red because scenarios were authored ad hoc, point the fix back at the relevant `AUTHORING.md` — that's the standard the build subtask owes.
- **Never patches to green.** Do not touch app code or specs to make a red run pass — a red gate is a true signal about the feature or the spec. Fix it upstream (subtask or grill), then re-run the gate.
- **Right target for the purpose.** `local` for dev sanity; `staging` (or the release target) for acceptance gating. Don't release-gate against a dev server.

## Next

Feature green → it's complete. Subtask MRs are still **Draft** and the human's to review + merge (`/afk:execute` left them that way on purpose). After the merges, the smoke suites stay under `11700-payable/verification` (`ui-e2e` + `api`) and are picked up by CI / scheduled verification / manual sanity runs from then on — re-run this skill (or the raw suites) whenever you want to re-confirm the system is sane.

Feature red → fix the failing scenario at its source (re-run `/afk:execute` on the owning subtask, `/afk:grill-verification` if the scenario itself was wrong, or `/afk:grill-solution` if a binding decision is wrong), then re-run `/afk:smoke-test`.

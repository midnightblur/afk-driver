---
name: smoke-test
description: Runs a feature's built verification suites (ui-e2e + api) against a running app; on green, stamps PLAN.md complete. Use when every subtask is done, or to re-verify feature sanity.
---

> **Language:** read `LANGUAGE.md` (plugin root) first. It binds every reply, question, and artifact this skill produces — Simplified Technical English, glossary terms verbatim.

# afk:smoke-test — the feature-level smoke gate

Each subtask's own `## Verification` tiers prove **one slice** works in isolation, in a dev worktree — a per-subtask `api` row when it exposes an endpoint, an `e2e/browser` row when it touches UI, each green before that subtask is `done`.

This skill is the **integrated feature smoke gate**: runs the feature's verification suites — cross-subtask UI journeys (`ui-e2e`) and direct-REST API contracts (`api`) — against a **real running app**, and stamps the feature **complete** only when **both** modalities pass. "All subtasks `done`" ≠ "feature works".

Those suites live on permanently under `11700-payable/verification` (`ui-e2e` Gherkin catalog + `api` `node:test` files), so CI, scheduled jobs, and ad-hoc human sanity runs invoke them directly. This skill is the **AFK-facing gate** plus a **manual runner** — not the only way the suites run.

## When it applies

Every feature has one of two gates:

- **Full gate** — a `## Feature smoke gate` section in `PLAN.md` (scenarios ↔ sources, suite paths, run commands, target env) plus a terminal build subtask **per modality** (`NNNN-smoke-e2e` and/or `NNNN-smoke-api`) that **built** the specs.
- **Minimal gate** — a `## Feature smoke gate (minimal)` section (features that skipped verification design): five fixed rows — compile, app-start, regression, existing ui-e2e suite, existing api suite — run as-is, no scenario table, no build subtasks. Green ⇒ stamp `Feature: complete (minimal gate, {YYYY-MM-DD})`; the stamp names the gate kind so "complete" is never mistaken for scenario-verified.

Neither section in `PLAN.md` → plan predates the minimal-gate rule; report `no_gate` and point the human at re-running the slicing skill's gate seeding.

## Argument

- `plan_path` *(or `ticket_id`)* — locates `…/{TICKET-ID}/plan/PLAN.md`.
- `target` *(optional)* — the running app both suites hit (browser navigates it; API client calls its REST surface): `local` (default — dev server), `staging`, or an explicit base URL. A feature-env base URL from envstack counts as explicit: `python tools/payable/envstack/envctl.py status <env> --json` → `baseUrls.payable` (see `tools/payable/envstack/README.md` to build/start one per feature branch — multiple run concurrently). Never silently default to a target the human didn't pick when release-gating; `local` for dev sanity, `staging` for acceptance.
- `scope` *(optional)* — a named subset of scenarios (manual spot-check), or a single modality (`ui-e2e` | `api`); default both whole suites. A scoped run never stamps the feature complete.

## Process

1. **Locate the gate.** Read `PLAN.md`. Find `## Feature smoke gate` or `## Feature smoke gate (minimal)`; neither → `no_gate` (see "When it applies"). **Full gate:** read the suite paths, run command **per modality**, and scenario table — each row carries its `Modality` (`ui-e2e` | `api`), its `Requires target` class (a table predating the column reads as `any`), and traces to its source (UI → a PRD User Story; API → an SDD §3 row / PRD Acceptance Criterion). **Minimal gate:** take step 1b instead.

1b. **Minimal-gate path** *(minimal gate only — Steps 4–6 below are the full-gate path)*. After the Step 2 precondition, run the section's rows in order (Step 3's env checks apply to the app-start and existing-suite rows); record each row's `Status` cell + the section's `Last run` line (part of the gate surface this skill owns — see Boundary). Any red row → `smoke_fail` naming the row; all green → apply Step 6's trace gate, then stamp `Feature: complete (minimal gate, {YYYY-MM-DD})` and report.

2. **Precondition — feature fully built.** Every row in the `## Progress tracker` (including terminal build subtasks `NNNN-smoke-e2e` and, when present, `NNNN-smoke-api`) must be `done`. Any subtask not `done` → refuse with `preconditions_unmet`, naming the laggards. A smoke gate on a half-built feature is meaningless — integrated scenarios can't pass until every slice lands.

3. **Precondition — app reachable + suite env set.** Confirm the `target` app is up (hit its base/health URL). Not reachable → `env_unreachable`; tell the human to start the app / bring up the env — or provision a feature env yourself: `envctl build <env> --services payable --worktree <path>` + `envctl up <env> --services payable` (`tools/payable/envstack/README.md`), then re-run with `target=<baseUrls.payable>`. Also confirm **each modality's** run env — the browser suite's auth token / base URL per `11700-payable/verification/ui-e2e/README.md`, and the API suite's token / base URL per `11700-payable/verification/api/AUTHORING.md` (API client mints via `../core`). This gate requires a **real running app**.

4. **Run the suites.** Execute each present modality's run command **as read from the gate section in Step 1** — the gate section owns the run commands; don't substitute your own — against `target`, skipping a modality only if `scope` named the other. The `ui-e2e` command already excludes the env-limited tags the gate declared (the exclusion set is whatever the run command carries, not a fixed list); the `api` run likewise skips scenarios the plan marked `env-limited`. All in-scope scenarios across both suites — or the `scope` subset. Do not modify the app or specs to coax a pass (Hard rules).

   Each modality's run goes through an `afk-runner` subagent, which returns per-scenario/per-test verdicts + failure digests and saves the raw suite output to an evidence file — that file's path is what Step 5 attaches to `fail` rows and the `Run history` line, per `DELEGATION.md` (plugin root). Verdict interpretation and every PLAN.md stamp stay with this skill (single-writer).

5. **Record per scenario.** Update each scenario row's `Status` in the `## Feature smoke gate` table (`pass` / `fail`), keyed by its `Modality`, and stamp the gate's `Last run` (date + target). A row pre-marked `env-limited` (a scenario that can't go green on `target` by design — either modality) stays `env-limited` — **not** run as pass/fail, never blocks the verdict. A row whose `Requires target` class the current `target` does not satisfy (e.g. requires a non-secure-context real-hostname origin, `target=local`) is recorded `target-mismatch` — **never** `pass`: on an incompatible target the asserted code path is structurally unreachable, so a green run there proves nothing about the row. Unlike `env-limited`, a `target-mismatch` row still owes a run — on a compatible target — before the feature can stamp complete (Step 6). Attach the failure trace/artifact path on any `fail` row so the human can open it.

   **Keep the run history.** Append one line to the gate section's `Run history` list (create the list under the gate section if missing; append-only, both gate shapes): `- {YYYY-MM-DD} {target} — {verdict}, failing: {scenario names | none}`. The `Last run` line shows only the latest state; the history shows a gate that went red four times before green. Also append the run's journal line to `plan/JOURNAL.md` (format: `skills/afk/to-subtasks/JOURNAL-FORMAT.md`).

6. **Verdict.** Computed over the **runnable** scenarios of **both** modalities — every row not marked `env-limited`.
   - **Any `target-mismatch` rows** (Step 5) → the run can go green for its target but the feature is **not stamped complete**: report `target_mismatch` naming each such row + the target class it requires, so the human (or an orchestrator) re-runs the gate on a compatible target. Rows already `pass` keep their status; only the mismatched rows owe the re-run.
   - **Trace gate.** Before stamping complete, read the sibling `plan/TRACE.md` (present whenever the plan's terminal sync-harness subtask ran): any row flagged `— UNSATISFIED` or otherwise non-satisfied (e.g. `PARTIAL`) → do **not** stamp complete even on all-green scenarios; report `trace_incomplete` naming the open criteria. A known-open acceptance criterion and a green completion stamp may never coexist.
   - **All runnable green across both modalities** (full run, not a `scope` subset, no `target-mismatch` rows, trace gate clear) → stamp the `PLAN.md` header `Feature: complete (smoke green {YYYY-MM-DD}, target={env})`. The completion milestone — a green UI suite with a red (or unrun) API suite is **not** complete, and vice versa. If any `env-limited` rows were skipped, note them in the report so "green" isn't read as "everything ran".
   - **Any runnable red** (either modality) → set `Feature: smoke-failing`; do **not** stamp complete. List failing scenarios + modality + source (User Story / §3 row) + artifact path. **No silent retry** — a flaky run is the human's to re-run deliberately; a real failure is fixed via a new/re-opened subtask or `/afk:grill-solution`, not by patching here. (An `env-limited` scenario going red is expected, not a gate failure — don't confuse the two.)

6b. **Update the ticket index.** Upsert the `Smoke gate` row in the ticket folder's `INDEX.md` (`red {date}` / `green {date} ({full|minimal} gate)`) per `skills/afk/to-prd/INDEX-FORMAT.md`; create the file per that format if missing.

7. **Report the structured outcome.** End with the status line plus one plain-terms sentence per the reporting protocol (`REPORTING.md`, plugin root):

   ```
   OUTCOME: <status> — <one-line summary> [target: <env>] [failing: <n>]
   In plain terms: <one jargon-free sentence — is the feature shippable, and if not, what broke>
   ```

   | Status | Meaning / next action |
   |---|---|
   | `smoke_green` | Every runnable scenario across both modalities passed on a full run (env-limited rows skipped by design); the feature is stamped complete in `PLAN.md`. Note any skipped env-limited scenarios. (MRs remain the human's to merge — see Boundary.) |
   | `smoke_fail` | ≥1 scenario red (either modality). Name each + its modality + its source (User Story / §3 row) + artifact path; the feature is **not** complete. |
   | `target_mismatch` | ≥1 row requires a target class the run's `target` can't satisfy; those rows were not counted. Re-run on a compatible target; the feature is **not** complete until they run there. |
   | `trace_incomplete` | All runnable scenarios green, but `plan/TRACE.md` carries an `— UNSATISFIED`/partial acceptance criterion. Name the open criteria; the feature is **not** complete. |
   | `env_unreachable` | The `target` app was not up. No scenarios were run. |
   | `preconditions_unmet` | Not every subtask is `done`; name the laggards. |
   | `no_gate` | `PLAN.md` carries neither gate section — a legacy plan from before the minimal-gate rule. Re-seed the gate via the slicing skill, then re-run. |
   | `other` | Unexpected failure. |

## Boundary (Hard rules)

- **Owns only the gate's surface in `PLAN.md`** — the gate section's table `Status` cells (full or minimal shape), its `Last run` line, its append-only `Run history` list, and the header `Feature:` line. Everything else in `PLAN.md` round-trips verbatim (the `## Progress tracker` status column stays `/afk:execute`'s). Outside `PLAN.md` it appends to `plan/JOURNAL.md` (append-only) and upserts the `Smoke gate` row of the ticket `INDEX.md` — nothing else.
- **Merges nothing, touches no Jira.** Stops at the human's lane: a green gate does not merge the Draft MRs and does not write to the tracker. The human merges out of band.
- **Authors no specs.** Spec code is the terminal `NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks' reviewed work, built per the canonical recipes `11700-payable/verification/ui-e2e/AUTHORING.md` and `11700-payable/verification/api/AUTHORING.md`. A scenario needing a new/changed spec is a subtask edit (re-run `/afk:execute` on it) — or a scenario redesign (`/afk:grill-verification`) — not an edit from inside the gate. A suite missing or red because scenarios were authored ad hoc → point the fix back at the relevant `AUTHORING.md` — the standard the build subtask owes.
- **Never patches to green.** Do not touch app code or specs to make a red run pass — a red gate is a true signal about the feature or spec. Fix it upstream (subtask or grill), then re-run the gate.
- **Right target for the purpose.** `local` for dev sanity; `staging` (or the release target) for acceptance gating. Don't release-gate against a dev server.

## Next

Feature green → complete; the feature is now demoable, so **`/afk:to-demo-plan`** can synthesize the ≤1h `DEMO-PLAN.md` for showing it to product owners + QA (its journeys are the ones just run). Subtask MRs are still **Draft** and the human's to review + merge (`/afk:execute` left them that way on purpose). After the merges, the smoke suites stay under `11700-payable/verification` (`ui-e2e` + `api`) and are picked up by CI / scheduled verification / manual sanity runs from then on — re-run this skill (or the raw suites) whenever you want to re-confirm the system is sane.

Feature red → fix the failing scenario at its source (re-run `/afk:execute` on the owning subtask, `/afk:grill-verification` if the scenario itself was wrong, or `/afk:grill-solution` if a binding decision is wrong), then re-run `/afk:smoke-test`.

---
name: smoke-test
description: The feature-level completion gate — after every subtask in a local plan is done, run the feature's already-built verification suites (the browser UI journeys `ui-e2e` and direct-REST API contracts `api` under `11700-payable/verification`) against a running app and, only on green across both, stamp the feature complete in `PLAN.md`. Use when every subtask in a local plan is `done` and a `## Feature smoke gate` exists in `PLAN.md`, or to manually re-verify a feature's sanity. This skill only EXECUTES scenarios designed by `/afk:grill-verification` and built by the terminal smoke-e2e / smoke-api subtasks — it authors nothing. Distinct from the per-subtask `api` / `e2e/browser` tiers: this verifies the integrated whole. Touches no Jira and merges nothing.
---

# afk:smoke-test — the feature-level smoke gate (runs, never authors)

`/afk:execute` proves each subtask works in isolation: every declared
`## Verification` tier — including a per-subtask `api` row when the subtask
exposes an endpoint and an `e2e/browser` row when it touches UI — goes green
before that subtask is `done`. That is **one slice**, in a dev worktree.

This skill is the **integrated feature smoke gate**: it runs the feature's
verification suites — the cross-subtask UI journeys (`ui-e2e`) and the direct-REST
API contracts (`api`) — against a **real running app**, and stamps the feature
**complete** only when **both** modalities pass. "All subtasks `done`" ≠ "the
feature works".

The same suites then live on permanently under `11700-payable/verification`
(`ui-e2e` Gherkin catalog + `api` `node:test` files), so CI, scheduled jobs, and
ad-hoc human sanity runs invoke them directly. This skill is the **AFK-facing
gate** plus a **manual runner** — not the only way the suites ever run.

## When it applies

Only when the feature has a smoke gate — i.e. someone ran
`/afk:grill-verification` to design the scenarios and `/afk:to-verification-plan`
to write `VERIFICATION-PLAN.md`, and `/afk:to-subtasks` therefore seeded a `## Feature
smoke gate` section in `PLAN.md` (scenarios ↔ sources, suite paths, run commands,
target env) and a terminal build subtask **per modality** (`NNNN-smoke-e2e`
and/or `NNNN-smoke-api`) that **built** the specs. If `PLAN.md` has no `##
Feature smoke gate`, this feature has no designed scenarios — there is nothing to
run (exit `no_gate`).

**This skill never authors or edits specs.** The scenarios are designed by
`/afk:grill-verification` (written up by `/afk:to-verification-plan`) and the specs are built by the terminal
`NNNN-smoke-e2e` / `NNNN-smoke-api` subtasks through `/afk:execute` (reviewed in
an MR like any code). This skill only **executes** the already-implemented
scenarios as the gate.

## Argument

- `plan_path` *(or `ticket_id`)* — locates `…/{TICKET-ID}/plan/PLAN.md`.
- `target` *(optional)* — the running app both suites hit (the browser navigates
  it; the API client calls its REST surface): `local` (default — the dev server),
  `staging`, or an explicit base URL. Never silently default to a target the human
  didn't pick when release-gating; `local` is for dev sanity, `staging` for
  acceptance.
- `scope` *(optional)* — run a named subset of scenarios (manual spot-check), or a
  single modality (`ui-e2e` | `api`); default is both whole suites. A scoped run
  never stamps the feature complete.

## Process

1. **Locate the gate.** Read `PLAN.md`. Find `## Feature smoke gate`. Absent →
   this feature has no smoke gate → report `no_gate` and stop (nothing failed;
   nothing to do). Read the suite paths, the run command **per modality**, and the
   scenario table — each row carries its `Modality` (`ui-e2e` | `api`) and traces
   to its source (UI → a PRD User Story; API → an SDD §3 row / PRD Acceptance
   Criterion).

2. **Precondition — feature fully built.** Every row in the `## Progress
   tracker` (including the terminal build subtasks `NNNN-smoke-e2e` and, when
   present, `NNNN-smoke-api`) must be `done`. Any subtask not `done` → refuse with
   `preconditions_unmet`, naming the laggards. A smoke gate on a half-built feature
   is meaningless — the integrated scenarios can't pass until every slice has
   landed.

3. **Precondition — app reachable + suite env set.** Confirm the `target` app
   instance is up (hit its base/health URL). Not reachable → `env_unreachable`;
   tell the human to start the app / bring up the env. Also confirm **each
   modality's** run env is configured — the browser suite's auth token / base URL
   per `11700-payable/verification/ui-e2e/README.md`, and the API suite's token /
   base URL per `11700-payable/verification/api/AUTHORING.md` (the API client mints
   via `../core`). A green build never compensates for a missing token at gate
   time. This gate requires a **real running app** — unlike the per-subtask tiers,
   which may run against a stub or a transient dev server.

4. **Run the suites.** Execute each present modality's run command against
   `target`, skipping a modality only if `scope` named the other:
   - **ui-e2e** — `cd 11700-payable/verification/ui-e2e && npm run smoke`, which
     already excludes the env-limited tags the gate declared (the same journeys
     marked `env-limited`; `@sap` is the common one but the exclusion set is
     whatever the run command carries, not a fixed list). (`npm run smoke:all` is
     the everything-incl-env-limited variant — not what the gate runs.)
   - **api** — `cd 11700-payable/verification/api && node --test`, likewise
     skipping the scenarios the plan marked `env-limited`.
   All in-scope scenarios across both suites — or the `scope` subset. Do not modify
   the app or the specs to coax a pass (Hard rules).

5. **Record per scenario.** Update each scenario row's `Status` in the
   `## Feature smoke gate` table (`pass` / `fail`), keyed by its `Modality`, and
   stamp the gate's `Last run` (date + target). A row pre-marked `env-limited` (a
   scenario that can't go green on `target` by design — either modality) stays
   `env-limited` — it is **not** run as a pass/fail and never blocks the verdict.
   Attach the failure trace/artifact path on any `fail` row so the human can open
   it.

6. **Verdict.** Computed over the **runnable** scenarios of **both** modalities —
   every row not marked `env-limited`.
   - **All runnable green across both modalities** (full run, not a `scope`
     subset) → stamp the `PLAN.md` header
     `Feature: complete (smoke green {YYYY-MM-DD}, target={env})`. This is the
     completion milestone — a green UI suite with a red (or unrun) API suite is
     **not** complete, and vice versa. If any `env-limited` rows were skipped, note
     them in the report so "green" isn't read as "everything ran".
   - **Any runnable red** (either modality) → set `Feature: smoke-failing`; do
     **not** stamp complete. List the failing scenarios + their modality + their
     source (User Story / §3 row) + the artifact path. **No silent retry** — a
     flaky run is the human's to re-run deliberately; a real failure is fixed via a
     new/re-opened subtask or `/afk:grill-solution`, not by patching here. (An
     `env-limited` scenario going red is expected, not a gate failure — don't
     confuse the two.)

7. **Report the structured outcome.** End with one line, mirroring
   `/afk:execute`'s style so a human or orchestrator can read it at a glance:

   ```
   OUTCOME: <status> — <one-line summary> [target: <env>] [failing: <n>]
   ```

   - `smoke_green` — every runnable scenario across both modalities passed on a
     full run (env-limited rows skipped by design); the feature is stamped complete
     in `PLAN.md`. Note any skipped env-limited scenarios. (MRs remain the human's
     to merge — see Boundary.)
   - `smoke_fail` — ≥1 scenario red (either modality). Name each + its modality +
     its source (User Story / §3 row) + artifact path; the feature is **not**
     complete.
   - `env_unreachable` — the `target` app was not up. No scenarios were run.
   - `preconditions_unmet` — not every subtask is `done`; name the laggards.
   - `no_gate` — `PLAN.md` has no `## Feature smoke gate`; this feature opted
     out. Nothing to run.
   - `other` — unexpected failure.

How this gate relates to the per-subtask tiers and the rest of the chain: see [RELATIONSHIP.md](RELATIONSHIP.md).

## Boundary (Hard rules)

- **Owns only the gate's surface in `PLAN.md`** — the `## Feature smoke gate`
  table `Status` cells, its `Last run` line, and the header `Feature:` line.
  Everything else in `PLAN.md` round-trips verbatim (the `## Progress tracker`
  status column stays `/afk:execute`'s).
- **Merges nothing, touches no Jira.** Like `/afk:execute`, it stops at the
  human's lane: a green gate does not merge the Draft MRs and does not write to
  the tracker. The human merges out of band.
- **Authors no specs.** Spec code is the terminal `NNNN-smoke-e2e` /
  `NNNN-smoke-api` subtasks' reviewed work, designed upstream by
  `/afk:grill-verification` and built per the canonical recipes
  `11700-payable/verification/ui-e2e/AUTHORING.md` and
  `11700-payable/verification/api/AUTHORING.md`. If a scenario needs a new/changed
  spec, that's a subtask edit (re-run `/afk:execute` on it) — or a scenario
  redesign (`/afk:grill-verification`) — not an edit from inside the gate. If a
  suite is missing or red because scenarios were authored ad hoc, point the fix
  back at the relevant `AUTHORING.md` — that's the standard the build subtask owes.
- **Never patches to green.** Do not touch app code or specs to make a red run
  pass — a red gate is a true signal about the feature or the spec. Fix it
  upstream (subtask or grill), then re-run the gate.
- **Right target for the purpose.** `local` for dev sanity; `staging` (or the
  release target) for acceptance gating. Don't release-gate against a dev server.

## Next

Feature green → it's complete. The subtask MRs are still **Draft** and the
human's to review + merge (`/afk:execute` left them that way on purpose). After
the merges, the smoke suites stay under `11700-payable/verification` (`ui-e2e` +
`api`) and are picked up by CI / scheduled verification / manual sanity runs from
then on — re-run this skill (or the raw suites) whenever you want to re-confirm
the system is sane.

Feature red → fix the failing scenario at its source (re-run `/afk:execute` on the
owning subtask, `/afk:grill-verification` if the scenario itself was wrong, or
`/afk:grill-solution` if a binding decision is wrong), then re-run
`/afk:smoke-test`.

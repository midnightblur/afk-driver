---
name: to-verification-plan
description: Turn the verification scenarios settled in a `/afk:grill-verification` conversation into `VERIFICATION-PLAN.md`, written next to the PRD/SDD as a local artifact. Use when the user runs `/afk:to-verification-plan`, or wants to write `VERIFICATION-PLAN.md` from a settled `/afk:grill-verification` conversation (UI journeys after `/afk:to-prd`; re-run after `/afk:to-sdd` to append API scenarios). Catalogs both modalities — UI journeys (traced to PRD User Stories) and API scenarios (traced to SDD §3 endpoints + Acceptance Criteria) — with env-limited flags and a surfaced-gaps section. Does NOT interview — synthesizes what `/afk:grill-verification` already settled. Produces the plan `/afk:to-subtasks` turns into build subtasks and `/afk:smoke-test` runs as the completion gate. Does not write to the tracker.
---

# afk:to-verification-plan — synthesize the verification plan

Synthesize the verification scenarios settled in a `/afk:grill-verification`
conversation into `VERIFICATION-PLAN.md` on disk. Like `/afk:to-prd` and
`/afk:to-sdd`, this is a **synthesis** skill — no re-interview; write down what was
already settled. If the scenarios aren't settled (the user hasn't been grilled, or
key envelopes/click-paths are still vague), stop and route to
`/afk:grill-verification` first.

The artifact catalogs both modalities:

- **UI journeys** — browser flows that decide "this feature works", each traced to
  a PRD User Story.
- **API scenarios** — direct-REST checks that prove the backend contract for
  API/MCP callers who bypass the UI, each traced to an SDD §3 endpoint + the PRD
  Acceptance Criterion it proves.

Downstream, `/afk:to-subtasks` reads this plan to seed the `## Feature smoke gate`
and emit the terminal build subtasks, and `/afk:smoke-test` runs both modalities
as the feature-completion gate.

## When to invoke — and which modalities land

Run **after** a `/afk:grill-verification` session. What you can write depends on
what that session could design, which depends on what's on disk:

| Upstream on disk | UI journeys | API scenarios |
|------------------|-------------|---------------|
| PRD only (after `/afk:to-prd`) | ✅ write now | ⏸ **deferred** placeholder |
| PRD + SDD (after `/afk:to-sdd`) | ✅ write now | ✅ write now |

- **API scenarios require the SDD.** A pre-SDD run writes the UI journeys and
  leaves the `## API Scenarios` section as the deferred placeholder (below).
- **Re-running appends, it doesn't rewrite.** If `VERIFICATION-PLAN.md` already
  exists (UI journeys written pre-SDD), a post-SDD re-run **adds** the
  `## API Scenarios` section and leaves the existing `## UI Journeys` untouched.
  Never clobber settled UI journeys.

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
  `VERIFICATION-PLAN.md` is written as its sibling.
- `sdd_path` *(optional)* — the sibling `SDD.md`. Present → write both modalities;
  absent → UI journeys only, API deferred.

## Process

1. **Confirm the scenarios are settled.** The `/afk:grill-verification`
   conversation must have walked each journey/scenario to a concrete click-path or
   request → response envelope. If anything load-bearing is still vague, stop —
   that's a `/afk:grill-verification` gap, not something to invent here.

2. **Detect prior state.** Check for an existing sibling `VERIFICATION-PLAN.md`.
   Present (UI written pre-SDD) + an SDD now on disk → you're **appending** the
   API section; read the existing file and preserve `## UI Journeys` verbatim.

3. **Write `VERIFICATION-PLAN.md`** sibling to the PRD (template below). For each
   scenario record its trace (UI → a PRD User Story; API → an SDD §3 endpoint + the
   PRD Acceptance Criterion it proves) and its **env-limited** flag (carried over
   from the grill — `@sap`, GL-post-on-FOS, etc. — so the gate excludes it from the
   green verdict rather than reading it as a failure). When no SDD exists, the
   `## API Scenarios` section is the one-line deferred placeholder.

3b. **Write the `## Aspect coverage` ledger.** Transcribe the per-aspect verdict
   the grill settled — triggered vs N/A-with-reason, the proving row IDs, and the
   env-limited flag. Role-based and data-scoped each cite a row in both modalities;
   an Envers row appears whenever the feature added a new entity. Do not invent a
   verdict the grill didn't settle — a missing verdict is a `/afk:grill-verification`
   gap, route back.

4. **Capture surfaced gaps.** Fold the grill's non-load-bearing gaps into the
   `## Gaps surfaced` section for the human. (Load-bearing gaps were already routed
   back during `/afk:grill-verification`.)

5. **Print the result.** The path and one line per scenario (modality,
   actor/surface, traces-to, env-limited?). State explicitly whether API scenarios
   were written or deferred.

## `VERIFICATION-PLAN.md` (the artifact)

Written next to `PRD.md` / `SDD.md` at `…/{TICKET-ID}/VERIFICATION-PLAN.md`. It is
the design artifact `/afk:to-subtasks` reads to seed the gate and emit the build
subtasks — the scenarios here are the source of truth for both modalities.

Write `VERIFICATION-PLAN.md` using the template in [VERIFICATION-PLAN-TEMPLATE.md](VERIFICATION-PLAN-TEMPLATE.md).

## Hard rules

(Synthesis-vs-interview, SDD-gating of the API section, and append-on-re-run are
defined above — Process and the modality matrix — and not repeated here.)

- **Carry env-limited flags through.** Both modalities — so the downstream gate
  excludes them from its green verdict.
- **Every scenario traces to a source.** No orphan rows: UI → User Story; API →
  SDD §3 row + PRD Acceptance Criterion.
- **The `## Aspect coverage` ledger is complete.** Every aspect has a verdict
  (triggered with proving rows, or N/A with a reason); role-based and data-scoped
  each cite a proving row in both modalities. A blank verdict is a grill gap to
  route back, not a row to leave empty.
- **Local artifact only.** Writes `VERIFICATION-PLAN.md` (+ gap notes). It touches
  no Jira and no GitLab.

## Next

`VERIFICATION-PLAN.md` is on disk. Fold any `## Gaps surfaced` back into the
PRD/SDD (and re-run `/afk:to-ticket` if the PRD changed and is already published).
Then run **`/afk:to-subtasks`**: it detects the plan and automatically emits the
`## Feature smoke gate` in `PLAN.md` (seeded from both modalities) plus the
terminal build subtasks — `NNNN-smoke-e2e` for the UI journeys (authored per
`verification/ui-e2e/AUTHORING.md`) and, when API scenarios exist, `NNNN-smoke-api`
for the API contracts (authored per `verification/api/AUTHORING.md`). Both are
blocked by every other subtask. After every subtask is `done`, **`/afk:smoke-test`**
runs both modalities against a running app as the completion gate.

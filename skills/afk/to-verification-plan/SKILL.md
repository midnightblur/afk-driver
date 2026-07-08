---
name: to-verification-plan
description: Synthesizes settled verification scenarios into `VERIFICATION-PLAN.md` sibling to the PRD/SDD — UI journeys need the PRD, API scenarios the SDD (re-run post-SDD to append them). Use when the user runs `/afk:to-verification-plan` once scenarios are settled in conversation. Does not interview; local artifact only, no tracker.
---

# afk:to-verification-plan — synthesize the verification plan

Synthesize the verification scenarios already settled in conversation into `VERIFICATION-PLAN.md` on disk. This is a **synthesis** skill — no re-interview; write down what was already settled. Scenarios not settled (key envelopes/click-paths still vague) → stop, route to `/afk:grill-verification` first.

The artifact catalogs both modalities:

- **UI journeys** — browser flows that decide "this feature works", each traced to a PRD User Story.
- **API scenarios** — direct-REST checks proving the backend contract for API/MCP callers who bypass the UI, each traced to an SDD §3 endpoint + the PRD Acceptance Criterion it proves.

Downstream: `/afk:to-subtasks` reads this plan to seed the `## Feature smoke gate` and emit the terminal build subtasks; `/afk:smoke-test` runs both modalities as the feature-completion gate.

## When to invoke — and which modalities land

Run once the verification scenarios are settled. What you can write depends on what's on disk:

| On disk | UI journeys | API scenarios |
|---------|-------------|---------------|
| PRD only | ✅ write now | ⏸ **deferred** placeholder |
| PRD + SDD | ✅ write now | ✅ write now |

- **API scenarios require the SDD.** Pre-SDD run writes UI journeys, leaves `## API Scenarios` as the deferred placeholder (below).
- **Re-running appends, doesn't rewrite.** If `VERIFICATION-PLAN.md` already exists (UI journeys written pre-SDD), a post-SDD re-run **adds** the `## API Scenarios` section, leaves existing `## UI Journeys` untouched. Never clobber settled UI journeys.

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`). `VERIFICATION-PLAN.md` written as its sibling.
- `sdd_path` *(optional)* — the sibling `SDD.md`. Present → write both modalities; absent → UI journeys only, API deferred.

## Process

1. **Confirm scenarios are settled.** If the settled scenarios didn't survive into this context (fresh session, compaction), first read the verification section of the ticket folder's `GRILL-LOG.md` — the checkpoint exists exactly for this. Each journey/scenario must have been walked to a concrete click-path or request → response envelope. Anything load-bearing still vague → stop; that's a `/afk:grill-verification` gap, not something to invent here.

2. **Detect prior state.** Check for an existing sibling `VERIFICATION-PLAN.md`. Present (UI written pre-SDD) + SDD now on disk → you're **appending** the API section; read the existing file, preserve `## UI Journeys` verbatim.

3. **Write `VERIFICATION-PLAN.md`** sibling to the PRD (template below). Per scenario record its trace (UI → a PRD User Story; API → an SDD §3 endpoint + the PRD Acceptance Criterion it proves) and its **env-limited** flag (carried from the grill — `@sap`, GL-post-on-FOS, etc. — so the gate excludes it from the green verdict rather than reading it as failure). No SDD → `## API Scenarios` is the one-line deferred placeholder.

3b. **Write the `## Aspect coverage` ledger.** Transcribe the per-aspect verdict the grill settled — triggered vs N/A-with-reason, proving row IDs, env-limited flag — per the template's `## Aspect coverage` rules (the template owns the both-modalities requirement). Don't invent a verdict the grill didn't settle — a missing verdict is a `/afk:grill-verification` gap, route back.

4. **Capture surfaced gaps.** Fold the grill's non-load-bearing gaps into the `## Gaps surfaced` section for the human. (Load-bearing gaps already routed back during `/afk:grill-verification`.)

5. **Update the ticket index.** Upsert the `Verification plan` row in the sibling `INDEX.md` (`UI only (API deferred)` or `UI + API`) per `skills/afk/to-prd/INDEX-FORMAT.md`; create the file per that format if missing.

6. **Print the result.** First reconcile counts: every scenario settled in the grill (in conversation or the `GRILL-LOG.md` checkpoint) appears as a row in the plan — count both sides; a silent drop is a failure. Then print the path and one line per scenario (modality, actor/surface, traces-to, env-limited?). State explicitly whether API scenarios were written or deferred.

## `VERIFICATION-PLAN.md` (the artifact)

Written next to `PRD.md` / `SDD.md` at `…/{TICKET-ID}/VERIFICATION-PLAN.md`. The design artifact `/afk:to-subtasks` reads to seed the gate and emit the build subtasks — the scenarios here are source of truth for both modalities.

Write `VERIFICATION-PLAN.md` using the template in [VERIFICATION-PLAN-TEMPLATE.md](VERIFICATION-PLAN-TEMPLATE.md).

## Hard rules

- **Carry env-limited flags through.** Both modalities — so the downstream gate excludes them from its green verdict.
- **Persistence reverify (UI) / refetch (API).** The owning statement of this rule is the template's `**Persistence reverify**` / `**Persistence refetch**` lines ([VERIFICATION-PLAN-TEMPLATE.md](VERIFICATION-PLAN-TEMPLATE.md)) — emit them per the template on every journey/scenario; `n/a` only for the reasons the template states.
- **Every scenario traces to a source.** No orphan rows: UI → User Story; API → SDD §3 row + PRD Acceptance Criterion.
- **The `## Aspect coverage` ledger is complete.** Every aspect has a verdict (triggered with proving rows, or N/A with a reason), satisfying the template's `## Aspect coverage` rules. A blank verdict is a grill gap to route back, not a row to leave empty.
- **Local artifact only.** Writes `VERIFICATION-PLAN.md` (+ gap notes). Touches no Jira, no GitLab.

## Next

`VERIFICATION-PLAN.md` is on disk. Fold any `## Gaps surfaced` back into the PRD/SDD (re-run `/afk:to-ticket` if the PRD changed and is already published). Then run **`/afk:to-subtasks`**: it detects the plan and emits the `## Feature smoke gate` in `PLAN.md` (seeded from both modalities) plus the terminal build subtasks — `NNNN-smoke-e2e` for UI journeys (authored per `verification/ui-e2e/AUTHORING.md`) and, when API scenarios exist, `NNNN-smoke-api` for the API contracts (authored per `verification/api/AUTHORING.md`). Both blocked by every other subtask. After every subtask is `done`, **`/afk:smoke-test`** runs both modalities against a running app as the completion gate.

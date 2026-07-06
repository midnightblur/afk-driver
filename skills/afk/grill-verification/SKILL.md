---
name: grill-verification
description: Interviews the user to design a feature's verification scenarios across two modalities — UI journeys (browser flows; need the PRD) and API scenarios (direct-REST contract checks; need the SDD). Use when the user runs `/afk:grill-verification` or wants to design or stress-test verification scenarios. Writes only its `GRILL-LOG.md` checkpoint section.
---

# afk:grill-verification — design the feature's verification scenarios with the user

Interview the user to nail **what it means for this feature to work** — not abstractly, but as concrete, runnable scenarios across two modalities:

- **UI journeys** — browser flows a person (or job) drives end to end. Proves **user-facing** behaviour. Designed against PRD User Stories.
- **API scenarios** — direct-REST checks hitting backend endpoints, no browser. Proves the **backend contract** the feature exposes to API and MCP callers, who bypass every UI guard. Designed against SDD endpoint contracts.

Cutting across **both** modalities is a fixed set of **verification aspects** — cross-cutting things almost every feature must prove and almost every "it's done" forgets. Each aspect has a **trigger** (when it applies) and the **modalities** it must be proven in. Walk every aspect, evaluate its trigger, then either design concrete scenarios for it **or record it N/A with the reason** — recording the N/A is what stops a silent gap:

| Aspect | Trigger | Prove in |
|--------|---------|----------|
| **Role-based access** | always | UI **and** API |
| **Data-scoped access** (company / vendor) | feature reads/writes company- or vendor-scoped data | UI **and** API |
| **Input validation** | user input **or** a workflow is involved | UI **and** API |
| **Envers audit trail** | feature adds a new JPA entity / DB table | API (history/revisions surface) |
| *situational* — concurrency, idempotency, pagination/sorting, state-machine transition guards, error-envelope shape | prompted; mark applies / N-A | per nature |

> The canonical miss this catches: an aspect proven in one modality but assumed in the other — e.g. role-based access enforced *below* the UI (backend `403`) but never *at* it (UI wide open).

Role-based, data-scoped, and validation aspects trace back to the PRD's **`## Access & validation policy`** matrix; the Envers aspect and the *mechanism* of role/scope enforcement come from the SDD (§5 L4 / §9b / §4 L3). An aspect is not designed in the abstract — it becomes **real woven rows** in the UI/API tables below, plus a line in the `## Aspect coverage` ledger `/afk:to-verification-plan` writes.

A **grilling** skill: you interview, you don't assume. Output of this session is a settled, shared understanding of the verification scenarios — which `/afk:to-verification-plan` then synthesizes into `VERIFICATION-PLAN.md`. Lens is **concreteness** — walk the actual scenario step by step (the click-path, or the request → response envelope). A User Story that can't be turned into a demonstrable journey, or an endpoint whose success/error envelope nobody can state, is underspecified.

## When to invoke — and which modality

Optional and **human-invoked**. Which modalities you can design depends on what's on disk:

| On disk | UI journeys | API scenarios |
|---------|-------------|---------------|
| PRD only | ✅ design now | ⏸ **deferred** — no settled endpoints to verify yet |
| PRD + SDD | ✅ design now | ✅ design now |

- Re-run once the SDD exists to design the deferred API scenarios — and re-run `/afk:to-verification-plan` to append them. (The gating itself: the matrix above + the "API needs the SDD" Hard rule.)
- If neither PRD nor SDD exists, stop and route the user to `/afk:to-prd` first — nothing to ground scenarios against.

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
- `sdd_path` *(optional)* — sibling `SDD.md`. Present → both modalities in play; absent → UI journeys only, API deferred.

## Process

1. **Read the sources.** `ctx_read` the PRD (full) — especially its **User Stories** and **Acceptance Criteria** — and, when present, the SDD (full), especially **§3 L2** (API contracts) and **§9b** (external seams). If a `PROTOTYPE.md` settled the UI, `ctx_read` it too — its screens are the concrete thing the **UI journeys** trace to (a real screen, not an imagined one). Skim the canonical build recipes so you grill **buildable** scenarios, never ones the suite can't drive:
   - UI: **`11700-payable/verification/ui-e2e/AUTHORING.md`** (+ its sibling `CLAUDE.md`) — each journey becomes one `Scenario` in the Cucumber+Playwright catalog, reusing the module's existing L2 domain flows.
   - API: **`11700-payable/verification/api/AUTHORING.md`** (+ `CLAUDE.md`) — each scenario becomes one `node:test` `*.test.mjs` using `fetch` + the shared `../core` primitives (auth/base-URL/poll). Dependency-free, no install.
   - Umbrella selection guidance: **`11700-payable/verification/README.md`**.

2. **Grill the UI journeys.** Work from the PRD's top User Stories — the definition-of-done flows. For each, drive the user through actor & trigger, the concrete click-path (plain business language), the observable definition-of-done (a visible state, a posted record, a status transition, a surfaced error — vague "it works" is not acceptance), the preconditions/data setup (the journey's `Given`), the alternate/error paths worth gating, and **env reachability** (can it go green on the dev stack? SAP-behind-VPN and GL-post-parking-on-FOS can't — note them `env-limited` now; see `verification/ui-e2e/AUTHORING.md`).

   Then walk the **aspects at the UI** for the surfaces this feature touches:
   - **Role-based access** — for every protected surface, walk the harness's role tiers and pin what each tier *sees* (the observable per tier). The **denied tier is a required row**, never optional. The tier set, its driving mechanics, and the reusable per-tier flows are canonical in `11700-payable/verification/ui-e2e/AUTHORING.md` — you specify the per-tier observable, you don't invent the flow.
   - **Data-scoped access** — a user scoped to one company/vendor sees only its rows on the relevant list/detail screen. Usually **`env-limited`** (needs two FOS-provisioned scoped users the smoke env may not have) — flag it now.
   - **Input validation** — the form refuses a violating input (inline field error + disabled submit), per the PRD validation policy.

3. **Grill the API scenarios** *(when the modality matrix puts them in play)* per [API-SCENARIOS.md](API-SCENARIOS.md).

4. **Check coverage.** Every top User Story maps to at least one UI journey; every endpoint the feature exposes maps to at least one API scenario; every scenario traces back to a Story / Acceptance Criterion / §3 row. Surface over-coverage (a scenario nothing asks for — is the spec missing it?) and under-coverage (a Story or endpoint with no demonstrable scenario — is it real?). UI and API are **complementary, not redundant**: the UI journey proves the user flow, the API scenario proves the contract a UI test can't see (the raw envelope, the below-the-UI guard).

   **Then check aspect coverage.** For every aspect in the table above, evaluate its trigger: if triggered, it must have **at least one proving woven row** in each modality it owns (role-based and data-scoped owe a row in *both* UI and API); if not triggered, record it **N/A — <reason>**. A triggered aspect with no proving row is an under-coverage gap to surface (step 5). This per-aspect verdict (triggered / N-A / proving row-IDs / env-limited) becomes the `## Aspect coverage` ledger `/afk:to-verification-plan` writes.

5. **Surface PRD/SDD gaps explicitly.** Revealing gaps is a primary output. When a walk exposes an ambiguous, missing, or contradictory detail, name it. Small → note it in the conversation so `/afk:to-verification-plan` captures it in the plan's `## Gaps surfaced` section for the human to fold back. Load-bearing (the scenario can't be designed without it) → **stop and route back**: a PRD gap to `/afk:grill-requirements` + `/afk:to-prd`; a technical / endpoint gap to `/afk:grill-solution` + `/afk:to-sdd`.

6. **Settle the set.** When every Story has a journey, every exposed endpoint has a scenario (or API is deferred for lack of an SDD), **every triggered aspect has a proving row or a recorded N/A reason**, and the user agrees the set is complete, recap the scenarios — modality, actor/surface, traces-to, env-limited?, plus the per-aspect coverage verdict and whether API was designed or deferred — and hand off to `/afk:to-verification-plan` to write `VERIFICATION-PLAN.md`.

## Hard rules

- **Grill, don't assume.** If a journey's steps, an endpoint's envelope, or a definition-of-done can't be stated concretely, that's a gap to surface (step 5) — never invent the flow or the contract to keep moving.
- **API needs the SDD.** No SDD → design UI journeys only and leave API deferred; never fabricate endpoint contracts from the PRD alone. SDD §3 too vague to state an envelope → route back to `/afk:to-sdd`, don't guess.
- **Design buildable scenarios.** Ground UI journeys in what `verification/ui-e2e` can drive and API scenarios in what `verification/api` + `../core` can issue (canonical recipes: `verification/ui-e2e/AUTHORING.md`, `verification/api/AUTHORING.md`). Reuse existing flows/helpers. Never spec a scenario the suite has no way to perform.
- **Every triggered aspect is covered, in every modality it owns.** Walk the aspect table; a triggered aspect with no proving row is a gap, and a non-N/A aspect with no recorded reason is a skip. The denied-role UI row is mandatory for every protected surface; the no-token/bad-token/role-scoping API assertions are mandatory for every protected endpoint (per the SDD §9b bidirectional seam).
- **Every scenario traces to a source; every gap is named.** No orphan scenarios, no silently-swallowed PRD/SDD ambiguities.
- **Note env-limited scenarios as you go** — both modalities — so `/afk:to-verification-plan` can mark them and the downstream gate excludes them from its green verdict rather than reading them as failures.
- **Your only write is the `GRILL-LOG.md` checkpoint; touch no tracker.** This skill interviews — the plan artifact is `/afk:to-verification-plan`'s job; no Jira, no GitLab. Mirror the per-aspect verdicts, settled journeys/scenarios, and the API designed-vs-deferred state into this skill's section of the ticket folder's `GRILL-LOG.md` per `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`, updated as they settle — so a pause before the synthesis skill runs loses nothing.

## Next

The scenarios are settled in the conversation. Run **`/afk:to-verification-plan`** to synthesize them into `VERIFICATION-PLAN.md` sibling to the PRD (it does NOT re-interview — it writes what was settled here). From there, `/afk:to-subtasks` detects the plan and emits the `## Feature smoke gate` plus the terminal build subtasks (`NNNN-smoke-e2e`, and `NNNN-smoke-api` when API scenarios exist), and `/afk:smoke-test` later runs both modalities against a running app as the completion gate.

---
name: grill-verification
description: Interview the user to design the feature's verification scenarios across two modalities — UI journeys (the real browser flows that decide "this feature works") and API scenarios (direct-REST checks that prove the backend contract for API/MCP callers who bypass the UI). A grilling skill like `/afk:grill-requirements` and `/afk:grill-solution` — it interviews and surfaces gaps; it does NOT write a file. Forces a concrete walk of each scenario, which routinely reveals PRD/SDD gaps. UI journeys can be designed after `/afk:to-prd`; API scenarios need the SDD's endpoint contracts, so they are only designed after `/afk:to-sdd`. Optional and human-invoked. Pair with `/afk:to-verification-plan` to synthesize the conversation into `VERIFICATION-PLAN.md`. Does not write to the tracker.
---

# afk:grill-verification — design the feature's verification scenarios with the user

You interview the user to nail down **what it means for this feature to work** —
not in the abstract, but as concrete, runnable scenarios across two modalities:

- **UI journeys** — the browser flows a person (or job) drives end to end. Proves
  the **user-facing** behaviour. Designed against the PRD's User Stories.
- **API scenarios** — direct-REST checks that hit the backend's endpoints with no
  browser at all. Proves the **backend contract** the feature exposes to API and
  MCP callers, who bypass every UI guard. Designed against the SDD's endpoint
  contracts.

This is a **grilling** skill, like `/afk:grill-requirements` and
`/afk:grill-solution`: you interview, you don't assume, and **you do not write a
file**. The output of this session is a settled, shared understanding of the
verification scenarios — which `/afk:to-verification-plan` then synthesizes into
`VERIFICATION-PLAN.md`. The lens is **concreteness** — you walk the actual
scenario step by step (the click-path, or the request → response envelope). A
User Story that can't be turned into a demonstrable journey, or an endpoint whose
success/error envelope nobody can state, is underspecified — and saying so out
loud is how this skill earns its keep.

## When to invoke — and which modality

Optional and **human-invoked**. Which modalities you can design depends on what's
on disk:

| Upstream on disk | UI journeys | API scenarios |
|------------------|-------------|---------------|
| PRD only (after `/afk:to-prd`) | ✅ design now | ⏸ **deferred** — no settled endpoints to verify yet |
| PRD + SDD (after `/afk:to-sdd`) | ✅ design now | ✅ design now |

- **API scenarios require the SDD.** They verify endpoint contracts, and the
  endpoints aren't settled until the SDD's §3 L2 API contract table exists. So a
  pre-SDD run designs **UI journeys only** and leaves API scenarios deferred.
  Re-run after `/afk:to-sdd` to design them — and re-run `/afk:to-verification-plan`
  to append them.
- If neither PRD nor SDD exists, stop and route the user to `/afk:to-prd` first —
  there's nothing to ground scenarios against.

**If the SDD has no usable endpoint contract.** API scenarios read the SDD §3 L2
**API contract table** (surface, method, request/response shape, error codes) and
the §9b external seams (especially the "a new API/MCP caller bypasses the UI"
guards `/afk:grill-solution` flags). If §3 is empty or too vague to state an
endpoint's success **and** error/empty envelope, that's an SDD gap — **stop and
route back** to `/afk:grill-solution` + `/afk:to-sdd` to settle the contract.
Don't invent endpoints to keep moving.

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
- `sdd_path` *(optional)* — the sibling `SDD.md`. Present → both modalities are in
  play; absent → UI journeys only, API deferred.

## Process

1. **Read the sources.** `ctx_read` the PRD (full) — especially its **User
   Stories** and **Acceptance Criteria** — and, when present, the SDD (full),
   especially **§3 L2** (API contracts) and **§9b** (external seams). Skim the
   canonical build recipes so you grill **buildable** scenarios, never ones the
   suite can't drive:
   - UI: **`11700-payable/verification/ui-e2e/AUTHORING.md`** (+ its sibling
     `CLAUDE.md`) — each journey becomes one `Scenario` in the Cucumber+Playwright
     catalog, reusing the module's existing L2 domain flows.
   - API: **`11700-payable/verification/api/AUTHORING.md`** (+ `CLAUDE.md`) — each
     scenario becomes one `node:test` `*.test.mjs` using `fetch` + the shared
     `../core` primitives (auth/base-URL/poll). Dependency-free, no install.
   - Umbrella selection guidance: **`11700-payable/verification/README.md`**.

2. **Grill the UI journeys.** Work from the PRD's top User Stories — the
   definition-of-done flows. For each, drive the user through actor & trigger, the
   concrete click-path (plain business language), the observable definition-of-done
   (a visible state, a posted record, a status transition, a surfaced error — vague
   "it works" is not acceptance), the preconditions/data setup (the journey's
   `Given`), the alternate/error paths worth gating, and **env reachability** (can
   it go green on the dev stack? SAP-behind-VPN and GL-post-parking-on-FOS can't —
   note them `env-limited` now so the gate excludes them rather than reading them
   as failures; see `verification/ui-e2e/AUTHORING.md`).

3. **Grill the API scenarios** *(only when an SDD is present)*. Work from the SDD
   §3 L2 endpoints and the §9b below-the-UI guards. For each endpoint the feature
   adds or changes, drive the user through:
   - **The call** — method + surface + the request shape (auth role/token, path,
     body), in terms the `../core` REST client can issue.
   - **The asserted contract** — the response envelope on success, **and** on the
     contract edges this backend actually returns. Pin the real shape, not the
     ideal one: e.g. a missing entity may return `200 + NULL_RESPONSE` (not 404),
     and an unauthorized vendor may return `403 "no.authorized.vendor"`
     (authorization, not authentication). If the user can't state the envelope,
     that's an SDD §3 gap — surface it (step 5).
   - **Auth/authz coverage** — because API callers bypass the UI, prove the guard
     lives **below** it: no-token and garbage-token rejection, and role-scoping
     (a role with access vs one without). This is the modality's whole reason to
     exist; don't skip it.
   - **Preconditions / data setup** — what must exist first (these become the
     test's setup via `../core`).
   - **Env reachability** — same `env-limited` rule as UI (e.g. an endpoint that
     fans out to SAP).

4. **Check coverage.** Every top User Story maps to at least one UI journey;
   every endpoint the feature exposes maps to at least one API scenario; every
   scenario traces back to a Story / Acceptance Criterion / §3 row. Surface
   over-coverage (a scenario nothing asks for — is the spec missing it?) and
   under-coverage (a Story or endpoint with no demonstrable scenario — is it
   real?). UI and API are **complementary, not redundant**: the UI journey proves
   the user flow, the API scenario proves the contract a UI test can't see (the
   raw envelope, the below-the-UI guard).

5. **Surface PRD/SDD gaps explicitly.** Revealing gaps is a primary output. When a
   walk exposes an ambiguous, missing, or contradictory detail, name it. Small →
   note it in the conversation so `/afk:to-verification-plan` captures it in the
   plan's `## Gaps surfaced` section for the human to fold back. Load-bearing (the
   scenario can't be designed without it) → **stop and route back**: a PRD gap to
   `/afk:grill-requirements` + `/afk:to-prd`; a technical / endpoint gap to
   `/afk:grill-solution` + `/afk:to-sdd`.

6. **Settle the set.** When every Story has a journey, every exposed endpoint has
   a scenario (or API is deferred for lack of an SDD), and the user agrees the set
   is complete, recap the scenarios — modality, actor/surface, traces-to,
   env-limited?, plus whether API was designed or deferred — and hand off to
   `/afk:to-verification-plan` to write `VERIFICATION-PLAN.md`. **You write
   nothing.**

## Hard rules

- **Grill, don't assume.** If a journey's steps, an endpoint's envelope, or a
  definition-of-done can't be stated concretely, that's a gap to surface (step 5) —
  never invent the flow or the contract to keep moving.
- **API needs the SDD.** No SDD → design UI journeys only and leave API deferred;
  never fabricate endpoint contracts from the PRD alone. SDD §3 too vague to state
  an envelope → route back to `/afk:to-sdd`, don't guess.
- **Design buildable scenarios.** Ground UI journeys in what
  `verification/ui-e2e` can drive and API scenarios in what `verification/api` +
  `../core` can issue (canonical recipes: `verification/ui-e2e/AUTHORING.md`,
  `verification/api/AUTHORING.md`). Reuse existing flows/helpers. Never spec a
  scenario the suite has no way to perform.
- **API scenarios must cover the below-the-UI guard.** An API/MCP caller bypasses
  every UI check — no-token, bad-token, and role-scoping assertions are mandatory
  where the endpoint is protected (per the SDD §9b seam). That coverage is the
  modality's reason to exist.
- **Every scenario traces to a source; every gap is named.** No orphan scenarios,
  no silently-swallowed PRD/SDD ambiguities.
- **Note env-limited scenarios as you go** — both modalities — so
  `/afk:to-verification-plan` can mark them and the downstream gate excludes them
  from its green verdict rather than reading them as failures.
- **You write no file and touch no tracker.** This skill only interviews. The
  artifact is `/afk:to-verification-plan`'s job; it touches no Jira and no GitLab.

## Next

The scenarios are settled in the conversation. Run **`/afk:to-verification-plan`**
to synthesize them into `VERIFICATION-PLAN.md` sibling to the PRD (it does NOT
re-interview — it writes what was settled here). From there, `/afk:to-subtasks`
detects the plan and emits the `## Feature smoke gate` plus the terminal build
subtasks (`NNNN-smoke-e2e`, and `NNNN-smoke-api` when API scenarios exist), and
`/afk:smoke-test` later runs both modalities against a running app as the
completion gate.

# Verification Plan — {Feature Name}

> Parent ticket: {TICKET-ID}   Sources: [PRD](PRD.md){· [SDD](SDD.md)}
> Suite: 11700-payable/verification   Built per: ui-e2e/AUTHORING.md · api/AUTHORING.md
> Status: draft (built by NNNN-smoke-e2e / NNNN-smoke-api; run by /afk:smoke-test)

## UI Journeys

Each is one integrated end-user browser flow that decides "feature works". Each
traces to a PRD User Story and becomes one `Scenario` in the ui-e2e Gherkin catalog.

| # | Journey (plain business language) | Actor | Traces to | Env-limited? |
|---|-----------------------------------|-------|-----------|--------------|
| 1 | <trigger → click-path → definition of done> | <role/job> | PRD User Story N | no |
| 2 | <journey> | <role> | PRD User Story M | env-limited (@sap) |

### U1 — <journey title>
- **Given** <preconditions / data setup>
- **When** <the concrete click-path, step by step>
- **Then** <the observable definition of done — the assertion>
- **Persistence reverify**: <iff the Then asserts a persisted (or deliberately not-persisted) DB value — reload the same screen/dialog (browser refresh / reopen) and re-assert against freshly-fetched data, proving the value reached the DB and isn't just optimistic client/form state; else "n/a">
- **Alt/error paths**: <edge journeys worth gating, or "none">
- **Reuses**: <existing L2 scenarios.mjs flows this leans on, if known>

## API Scenarios

<present iff an SDD exists; otherwise this whole section is the one-line placeholder:>
> Deferred — needs the SDD's §3 endpoint contracts. Re-run /afk:grill-verification
> after /afk:to-sdd, then /afk:to-verification-plan to append these.

Each is one direct-REST check that proves a backend contract without the UI. Each
traces to an SDD §3 endpoint (+ the PRD Acceptance Criterion it proves) and becomes
one `node:test` *.test.mjs in verification/api/ (using ../core).

| # | Scenario (call → asserted contract) | Surface (method + path) | Traces to | Env-limited? |
|---|-------------------------------------|-------------------------|-----------|--------------|
| 1 | <call → response envelope asserted> | GET /api/... | SDD §3 row "..." · PRD AC k | no |
| 2 | <unauthorized role → 403 envelope> | POST /api/... | SDD §9b row "..." | no |

### A1 — <scenario title>
- **Given** <preconditions / data setup via ../core>
- **When** <method + surface + request shape (auth role, path, body)>
- **Then** <the asserted response envelope — the REAL shape, success AND edge>
- **Persistence refetch**: <iff the contract is a state change that must persist (or must *not* — rejected write / rolled-back txn) — issue an independent GET (not the write's own response body) and assert the persisted shape; else "n/a">
- **Auth/authz**: <no-token / garbage-token / role-scoping assertions>
- **Reuses**: <existing core/api helpers this leans on, if known>

## Aspect coverage

One verdict per aspect: a triggered aspect points at the row(s) that prove it; a
non-triggered one records why it's N/A. Role-based and data-scoped access each owe
a proving row in **both** modalities.

<!-- aspect set below: lockstep copy — owned by skills/afk/grill-verification/SKILL.md (aspect table) -->

| Aspect | Verdict | Proving rows | Env-limited? |
|--------|---------|--------------|--------------|
| Role-based access | triggered (always) | U1 (denied tier), A2 (403) | no |
| Data-scoped access | triggered / N-A — <reason> | <U#, A#> | env-limited (no scoped users) |
| Input validation | triggered / N-A — <reason> | <U#, A#> | no |
| Envers audit trail | triggered / N-A — no new entity | <A#> | no |
| <situational, if applies> | triggered / N-A — <reason> | <#> | <?> |

## Gaps surfaced

Gaps the scenario-walk exposed, for the human to fold back into the PRD/SDD.
(Load-bearing gaps were routed back during /afk:grill-verification.)

- <gap> — <which Story / endpoint / scenario exposed it>

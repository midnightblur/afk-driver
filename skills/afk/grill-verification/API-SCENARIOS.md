# afk:grill-verification — API scenarios

Sibling detail for [SKILL.md](SKILL.md). **API scenarios** are direct-REST checks
hitting the backend's endpoints with no browser — they prove the backend contract
the feature exposes to API and MCP callers, who bypass every UI guard. Everything
else — the modality matrix, the UI-journey grill loop, the aspect table, the Hard
rules (incl. "API needs the SDD" and its route-back) — stays in `SKILL.md`.

## Grill the API scenarios

Work from the SDD §3 L2 endpoints and §9b below-the-UI guards. For each endpoint
the feature adds or changes, drive the user through:

- **The call** — method + surface + request shape (auth role/token, path, body),
  in terms the `../core` REST client can issue (see
  `11700-payable/verification/api/AUTHORING.md`).
- **The asserted contract** — the success response envelope, **and** the contract
  edges this backend actually returns. Pin the real shape, not the ideal — actual
  edge envelopes (missing entity, unauthorized scope, …) are documented in
  `11700-payable/verification/api/AUTHORING.md`. User can't state the envelope →
  SDD §3 gap, surface it (the "Surface PRD/SDD gaps" step in `SKILL.md`).
- **Aspects below the UI** — API/MCP callers bypass every UI guard, so this
  modality proves the aspects *at the contract*:
  - **Role-based access** — no-token and garbage-token rejection, plus
    role-scoping: a role *with* access accepted vs one *without* refused
    (token minting per `11700-payable/verification/api/AUTHORING.md`).
  - **Data-scoped access** — a token/user scoped to one company/vendor gets
    only its rows; a cross-scope read is refused. Often `env-limited`
    (needs scoped users). Enumerate every dropdown/lookup/reference-data
    endpoint the feature's UI consumes — including shared endpoints inherited
    from other surfaces — and give each a scenario proving both role
    authorization and company/vendor scoping with a non-full-access identity,
    or a recorded N/A with the reason.
  - **Input validation** — a violating body returns the real rejection
    envelope (the contract's `400`/`422` shape), not a `500`.
  - **Envers audit** *(when the feature adds a new entity)* — after a write,
    the history/revisions surface returns the audited revision.
- **New boundary over an existing pipeline** — when the endpoint wraps an
  existing create/update pipeline in its own transaction boundary
  (orchestrator / consume / bulk wrapper), re-prove the wrapped pipeline's
  standard validation failures at the NEW surface: one negative scenario per
  conditionally-required field absent, asserting the 4xx contract. A new
  `@Transactional` boundary changes checked-exception rollback semantics — a
  validation error that returned 400 at the old surface can surface as a 500
  at the new one, so the wrapped pipeline's own scenarios don't cover it.
- **Preconditions / data setup** — what must exist first (becomes the test's
  setup via `../core`).
- **Env reachability** — same `env-limited` rule as UI (e.g. an endpoint that
  fans out to SAP).

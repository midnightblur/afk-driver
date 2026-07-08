# afk:grill-verification — API scenarios

Sibling detail for [SKILL.md](SKILL.md). **API scenarios** are direct-REST checks
that hit the backend's endpoints with no browser at all — they prove the backend
contract the feature exposes to API and MCP callers, who bypass every UI guard.
Everything else — the modality matrix (when API scenarios are in play), the
UI-journey grill loop, the aspect table, and the Hard rules (including "API needs
the SDD" and its route-back) — stays in `SKILL.md`.

## Grill the API scenarios

Work from the SDD §3 L2 endpoints and the §9b below-the-UI guards. For each
endpoint the feature adds or changes, drive the user through:

- **The call** — method + surface + the request shape (auth role/token, path,
  body), in terms the `../core` REST client can issue (see
  `11700-payable/verification/api/AUTHORING.md`).
- **The asserted contract** — the response envelope on success, **and** on the
  contract edges this backend actually returns. Pin the real shape, not the
  ideal one — the backend's actual edge envelopes (missing entity, unauthorized
  scope, …) are documented in `11700-payable/verification/api/AUTHORING.md`. If
  the user can't state the envelope, that's an SDD §3 gap — surface it (the
  "Surface PRD/SDD gaps" step in `SKILL.md`).
- **Aspects below the UI** — because API/MCP callers bypass every UI guard,
  this modality is where the aspects are proven *at the contract*:
  - **Role-based access** — no-token and garbage-token rejection, and
    role-scoping: a role *with* access accepted vs one *without* refused
    (token minting per `11700-payable/verification/api/AUTHORING.md`).
  - **Data-scoped access** — a token/user scoped to one company/vendor gets
    only its rows, and a cross-scope read is refused. Often `env-limited`
    (needs scoped users).
  - **Input validation** — a violating body returns the real rejection
    envelope (the contract's `400`/`422` shape), not a `500`.
  - **Envers audit** *(when the feature adds a new entity)* — after a write,
    the history/revisions surface returns the audited revision.
- **Preconditions / data setup** — what must exist first (these become the
  test's setup via `../core`).
- **Env reachability** — same `env-limited` rule as UI (e.g. an endpoint that
  fans out to SAP).

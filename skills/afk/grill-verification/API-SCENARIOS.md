# afk:grill-verification — API scenarios

Sibling detail for [SKILL.md](SKILL.md). **API scenarios** are direct-REST checks
that hit the backend's endpoints with no browser at all — they prove the backend
contract the feature exposes to API and MCP callers, who bypass every UI guard.
They are designed **only when an SDD is present** (they verify the SDD's §3 L2
endpoint contracts). Everything else — the UI-journey grill loop, the aspect and
modality tables, and the Hard rules — stays in `SKILL.md`.

## When to invoke — if the SDD has no usable endpoint contract

**If the SDD has no usable endpoint contract.** API scenarios read the SDD §3 L2
**API contract table** (surface, method, request/response shape, error codes) and
the §9b external seams (especially the "a new API/MCP caller bypasses the UI"
guards `/afk:grill-solution` flags). If §3 is empty or too vague to state an
endpoint's success **and** error/empty envelope, that's an SDD gap — **stop and
route back** to `/afk:grill-solution` + `/afk:to-sdd` to settle the contract.
Don't invent endpoints to keep moving.

## Process — grill the API scenarios

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
   - **Aspects below the UI** — because API/MCP callers bypass every UI guard,
     this modality is where the aspects are proven *at the contract*:
     - **Role-based access** — no-token and garbage-token rejection, and
       role-scoping: mint a token for a role *with* access vs one *without*
       (`mintToken('<descriptor role>')` in `../core`) → `200` vs `403`.
     - **Data-scoped access** — a token/user scoped to one company/vendor gets
       only its rows, and a cross-scope read is refused (e.g. `403
       "no.authorized.vendor"`). Often `env-limited` (needs scoped users).
     - **Input validation** — a violating body returns the real rejection
       envelope (the contract's `400`/`422` shape), not a `500`.
     - **Envers audit** *(when the feature adds a new entity)* — after a write,
       the history/revisions surface returns the audited revision.
   - **Preconditions / data setup** — what must exist first (these become the
     test's setup via `../core`).
   - **Env reachability** — same `env-limited` rule as UI (e.g. an endpoint that
     fans out to SAP).

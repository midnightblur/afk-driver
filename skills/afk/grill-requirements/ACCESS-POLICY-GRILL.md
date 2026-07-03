### Grill the access & validation policy (every feature)

Almost every feature has an access boundary, and the boundary is the thing most
often *assumed* and never *stated* — which is how a feature ships "done" with the
backend correctly blocking a role while the UI happily lets that role in — the
surface itself never gated, even though the API is. So for **every actor and every User Story**, grill the
policy out loud — it is requirement-level (the *what*, not the *how*), and lands
in the PRD's `## Access & validation policy` matrix that `/afk:to-prd` writes:

- **Role policy** — the permitted role(s) **and at least one role that must be
  denied** the capability. A story whose author can't name who is *denied* is a
  flagged requirements gap, not a story that's done. Naming the denied role is
  what makes a verification scenario (UI: nav-item absent / route redirect; API:
  `403`) designable later.
- **Data-scope policy** — *which* entities / surfaces this actor sees only a
  scoped slice of, scoped by **company and/or vendor**. Note: tenancy here is
  build-per-tenant (single-tenant in dev — see core-services `CLAUDE.md`
  "Tenancy & data scoping"), so the scope is company/vendor, **never tenant**.
  Capture *which entity is scoped*, not concrete company/vendor values — those
  are FOS-configured at runtime, not a requirement. ("Unscoped — this actor sees
  all" is a valid, but explicit, answer.)
- **Validation policy** — the business rules on inputs / workflow transitions,
  whenever user input or a workflow is involved (required fields, bounds,
  allowed transitions, what a violation should refuse).

These three are the requirement-level aspects. **Envers audit** (a new entity →
must be audited) and the *mechanism* of role/scope enforcement are
solution-level — leave them to `/afk:grill-solution` + `/afk:to-sdd`; just flag
them in passing if they surface.

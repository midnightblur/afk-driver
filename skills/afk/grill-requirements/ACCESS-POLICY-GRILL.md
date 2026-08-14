### Grill the access & validation policy (every feature)

Almost every feature has an access boundary — the thing most
often *assumed*, never *stated* (why a one-sided guard ships broken: the
both-sides doctrine in `../grill-solution/EXTERNAL-SEAM-RULE.md`, check 3).
For **every actor and every User Story**, grill the
policy out loud — requirement-level (the *what*, not the *how*), landing
in the PRD's `## Access & validation policy` matrix that `/afk:to-prd` writes:

- **Role policy** — the permitted role(s) **and at least one role that must be
  denied** the capability. A story whose author can't name who is *denied* is a
  flagged requirements gap, not a done story. Naming the denied role is
  what makes a verification scenario (UI: nav-item absent / route redirect; API:
  `403`) designable later.
- **Data-scope policy** — *which* entities / surfaces this actor sees only a
  scoped slice of, scoped by **company and/or vendor**. Tenancy here is
  build-per-tenant (single-tenant in dev — see core-services `CLAUDE.md`
  "Tenancy & data scoping"), so scope is company/vendor, **never tenant**.
  Capture *which entity is scoped*, not concrete company/vendor values — those
  are FOS-configured at runtime, not a requirement. ("Unscoped — this actor sees
  all" is a valid but explicit answer.)
- **Validation policy** — business rules on inputs / workflow transitions,
  whenever user input or a workflow is involved (required fields, bounds,
  allowed transitions, what a violation should refuse).

These three are the requirement-level aspects. **Envers audit** (a new entity →
must be audited) and the *mechanism* of role/scope enforcement are
solution-level — leave them to `/afk:grill-solution` + `/afk:to-sdd`; flag
them in passing if they surface.

# SDD template

<sdd-template>

# SDD — {Feature Name}

> Parent PRD: `{relative path to PRD.md}`
> Status: Draft | Approved | Superseded
> Last updated: {YYYY-MM-DD}

## §0 Binding Contract

This SDD and its accepted ADRs are **binding** on implementing agents and reviewers.

**Required visual:** the lock-vs-latitude table below.

| Aspect | Locked by SDD/ADR | Executor latitude |
|--------|-------------------|-------------------|
| Pattern choice | ✅ | ❌ |
| Module public interface | ✅ | ❌ |
| API contract / schema | ✅ | ❌ |
| Aggregate boundary | ✅ | ❌ |
| Txn / idempotency strategy | ✅ | ❌ |
| External-seam contract (§9b: framework I/O shape, field source-of-truth, enforcement point, failure surface) | ✅ | ❌ |
| File / package layout *within* a named module | ❌ | ✅ |
| Private helper extraction | ❌ | ✅ |
| Internal naming, control flow | ❌ | ✅ |
| Test fixture structure | ❌ | ✅ |

**Conflict procedure.** If an executor finds a binding decision wrong / infeasible / contradicting reality, exit the subtask with `design_conflict` status quoting the SDD section + the conflict. Route back to `/afk:grill-solution` for a new ADR (Status: Accepted, Supersedes: NNNN). Do not override silently.

## §1 Context Summary

One paragraph. WHY this design exists. Reference the PRD for the WHAT.

**Required visual:** none (orientation only).

---

## §2 L1 — System Topology

Monolith vs microservices, sync vs event-driven backbone, multi-tenancy, deployment model. Almost always one line: "Inherited from {existing system}."

**Required visual:** if the feature touches more than one deployable unit, a `C4Context` or `flowchart` showing where this feature lives in the wider system. Otherwise: one-line statement of inheritance.

## §3 L2 — Service Boundaries & Integration

Which service owns what. Where the seam falls. Integration style. Versioning posture.

**Visuals (those that carry signal for this feature):**

1. `flowchart LR` — services as nodes, edges labeled with integration style (REST / gRPC / async-event / shared DB) + the message name.
2. `sequenceDiagram` — one per non-trivial cross-service interaction.
3. **API contract table** — surface, method, request shape ref, response shape ref, error codes, version. Cite OpenAPI / proto file paths; do not inline schemas that will rot. This table is the **source `/afk:grill-verification` reads to design the API verification scenarios** (direct-REST checks for API/MCP callers), so each row must be concrete enough to assert against: state the **success envelope AND the real edge envelopes** the backend actually returns (e.g. a missing entity → `200 + NULL_RESPONSE` rather than 404; an unauthorized vendor → `403 "no.authorized.vendor"`), plus the auth/role required (the below-the-UI guard, cross-referenced to its §9b seam). A row too vague to state its envelope is a §13 gap, not a publishable contract.

## §4 L3 — Data Architecture

For each piece of state.

**Visuals (those that carry signal for this feature):**

1. **State table** — one row per piece of state:

   | State | Datastore | Partitioning | Replication | Retention | Schema-evolution policy | PII? | Audited? (Envers) |
   |-------|-----------|--------------|-------------|-----------|--------------------------|------|-------------------|

   A new entity marked **Audited? = yes** is the trigger that makes the audit-trail
   verification aspect mandatory in `/afk:grill-verification`.

2. `erDiagram` — cross-state relations (FK, reference-by-id, denormalization edges). Even single-table designs benefit from one entity box.
3. **Cache topology diagram** (`flowchart`) if a cache is in play, showing read-through / write-behind / TTL per layer.

## §5 L4 — Cross-Cutting & Quality Attributes

**Required visuals (per concern present):**

| Concern | Required visual |
|---------|-----------------|
| AuthN flow | `sequenceDiagram` showing token issuance + propagation |
| AuthZ rules | table — surface × **permitted roles** × **denied roles** × **enforcement point (UI route/menu guard AND backend guard — both, cf. §9b)**. A surface guarded on only one side ships silently broken. This table is what `/afk:grill-verification` reads to design the role-based aspect rows. |
| Data-scoping | table — scoped entity × scope (company / vendor — never tenant) × enforcement mechanism (e.g. AOP aspect + projection filter; company always-on vs vendor toggle) |
| Idempotency | table — surface, key shape, dedup window, side-effect ledger |
| Retry + timeout | table — call, attempts, backoff (numbers), timeout (ms) |
| Rate limit | table — surface, limit, window, enforcer |
| Sync vs async | `sequenceDiagram` per long-running op + a one-row table per op with the latency budget that drove the choice |
| Feature flags | table — flag key, default, rollout plan, cleanup date |
| Observability | table — signal (log/metric/trace/alert), what it detects (cite §7 row) |

## §6 L5 — Domain Model

**Visuals (those that carry signal for this feature):**

1. `erDiagram` — aggregates, entities, value objects, relations. Mark aggregate roots.
2. **Invariants table** — invariant text, owner aggregate, guardian method.
3. `stateDiagram-v2` — per aggregate with non-trivial lifecycle. Terminal states marked.
4. **Domain events table** — event name, emitter aggregate, consumers, payload schema ref.

## §7 L6 — Process & Coordination

For each top use case from the PRD.

**Visuals (those that carry signal for this feature):**

1. `sequenceDiagram` — actors + aggregates + external services as participants. Mark txn boundaries with `Note over ...: TXN START / COMMIT`.
2. **Use-case detail table** — trigger, txn boundary strategy (single-txn / saga / outbox / 2PC / accept-eventual), consistency model per read path, concurrency control.
3. `stateDiagram-v2` — for each saga / outbox flow.
4. **Failure & recovery matrix** (consolidated for the feature):

   | Failure point | Detection signal | Automatic recovery | Manual recovery | Owner |
   |---------------|------------------|--------------------|-----------------|-------|

## §8 L7 — Module Decomposition

**Visuals (those that carry signal for this feature):**

1. `flowchart TB` — module-dependency DAG. Edges point from dependent to dependency. **Cycles are a bug.** Group by hex / onion / clean ring with `subgraph`.
2. **Module table** — module, purpose (one line), public interface (signature-level), depends on, owner aggregate from §6.

## §9 L8 — Tactical Patterns

**Required visuals (per pattern):**

1. **Patterns Applied table** — concern, pattern, ADR file:

   | Concern | Pattern | ADR |
   |---------|---------|-----|

2. `classDiagram` — interface + impls + how the pattern is wired (registry, factory, DI scope). One per non-trivial pattern.

## §9b External Seams & Failure Affordance

The seams where our code meets things we don't control — synthesized from
the External-seam rule's four checks in `/afk:grill-solution`. Capture, in
whatever table shape fits: each framework boundary (what it does to our
value at the pinned version + the **seam-test** that asserts on its real
output), each field contract's canonical source of truth, each relied-on
invariant's enforcement point **on both sides of the UI seam** (the UI-surface
guard *and* the below-UI guard proven for the new caller — a guard on only one
side ships silently broken — e.g. backend `403`, UI ungated), and the
failure affordance per violation class. If the feature has no external seam, say
so in one line rather than deleting the section.

**Required visual:** a table covering the seams present. The framework
rows' **seam-test** entry is mandatory — a test on the framework's real
output (serialized result / generated schema / surfaced error), not our
objects; that name is what `/afk:to-subtasks` cites in `## Acceptance`. E.g.:

| Boundary | Framework @ pin | What it does to our value | Failure surface | Seam-test |
|----------|-----------------|---------------------------|-----------------|-----------|

---

## §10 NFRs

**Required visual:** quantified table. Numbers, not adjectives.

| Concern | Target | Measurement | Owner |
|---------|--------|-------------|-------|
| Latency p95 (ms) | < 200 | server-side trace | service-X team |
| Throughput (rps) | ≥ 500 | load test Y | ... |
| Availability (%) | 99.9 | SLO dashboard Z | ... |

Add a `pie` chart for any concern with a budget split worth visualizing (e.g. p95 latency budget across hops).

## §11 Out of Scope

Bullet list. Cite PRD's Out of Scope and add design-level exclusions.

## §12 Reversed Decisions

**Required visual:** table.

| Prior ADR | Superseded by | Reason |
|-----------|---------------|--------|

## §13 Open Questions

**Required visual:** table.

| Question | Layer (L1-L8) | Blocks executor? | Owner | Target resolve date |
|----------|---------------|------------------|-------|---------------------|

If any row has `Blocks executor? = yes` in L2-L7, the design is NOT publishable — bounce back to `/afk:grill-solution`. L1 / L8 open questions may pass if scoped.

</sdd-template>

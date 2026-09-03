# SDD template

Before filling any section, read `LANGUAGE.md` (plugin root) and apply it throughout — compact by default, no fact dropped.

<sdd-template>

# SDD — {Feature Name}

> Parent PRD: `{relative path to PRD.md}`
> Status: Draft | Approved | Superseded
> Last updated: {YYYY-MM-DD}
> Reading guide: sections follow the L1–L9 design-layer ladder, top of the system down to the code
> (L1 topology · L2 service boundaries · L3 data · L4 cross-cutting quality · L5 domain model ·
> L6 processes · L7 modules · L8 patterns · L9 seams into existing code). Skim §0 (what's locked)
> and §1 (why) first; non-implementers can stop there or read the DESIGN-BRIEF instead.

## §0 Binding Contract

This SDD and its accepted ADRs are **binding** on implementing agents and reviewers.

**Required visual:** the lock-vs-latitude table below.

| Aspect | Locked by SDD/ADR | Executor latitude |
|--------|-------------------|-------------------|
| Pattern choice | ✅ | ❌ |
| Module public interface | ✅ | ❌ |
| API contract / schema | ✅ | ❌ |
| Persisted schema — fields, relations, migration (§4) | ✅ | ❌ |
| Lifecycle states + legal transitions (§6) | ✅ | ❌ |
| Roles permitted/denied per surface (§5) | ✅ | ❌ |
| Aggregate boundary | ✅ | ❌ |
| Txn / idempotency strategy | ✅ | ❌ |
| External-seam contract (§9b: framework I/O shape, field source-of-truth, enforcement point, failure surface) | ✅ | ❌ |
| File / package layout *within* a named module | ❌ | ✅ |
| Private helper extraction | ❌ | ✅ |
| Internal naming, control flow | ❌ | ✅ |
| Test fixture structure | ❌ | ✅ |

**Conflict procedure.** Executor finds a binding decision wrong / infeasible / contradicting reality → classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits the subtask with `design_conflict` status quoting the SDD section + the conflict, routed back to `/afk-toolkit:grill-solution` for a new ADR (Status: Accepted, Supersedes: NNNN). Never override off the record.

**Human sign-off register.** One row per human-locked aspect (the set, its contract grades, and the signing protocol: `skills/afk/grill-solution/HUMAN-SIGNOFF.md`), transcribed from the solution grill's log — never re-derived, never inferred. These aspects were decided by a human, not by the design conversation; the row is the proof.

| Aspect | Section | Status | Signed by / date | Approved wording |
|--------|---------|--------|------------------|------------------|
| HL-n {aspect} | §n | signed \| n/a | {who} / {YYYY-MM-DD} | "{their words}" |

A live aspect that is not `signed`, or whose section says something the signature didn't cover, makes this SDD unpublishable.

## §1 Context Summary

One paragraph. WHY this design exists. Reference the PRD for the WHAT.

**Required visual:** none (orientation only).

---

## §2 L1 — System Topology

Monolith vs microservices, sync vs event-driven backbone, multi-tenancy, deployment model. Almost always one line: "Inherited from {existing system}."

**Required visual:** feature touches >1 deployable unit → a `C4Context` or `flowchart` showing where this feature lives in the wider system. Otherwise: one-line inheritance statement.

## §3 L2 — Service Boundaries & Integration

Which service owns what. Where the seam falls. Integration style. Versioning posture.

**Visuals (those that carry signal for this feature):**

1. `flowchart LR` — services as nodes, edges labeled with integration style (REST / gRPC / async-event / shared DB) + the message name.
2. `sequenceDiagram` — one per non-trivial cross-service interaction.
3. **API contract table** — one row per surface this feature adds or changes, at HL-2 contract grade (`skills/afk/grill-solution/HUMAN-SIGNOFF.md`): method + path, auth + permitted roles (the below-the-UI guard, cross-referenced to its §9b seam), request fields with their validation, success envelope, each error envelope with its code and trigger, paging/filtering/sorting, idempotency posture, version, and — where the surface already exists — the verdict on existing callers (compatible / breaking). A **signed-off aspect**: this table and the §0 register describe the same design, or neither is publishable. Where a canonical schema artifact exists (OpenAPI / proto), cite its path for the field-by-field shape rather than inlining what will rot; where none exists, the fields belong here — an executor must not be left to invent the contract a human signed.

   This table is also the **source `/afk-toolkit:grill-verification` reads to design the API verification scenarios** (direct-REST checks for API/MCP callers), so each row must be concrete enough to assert against: the **success envelope AND the real edge envelopes** the backend returns (a missing entity may be an empty-success envelope rather than 404, a denial a coded 403 — envelope conventions: `11700-payable/verification/api/AUTHORING.md`). A row too vague to state its envelope is a §13 gap, not a publishable contract.

## §4 L3 — Data Architecture

For each piece of state.

**Visuals (those that carry signal for this feature):**

1. **State table** — one row per piece of state:

   | State | Datastore | Partitioning | Replication | Retention | Schema-evolution policy | PII? | Audited? (Envers) |
   |-------|-----------|--------------|-------------|-----------|--------------------------|------|-------------------|

   A new entity marked **Audited? = yes** makes the audit-trail
   verification aspect mandatory in `/afk-toolkit:grill-verification`.

2. **Entity design** — for every entity this feature persists or alters, at HL-1 contract grade (`skills/afk/grill-solution/HUMAN-SIGNOFF.md`). A **signed-off aspect**: what the §0 register signed is what stands here.

   | Field | Type | Null? | Default | Unit / precision | Constraint | Indexed / unique | Note |
   |-------|------|-------|---------|------------------|------------|------------------|------|

   Plus, per entity: its identity (key + generation), and one relation row each —

   | Relation | Target | Cardinality | Owning side | On delete / orphan | Fetch posture |
   |----------|--------|-------------|-------------|--------------------|---------------|

   **Surface reachability** — for every field this feature **adds** to an existing entity, or makes mandatory/forbidden on one, state whether each programmatic surface already exposing that entity must change with it: the agent-facing tool schemas, the import/export templates, the public API DTOs. A field the domain now requires but a surface's schema cannot express makes that surface **unusable**, not merely incomplete — its callers fail on a field they were never shown. The verdict is one line per surface (`changes` / `no change, because …`); "the feature touches no file under that surface" is the symptom, not the answer. Where the service's `STAPLES.md` carries a matching staple, that staple's obligation is the standard this line is judged against.

   **Migration & backfill** — for every altered entity, what happens to rows that already exist (new column's value for old rows, a widened/narrowed constraint, a dropped field's data) and whether the change is reversible. An altered entity with no migration line is an unpublishable §13 gap, not a silent "the ORM will handle it".

3. `erDiagram` — cross-state relations (FK, reference-by-id, denormalization edges). Even single-table designs benefit from one entity box.
4. **Cache topology diagram** (`flowchart`) if a cache is in play, showing read-through / write-behind / TTL per layer.

## §5 L4 — Cross-Cutting & Quality Attributes

**Required visuals (per concern present):**

| Concern | Required visual |
|---------|-----------------|
| AuthN flow | `sequenceDiagram` showing token issuance + propagation |
| AuthZ rules | table — surface × **permitted roles** × **denied roles** × **enforcement point (UI route/menu guard AND backend guard — both, cf. §9b and the both-sides doctrine in `skills/afk/grill-solution/EXTERNAL-SEAM-RULE.md` check 3)**. This table is what `/afk-toolkit:grill-verification` reads to design the role-based aspect rows. |
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
the External-seam rule's four checks in `/afk-toolkit:grill-solution`. Capture, in
whatever table shape fits: each framework boundary (what it does to our
value at the pinned version + the **seam-test** asserting on its real
output), each field contract's canonical source of truth, each relied-on
invariant's enforcement point **on both sides of the UI seam** (per the
both-sides doctrine in `skills/afk/grill-solution/EXTERNAL-SEAM-RULE.md`
check 3), and the failure affordance per violation class. No external seam →
say so in one line rather than deleting the section.

**Required visual:** a table covering the seams present. The framework
rows' **seam-test** entry is mandatory — a test on the framework's real
output (serialized result / generated schema / surfaced error), not our
objects; that name is what `/afk-toolkit:to-subtasks` cites in `## Acceptance`. E.g.:

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

| Question | Layer (L1-L9) | Blocks executor? | Owner | Target resolve date |
|----------|---------------|------------------|-------|---------------------|

If any row has `Blocks executor? = yes` in L2-L7 or L9, the design is NOT publishable — bounce back to `/afk-toolkit:grill-solution`. L1 / L8 open questions may pass if scoped.

## §14 L9 — Implementation Seams & Change Impact

**Required visual:** table — one row per seam the design touches in existing code, from the L9 seam walk.

| Seam (class/method/contract) | Existing contract (verified where) | Planned change | Impacted flows | Conventions / landmines | Verdict |
|------------------------------|------------------------------------|----------------|----------------|-------------------------|---------|

Every row's existing contract cites where it was verified (file); `Verdict` is `fits` / `extends (ADR-NNNN)` / `reworked`. Below the table, list each compatibility-audit finding that was **accepted** rather than resolved, with its rationale (resolved findings changed the design, need no entry). A §14 with an unverified contract or an unlisted accepted finding is not publishable.

</sdd-template>

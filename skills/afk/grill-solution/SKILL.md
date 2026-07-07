---
name: grill-solution
description: Interview the user relentlessly about the solution design top-down across 9 layers (L1 system topology -> L9 implementation seams), resolving each layer before descending. Use when user has a PRD and wants to design the system, get grilled on architecture, or mentions "grill-solution" / "architect-grill". Does NOT produce documents — pair with `/afk:to-sdd`.
---

Interview the user relentlessly about every aspect of the architecture until shared understanding. Walk the design tree **top-down across 9 layers**. Resolve each layer before descending — lower-layer choices are brittle when higher-layer choices aren't pinned (e.g. picking Strategy at L8 before deciding at L4 whether rendering is sync or async → strategy interface might need to return a `Future<T>` you didn't plan for).

Ask questions one at a time. For each, give your recommended answer with the trade-off and the alternative you reject.

If a question can be answered from the codebase, PRD, a `PROTOTYPE.md` if one settled the UI (its UX decisions — modal vs page, inline vs wizard — are design inputs here), existing ADRs, or the project glossary (start at root `GLOSSARY-MAP.md`, then owning service's `GLOSSARY.md`), do that instead. Speak the design in the glossary's canonical vocabulary.

The staples the PRD **accepted** (from `{service}/STAPLES.md`) are **binding design inputs**: realize each in the layer it belongs to, using the staple's registry **Reference** as the template, and weigh it with ≥2 alternatives like any other decision. A design that drops an accepted staple isn't exhausted.

## The 9 layers (grill in this order)

### L1 — System / topology
Monolith vs microservices, sync vs event-driven backbone, multi-tenancy stance, deployment model (single / multi-region), runtime model (request/response, streaming, batch). Usually inherited; only ADR if THIS feature reverses a default.

### L2 — Service boundaries & integration
Which service owns what, where the seam falls between this feature and the rest, integration style (REST / gRPC / message / shared DB — last almost always wrong), public-contract versioning posture, breaking-change policy.

### L3 — Data architecture
Datastore per piece of state (RDBMS / document / KV / search / event store / object store), partitioning / sharding, replication topology, cache placement, schema-evolution policy, retention. Most expensive layer to get wrong — grill hard here. For every **new entity / table**, decide whether it is **Envers-audited** — a new audited entity triggers the mandatory audit-trail verification aspect (`/afk:grill-verification`), and the SDD §4 L3 state table records the `Audited?` verdict.

### L4 — Cross-cutting & quality attributes
Auth model (session / JWT / mTLS / OAuth flow); **authz model** (RBAC / ABAC / ReBAC) — for each protected surface, the permitted **and denied** role(s) **and where each guard is enforced on both sides of the UI seam** (per [EXTERNAL-SEAM-RULE.md](EXTERNAL-SEAM-RULE.md), check 3); **data-scoping** — which entities are company/vendor-scoped (never tenant — build-per-tenant, single-tenant in dev) and the enforcement mechanism (e.g. AOP aspect + projection query-filter; company always-on vs vendor toggle); observability stack (logs / metrics / traces / SLOs), retry + timeout policy, **idempotency strategy** (key shape, dedup window, side-effect ledger), rate-limit, secrets handling, feature-flag posture, sync vs async for long-running work.

### L5 — Domain model (tactical DDD)
Aggregates, aggregate roots, invariants and their guardians, entities vs value objects, domain events, anti-corruption layers at boundaries. Every entity has exactly one owner aggregate; every invariant exactly one guardian. Name them in the glossary's terms; if the design needs a term conflicting with or missing from `GLOSSARY.md`, flag it — a language gap to resolve in `/afk:grill-requirements`, not to silently coin here.

### L6 — Process / coordination
Transaction boundaries per use case (what's in one txn, what's across), cross-aggregate strategy (saga / outbox / 2PC / accept-eventual), consistency model per read path (strong / read-after-write / eventual + staleness budget), ordering guarantees, concurrency control (optimistic version / pessimistic lock / CRDT), failure-and-recovery matrix per multi-step flow.

### L7 — Module / component decomposition
Module split inside a service, public module interfaces (the testable seams), dependency direction (hex / onion / clean — pick one and apply), DI scopes, deep vs shallow module.

### L8 — Tactical patterns
Strategy, Visitor, State Machine, Specification, Builder, Chain of Responsibility, Registry, Factory, Template Method, etc. Pattern choice ≠ implementation; it shapes the public seams executors implement against.

### L9 — Implementation seams & change impact
The assembled design proven against the code that exists: per-seam signature/contract alignment, change impact on existing flows, house-convention compliance, must-do landmines (what the existing entry path does that a new path would skip) — then a parallel compatibility audit attacking the whole design vs the codebase. Run per [L9-SEAM-GRILL.md](L9-SEAM-GRILL.md); its seam rows become the SDD's §14.

## Executor latitude (the line below L9)

Below the layers is **executor latitude** — NOT grilled here, NOT in SDD, NOT in ADR. The distinction: L9 reads **existing** code to verify the contracts the design lands on; latitude governs the **new** code the executor writes inside the design's boundaries:

- File / package layout *within* a module the SDD already named.
- Private helper extraction, internal naming.
- Which existing util class to reuse.
- Test fixture structure.
- Local control flow inside one method.
- Library API call shape (when SDD has picked the library).

If a question is below the line, don't ask it. Redirect: "that's executor latitude."

## Triviality cutoff (avoid ADR fatigue)

A decision is **ADR-worthy** when it clears the design-level three-part bar owned by `skills/afk/to-sdd/SKILL.md` (Step 4, "Apply the triviality cutoff"). Apply ADRs for: "Postgres over Mongo because we need cross-aggregate ACID", "async job + signed URL over sync HTTP because p99 render is 8s."

A decision can be in the SDD without being an ADR. ADRs are the subset where the *why* is non-obvious enough to warrant a standalone record.

## Grilling protocol

For each layer L1 → L9:

1. **State the layer and what it covers in one sentence.**
2. **Probe: is anything in this layer non-trivial for THIS feature?** If no -> say so explicitly ("L1 inherited from the monolith — skipping") and move on.
3. **For each non-trivial concern, ask one question at a time.** Recommend an answer. Force ≥2 alternatives — and for **L1–L3** decisions, present one deliberately different **third option** before settling: a different paradigm (event-driven vs sync, buy vs build, denormalize vs join), not a variant of the front-runner, with an honest cost. Two look-alike options is how the obvious answer wins unexamined. Capture the rationale before the next concern. **When the question's premise OR the user's answer references existing infrastructure, apply [GROUNDING-RULE.md](GROUNDING-RULE.md) before locking the decision in.** When a human is present, render per LAVISH.md (RP-1, playbook `comparison`) to lay the alternatives side by side; markdown fallback and driven mode use the prose recap above instead.
4. **Before descending, restate the locked decisions** so the user can challenge. As each layer locks, checkpoint it (one row) into this skill's section of the ticket folder's `GRILL-LOG.md` per `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md` — a 9-layer grill is long; the log is what lets a paused or compacted session resume at the right layer with the locked set intact, and it records L9 seam verdicts until the SDD lands.
5. **Do not skip ahead.** If the user pulls toward L8 (the fun layer) before L3/L4/L6 are pinned, refuse: "Pin the datastore + sync-vs-async first — Strategy interface depends on whether it returns `T` or `Future<T>`."

When the design crosses an external seam, run the checks in [EXTERNAL-SEAM-RULE.md](EXTERNAL-SEAM-RULE.md).

## Stop conditions

Only declare the design exhausted when ALL hold:

- L1 explicitly addressed (even if "inherited").
- Every L2 service boundary has a named owner and integration style.
- Every L3 piece of state has a datastore + retention + evolution policy.
- Every L4 concern has an explicit posture (idempotency keys defined, retry budgets numbered); every protected surface has its permitted **and denied** roles named with an enforcement point on **both** the UI surface and below it; every scoped entity has a named company/vendor scoping mechanism.
- Every L5 entity has exactly one owner aggregate; every invariant exactly one guardian.
- Every L6 use case has a txn strategy; every external call a retry + idempotency posture; every failure point in the matrix a named recovery action.
- Every L7 module has a public interface stated and a dependency-direction call.
- Every L8 pattern choice has ≥2 alternatives weighed.
- Every NFR has a number, not an adjective ("p95 < 200 ms", not "fast").
- **Every claim about existing infrastructure verified against the codebase OR explicitly labelled "unverified premise" with the user's acknowledgement** (per the Grounding rule). A design built on a fictional premise isn't exhausted, it's poisoned.
- **Every external seam has cleared the four checks** (per the External-seam rule): framework runtime behavior verified against the pin, every field contract sourced from its canonical truth, every relied-on invariant enforced on **both** sides of the UI seam (at the surface and below the new caller), every surface's failure affordance pinned — with a framework-seam test flagged wherever check 1 fired.
- **L9 exhausted** per its exit criteria (every seam row verified + verdicted, every landmine handled, every compatibility-audit finding resolved or accepted).

Until all hold, keep grilling.

## Out of scope for this skill

- Do NOT produce SDD or ADR documents. Pair with `/afk:to-sdd` to synthesize artifacts.
- Do NOT descend into implementation (file paths, code snippets, library version pins, helper-function names). Reading existing code for the L9 seam walk is verification, not implementation — that stays in.
- Do NOT grill below L9 (executor latitude).

## Next

Once the Stop conditions hold, run **`/afk:to-sdd`** to synthesize the SDD + per-decision ADRs as artifacts. `/afk:to-sdd` does NOT interview — it synthesizes what was decided here. If it finds a gap, it bounces you back to this skill.

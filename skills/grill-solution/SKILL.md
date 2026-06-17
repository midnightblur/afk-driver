---
name: grill-solution
description: Interview the user relentlessly about the solution design top-down across 8 layers (L1 system topology -> L8 tactical patterns) until every non-trivial decision has a rationale and >=2 alternatives weighed. Walks the design tree layer-by-layer, resolving higher layers before descending — because lower-layer choices are brittle when upper-layer choices haven't been pinned. Use when user has a PRD and wants to design the system, get grilled on architecture, or mentions "grill-solution" / "architect-grill". Does NOT produce documents — pair with `/afk:to-sdd` for that.
---

Interview me relentlessly about every aspect of the architecture until we reach a shared understanding. Walk the design tree **top-down across 8 layers**. Resolve each layer before descending — choices at a lower layer are brittle when choices at a higher layer haven't been pinned (e.g. picking Strategy at L8 before deciding at L4 whether rendering is sync or async means the strategy interface might need to return a `Future<T>` you didn't plan for).

Ask the questions one at a time. For each question, provide your recommended answer with the trade-off and the alternative you are rejecting.

If a question can be answered by exploring the codebase, the PRD, the existing ADRs, or the project glossary (start at the root `GLOSSARY-MAP.md`, then the owning service's `GLOSSARY.md`), do that instead. Speak the design in the glossary's canonical vocabulary.

## The 8 layers (grill in this order)

### L1 — System / topology
Monolith vs microservices, sync vs event-driven backbone, multi-tenancy stance, deployment model (single region / multi-region), runtime model (request/response, streaming, batch). Usually inherited from the existing system; only ADR if THIS feature reverses a default.

### L2 — Service boundaries & integration
Which service owns what, where the seam falls between this feature and the rest, integration style (REST / gRPC / message / shared DB — last is almost always wrong), public contract versioning posture, breaking-change policy.

### L3 — Data architecture
Datastore choice per piece of state (RDBMS / document / KV / search / event store / object store), partitioning / sharding, replication topology, cache placement, schema-evolution policy, retention. Most expensive layer to get wrong — grill hard here.

### L4 — Cross-cutting & quality attributes
Auth model (session / JWT / mTLS / OAuth flow), authz model (RBAC / ABAC / ReBAC), observability stack (logs / metrics / traces / SLOs), retry + timeout policy, **idempotency strategy** (key shape, dedup window, side-effect ledger), rate-limit, secrets handling, feature-flag posture, sync vs async invocation for long-running work.

### L5 — Domain model (tactical DDD)
Aggregates, aggregate roots, invariants and their guardians, entities vs value objects, domain events, anti-corruption layers at boundaries. Every entity has exactly one owner aggregate. Every invariant has exactly one guardian. Name them in the glossary's terms; if the design needs a term that conflicts with or is missing from `GLOSSARY.md`, flag it — that's a language gap to resolve in `/afk:grill-requirements`, not to silently coin here.

### L6 — Process / coordination
Transaction boundaries per use case (what's in one txn, what's across), cross-aggregate strategy (saga / outbox / 2PC / accept-eventual), consistency model per read path (strong / read-after-write / eventual + staleness budget), ordering guarantees, concurrency control (optimistic version / pessimistic lock / CRDT), failure-and-recovery matrix per multi-step flow.

### L7 — Module / component decomposition
Module split inside a service, public module interfaces (the testable seams), dependency direction (hex / onion / clean — pick one and apply), DI scopes, what is a deep module vs shallow.

### L8 — Tactical patterns
Strategy, Visitor, State Machine, Specification, Builder, Chain of Responsibility, Registry, Factory, Template Method, etc. Pattern choice ≠ implementation; it shapes the public seams executors implement against.

## The line below L8

Below L8 is **executor latitude** — NOT grilled here, NOT in SDD, NOT in ADR:

- File / package layout *within* a module the SDD already named.
- Private helper extraction, internal naming.
- Which existing util class to reuse.
- Test fixture structure.
- Local control flow inside one method.
- Library API call shape (when SDD has picked the library).

If a question is below the line, do not ask it. Redirect: "that's executor latitude."

## Triviality cutoff (avoid ADR fatigue)

A decision is **ADR-worthy** when ALL THREE hold:

1. Non-obvious — not the community default for the stack.
2. ≥2 real alternatives exist for THIS context.
3. Reversing it later is expensive.

Skip ADRs for: "we use HTTPS / UTF-8 / JSON / ISO-8601 / the framework's idiomatic way." Apply ADRs for: "we picked Postgres over Mongo because we need cross-aggregate ACID", "we picked async job + signed URL over sync HTTP because p99 render is 8s."

A decision can be in the SDD without being an ADR. ADRs are the subset where the *why* is non-obvious enough to warrant a standalone record.

## Grilling protocol

For each layer L1 → L8:

1. **State the layer and what it covers in one sentence.**
2. **Probe: is anything in this layer non-trivial for THIS feature?** If no -> say so explicitly ("L1 inherited from the monolith — skipping") and move on.
3. **For each non-trivial concern, ask one question at a time.** Recommend an answer. Force ≥2 alternatives. Capture the rationale before moving to the next concern. **If either the question's premise OR the user's answer references existing infrastructure (a library, service, module, schema, queue, cache, auth posture, etc.), verify it against the codebase BEFORE locking the decision in — see the Grounding rule below. A fictional premise yields a fictional design.**
4. **Before descending to the next layer, restate the locked decisions** so the user can challenge.
5. **Do not skip ahead.** If the user pulls toward L8 (the fun layer) before L3/L4/L6 are pinned, refuse: "Pin the datastore + sync-vs-async first — Strategy interface depends on whether it returns `T` or `Future<T>`."

## Grounding rule — verify claims about existing infra

When the user (or your own draft answer) asserts something about
existing infrastructure — libraries, services, frameworks, datastores,
caches, queues, auth providers, observability stacks, modules, schemas,
build/deploy topology — do **not** accept it into the design. Verify
against the codebase before letting it constrain a downstream decision.
A fictional premise propagates into the SDD, then into ADRs, then into
SubTask `## Produces` contracts referencing types that don't exist —
every downstream layer inherits the lie, and no preflight grep can
catch it because the contracts are *internally* consistent with the
fiction.

**Trigger phrases.** When you hear (or are about to write) any of these,
verify before continuing:

- "We use {library/service/framework}" / "we already have {X}"
- "The existing {ClassName/ServiceName/ModuleName}"
- "{X} version {N}.{M} supports {API}" (cross-check `pom.xml` /
  `package.json` / lockfile pin)
- "{X} is configured to {behavior}" (check actual config)
- "Auth is {scheme}" / "we shard by {key}" / "we cache in {store}"
- "There's already a {pattern} for {feature}"

**How to verify, by claim type.**

| Claim about | Verify with |
|---|---|
| Library / dep usage | `ctx_search` `pom.xml`, `build.gradle`, `package.json`, `requirements.txt`. Check the **pinned version**, not just the name. |
| Service / module / class existence | `ctx_search` for the symbol declaration; `ctx_tree` the package. |
| Configuration posture | `ctx_search` `application.yml` / `application.properties` / `*.env*` / framework-specific config files. |
| Schema / table / sharding key | `ctx_search` migration files / changelog / DDL / JPA entity annotations. |
| Existing pattern reuse ("we already use Strategy for X") | `ctx_search` for the named interface / abstract class. |
| Cross-repo / runtime topology / deploy posture | Often unverifiable from this repo alone — see "external claims" below. |

**How to handle a verification miss.**

1. **Surface the gap explicitly.** Quote what the user said. Quote what
   the search found (or didn't find). No papering over.
2. **Walk the user through three options.** (a) They were mistaken —
   redo the question with the actual posture. (b) They're proposing to
   introduce it as part of this feature — that becomes its own
   L1/L2/L3 decision with an ADR, not a casual reference. (c) They
   confused this service with a different repo / module — clarify
   scope, then verify in the right place.
3. **Re-ask the original question** with the corrected premise. The
   answer changes when the premise changes.

**External claims you cannot verify from this repo** (sibling services
in other repos, multi-region routing, ops-team-owned infra) — say so
plainly: *"I can't verify {claim} from this repo. I'll record it as
'unverified premise: {claim} per user assertion.' Want me to ask for
evidence (link / screenshot / second pair of eyes) or proceed with the
unverified label?"* Letting the user decide whether to chase external
verification is fine; **pretending you verified is not**.

**This rule binds across all 8 layers**, not just L1/L2 where infra
claims are most common. Verification triggers at every layer:

- L1 ("we deploy multi-region") — check ops manifests / Terraform.
- L2 ("payable-svc owns invoices") — check ownership in module roots.
- L3 ("we shard payables by tenant_id") — check the sharding config
  or DDL.
- L4 ("we have an idempotency table") — `ctx_search` the schema.
- L5 ("the Order aggregate lives in `core.order`") — verify the
  package + the aggregate-root annotation/class.
- L6 ("the order saga is implemented via outbox") — verify the
  outbox table + dispatcher.
- L7 ("the API contract is in `openapi.yaml`") — `ctx_read` the file.
- L8 ("we already use Strategy here for ExportFormat") — find the
  interface.

Verification is cheap (one `ctx_search` / `ctx_read`); a wrong premise
is not. If you find yourself drafting an answer that references
something specific in the codebase, **verify before you write it down**
— this rule applies to your own drafts too, not just the user's
assertions.

## External-seam rule — the boundary with code you don't control

The Grounding rule proves things *exist*. It won't catch a design that's
wrong at the seam with a framework, a UI contract, or another layer's
enforcement — the grill is sharp on seams between *our* modules and blind
where our code meets things we don't own. Before locking any decision that
crosses such a seam, **verify (don't assume)** the four things that pass
existence checks and still ship broken:

1. **Framework runtime behavior** — not the API signature, what it *does*
   at the pinned version: how it serializes your output, generates the
   input schema from your types, which annotations it honors, how it
   surfaces errors. (Classic misses: a Jackson-2 value serialized by
   Jackson 3; a `@NotNull` that moves no schema.) A test on your own
   object can't cover this — only one asserting on the framework's real
   output can; flag that test so `/afk:to-sdd` binds it.
2. **Contract source of truth** — required / immutable / constraint come
   from the canonical source, not a proxy. Here: UI vuelidate `*Form.vue`
   (required) and edit-mode `:readonly` (immutable), not DB `NOT NULL`.
   Name it and read it.
3. **Where it's enforced** — "the UI prevents X" ≠ "the system prevents
   X." A new API/MCP caller bypasses the UI; verify the guard lives below
   it, or design one that does.
4. **Failure affordance** — design the error contract, not just the happy
   path: per violation class, what the consumer gets, and whether a
   business refusal is distinguishable from a server fault (including the
   framework's own signal, e.g. MCP `isError`).

## Stop conditions

Only declare the design exhausted when ALL hold:

- L1 explicitly addressed (even if "inherited").
- Every L2 service boundary has a named owner and integration style.
- Every L3 piece of state has a datastore + retention + evolution policy.
- Every L4 concern has an explicit posture (idempotency keys defined, retry budgets numbered).
- Every L5 entity has exactly one owner aggregate; every invariant has exactly one guardian.
- Every L6 use case has a txn strategy; every external call has retry + idempotency posture; every failure point in the matrix has a named recovery action.
- Every L7 module has a public interface stated and a dependency-direction call.
- Every L8 pattern choice has ≥2 alternatives weighed.
- Every NFR has a number, not an adjective ("p95 < 200 ms", not "fast").
- **Every claim about existing infrastructure has been verified against the codebase OR explicitly labelled "unverified premise" with the user's acknowledgement** (per the Grounding rule). A design built on a fictional premise is not exhausted, it's poisoned.
- **Every external seam has cleared the four checks** (per the External-seam rule): framework runtime behavior verified against the pin, every field contract sourced from its canonical truth, every relied-on invariant enforced below the new caller, every surface's failure affordance pinned — with a framework-seam test flagged wherever check 1 fired.

Until all hold, keep grilling.

## Out of scope for this skill

- Do NOT produce SDD or ADR documents. Pair with `/afk:to-sdd` to synthesize artifacts.
- Do NOT descend into implementation (file paths, code snippets, library version pins, helper-function names).
- Do NOT grill below L8.

## Next

Once L1 → L8 are exhausted (every entity has an owner aggregate, every
cross-aggregate op has a txn strategy, every NFR has a number, every
existing-infra claim verified against the codebase, and every external
seam cleared per the External-seam rule), run
**`/afk:to-sdd`** to synthesize the SDD + per-decision ADRs as artifacts.
`/afk:to-sdd` does NOT interview — it synthesizes what was decided here. If
it finds a gap, it bounces you back to this skill.

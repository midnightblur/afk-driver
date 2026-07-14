# api-contract — surface design of new/changed contracts

Design-level. Default `class: design`; a one-step breaking change to a published contract with live consumers → `class: correctness`, severity `high`. Repo-pattern overrides → `pattern-debt` per PRECEDENCE.md. Scope: quality of the *new or changed* public surface — endpoints, published DTOs, events, client-module symbols.
**Not yours:** propagation to existing callers of changed symbols → `scope-and-impact`; runtime failure handling → `resilience`; entity/aggregate placement → `domain-alignment`.

## Reviewer checklist

Surface size:
- **Needless surface** (Bloch-API: when in doubt, leave it out) — new public endpoint/DTO field/method with no consumer named by the contract or reachable in the repo → delete or make internal; adding later is cheap, removing is a breaking change.
- **Leaky contract** (Bloch-API) — persistence entity serialized outward, internal exception type or implementation vocabulary crossing the boundary → dedicated DTO, translated errors.

Misuse resistance:
- **Easy to misuse** (Bloch-API) — invalid input combinations are representable: two booleans where one enum was meant, consecutive same-type params, required-together fields passable apart → shape the type so the wrong call can't compile/deserialize.
- **Null in the contract** (EJ-54) — new API returns null for an empty collection or missing value where empty/Optional/404 is the honest shape → return the explicit shape.

Compatibility:
- **Breaking change without expand-contract** (Newman) — published DTO field removed/renamed/retyped, endpoint path/verb/status changed in one step → expand (add alongside), migrate consumers, contract later.
- **Tolerant-reader breach** (Newman) — consumer code newly failing on unknown fields of a peer's payload → ignore unknowns.

Coherence:
- **Vocabulary drift** (Bloch-API: an API is a little language) — new endpoint's nouns/verbs/param names inconsistent with the service's existing surface (same concept renamed, different casing/pluralization pattern) → match the local dialect.
- **Wrong protocol semantics** — non-idempotent GET, mutation reporting success on failure, collection endpoint missing the pagination params its siblings carry → align with the surface's conventions.
- **Error contract absent** — new endpoint declares only the happy path: validation, authz, conflict shapes undefined → declare them in the service's error envelope.
- **Undocumented surface** (Bloch-API) — new public contract without the param/return/error documentation the repo's convention expects at the boundary → document it.

## Guardrails (design-time digest)

- Smallest surface that satisfies the named consumer; no consumer, no endpoint.
- Change published contracts expand → migrate → contract, never in one step.
- Entities never serialize out; DTOs speak the surface's existing vocabulary.
- Every endpoint declares its error shape; collections paginate.
- Make invalid inputs unrepresentable.

# domain-alignment — language, aggregates, transactions, ownership

Design-level. Default `class: design` (glossary/documented-pattern breaches → `compliance`; a demonstrable data-integrity bug → `correctness`; repo-pattern overrides → `pattern-debt` per PRECEDENCE.md). Reads the diff against the nearest `GLOSSARY.md`, the SDD/ADRs when present, and the entity/service split.
**Not yours:** primitive-obsession mechanics → `code-quality`; dual-write/outbox, idempotency → `resilience`; published-DTO compat → `api-contract`; `rollbackFor` override landmine → `claude-md-compliance`.

## Reviewer checklist

Language:
- **Language drift** (DDD) — new symbol names diverge from the nearest `GLOSSARY.md`/spec term; two names for one concept, or one name for two → rename to the glossary term; a genuinely new concept is an advisory to add the term, not invent a synonym.
- **Translation inside one context** (DDD) — mapper between two representations of the same concept within one service, with no boundary justifying it → collapse to one representation.
- **Query that mutates** (DDD) — method named as a query (`get`/`find`/`is`) with side effects → rename honestly or split command from query.

Aggregates & invariants:
- **Invariant far from its data** (DDD) — service reads entity fields, validates, writes back what the entity could enforce itself → move the rule onto the owning aggregate. Judgment: a repo whose documented idiom keeps entities thin may host the rule in one canonical service — the finding is *scattered or duplicated* invariant enforcement, not "entities must have behaviour".
- **Aggregate bypass** (DDD) — entity mutated from outside its root; new repository for a non-root entity → route mutations through the root.
- **Business rule in the controller/UI** (DDD) — domain branching/validation in a controller or frontend component when a domain home exists → push down.

Transactions:
- **Transaction spanning aggregates or remote calls** (PoEAA) — one `@Transactional` writing multiple aggregates, or holding a DB tx across an HTTP/JMS/RFC call → split; remote work outside the tx, or accept eventual consistency explicitly.
- **Transaction boundary misplaced** (PoEAA) — `@Transactional` on a controller; a multi-write sequence with none; a pure read missing the repo's read-only convention → boundary belongs on the use-case-shaped service method.
- **No concurrent-edit story** (PoEAA) — new mutable operation on shared data with no visible version/lock/last-write-wins decision → name the story, matching the repo's documented locking pattern.

Ownership:
- **Wrong-service logic** (Newman) — new logic operating on data another service/module owns; a consumer-specific read implemented inside the data's owner → the consumer owns its read; reach data via the owner's published contract only.

## Guardrails (design-time digest)

- Name with glossary terms; new concept → propose the term before coding it.
- Invariants live on the aggregate that owns the data; services orchestrate, they don't babysit fields.
- One aggregate per transaction; never hold a DB tx across a remote call.
- Mutations enter through the aggregate root.
- Queries don't mutate; commands don't answer questions.
- Logic lives with the data it changes; consumers own their reads.
- Every new mutable endpoint declares its concurrent-edit story.

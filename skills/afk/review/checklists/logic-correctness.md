# logic-correctness — the bug hunt

Default `class: correctness`.
**Not yours:** unbounded queries, N+1 remote calls, missing timeouts → `resilience`.

Boundary values, empty/null/missing inputs, error and rollback paths, off-by-one, concurrency/ordering, integer/decimal precision (BigDecimal for money), partial-failure handling. Cite `file:line`; give a concrete failing input.

Lifecycle & persistence:
- A query on a lifecycle entity (state-machined, revisioned) constrains to the intended state — a lookup assuming one row breaks when a draft revision coexists with the active one.
- Deleting a parent deletes its dependent link/relation rows in the same transaction — an orphaned link row is a correctness bug, not cleanup debt.
- SQL never assembled via string replace/format — schema refs through the platform's schema resolver, values through parameters.
- Renaming/removing a persisted identifier (enum constant, state id) without a data migration strands existing rows — deserialization throws on read and fails the whole query.

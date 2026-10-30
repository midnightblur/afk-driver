# ADR-0001 — Join table for export runs

> Status: Accepted
> Date: 2026-01-06
> Audited: 2026-01-06
> Layer: L3
> Context ticket: PROJ-1
> Forks: f-relations

## Context

Each run must keep its orders (SDD §4).

## Decision

A join table links a run to its orders.

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| Run id on the order | one column | keeps the last run only | past runs must stay readable |

## Consequences

- **Positive** — every past run stays readable.
- **Negative** — one more table.

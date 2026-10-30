# Design ADR format

A design ADR records how the feature is built. The records live in `adr/design/` beside the SDD. Numbers are local to that folder and start at `0001`. Take the highest number and add one. Never edit a record in `adr/requirements/`: a requirement that blocks the design is a gap for `/afkv2:grill`.

## When to write one

Write a record when a decision meets all 3 tests. A decision can stand in the SDD with no record.

1. Not obvious for this stack.
2. A real trade-off: at least 2 real alternatives. A settled fork card passes this test.
3. Expensive to reverse.

To reverse an earlier design ADR, write a new one with `Superseded by` on the old status line, and add a row to SDD §12.

## Template

```markdown
# ADR-NNNN — <decision title>

> Status: Decided by agent | Accepted | Superseded by ADR-MMMM
> Date: <YYYY-MM-DD>
> Audited: not yet | <YYYY-MM-DD>
> Layer: L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9
> Context ticket: <ticket key>
> Forks: <fork card ids this record settles, or none>

## Context

The forces at play. Cite the SDD section.

## Decision

The chosen approach, in one paragraph, with one diagram of its shape.

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|

## Consequences

- **Positive** — what this enables.
- **Negative** — what this costs.
- **Follow-ups** — work this creates outside the scope.
```

## The status line

- The human accepted the card: `Status: Accepted`, and `Audited:` the accept date. The card was the audit.
- You decided and no card asked it: `Status: Decided by agent`, `Audited: not yet`, until a human reads the record and stamps the date.
- The human decided it, as on a fork: `Status: Accepted`, and no `Audited:` line. The line's presence says the agent decided.

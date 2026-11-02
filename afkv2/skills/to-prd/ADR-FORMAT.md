# Requirement ADR format

A requirement ADR records how the feature must behave and what is in or out of scope: what and why. A design ADR records how it is built, and is not written here. The records live in `adr/requirements/` beside the PRD. Numbers are local to that folder and start at `0001`. Take the highest number and add one.

## When to write one

Write a record when a decision meets all 3 tests. Most small PRDs have none.

1. Hard to reverse.
2. Surprising without context: a future reader would ask why.
3. A real trade-off: there were real alternatives, and one was chosen for a reason.

An `in` or `out` call on a staple usually meets the tests.

## Template

```markdown
# <short title of the decision>

> Status: Decided by agent | Accepted | Superseded by ADR-NNNN
> Audited: not yet | <YYYY-MM-DD>
> Layer: Requirements
> Context ticket: <ticket key>

<1 to 3 sentences: the context, what was decided, why.>

## Considered Options

- <option>. Rejected by <who> in <grill card id>, because <reason>.
```

`Considered Options` is optional. A record the human decided leaves out `Status` and `Audited`. A record from a `decided-by agent` row of the grill log has both lines: `Decided by agent` and `Audited: not yet`, until a human reads it and stamps the date.

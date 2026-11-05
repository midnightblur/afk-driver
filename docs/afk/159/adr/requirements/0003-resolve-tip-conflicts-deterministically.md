# Resolve tip conflicts deterministically

> Status: Decided by agent
> Audited: 2026-11-04
> Layer: Requirements
> Context ticket: #159

A page-owned tip beats a shared glossary tip. An exact page ID beats a page feature term. Validation rejects entries in one catalog that can match the same visible token.

## Considered Options

- Let dictionary order choose. Rejected by the agent in `r3-collision-rule`, because order does not state the intended meaning.
- Let a term override an exact ID. Rejected by the agent in `r3-collision-rule`, because an exact ID names one item more specifically.
- Reject every cross-catalog collision. Rejected by the agent in `r3-collision-rule`, because deterministic precedence preserves valid page data.

# SDD — order export

> Parent PRD: `PRD.md`
> Status: Draft
> Last updated: 2026-01-06

## §0 Binding Contract

This SDD and its accepted ADRs are binding on implementing agents and reviewers.

| Aspect | Section | Status | Signed by / date | Approved wording |
|--------|---------|--------|------------------|------------------|
| HL-1 Persistence and entity design | §4 | signed | owner / 2026-01-06 | "sign" (R-4) |
| HL-2 API surface | §3 | n/a | owner / 2026-01-06 | no surface is added |
| HL-3 Authorization and data scoping | §5 | n/a | owner / 2026-01-06 | no protected surface changes |
| HL-4 Life cycle and invariants | §6 | n/a | owner / 2026-01-06 | no state is added |
| HL-5 Irreversible and outward side effects | §7 | n/a | owner / 2026-01-06 | no outward write |
| HL-6 Change to existing behaviour | §14 | n/a | owner / 2026-01-06 | no existing flow changes |

## §1 Context Summary

The clerk stops copying orders by hand.

## §2 L1 — System Topology

Inherited.

## §3 L2 — Service Boundaries & Integration

Inherited.

## §4 L3 — Data Architecture

One table.

## §5 L4 — Cross-Cutting & Quality Attributes

Inherited.

## §6 L5 — Domain Model

Inherited.

## §7 L6 — Process & Coordination

Inherited.

## §8 L7 — Module Decomposition

One module.

## §9 L8 — Tactical Patterns

None.

## §9b External Seams & Failure Affordance

No external seam.

## §10 NFRs

| Concern | Target | Measurement | Owner |
|---------|--------|-------------|-------|
| export of 1,000 orders (s) | < 5 | test | clerk team |

## §11 Out of Scope

Scheduled exports.

## §12 Reversed Decisions

| Prior ADR | Superseded by | Reason |
|-----------|---------------|--------|

## §13 Open Questions

| Question | Layer (L1-L9) | Blocks executor? | Owner | Target resolve date |
|----------|---------------|------------------|-------|---------------------|
| Which font does the report use? | L8 | yes | clerk team | 2026-02-01 |

## §14 L9 — Implementation Seams & Change Impact

| Seam | Existing contract | Planned change | Impacted flows | Conventions | Verdict |
|------|-------------------|----------------|----------------|-------------|---------|
| none | — | — | — | — | fits |

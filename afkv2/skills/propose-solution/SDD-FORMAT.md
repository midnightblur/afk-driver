# SDD.md format

The design document, beside the PRD. It holds only what the session settled. Every card and note is in the page document: the SDD states the result, with its reason.

- Keep each `## §` heading exactly: `design_files.py gate` compares them with the template below, and later skills cite them.
- A layer with nothing to say holds one line, "Inherited" or "None". Keep the heading.
- Every non-trivial layer has the visual that carries its signal. Use Mermaid blocks and tables. Label each node and edge. Split a diagram with more than 12 nodes. Caption each diagram with its takeaway.
- Use numbers, not adjectives. Put the unit in the table header.
- No code and no file paths, because they go stale. A citation of a checked fact in §3 or §14 is the exception.
- The gate refuses a blocker token outside a code block: `TBD`, `TODO`, `FIXME`, `XXX`, `???`, `(decide later)`, `(unresolved)`, `(open)`, or a placeholder of the template below. Do not move a blocker to §13 to pass: a row with `Blocks executor? = yes` in L2 to L7 or L9 also fails.
- Transcribe the §0 register from the sign-off cards and the human's words. A row is `signed` or `n/a`; never infer a signature.

## Template

```markdown sdd-template
# SDD — {Feature Name}

> Parent PRD: `PRD.md`
> Status: Draft
> Last updated: {YYYY-MM-DD}

## §0 Binding Contract

This SDD and its accepted ADRs are binding on implementing agents and reviewers.

| Aspect | Locked by SDD/ADR | Executor latitude |
|--------|-------------------|-------------------|
| Pattern choice | yes | no |
| Module public interface | yes | no |
| API contract and schema | yes | no |
| Persisted schema (§4) | yes | no |
| Life cycle states and legal moves (§6) | yes | no |
| Roles per surface (§5) | yes | no |
| Transaction and idempotency strategy | yes | no |
| External-seam contract (§9b) | yes | no |
| File layout inside a named module | no | yes |
| Private helpers, internal names, control flow | no | yes |
| Test fixture structure | no | yes |

**Conflict procedure.** An executor finds a binding decision wrong, infeasible or against reality. A two-way-door correction is recorded in `plan/DECISIONS.md` and built. A one-way door or a tie parks the subtask and returns to `/afkv2:propose-solution` for a new ADR that supersedes the old one. Never override off the record.

**Human sign-off register.** One row per human-locked aspect (`DRAFT.md`).

| Aspect | Section | Status | Signed by / date | Approved wording |
|--------|---------|--------|------------------|------------------|
| HL-1 Persistence and entity design | §4 | signed or n/a | {who} / {YYYY-MM-DD} | the human's words, with the round; for n/a the reason |
| HL-2 API surface | §3 | signed or n/a | {who} / {YYYY-MM-DD} | as above |
| HL-3 Authorization and data scoping | §5 | signed or n/a | {who} / {YYYY-MM-DD} | as above |
| HL-4 Life cycle and invariants | §6 | signed or n/a | {who} / {YYYY-MM-DD} | as above |
| HL-5 Irreversible and outward side effects | §7 | signed or n/a | {who} / {YYYY-MM-DD} | as above |
| HL-6 Change to existing behaviour | §14 | signed or n/a | {who} / {YYYY-MM-DD} | as above |

## §1 Context Summary

One paragraph: why this design exists. The PRD holds what it does.

## §2 L1 — System Topology

Where the feature lives in the wider system. Usually one line: "Inherited from {system}." A feature across more than 1 deployable unit shows a `flowchart`.

## §3 L2 — Service Boundaries & Integration

A `flowchart LR` of services, with each edge labelled by its integration style. A `sequenceDiagram` per non-trivial interaction. One contract row per surface the feature adds or changes, at HL-2 grade, concrete enough to assert against.

## §4 L3 — Data Architecture

One state row per piece of state:

| State | Datastore | Partitioning | Replication | Retention | Schema-evolution policy | PII? | Audited? |
|-------|-----------|--------------|-------------|-----------|-------------------------|------|----------|

Per entity the feature persists or alters, at HL-1 grade:

| Field | Type | Null? | Default | Unit / precision | Constraint | Indexed / unique | Note |
|-------|------|-------|---------|------------------|------------|------------------|------|

| Relation | Target | Cardinality | Owning side | On delete / orphan | Fetch posture |
|----------|--------|-------------|-------------|--------------------|---------------|

**Surface reachability.** For each field added to an existing entity, or made mandatory on one: does each surface that exposes the entity change?

**Migration and backfill.** For each altered entity: what happens to existing rows, and can the change go back?

An `erDiagram` of the links between pieces of state.

## §5 L4 — Cross-Cutting & Quality Attributes

Per concern present, one table: authorization (surface, permitted roles, denied roles, guard above and below the UI), data scoping, idempotency (surface, key shape, window, ledger), retry and timeout (call, attempts, backoff in s, timeout in s), rate limit, feature flags, observability. Secrets in one line.

## §6 L5 — Domain Model

An invariants table (invariant, owner, guardian, answer to a violation). A `stateDiagram-v2` per life cycle, at HL-4 grade. Domain events, or "None".

## §7 L6 — Process & Coordination

A `sequenceDiagram` per top use case, with its transaction boundary. One failure matrix:

| Failure point | Detection signal | Automatic recovery | Manual recovery | Owner |
|---------------|------------------|--------------------|-----------------|-------|

Each irreversible or outward effect at HL-5 grade.

## §8 L7 — Module Decomposition

A `flowchart TB` of module dependencies, with no cycle. One table: module, purpose, public interface, depends on.

## §9 L8 — Tactical Patterns

| Concern | Pattern | ADR |
|---------|---------|-----|

## §9b External Seams & Failure Affordance

Each framework boundary, field source of truth, enforcement point and failure surface. Each framework row names a test on the real output. No external seam: say so in one line.

| Boundary | Framework at its pin | What it does to our value | Failure surface | Seam test |
|----------|----------------------|---------------------------|-----------------|-----------|

## §10 NFRs

| Concern | Target | Measurement | Owner |
|---------|--------|-------------|-------|

## §11 Out of Scope

The PRD's list, plus the exclusions of the design.

## §12 Reversed Decisions

| Prior ADR | Superseded by | Reason |
|-----------|---------------|--------|

## §13 Open Questions

| Question | Layer (L1-L9) | Blocks executor? | Owner | Target resolve date |
|----------|---------------|------------------|-------|---------------------|

## §14 L9 — Implementation Seams & Change Impact

One row per seam into existing code. Cite the check of each fact. The verdict is `fits`, `extends (ADR-NNNN)` or `reworked`. Below the table, list each compatibility finding the human accepted.

| Seam | Existing contract | Planned change | Impacted flows | Conventions and landmines | Verdict |
|------|-------------------|----------------|----------------|---------------------------|---------|
```

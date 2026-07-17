
> **Concision doctrine — apply to every section.** Precise capture is non-negotiable; word count is.
> Both come from **one fact, one home**: each fact (rule semantics, state meaning, endpoint contract,
> decision rationale) is stated in exactly ONE place; elsewhere reference it by stable ID.
> - **Enumerable domain data** (parallel things: rules, states, roles, value types, endpoints) → a
>   **catalog table**, one column per attribute. That table is its home — never re-narrate rows as prose.
> - **Tables beat prose** for parallel structure. Reach for one at the third bullet of the same shape.
> - **Reference by ID.** N items sharing a shape → ONE parameterized statement + catalog ref, not N clones.
> - **An ADR is the home for its own rationale.** Where one exists, the PRD gives a one-line decision + link.
> - **No padding.** State each thing once, plainly. No role-play quotes, no re-inverting Problem into
>   Solution, no meta-commentary about the sections. Drop any clause carrying no actionable fact.
> - **Less is more — sacrifice grammar for concision.** Tighter is better: drop articles, filler, and
>   connective prose; write phrases and fragments, not full sentences, wherever meaning survives.
>   Precision and completeness are non-negotiable — a shorter PRD that loses a fact, boundary, or row
>   has failed. Compress the wording, never the content.
>
> Load-bearing on complex features: a rule/state/endpoint-heavy PRD triples when a set is stated as
> stories AND acceptance criteria AND a catalog. State it once (the catalog); reference it elsewhere.
> Precision is preserved because the catalog columns carry the exact per-item data.

## Problem Statement

The problem the user faces, from their perspective — plainly, a few sentences. Concrete pains as a short list if several. No role-play quotes.

## Solution

What is delivered, from the user's perspective. Describe the capability — not "the pain, but solved."

## Catalog (when applicable)

If the feature has a **set of parallel things** (validation rules, lifecycle states, role tiers, value types, endpoints), define them **once** here (or inline in the most natural section) as a table with a stable ID column + one column per attribute. This is the **home** for that data: User Stories, Acceptance Criteria, and Implementation Decisions **reference rows by ID** rather than re-enumerating.

| ID | Name | <attribute> | <attribute> | <attribute> |
|----|------|-------------|-------------|-------------|
| <STABLE-ID> | <short name> | … | … | … |

Omit entirely when nothing is enumerable. When kept, it is what makes the rest short — invest the precision here.

## User Stories

The **handful of most common, highest-value use cases** — value-ordered, most important first. **NOT** a feature list, **NOT** exhaustive: the representative journeys a reader skims to grasp *what the feature is for*. A large feature still has few. Format:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see the balance on my accounts, so that I can make better-informed spending decisions.
</user-story-example>

- **Representative, not exhaustive.** The few a stakeholder names for "what does this let me do?" — small even for a large feature. Never one per capability or catalog row.
- **Details live elsewhere.** Edge/minor/secondary cases and the full item set belong to **Catalog**, **Acceptance Criteria**, **Implementation Decisions** — where completeness is guaranteed. Omitting them here drops nothing.
- **Value-order.** A reader stopping after the first few still has the essence.
- **Drop `so that <benefit>`** when self-evident; keep only for non-obvious rationale.

## Acceptance Criteria

**The section QA reads to independently generate test cases** — so its one job: define, precisely and completely, **what success and failure look like**. NOT test cases, NOT Gherkin: don't pick concrete inputs/data/click-paths, don't write `Given/When/Then` — deriving cases is QA's work (and `VERIFICATION-PLAN.md`'s). Define the contract; let QA derive the cases.

A checklist of **binary, verifiable conditions** — each a single pass/fail statement in business language, black-box (*condition → observable outcome*), independent of *how* tested:

- [ ] <a condition unambiguously true or false on inspection>

Each criterion must:
- **Define both sides of the line.** Success AND failure outcomes; name the **boundary value and both outcomes** (e.g. "effective date today or later accepted; earlier rejected"). This defines the contract, not the case — QA still picks which values to probe.
- **Be outcome-precise.** The exact rejection — error/status/observable effect — not just "rejected." Localized message → reference the caption key, but assert *a specific* message.
- **Carry a stable ID** (`AC-NNN`), never renumbered, so a QA case traces back.
- **Be atomic** — one condition; split compounds.

**Coverage the set must hit:** happy path per capability; every threshold/transition **boundary, both sides**; every negative — permission denials (one per **denied-role** row in the Access & validation matrix), validation rejections, data-scope violations; any non-functional bar gating acceptance (e.g. an audit record captured).

**Concision — parameterize over the catalog, only while testable.** When many rows share a success/failure shape, write ONE criterion quantifying over the catalog ("for every rule in <X>, a document violating its configured value at its listed checkpoint is rejected with its rule-context error") + **name the exact table**. Sound only if that table carries the columns QA needs to expand each row (a representative violating input, expected outcome, checkpoint). If not, spell it out — else the row is untestable.

**Distinct from:**
- **Testing Decisions** — test *strategy* (what/how/prior-art); ACs are the *conditions*.
- **verification scenarios** (`VERIFICATION-PLAN.md`) — concrete click-paths + API checks; ACs are the outcomes those must satisfy. One criterion → several tests; one scenario → several criteria.

## Access & validation policy

The requirement-level access boundary, per capability/User Story so it is *stated* not assumed (the gap that ships a backend blocking a role while the UI lets it in). `/afk:grill-verification` reads this to design **role-based**, **data-scoped**, and **validation** aspects — every row must be concrete enough to become a denial/scoping scenario.

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope (entity → company/vendor, or "unscoped") | Key validation rules |
|-------------------------|-------------------|----------------|------------------------------------------------------|----------------------|
| <capability> | <roles allowed> | <≥1 role blocked> | <which entity, by company and/or vendor — not values> | <required/bounds/transition, or "none"> |

- **Every row names ≥1 denied role.** "Everyone may" is valid only when stated; a blank denied column is an unresolved requirement.
- **Data scope is by company and/or vendor, never tenant** (build-per-tenant, single-tenant in dev — see core-services `CLAUDE.md`). Record *which entity* is scoped, not concrete values (FOS-configured at runtime).
- Enforcement *mechanism* and **Envers audit** are solution-level — SDD, not here.

## Implementation Decisions

Product/architecture-level decisions — **terse**: modules to build/modify + responsibilities (a table works), schema changes, API contracts, technical clarifications, architectural choices.

- **Where a requirement ADR exists, one-line decision + link — do NOT restate its rationale.** The ADR is the home for the "why".
- **Reference the catalog, don't re-narrate** for catalogued items.
- No file paths or code snippets — they drift. Exception: a prototype snippet encoding a decision more precisely than prose (state machine, reducer, schema, type shape) — inline just the decision-rich bits, note it came from a prototype.

## Testing Decisions

Test strategy: what makes a good test here (test external behaviour, not implementation), which modules get tested, prior art in the codebase. Strategy only — concrete scenarios live in `VERIFICATION-PLAN.md`, conditions in Acceptance Criteria.

## Out of Scope

What is deliberately not covered — one line each, pointer to where it *is* handled if relevant.

## Further Notes

Anything else to pin: reconciled source discrepancies, known carried defects, environment limitations. Facts a downstream reader must know.

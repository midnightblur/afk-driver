
> **Concision doctrine — apply to every section below.** Precise capture is non-negotiable;
> word count is. The way to have both is **one fact, one home**: each fact (a rule's semantics,
> a state's meaning, an endpoint's contract, a decision's rationale) is stated in exactly ONE
> place; everywhere else references it by a stable ID. Concretely:
> - **Enumerable domain data** (a set of parallel things: rules, states, roles, value types,
>   endpoints) → a **catalog table**, stated once with a column per attribute. This is its home.
>   Never re-narrate the rows as prose elsewhere — point at the table.
> - **Tables beat prose** for anything with parallel structure. Reach for a table the moment you
>   catch yourself writing the third bullet of the same shape.
> - **Reference by ID, don't restate.** When N items share a shape, write ONE parameterized
>   statement + a catalog reference, not N near-clones.
> - **A requirement ADR is the home for its own rationale.** Where an ADR exists, the PRD gives a
>   one-line decision + link — it does NOT restate the reasoning the ADR already holds.
> - **No prose padding.** State a thing once, plainly. No perspective role-play quotes, no
>   re-inverting the Problem into the Solution, no meta-commentary about the sections themselves.
>   Drop a clause the moment it carries no fact the reader can act on.
>
> These rules are load-bearing on complex features — a rule/state/endpoint-heavy PRD triples in
> length when the same set is stated as stories AND acceptance criteria AND a catalog. State it
> once (the catalog); let the other sections reference it. Preserving precision means the catalog
> columns carry the exact per-item data — nothing is dropped, it is stated once.

## Problem Statement

The problem the user faces, from the user's perspective — stated plainly in a few sentences.
The concrete pains, as a short list if there are several. No role-play quotes.

## Solution

What is delivered, from the user's perspective. Do not re-state the Problem inverted — describe
the capability, not "the pain, but solved."

## Catalog (when applicable)

If the feature has a **set of parallel things** — validation rules, lifecycle states, role
tiers, value types, endpoints — define them **once** here (or inline in the most natural section)
as a table with a stable ID column and one column per attribute. This table is the **home** for
that data: User Stories, Acceptance Criteria, and Implementation Decisions all **reference its
rows by ID** rather than re-enumerating them.

| ID | Name | <attribute> | <attribute> | <attribute> |
|----|------|-------------|-------------|-------------|
| <STABLE-ID> | <short name> | … | … | … |

Omit this section entirely when the feature has nothing enumerable. When kept, it is what makes
the rest of the PRD short — invest the precision here.

## User Stories

The **handful of most common, highest-value use cases** that represent what the feature delivers —
value-ordered, most important first. User stories are **NOT** a feature list and **NOT** an
exhaustive enumeration of capabilities: they are the representative journeys a reader skims to
grasp *what the feature is for*. A large feature still has few stories. Format:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see the balance on my accounts, so that I can make better-informed spending decisions.
</user-story-example>

Rules:
- **Representative, not exhaustive.** Write the few stories a stakeholder would name if asked
  "what does this feature let me do?" — a small set even for a large feature. Resist one story per
  capability, and never one per catalog row.
- **The details live elsewhere, not here.** Edge cases, minor/secondary cases, intricacies, and
  the full item set belong to the **Catalog**, **Acceptance Criteria**, and **Implementation
  Decisions** — that is where completeness is guaranteed and nothing is lost. Omitting them from
  the stories drops nothing; those sections carry them.
- **Value-order them.** A reader who stops after the first few still has the essence of the feature.
- **Drop `so that <benefit>` when the benefit is self-evident.** Keep it only where it carries
  non-obvious rationale.

## Acceptance Criteria

**This is the section QA reads to independently generate their test cases** — so its one job is to
define, precisely and completely, **what success and what failure look like**. It is NOT a set of
test cases and NOT Gherkin scenarios: do not pick concrete inputs, data, or click-paths, and do not
write `Given/When/Then` scripts — deriving cases is QA's work (and the `VERIFICATION-PLAN.md`
suite's). If you write the scenarios, you have become the QA. Define the success/failure
*contract*; let QA derive the cases that probe it.

A checklist of **binary, verifiable conditions** — each a single observable pass/fail statement in
business language, black-box (stated as *condition → observable outcome*), independent of *how* it
is tested:

- [ ] <a condition that is unambiguously true or false on inspection>

Each criterion must:
- **Define both sides of the line.** State the outcome for success AND for failure — QA must know
  exactly where "accepted" turns into "rejected." Name the **boundary value and both outcomes**
  (e.g. "effective date today or later is accepted; earlier than today is rejected"). Naming the
  boundary defines the contract; it does not write the case — QA still chooses which values to probe.
- **Be outcome-precise.** The exact rejection — error / status / observable effect — not just
  "rejected." If the message is localized, reference the caption key rather than inlining languages,
  but assert *a specific* message is expected.
- **Carry a stable ID** (`AC-NNN`), never renumbered across revisions, so a QA case traces back and
  coverage stays trackable.
- **Be atomic** — one condition; split compounds.

**Coverage the set must hit** so QA can build a complete suite from it: the happy path per
capability; every threshold/transition **boundary, both sides**; every negative — permission denials
(one criterion per **denied-role** row in the Access & validation matrix), validation rejections,
data-scope violations; and any non-functional bar that gates acceptance (e.g. an audit record
captured).

**Concision — parameterize over the catalog, but only while it stays testable.** When many catalog
rows share a success/failure shape, write ONE parameterized criterion quantifying over the catalog
("for every rule in the <X> catalog, a document violating its configured value at its listed
checkpoint is rejected with its rule-context error"), not one per row — and **name the exact catalog
table it quantifies over**. This is sound only if that table carries the columns QA needs to expand
each row: a representative violating input, the expected outcome, and the checkpoint(s). If the
catalog lacks that per-row data, do not parameterize — spell the criterion out, or the row is
untestable. (QA reads the whole PRD, so the referenced catalog travels with the ACs.)

**Distinct from two neighbours:**
- vs. **Testing Decisions** — that is the test *strategy* (what to test, how, prior art);
  Acceptance Criteria are the *conditions*, not the approach.
- vs. **verification scenarios** (`VERIFICATION-PLAN.md`) — those are concrete click-paths and API
  request/response checks; Acceptance Criteria are the outcomes those (and QA's tests) must satisfy.
  One criterion may be proven by several tests; one scenario may cover several criteria.

## Access & validation policy

The requirement-level access boundary, captured per capability/User Story so it is *stated* rather
than assumed (the gap that ships a feature with the backend blocking a role while the UI lets it
in). This matrix is the source `/afk:grill-verification` reads to design the **role-based**,
**data-scoped**, and **validation** verification aspects — every row must be concrete enough to
turn into a denial/scoping scenario.

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope (entity → company/vendor, or "unscoped") | Key validation rules |
|-------------------------|-------------------|----------------|------------------------------------------------------|----------------------|
| <capability> | <roles allowed> | <≥1 role that must be blocked> | <which entity is scoped, by company and/or vendor — not values> | <required/bounds/transition rules, or "none"> |

Rules for the matrix:
- **Every row names at least one denied role.** "Everyone may" is valid only when stated
  explicitly; a blank denied column is an unresolved requirement, not an open door.
- **Data scope is by company and/or vendor, never tenant** (build-per-tenant — single-tenant in
  dev; see core-services `CLAUDE.md`). Record *which entity* is scoped, not concrete
  company/vendor values (FOS-configured at runtime).
- The *mechanism* of enforcement and **Envers audit** are solution-level — they live in the SDD,
  not here.

## Implementation Decisions

The decisions made, at the product/architecture level — **terse**. This can include: modules to
build/modify and their responsibilities (a table works well), schema changes, API contracts,
technical clarifications, architectural choices.

Rules:
- **Where a requirement ADR exists, give a one-line decision + link — do NOT restate the ADR's
  rationale.** The ADR is the home for the "why"; duplicating it here is exactly the redundancy
  this template exists to kill.
- **Reference the catalog, don't re-narrate it.** If a decision concerns the catalogued items,
  point at the table.
- Do NOT include specific file paths or code snippets — they drift.
- Exception: if a prototype produced a snippet that encodes a decision more precisely than prose
  (state machine, reducer, schema, type shape), inline just the decision-rich bits and note it
  came from a prototype.

## Testing Decisions

The testing strategy: what makes a good test here (test external behaviour, not implementation
details), which modules will be tested, and prior art in the codebase for those tests. Keep it to
the strategy — the concrete scenarios live in `VERIFICATION-PLAN.md`, the conditions in
Acceptance Criteria.

## Out of Scope

What is deliberately not covered — one line each, with a pointer to where it *is* handled if
relevant.

## Further Notes

Anything else worth pinning: reconciled source discrepancies, known carried defects, environment
limitations. Keep to facts a downstream reader must know.

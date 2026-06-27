
## Problem Statement

The problem that the user is facing, from the user's perspective.

## Solution

The solution to the problem, from the user's perspective.

## User Stories

A LONG, numbered list of user stories. Each user story should be in the format of:

1. As an <actor>, I want a <feature>, so that <benefit>

<user-story-example>
1. As a mobile bank customer, I want to see balance on my accounts, so that I can make better informed decisions about my spending
</user-story-example>

This list of user stories should be extremely extensive and cover all aspects of the feature.

## Acceptance Criteria

A checklist of **binary, verifiable conditions** that must all hold for the
feature to be accepted — the definition of done from the product's point of view.
Each is a single observable pass/fail statement in business language, independent
of *how* it's tested:

- [ ] <a condition that is unambiguously true or false on inspection>

Write enough to pin down the feature's accepted behaviour (happy path, the
important edge/error conditions, and any non-functional bar that gates
acceptance — e.g. a permission rule, a data-integrity guarantee). Keep each
criterion atomic; split compound ones.

This is **distinct** from two neighbours, and the distinction is load-bearing:
- vs. **Testing Decisions** (below) — that's the test *strategy* (what to test,
  how, prior art); Acceptance Criteria are the *conditions*, not the approach.
- vs. **verification scenarios** (`/afk:grill-verification` →
  `/afk:to-verification-plan` → `VERIFICATION-PLAN.md`) — those are concrete UI click-paths and API
  request/response checks; Acceptance Criteria are the outcomes those scenarios
  (and unit/integration tests) must satisfy. A criterion may be proven by several
  tests; a scenario may cover several criteria.

## Access & validation policy

The requirement-level access boundary, captured per capability/User Story so it
is *stated* rather than assumed (the gap that ships a feature with the backend
blocking a role while the UI lets it in). This matrix is the source
`/afk:grill-verification` reads to design the **role-based**, **data-scoped**, and
**validation** verification aspects — so every row must be concrete enough to turn
into a denial/scoping scenario.

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope (entity → company/vendor, or "unscoped") | Key validation rules |
|-------------------------|-------------------|----------------|------------------------------------------------------|----------------------|
| <capability> | <roles allowed> | <≥1 role that must be blocked> | <which entity is scoped, by company and/or vendor — not values> | <required/bounds/transition rules, or "none"> |

Rules for the matrix:
- **Every row names at least one denied role.** "Everyone may" is a valid answer
  only when stated explicitly; a blank denied column is an unresolved requirement,
  not an open door.
- **Data scope is by company and/or vendor, never tenant** (tenancy is
  build-per-tenant — single-tenant in dev; see core-services `CLAUDE.md`). Record
  *which entity* is scoped, not concrete company/vendor values (FOS-configured at
  runtime).
- The *mechanism* of enforcement and **Envers audit** are solution-level — they
  live in the SDD (`/afk:to-sdd` §5 L4 / §9b / §4 L3), not here.

## Implementation Decisions

A list of implementation decisions that were made. This can include:

- The modules that will be built/modified
- The interfaces of those modules that will be modified
- Technical clarifications from the developer
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Do NOT include specific file paths or code snippets. They may end up being outdated very quickly.

Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it within the relevant decision and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Testing Decisions

A list of testing decisions that were made. Include:

- A description of what makes a good test (only test external behavior, not implementation details)
- Which modules will be tested
- Prior art for the tests (i.e. similar types of tests in the codebase)

## Out of Scope

A description of the things that are out of scope for this PRD.

## Further Notes

Any further notes about the feature.

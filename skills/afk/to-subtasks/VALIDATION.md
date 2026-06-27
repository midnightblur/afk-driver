# Validation checklist

**(a) Contract graph.** Walk every `## Consumes` line: `{PRODUCER-ID}` must
resolve to a subtask **earlier in rank order** (forward refs = circular dep;
bounce), and `{file}#{anchor}` must appear verbatim in that producer's
`## Produces`. A consumer expecting a signature the producer doesn't declare is
a broken slice — refuse, name the pair. Orphan producers (no consumer, not a
leaf) are warn-level — surface them.

**(b) Anchor quality.** For every `## Produces` `{grep-anchor}`: not a forbidden
generic token (`class`, `interface`, `void`, `function`, `def`, `method`,
`struct`, `enum`, `type`, `record`); length ≥12 chars; trial `ctx_search`
against `{file}` at HEAD returns ≤1 match (≥2 = ambiguous → would fail-open at
runtime → refuse). New files: trial grep N/A, the first two checks still apply.

**(c) Acceptance citations.** Every cited bullet ends with `(PRD §…)` / `(SDD
§…)` / `(SDD §9b row "…")` / `(ADR-NNNN)`, and the citation **resolves** (grep
the target file — a phantom citation is worse than none). At least one bullet
cites the SDD §8 module row this subtask owns.

**(d) Seam coverage.** Every SDD §9b seam appears in the seam register with a
named implementer; the implementing subtask lists it `implement:` in `## Seams`
and carries its seam-test as a Verification row. A seam sliced without its
framework-output test fails the slice — that's the gap green unit tests hide.
Every `use:` seam points at a real register row.

**(e) Verification tiers.** Every subtask's `## Verification` has at least the
`static` row; tiers are appropriate to the change (UI subtask → e2e present;
protected-endpoint subtask → api present; JPA entity → integration/pickup
present). Every command is runnable from repo root.

**(f) Scope sanity.** Globs are concrete (no bare `**`), and the union of all
subtask Scopes covers the PRD's stated work with no silent gap.

**(g) Smoke gate (iff a `VERIFICATION-PLAN.md` is present).** Every plan scenario
— across `## UI Journeys` and `## API Scenarios` — is seeded as a `## Feature
smoke gate` row carrying its `Modality`, each tracing to its real source (UI →
grep the PRD User Story; API → the SDD §3 row / PRD Acceptance Criterion) and
naming its spec; no gate row invents a scenario absent from the plan. The build
subtasks exist **per modality present**:
  - `NNNN-smoke-e2e` (always, when UI journeys exist) — `## Blocked by` **every**
    other subtask, pointing the build agent at
    `11700-payable/verification/ui-e2e/AUTHORING.md`; `## Verification` carries a
    `static` `cucumber-js --dry-run` row and an `e2e/browser` `npm run smoke` row.
  - `NNNN-smoke-api` (only when `## API Scenarios` is real, not the deferred
    placeholder) — `## Blocked by` **every** other subtask, pointing at
    `11700-payable/verification/api/AUTHORING.md`; `## Verification` carries a
    `static` `node --check` row and an `api` `node --test` row.
Any gate row marked `env-limited` carries that flag from the plan. Conversely, no
`VERIFICATION-PLAN.md` → neither the section nor any build subtask is present, and
a UI-only plan emits only `NNNN-smoke-e2e` (don't emit a half-gate or a phantom
API subtask).

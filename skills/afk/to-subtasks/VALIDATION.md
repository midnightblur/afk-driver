# Validation checklist

**(a) Contract graph.** Walk every `## Consumes` line: `{PRODUCER-ID}` must
resolve to a subtask **earlier in rank order** (forward refs = circular dep;
bounce), and `{file}#{anchor}` must appear verbatim in that producer's
`## Produces`. A consumer expecting a signature the producer doesn't declare is
a broken slice — refuse, name the pair. Orphan producers (no consumer, not a
leaf) are warn-level — surface them. The `[materialized]` marker must agree
across the pair: on a producer bullet iff on every consumer line citing it.

**(b) Anchor quality.** For every `## Produces` `{grep-anchor}`: not a forbidden
generic token (`class`, `interface`, `void`, `function`, `def`, `method`,
`struct`, `enum`, `type`, `record`); length ≥12 chars; trial `ctx_search`
against `{file}` at HEAD returns ≤1 match (≥2 = ambiguous → would fail-open at
runtime → refuse). New files: trial grep N/A, first two checks still apply —
except a `[materialized]` anchor, whose file exists at emit time: its trial grep
must return **exactly 1** and the stub's module must `test-compile` (a marked
bullet whose stub is absent or uncompilable is a broken slice).

**(c) Acceptance citations.** Every cited bullet ends with `(PRD §…)` / `(SDD
§…)` / `(SDD §9b row "…")` / `(ADR-NNNN)`, and the citation **resolves** (grep
the target file — a phantom citation is worse than none). At least one bullet
cites the SDD §8 module row this subtask owns.

**(d) Seam coverage.** Every SDD §9b seam appears in the seam register with a
named implementer; the implementing subtask lists it `implement:` in `## Seams`
and carries its seam-test as a Verification row. A seam sliced without its
framework-output test fails the slice — the gap green unit tests hide. Every
`use:` seam points at a real register row. A **materialized** seam's pre-created
`{Seam}ContractTest` must be the implementer's seam-test Verification row
(enabling + greening it is that subtask's job — don't emit a second, parallel
seam-test).

**(e) Verification tiers — mechanical mandates.** Every subtask's
`## Verification` has at least the `static` row, and every command is runnable
from repo root. Additionally, tier rows are **mandated by what the Scope globs
touch** — a missing mandated row means refuse the plan, naming the subtask and
the rule:

| Scope touches | Mandated tier row |
|---|---|
| any `*-ui/**` path (components, pages, stores, router) | `e2e/browser` |
| a controller / `@RestController` / any SDD §3 endpoint | `api` |
| `*-entities/**` (`@Entity`, repository, schema pickup) | `integration` (incl. the liquibase-pickup check) |
| messaging / JMS listener / async job wiring | `integration` |

Mandates are **hard downstream** — the no-waiver rule's owning statement is the
execute contract's "Driven mode" section; this check only guarantees the rows
exist to be enforced.

Additionally scan every subtask's `## Acceptance` for runtime-effect language
("within N seconds", live/watch/poll/reactive). Each hit must map to a
unit/integration row whose Check triggers that condition and asserts that
outcome (rule: SKILL.md "Choosing verification tiers"); a row that only
exercises surrounding shape/structure fails — refuse, naming the subtask and the
bullet.

**(f) Scope sanity.** Globs are concrete (no bare `**`), and the union of all
subtask Scopes covers the PRD's stated work with no silent gap.

**(g) Smoke gate (always — shape depends on `VERIFICATION-PLAN.md`).** When the
plan is present: every plan scenario — across `## UI Journeys` and `## API
Scenarios` — is seeded as a `## Feature smoke gate` row carrying its `Modality`,
each tracing to its real source (UI → grep the PRD User Story; API → the SDD §3
row / PRD Acceptance Criterion) and naming its spec; no gate row invents a
scenario absent from the plan. The build subtasks exist **per modality
present**:
  - `NNNN-smoke-e2e` (when UI journeys exist) — `## Blocked by` **every**
    other subtask, pointing the build agent at
    `11700-payable/verification/ui-e2e/AUTHORING.md`; `## Verification` carries a
    `static` `cucumber-js --dry-run` row and an `e2e/browser` `npm run smoke` row.
  - `NNNN-smoke-api` (only when `## API Scenarios` is real, not the deferred
    placeholder) — `## Blocked by` **every** other subtask, pointing at
    `11700-payable/verification/api/AUTHORING.md`; `## Verification` carries a
    `static` `node --check` row and an `api` `node --test` row.
Any gate row marked `env-limited` carries that flag from the plan. A UI-only plan
emits only `NNNN-smoke-e2e` (no half-gate, no phantom API subtask). No
`VERIFICATION-PLAN.md` → the `## Feature smoke gate (minimal)` section is present
instead (see SMOKE-GATE.md), with no build subtasks and no scenario table — a
plan with neither gate section is invalid.

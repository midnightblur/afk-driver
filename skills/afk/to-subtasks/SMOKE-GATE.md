# Feature smoke gate (driven by `VERIFICATION-PLAN.md`)

The per-subtask `api` / `e2e/browser` tiers prove **one slice** in isolation. A
feature whose verification scenarios were designed via `/afk:grill-verification`
(and written by `/afk:to-verification-plan`) also gets an **integrated smoke
gate**: those cross-subtask scenarios — both
modalities — run against a real running app as the final "feature complete"
check, and reused afterward by CI / scheduled jobs / manual sanity runs. The gate
that *runs* them is a separate skill (`/afk:smoke-test`); this skill **seeds** the
gate and **emits the build subtasks** that author the specs.

**The trigger is the artifact, not an ask.** If `VERIFICATION-PLAN.md` sits next
to the PRD, the human already decided (by running `/afk:grill-verification` →
`/afk:to-verification-plan`).
Emit the gate section **and one build subtask per modality the plan carries**:

- **The PLAN.md `## Feature smoke gate` section** (template below): seed one row
  per scenario across **both** the plan's `## UI Journeys` and `## API Scenarios`
  — its plain-language summary, the source it traces to (UI → PRD User Story;
  API → SDD §3 row / PRD Acceptance Criterion), the spec it maps to, its
  `Modality` (`ui-e2e` | `api`), and its `env-limited` flag carried over verbatim
  (so `/afk:smoke-test` excludes those from its green verdict). Don't invent
  scenarios here — `VERIFICATION-PLAN.md` is the source of truth.
- **The terminal `NNNN-smoke-e2e` build subtask** (UI journeys) and, when the
  plan has real `## API Scenarios`, **the terminal `NNNN-smoke-api` build
  subtask** (API contracts) — Process step 3, using the base subtask contract
  with the fields below. The how-to-build recipes (layers, conventions, reference
  data, verify-in-order, definition-of-done) are **not** restated here or anywhere
  in this repo — they live canonically at
  **`11700-payable/verification/ui-e2e/AUTHORING.md`** and
  **`11700-payable/verification/api/AUTHORING.md`**, versioned with the
  verification code so they can't drift. Each subtask's job is to point the build
  agent there and read it first. Both blocked by every other subtask.

```
## Goal
Author the integrated browser smoke specs for {Feature} into the existing
11700-payable/verification/ui-e2e module, one Scenario per VERIFICATION-PLAN.md UI
journey, so /afk:smoke-test can run them as the gate. FOLLOW THE CANONICAL RECIPE:
read 11700-payable/verification/ui-e2e/AUTHORING.md first — it is the authoritative
how-to (layer rules, conventions, reference data, verify steps, definition-of-done).
Also see its siblings README.md (run/env) + CLAUDE.md.

## Scope
- 11700-payable/verification/ui-e2e/features/*.feature   # new Scenarios / a new feature file
- 11700-payable/verification/ui-e2e/steps/*.mjs          # only if a new step sentence is needed
- 11700-payable/verification/ui-e2e/scenarios.mjs        # only if a genuinely new L2 action is needed

## Acceptance
- [ ] Authored per 11700-payable/verification/ui-e2e/AUTHORING.md (read first; followed, not improvised)
- [ ] One Scenario per VERIFICATION-PLAN.md UI journey, each tracing to its PRD User Story
- [ ] Env-limited journeys tagged + flagged env-limited in the gate table (not left to fail the gate)

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `cd 11700-payable/verification/ui-e2e && npx cucumber-js --dry-run` | every step resolves; 0 undefined / 0 ambiguous |
| e2e/browser | `cd 11700-payable/verification/ui-e2e && npm run smoke` | the runnable (non-env-limited) scenarios go green locally |

## Blocked by
<every other non-build subtask id>

## Implementation Notes (auto-maintained)
<!-- the authoritative recipe is 11700-payable/verification/ui-e2e/AUTHORING.md; do not duplicate it here -->
```

```
## Goal
Author the integrated API smoke specs for {Feature} into the existing
11700-payable/verification/api module, one node:test *.test.mjs scenario per
VERIFICATION-PLAN.md API scenario (using ../core for auth/base-URL/poll), so
/afk:smoke-test can run them as the gate. FOLLOW THE CANONICAL RECIPE: read
11700-payable/verification/api/AUTHORING.md first — it is the authoritative how-to
(request shape, asserting the real envelope incl. error/empty, below-the-UI authz,
reference data). Also see its sibling CLAUDE.md. Dependency-free; no install.

## Scope
- 11700-payable/verification/api/*.test.mjs      # new node:test scenarios / a new test file
- 11700-payable/verification/api/helpers/*.mjs   # only if a new api-local helper is needed
# do NOT edit ../core (shared, dependency-free); api must never import ui-e2e

## Acceptance
- [ ] Authored per 11700-payable/verification/api/AUTHORING.md (read first; followed, not improvised)
- [ ] One scenario per VERIFICATION-PLAN.md API scenario, each tracing to its SDD §3 row / PRD AC
- [ ] Asserts the REAL response envelope (success AND error/empty), not the idealized one
- [ ] Below-the-UI authz covered where the endpoint is protected (no-token / bad-token / role-scoping)
- [ ] Env-limited scenarios tagged + flagged env-limited in the gate table (not left to fail the gate)

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `node --check` each new *.test.mjs (parses; ../core imports resolve) | specs load; no syntax/import error |
| api | `cd 11700-payable/verification/api && node --test` | the runnable (non-env-limited) scenarios go green locally |

## Blocked by
<every other non-build subtask id>

## Implementation Notes (auto-maintained)
<!-- the authoritative recipe is 11700-payable/verification/api/AUTHORING.md; do not duplicate it here -->
```

If there is no `VERIFICATION-PLAN.md`, emit no gate and no build subtask — the
per-subtask `api` / `e2e/browser` tiers are the only verification coverage. If the
plan has UI journeys but its `## API Scenarios` is the "deferred" placeholder,
emit only `NNNN-smoke-e2e`. (To add coverage later, run
`/afk:grill-verification` → `/afk:to-verification-plan`, then re-run this skill.)

# Feature smoke gate (driven by `VERIFICATION-PLAN.md`)

This skill **seeds** the gate section and **emits the build subtasks** that
author its specs; running them is `/afk-toolkit:smoke-test`'s job (the per-subtask-tier
vs integrated-gate story lives in `skills/afk/smoke-test/SKILL.md`).

**The trigger is the artifact, not an ask.** If `VERIFICATION-PLAN.md` sits next
to the PRD, the human already decided. Emit the gate section **and one build
subtask per modality the plan carries**:

- **The PLAN.md `## Feature smoke gate` section** (template below): seed one row
  per scenario across **both** `## UI Journeys` and `## API Scenarios` — its
  plain-language summary, the source it traces to (UI → PRD User Story; API →
  SDD §3 row / PRD Acceptance Criterion), the spec it maps to, its `Modality`
  (`ui-e2e` | `api`), its `env-limited` flag carried over verbatim (so
  `/afk-toolkit:smoke-test` excludes those from its green verdict), and its
  `Requires target` class carried over verbatim (so `/afk-toolkit:smoke-test` refuses
  to count the row green on an incompatible target). Don't invent
  scenarios here — `VERIFICATION-PLAN.md` is the source of truth.
- **The terminal `NNNN-smoke-e2e` build subtask** (UI journeys) and, when the
  plan has real `## API Scenarios`, **the terminal `NNNN-smoke-api` build
  subtask** (API contracts) — Process step 3, using the base subtask contract
  with the fields below. Build recipes live canonically at
  **`11700-payable/verification/ui-e2e/AUTHORING.md`** and
  **`11700-payable/verification/api/AUTHORING.md`** (versioned with the
  verification code) — pointed at, never restated. Both blocked by every other
  subtask.

```
## Goal
Author the integrated browser smoke specs for {Feature}: one Scenario per
VERIFICATION-PLAN.md UI journey in 11700-payable/verification/ui-e2e, run by
/afk-toolkit:smoke-test as the gate. Read 11700-payable/verification/ui-e2e/AUTHORING.md
first (layer rules, conventions, definition-of-done) + sibling README/CLAUDE.md;
author accordingly.

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
<every implementation subtask id — not the other NNNN-smoke-* build subtask, not NNNN-sync-harness>
```

```
## Goal
Author the integrated API smoke specs for {Feature}: one node:test *.test.mjs per
VERIFICATION-PLAN.md API scenario (using ../core for auth/base-URL/poll) in
11700-payable/verification/api, run by /afk-toolkit:smoke-test as the gate. Read
11700-payable/verification/api/AUTHORING.md first (request shape, real envelope
incl. error/empty, below-the-UI authz, definition-of-done) + sibling CLAUDE.md;
author accordingly. Dependency-free; no install.

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
<every implementation subtask id — not the other NNNN-smoke-* build subtask, not NNNN-sync-harness>
```

If the plan has UI journeys but its `## API Scenarios` is the "deferred"
placeholder, emit only `NNNN-smoke-e2e`. (To add coverage later, run
`/afk-toolkit:grill-verification` → `/afk-toolkit:to-verification-plan`, then re-run this skill.)

## No `VERIFICATION-PLAN.md` → the minimal gate (never no gate)

A feature without a verification plan still may not stamp complete on
per-subtask tiers alone. Emit a `## Feature smoke gate (minimal)` section instead
— no build subtasks, no scenario table, five fixed rows the gate skill executes
as-is:

```
## Feature smoke gate (minimal)

| # | Check | Command | Status |
|---|-------|---------|--------|
| 1 | compile | ./mvnw -f all-modules-pom.xml --projects={changed modules} --also-make compile -DskipUi=true | |
| 2 | app-start | bash $AFK_PLUGIN_ROOT/adapters/build-gate/maven/app-start-gate.sh {leaf module} (exit 0) | |
| 3 | regression | ./mvnw -f all-modules-pom.xml --projects={changed modules} --also-make test -DskipUi=true | |
| 4 | existing ui-e2e suite | cd 11700-payable/verification/ui-e2e && npm run smoke (pre-existing scenarios still green) | |
| 5 | existing api suite | cd 11700-payable/verification/api && node --test (pre-existing scenarios still green) | |

Last run: —
```

`{main checkout}` fills at seeding time with the absolute path of the first
entry of `git worktree list` — the persisted command must run the main
checkout's plugin copy from any worktree, resolving nothing at gate time
(`GLOSSARY.md` "Main checkout").

`{changed modules}` = union of every subtask's Scope-derived Maven modules. Rows
4–5 prove the feature broke nothing the suites already covered; they add no
feature-specific scenarios — that coverage requires a real `VERIFICATION-PLAN.md`
(upgrade any time: grill → plan → re-run this skill; the full gate then replaces
the minimal section).

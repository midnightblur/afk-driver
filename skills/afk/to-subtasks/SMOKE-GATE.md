# Feature smoke gate (driven by `VERIFICATION-PLAN.md`)

This skill **seeds** the gate section and **emits the build subtasks** that
author its specs; running them is `/afk:smoke-test`'s job (the per-subtask-tier
vs integrated-gate story lives in `skills/afk/smoke-test/SKILL.md`).

**The trigger is the artifact, not an ask.** If `VERIFICATION-PLAN.md` sits next
to the PRD, the human already decided. Emit the gate section **and one build
subtask per modality the plan carries**:

- **The PLAN.md `## Feature smoke gate` section** (template below): seed one row
  per scenario across **both** `## UI Journeys` and `## API Scenarios` — its
  plain-language summary, the source it traces to (UI → PRD User Story; API →
  SDD §3 row / PRD Acceptance Criterion), the spec it maps to, its `Modality`
  (`ui-e2e` | `api`), its `env-limited` flag carried over verbatim (so
  `/afk:smoke-test` excludes those from its green verdict), and its
  `Requires target` class carried over verbatim (so `/afk:smoke-test` refuses
  to count the row green on an incompatible target). Don't invent
  scenarios here — `VERIFICATION-PLAN.md` is the source of truth.
- **The terminal `NNNN-smoke-e2e` build subtask** (UI journeys) and, when the
  plan has real `## API Scenarios`, **the terminal `NNNN-smoke-api` build
  subtask** (API contracts) — Process step 3, using the base subtask contract
  with the fields below. Build recipes live canonically with the repository's
  own verification code (its `AUTHORING.md`, `README.md` or `CLAUDE.md` beside
  the suite) — pointed at, never restated. Both blocked by every other subtask.

**Placeholders.** `{e2e-suite}` and `{api-suite}` are the suite directories the
repository's `e2e/browser` and `api` tiers run in — read them out of
`verification.tiers` in `.afk/config.yaml`, and fill them at seeding time so
the persisted subtask carries a real path. `{e2e-command}` and `{api-command}`
are those tiers' own command lines, filled the same way. A repository that
declares neither tier gets neither build subtask.

```
## Goal
Author the integrated browser smoke specs for {Feature}: one Scenario per
VERIFICATION-PLAN.md UI journey in {e2e-suite}, run by
/afk:smoke-test as the gate. Read that suite's authoring recipe first
(layer rules, conventions, definition-of-done) + sibling README/CLAUDE.md;
author accordingly.

## Scope
- {e2e-suite}/features/*.feature   # new Scenarios / a new feature file
- {e2e-suite}/steps/*.mjs          # only if a new step sentence is needed
- {e2e-suite}/scenarios.mjs        # only if a genuinely new shared action is needed

## Acceptance
- [ ] Authored per the suite's own authoring recipe (read first; followed, not improvised)
- [ ] One Scenario per VERIFICATION-PLAN.md UI journey, each tracing to its PRD User Story
- [ ] Env-limited journeys tagged + flagged env-limited in the gate table (not left to fail the gate)

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | the suite's own dry-run form (`{e2e-suite}`) | every step resolves; 0 undefined / 0 ambiguous |
| e2e/browser | `{e2e-command}` | the runnable (non-env-limited) scenarios go green locally |

## Blocked by
<every implementation subtask id — not the other NNNN-smoke-* build subtask, not NNNN-sync-harness>
```

```
## Goal
Author the integrated API smoke specs for {Feature}: one test per
VERIFICATION-PLAN.md API scenario, using the suite's shared auth/base-URL/poll
primitives, in {api-suite}, run by /afk:smoke-test as the gate. Read
that suite's authoring recipe first (request shape, real envelope incl.
error/empty, below-the-UI authz, definition-of-done) + sibling CLAUDE.md;
author accordingly.

## Scope
- {api-suite}/*.test.mjs      # new scenarios / a new test file
- {api-suite}/helpers/*.mjs   # only if a new api-local helper is needed
# do NOT edit the suite's shared primitives; the api suite must never import the e2e one

## Acceptance
- [ ] Authored per the suite's own authoring recipe (read first; followed, not improvised)
- [ ] One scenario per VERIFICATION-PLAN.md API scenario, each tracing to its SDD §3 row / PRD AC
- [ ] Asserts the REAL response envelope (success AND error/empty), not the idealized one
- [ ] Below-the-UI authz covered where the endpoint is protected (no-token / bad-token / role-scoping)
- [ ] Env-limited scenarios tagged + flagged env-limited in the gate table (not left to fail the gate)

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | the suite's own parse check on each new spec file | specs load; no syntax/import error |
| api | `{api-command}` | the runnable (non-env-limited) scenarios go green locally |

## Blocked by
<every implementation subtask id — not the other NNNN-smoke-* build subtask, not NNNN-sync-harness>
```

If the plan has UI journeys but its `## API Scenarios` is the "deferred"
placeholder, emit only `NNNN-smoke-e2e`. (To add coverage later, run
`/afk:grill-verification` → `/afk:to-verification-plan`, then re-run this skill.)

## No `VERIFICATION-PLAN.md` → the minimal gate (never no gate)

A feature without a verification plan still may not stamp complete on
per-subtask tiers alone. Emit a `## Feature smoke gate (minimal)` section instead
— no build subtasks, no scenario table, five fixed rows the gate skill executes
as-is:

```
## Feature smoke gate (minimal)

| # | Check | Command | Status |
|---|-------|---------|--------|
| 1 | compile | the `static` tier from `verification.tiers`, `{module}` = the changed modules | |
| 2 | app-start | `bash $AFK_PLUGIN_ROOT/adapters/build-gate/<kind>/gates.sh app-start {leaf module}` (exit 0) — only where the selected build-gate kind offers it | |
| 3 | regression | the `unit` tier from `verification.tiers`, same modules | |
| 4 | existing e2e suite | `{e2e-command}` (pre-existing scenarios still green) | |
| 5 | existing api suite | `{api-command}` (pre-existing scenarios still green) | |

A row whose tier the repository does not declare is dropped at seeding time,
not left in the table as an unrunnable command.

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

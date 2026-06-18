---
name: grill-e2e
description: Interview the user to design the feature's end-to-end test scenarios — the real end-user journeys that decide "this feature works" — and emit an E2E-PLAN.md sibling to the PRD. Forces agent and user to walk the actual UI journey concretely, which routinely reveals gaps in the PRD (a story with no demonstrable journey is an underspecified story). Invoke manually after `/afk:to-prd` (the common case — journeys are usually clear from the PRD) or after `/afk:to-sdd` (when the technical solution must be settled before the journey is realistic). Optional and human-invoked. Produces the plan `/afk:to-subtasks` turns into a build subtask and `/afk:smoke-test` later runs as the completion gate. Does not write to the tracker.
---

# afk:grill-e2e — design the feature's end-user journeys with the user

You interview the user to nail down **what it means for this feature to work for
a real user** — the concrete browser journeys a person (or job) drives through
the UI, end to end. The output is `E2E-PLAN.md`: the catalog of those journeys,
each traced to a PRD User Story. Downstream, `/afk:to-subtasks` turns the plan
into a build subtask that authors the specs, and `/afk:smoke-test` runs them as
the feature-completion gate.

This is a **grilling** skill, like `/afk:grill-requirements` and
`/afk:grill-solution`: you interview, you don't assume. The difference is the
lens — you walk the **actual end-user journey** step by step. That concreteness is
the point: a User Story that can't be turned into a demonstrable click-path is an
underspecified story, and saying so out loud is how this skill earns its keep.

## When to invoke

Optional and **human-invoked** — the user decides when:

- **After `/afk:to-prd`** (the common case): the PRD's User Stories are usually
  concrete enough to walk the journeys directly.
- **After `/afk:to-sdd`**: when a journey only becomes realistic once the
  technical solution is settled (e.g. a flow that depends on a new endpoint, a
  job, or a state machine the SDD defines). Read the SDD too in that case.

If neither artifact exists yet, stop and route the user to `/afk:to-prd` first —
there's nothing to ground journeys against.

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
- `sdd_path` *(optional)* — the sibling `SDD.md`, when invoked post-SDD. Present →
  ground journeys in the settled technical solution too.

## Process

1. **Read the sources.** `ctx_read` the PRD (full) — especially its **User
   Stories** — and the SDD (full) when present. Skim the canonical build recipe
   **`11700-payable/e2e/AUTHORING.md`** (and its sibling `CLAUDE.md`) so you grill
   **buildable** journeys: each is later turned into a `Scenario` by following
   that recipe, reusing the module's existing L2 domain flows where they exist.
   Frame journeys as concrete, assertable UI outcomes the recipe can express as
   `Then` steps — don't design a journey the module has no way to drive.

2. **Grill each candidate journey.** Work from the PRD's top User Stories — those
   are the definition-of-done flows. For each, drive the user through:
   - **Actor & trigger** — who acts (persona / role / scheduled job), and what
     starts the journey.
   - **The click-path** — the concrete step-by-step through the UI, in plain
     business language. If you or the user can't narrate the steps, that's a PRD
     gap — flag it (step 4), don't invent the flow.
   - **Definition of done** — the observable outcome that proves it worked: a
     visible state, a posted record, a status transition, a surfaced error. Vague
     "it works" is not acceptance; pin the assertion.
   - **Preconditions / data setup** — what must exist first (a created invoice, an
     approval, a config). These become the journey's `Given`.
   - **Alternate & error paths** — the failure/edge journeys worth gating, not
     just the happy path.
   - **Env reachability** — can this journey actually go green on the dev stack?
     Some can't by design (SAP needing VPN; a GL post parking on missing FOS
     config). Mark those `env-limited` now — they'll be tagged and excluded from
     the gate's green verdict, not treated as broken (see
     `11700-payable/e2e/AUTHORING.md`).

3. **Check coverage against the PRD.** Every top User Story should map to at least
   one journey; every journey should trace back to a Story. Surface
   over-coverage (a journey no Story asks for — is the Story missing?) and
   under-coverage (a Story with no demonstrable journey — is the Story real?).

4. **Surface PRD gaps explicitly.** Revealing gaps is a primary output, not a side
   effect. When a journey exposes an ambiguous, missing, or contradictory PRD
   detail, name it. If the gap is small, capture it in the plan's `## PRD gaps
   surfaced` section for the human to fold back into the PRD. If it's
   load-bearing (the journey can't be designed without it), **stop and route the
   user back** to `/afk:grill-requirements` + `/afk:to-prd` (or
   `/afk:grill-solution` + `/afk:to-sdd` for a technical gap) before emitting.

5. **Emit `E2E-PLAN.md`** sibling to the PRD (template below) once the journeys
   are settled and the user agrees the set is complete. Print the path and a
   one-line-per-journey summary (actor, traces-to Story, env-limited?).

## `E2E-PLAN.md` (the artifact)

Written next to `PRD.md` / `SDD.md` at `…/{TICKET-ID}/E2E-PLAN.md`. It is the
design artifact `/afk:to-subtasks` reads to seed the gate and emit the build
subtask — the journeys here are the source of truth for both.

````
# E2E Plan — {Feature Name}

> Parent ticket: {TICKET-ID}   Sources: [PRD](PRD.md){· [SDD](SDD.md)}
> Suite: 11700-payable/e2e   Built per: 11700-payable/e2e/AUTHORING.md
> Status: draft (built by NNNN-smoke-e2e; run by /afk:smoke-test)

## Journeys

Each journey is one integrated end-user flow that decides "feature works". Each
traces to a PRD User Story and will become one `Scenario` in the Gherkin catalog.

| # | Journey (plain business language) | Actor | Traces to | Env-limited? |
|---|-----------------------------------|-------|-----------|--------------|
| 1 | <trigger → click-path → definition of done> | <role/job> | PRD User Story N | no |
| 2 | <journey> | <role> | PRD User Story M | env-limited (@sap) |

### 1 — <journey title>
- **Given** <preconditions / data setup>
- **When** <the concrete click-path, step by step>
- **Then** <the observable definition of done — the assertion>
- **Alt/error paths**: <edge journeys worth gating, or "none">
- **Reuses**: <existing L2 scenarios.mjs flows this leans on, if known>

## PRD gaps surfaced

Gaps the journey-walk exposed, for the human to fold back into the PRD/SDD.
(Load-bearing gaps were routed back before this plan was emitted.)

- <gap> — <which Story / which journey exposed it>
````

## Hard rules

- **Grill, don't assume.** If a journey's steps or its definition-of-done can't
  be stated concretely, that's a PRD gap to surface (step 4) — never invent the
  flow to keep moving.
- **Design buildable journeys.** Ground scenarios in what the `11700-payable/e2e`
  module can actually drive (canonical recipe: `11700-payable/e2e/AUTHORING.md`);
  reuse existing L2 flows. Don't spec a journey the suite has no way to perform.
- **Every journey traces to a Story; every gap is named.** No orphan journeys, no
  silently-swallowed PRD ambiguities.
- **Mark env-limited journeys at design time** — so the downstream gate excludes
  them from its green verdict rather than reading them as failures.
- **No tracker writes.** This skill produces a local artifact only (`E2E-PLAN.md`
  + PRD-gap notes). It touches no Jira and no GitLab.

## Next

`E2E-PLAN.md` is on disk. Fold any `## PRD gaps surfaced` back into the PRD (and
re-run `/afk:to-ticket` if the PRD changed and is already published). Then run
**`/afk:to-subtasks`**: it detects the plan and automatically emits a terminal
`NNNN-smoke-e2e` build subtask (blocked by every other subtask) that authors
these journeys as specs, plus the `## Feature smoke gate` in `PLAN.md` seeded
from them. After every subtask is `done`, **`/afk:smoke-test`** runs the
integrated journeys against a running app as the completion gate.

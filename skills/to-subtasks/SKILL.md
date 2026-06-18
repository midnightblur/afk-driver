---
name: to-subtasks
description: Slice a PRD (and the accompanying SDD + ADRs, when present) into a local, reviewable execution plan on disk — a plan/ directory with a PLAN.md index (solution map, seam register, live progress tracker) and one NNNN-slug.md contract per subtask. No Jira: subtasks are local artifacts the human reviews and `/afk:execute` works one at a time. Cited mode (PRD + SDD, from `/afk:grill-solution`) carries binding design refs, typed Produces/Consumes contracts, and a per-subtask seam list; uncited mode (PRD only, from `/afk:grill-requirements`) is lighter and human-gated. Every subtask declares tiered verification (static → unit → integration → e2e/browser). Use when you have a PRD (and optionally an SDD) and want to plan the work.
---

# afk:to-subtasks — slice a PRD (+ SDD/ADRs) into a local execution plan

This skill turns a finished design into a **plan you can read, review, and
track** — entirely on disk, no tracker writes. It emits a `plan/` directory
sibling to the PRD:

```
{TICKET-ID}/
  PRD.md  SDD.md  adr/…
  plan/
    PLAN.md          # index: solution map, seam register, progress tracker
    0001-{slug}.md   # one contract per subtask, in rank order
    0002-{slug}.md
    …
```

`PLAN.md` is the artifact a human scans to understand the plan, spot the
critical parts (the seams), and watch progress as `/afk:execute` works each
subtask. The per-subtask files are the binding contracts `/afk:execute` parses.

The plan is the load-bearing interface between this skill (emitter) and
`/afk:execute` (parser + progress writer). They live in the same repo so the
contract is enforced by a single commit — change a section here, change the
parser there, same commit.

## Two modes, set by what's upstream

| You came from | On disk | Mode | What the plan carries |
|---|---|---|---|
| `/afk:grill-solution` → `/afk:to-sdd` | PRD **+ SDD + ADRs** | **cited** | binding design refs, typed `## Produces`/`## Consumes` graph, per-subtask `## Seams` (SDD §9b), citation-tagged Acceptance |
| `/afk:grill-requirements` → `/afk:to-prd` only | PRD, **no SDD** | **uncited** | PRD-derived Goal/Scope/Acceptance, tiered Verification; no binding contract |

Cited mode is the default whenever an `SDD.md` sits next to the PRD. Uncited
mode is for small features / bugs / refactors / tooling where an SDD would be
overkill — and it is **human-gated**: never decide on your own that the design
warrants no SDD (see "Design-doc optionality").

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
- `sdd_path` *(optional)* — defaults to the PRD's sibling `SDD.md`. Present →
  cited mode.
- `ticket_id` — parent Enhancement/Bug key (e.g. `P2P-1220`), used only to label
  the plan and the eventual branch. **Nothing is written to Jira.**
- `skip_design_docs` *(optional, default false)* — human override to slice
  uncited even though an SDD might be warranted.
- `e2e_plan_path` *(optional)* — defaults to the PRD's sibling `E2E-PLAN.md`.
  **Its presence is the trigger**: if an `E2E-PLAN.md` exists (the user ran
  `/afk:grill-e2e`), automatically emit the feature smoke gate + a terminal
  `NNNN-smoke-e2e` build subtask (see "Feature smoke gate" below). No ask — the
  decision was made by running `grill-e2e`. Absent → no gate, no build subtask.

## Process

1. **Read the sources.** `ctx_read` the PRD (mode=full) and the parent ticket
   description for context (target branch, components). In cited mode also read
   `SDD.md` (full) and every `adr/{requirements,design}/NNNN-*.md`
   (mode=signatures). The set of `(SDD section IDs, §9b seam rows, ADR IDs)` is
   your **citation pool** — every cited subtask references at least one entry.
   Also check for a sibling `E2E-PLAN.md` (from `/afk:grill-e2e`); if present,
   read it (full) — its journeys drive the smoke gate + build subtask (step 3).

2. **Refuse-to-slice gate (cited mode).** A plan built on an unstable SDD ships
   the instability into every subtask. Before slicing, scan the SDD + every ADR
   and **refuse on any hit** — print offenders, bounce to `/afk:grill-solution`
   + `/afk:to-sdd`:
   - **Executor-blocking markers** — the canonical blocker set `/afk:to-sdd`
     Step 7 enforces (`\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`, `\?\?\?`,
     `<TBD>`/`<TODO>`/`<placeholder>`/`<fill>`/`<\?>`, `\[\?\]`,
     `_?FILL[_-]?IN_?`, `\(decide later\)`/`\(unresolved\)`/`\(open\)`,
     unsubstituted template literals like `<TICKET-ID>`/`{Feature Name}`), plus
     §13 Open-Questions rows marked `Blocks executor? = yes`. Skip code-block
     contents (real generics `<T>`, nullable `Foo?` are not blockers).
   - **Library-version pins** — every pin the SDD/ADR cites (`Spring Boot
     3.2.4`, `Vue 3.4`, …) must match the build manifest (`pom.xml` + BOM /
     `build.gradle` / `package-lock.json` / `pyproject.toml`). A divergent pin
     means a fictional API surface — refuse, unless the SDD labelled it
     `"inherited from {BOM}; not a direct pin"` (the documented escape hatch).

   Uncited mode skips this gate — the human has accepted the PRD as the only
   source of truth.

3. **Slice into subtasks.** A good subtask is independently buildable (no
   dependency on an unlanded sibling except via `## Blocked by`), bounded by a
   clear Scope (one or two globs), verifiable on its own, and sized for one
   `/afk:execute` sitting (~1 hour). In cited mode, **slice along SDD §8 module
   boundaries** — one subtask per module's public interface. If you find
   yourself splitting a §8 module, the SDD is too coarse: bounce, don't invent a
   split that contradicts §8. Aim for 4–10 subtasks; more than 10 means the PRD
   is too big or the slice too fine.

   **Detect the e2e plan.** Check for `E2E-PLAN.md` next to the PRD. If present,
   the user designed the feature's end-user journeys via `/afk:grill-e2e`, so you
   **automatically** append one **terminal** build subtask `NNNN-smoke-e2e.md`
   (`## Blocked by` **every** other subtask) that authors those journeys as specs
   in the `11700-payable/e2e` module — using the "Feature smoke gate" build-subtask
   template below. The build agent follows the **canonical authoring recipe at
   `11700-payable/e2e/AUTHORING.md`** (versioned with the e2e code; never copied
   here). It's normal `/afk:execute` work; the specs land as reviewed code. The
   integrated gate that *runs* them is `/afk:smoke-test`, after this subtask is
   `done` (not part of this skill). No `E2E-PLAN.md` → no build subtask, no gate.

4. **Write each subtask file** `plan/NNNN-{slug}.md` in rank order, using the
   contract below. `NNNN` is the zero-padded rank; `{slug}` is a short kebab
   title. The subtask's **id** is `NNNN-{slug}` — that's what `## Blocked by`,
   `## Consumes`, and the tracker reference (no Jira keys anywhere).

5. **Write `PLAN.md`** (the index) using the PLAN template below: the solution
   map, the seam register (cited), and the progress tracker seeded with every
   subtask at status `pending`. `/afk:execute` owns the tracker's status column
   from here on.

6. **Validate the slice** (see "Validation"). Cited mode runs the contract-graph
   + anchor-quality + Acceptance-citation + seam-coverage checks; all must pass
   before the plan is considered emitted. Uncited mode runs only the
   Verification-tier and Scope sanity checks.

7. **Output.** Print the plan path and a one-line-per-subtask summary (id,
   title, tiers, seams touched, blocked-by) so the human can review before any
   execution. Flag every seam-touching subtask explicitly — those are the rows
   worth a careful human read.

## Subtask contract (`plan/NNNN-{slug}.md`)

`/afk:execute` parses these section headings exactly. Keep them verbatim.

```
## Goal
<one paragraph: what this subtask delivers>

## Design refs
<cited>
- SDD: SDD.md#<anchor> — <one phrase on what it binds>
- ADR: adr/design/NNNN-*.md — <one phrase>
<uncited>
(none — sliced from the PRD without an SDD, per human approval)

## Scope
- <glob 1>
- <glob 2>

## Seams
<cited — the SDD §9b external seams this subtask touches; mark each implement|use>
- implement: <SDD §9b row "boundary"> — this subtask owns the seam's code + seam-test
- use: <SDD §9b row "boundary"> — this subtask calls across it; relies on its contract
<uncited or no seam>
(none — no SDD seam register)

## Acceptance
<cited — every bullet ends with a citation tag: (PRD §X.Y) / (SDD §N) /
(SDD §N row "...") / (SDD §9b row "...") / (ADR-NNNN)>
- [ ] <criterion> (PRD §X.Y)
- [ ] Implements the public interface in SDD §8 row "<module>" unmodified (SDD §8)
- [ ] Conforms to ADR-<NNNN> — no silent pattern substitution (ADR-NNNN)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] <iff this subtask implements a §9b seam> Seam-test asserts on <framework>'s
      real output (serialized result / generated schema / surfaced error), not our
      intermediate objects (SDD §9b row "<boundary>")
<uncited — bullets reference PRD prose, no tags>
- [ ] <criterion referencing User Story N>

## Produces
<cited — one bullet per consumer-visible artifact this subtask creates>
- <file-path>#<grep-anchor> — <one-line contract>
<uncited — omit this block>

## Consumes
<cited AND Blocked by non-empty — one bullet per upstream artifact read>
- <PRODUCER-ID> <file-path>#<grep-anchor> — <what we expect>
<otherwise — omit this block>

## Verification
<tiered — one row per tier this subtask needs; static is always present.
The implementor (/afk:execute) must turn EVERY listed tier green.>
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `<compile/lint/type cmd>` + grep the ## Produces anchors | code builds; declared symbols present |
| unit | `<unit test cmd, e.g. mvn -pl {module} test -Dtest=FooTest>` | unit behavior |
| integration | `<cmd>` | cross-module wiring / persistence / framework pickup |
| e2e/browser | `<cmd, e.g. npx playwright test specs/foo.spec.ts>` | user-visible flow end-to-end |

## Parent PRD
<prd_path>

## Parent SDD
<sdd_path or "(none — uncited mode)">

## Blocked by
<subtask ids (NNNN-slug) or "(none)">

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, exit `design_conflict` quoting the SDD section + the
conflict. Do NOT override silently. Route back to `/afk:grill-solution` for a
superseding ADR.
(omit this block in uncited mode)

## Implementation Notes (auto-maintained)
<!-- /afk:execute appends one note per run; humans may add prose around it -->
```

### Choosing verification tiers

Pick the tiers the change actually demands — don't pad, don't under-cover:

- **static** is always present: it compiles/lints and greps the `## Produces`
  anchors so the declared symbols exist. A pure rename / config / docs subtask
  may be static-only.
- **unit** whenever the subtask adds behavior worth asserting in isolation.
- **integration** for cross-module wiring, persistence, or framework-pickup
  (e.g. the liquibase-hibernate7 entity-pickup check for a JPA entity, or a
  §9b seam-test asserting on the framework's real serialized/generated output).
- **e2e/browser** for user-visible flows — a Playwright/Cypress spec that drives
  the actual UI. A backend-only subtask omits this; a UI subtask must not.

A subtask that **implements** a §9b seam must carry the seam's test as a
Verification row (unit or integration tier) asserting on the framework's real
output, not our DTO — it's the only test that covers the boundary.

### Feature smoke gate (driven by `E2E-PLAN.md`)

The per-subtask `e2e/browser` tier proves **one slice's** UI in isolation. A
feature whose end-user journeys were designed via `/afk:grill-e2e` also gets an
**integrated smoke gate**: those cross-subtask journeys, run against a real
running app, as the final "feature complete" check — and reused afterward by CI /
scheduled jobs / manual sanity runs. The gate that *runs* them is a separate
skill (`/afk:smoke-test`); this skill **seeds** the gate and **emits the build
subtask** that authors the specs.

**The trigger is the artifact, not an ask.** If `E2E-PLAN.md` sits next to the
PRD, the human already decided (by running `/afk:grill-e2e`). Emit **both**:

- **The PLAN.md `## Feature smoke gate` section** (template below): seed one row
  per `E2E-PLAN.md` journey — its plain-language summary, the PRD User Story it
  traces to, the `features/*.feature ▸ scenario` it maps to, and its
  `env-limited` flag carried over verbatim (so `/afk:smoke-test` excludes those
  from its green verdict). Don't invent journeys here — `E2E-PLAN.md` is the
  source of truth.
- **The terminal `NNNN-smoke-e2e` build subtask** (Process step 3), using the
  base subtask contract with the fields below. The how-to-build recipe (module
  layers, conventions, reference data, verify-in-order, definition-of-done) is
  **not** restated here or anywhere in this repo — it lives canonically at
  **`11700-payable/e2e/AUTHORING.md`**, versioned with the e2e code so it can't
  drift. The subtask's job is to point the build agent there and read it first.
  Blocked by every other subtask.

```
## Goal
Author the integrated browser smoke specs for {Feature} into the existing
11700-payable/e2e module, one Scenario per E2E-PLAN.md journey, so /afk:smoke-test
can run them as the gate. FOLLOW THE CANONICAL RECIPE: read
11700-payable/e2e/AUTHORING.md first — it is the authoritative how-to (layer
rules, conventions, reference data, verify steps, definition-of-done). Also see
its siblings README.md (run/env) + CLAUDE.md.

## Scope
- 11700-payable/e2e/features/*.feature          # new Scenarios / a new feature file
- 11700-payable/e2e/steps/*.mjs                  # only if a new step sentence is needed
- 11700-payable/e2e/scenarios.mjs               # only if a genuinely new L2 action is needed

## Acceptance
- [ ] Authored per 11700-payable/e2e/AUTHORING.md (read first; followed, not improvised)
- [ ] One Scenario per E2E-PLAN.md journey, each tracing to its PRD User Story
- [ ] Env-limited journeys tagged + flagged env-limited in the gate table (not left to fail the gate)

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `cd 11700-payable/e2e && npx cucumber-js --dry-run` | every step resolves; 0 undefined / 0 ambiguous |
| e2e/browser | `cd 11700-payable/e2e && npm run smoke` | the runnable (non-env-limited) scenarios go green locally |

## Blocked by
<every other subtask id>

## Implementation Notes (auto-maintained)
<!-- the authoritative recipe is 11700-payable/e2e/AUTHORING.md; do not duplicate it here -->
```

If there is no `E2E-PLAN.md`, emit neither — the per-subtask e2e tiers are the
only browser coverage. (To add a gate later, run `/afk:grill-e2e`, then re-run
this skill.)

## PLAN.md (the index)

````
# Execution Plan — {Feature Name}

> Parent ticket: {TICKET-ID}   Mode: cited | uncited
> Sources: [PRD](../PRD.md){cited: · [SDD](../SDD.md) · [ADRs](../adr/)}
> Branch (for /afk:execute): mvu/afk/{ticket-id-lower}
> Last updated: {YYYY-MM-DD} (status column maintained by /afk:execute)
> Feature: in-progress   <!-- /afk:smoke-test stamps "complete (smoke green …)" iff a smoke gate exists -->

## Solution map

A diagram mapping each subtask to the parts of the solution it touches, so a
reviewer sees coverage and overlap at a glance. Mark every seam edge with the
`seam` label so the critical boundaries stand out.

```mermaid
flowchart LR
  subgraph Components
    C1[module / layer]
    C2[module / layer]
  end
  T1([0001 slug]) --> C1
  T2([0002 slug]) --> C2
  T2 -. seam .-> S1{{§9b boundary}}
```

## Seam register   <!-- cited mode only; omit whole section in uncited -->

| § | Seam (SDD §9b row) | Implemented by | Used by |
|---|--------------------|----------------|---------|
| 1 | "<boundary>" | 0002-slug | 0004-slug, 0005-slug |

## Progress tracker

| # | Subtask | Title | Status | Blocked by | Tiers | Seams |
|---|---------|-------|--------|------------|-------|-------|
| 1 | 0001-slug | … | pending | — | static, unit | — |
| 2 | 0002-slug | … | pending | — | static, unit, integration | impl §1 |
| 3 | 0003-slug | … | pending | 0002-slug | static, unit, e2e | use §1 |

Status values: `pending` → `designing` → `developing` → `verifying` → `done`,
or `blocked(<reason>)`. `/afk:execute` advances the row it is working and writes
the date in the header; everything else in PLAN.md is yours to edit.

## Feature smoke gate   <!-- present iff an E2E-PLAN.md exists; omit whole section otherwise -->

> Gate: /afk:smoke-test   Suite: 11700-payable/e2e   Target env: local | staging
> Run: npm run smoke   (full incl. env-limited: npm run smoke:all)
> Source: ../E2E-PLAN.md   Built by: NNNN-smoke-e2e (terminal subtask, blocked by all)
> Last run: — (date + target; maintained by /afk:smoke-test)

Integrated user journeys that decide "feature complete", seeded from
`E2E-PLAN.md` (one row per journey). Each traces to a PRD User Story and maps to
a `Scenario` in the e2e module's Gherkin catalog. `/afk:smoke-test` runs them
against a running app and owns the Status column + the header `Feature:` line;
the rows themselves are seeded here. An `env-limited` journey (e.g. `@sap`,
GL-post) carries that flag from `E2E-PLAN.md` — the gate excludes it from its
green verdict.

| # | Scenario (integrated journey) | Traces to | Spec (feature ▸ scenario) | Status |
|---|-------------------------------|-----------|---------------------------|--------|
| 1 | <journey in plain language> | PRD User Story N | features/<feature>.feature ▸ "<scenario>" | pending |
| 2 | <journey, env-gated> | PRD User Story M | features/<feature>.feature ▸ "<scenario>" | env-limited |
````

## Validation

Run before declaring the plan emitted. **Cited mode** runs (a)–(f);
**uncited mode** runs only (e) and (f). Check **(g)** runs in either mode
whenever an `E2E-PLAN.md` is present.

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
JPA entity → integration/pickup present). Every command is runnable from repo
root.

**(f) Scope sanity.** Globs are concrete (no bare `**`), and the union of all
subtask Scopes covers the PRD's stated work with no silent gap.

**(g) Smoke gate (iff an `E2E-PLAN.md` is present).** Every `E2E-PLAN.md` journey
is seeded as a `## Feature smoke gate` row, each tracing to a real PRD User Story
(grep the PRD) and naming a `features/*.feature ▸ scenario` spec; no gate row
invents a journey absent from `E2E-PLAN.md`. A terminal `NNNN-smoke-e2e` build
subtask exists, `## Blocked by` **every** other subtask, pointing the build agent
at `11700-payable/e2e/AUTHORING.md` (e2e authoring layer in `## Scope`;
`## Verification` carries both a `static` `cucumber-js --dry-run` row and an `e2e`
`npm run smoke` row). Any gate row marked `env-limited` carries that flag from
`E2E-PLAN.md`.
Conversely, no `E2E-PLAN.md` → neither the section nor the build subtask is
present (don't emit a half-gate).

## Hard rules

- **No tracker writes.** This skill only writes files under `plan/`. It creates
  no Jira issue, sets no label, opens no branch. (`/afk:execute` self-creates
  the branch.)
- **The plan round-trips.** `/afk:execute` parses these exact section headings;
  if you add/rename/reorder a section, update the `/afk:execute` parser in the
  same commit (lockstep).
- **Don't fabricate Acceptance.** Every bullet traces to the PRD or (cited) the
  SDD/an ADR; cited bullets carry a resolving citation tag (validation (c)).
- **Don't invent a public interface.** Cited interfaces come from SDD §8
  verbatim; a missing one is a design gap → bounce to `/afk:grill-solution`.
- **Verification is part of the plan, not an afterthought.** Every subtask
  declares the tiers it needs and the exact commands; `static` is mandatory, and
  the highest tier the change demands (up to e2e/browser) must be present.
- **Seam-implementing subtasks carry the seam-test** as a Verification row
  asserting on the framework's real output, not our DTO.
- **JPA-entity subtasks verify liquibase-hibernate7 pickup** (core-services Java
  only): a `## Produces` `.java` file with `@Entity` / `@MappedSuperclass` /
  `@Embeddable` must list an integration-tier row running the documented pickup
  check (`mvn -pl {module} compile liquibase:diff …` then grep the diff for the
  entity/column) — not just a unit test against the entity in isolation.
- **Uncited mode is human-approved per ticket.** Never decide on your own that
  the design needs no SDD.
- **The smoke gate is artifact-driven, all-or-nothing.** An `E2E-PLAN.md` next to
  the PRD emits **both** the `## Feature smoke gate` section AND the terminal
  `NNNN-smoke-e2e` build subtask (blocked by all); no `E2E-PLAN.md` emits neither.
  Never invent a gate without the plan, and never half-emit. The journey design is
  `/afk:grill-e2e`'s job, the build recipe is the e2e repo's
  `11700-payable/e2e/AUTHORING.md` (referenced, never copied), and running the
  gate is `/afk:smoke-test`'s — this skill only seeds + slices.

## Design-doc optionality

Not every ticket warrants an SDD; the human decides. New complex feature
(≥2 modules / new pattern / non-trivial txn or data) → SDD **required**, refuse
to slice cited-less unless `skip_design_docs=true`. Small enhancement / bug fix
/ refactor / tooling → uncited is fine. When no `SDD.md` is on disk and
`skip_design_docs` is unset, **ask** before proceeding:

> *No SDD found at `{path}`. Slice from the PRD alone (uncited), or pause and run
> `/afk:grill-solution` + `/afk:to-sdd` first?*

Record the human's choice in the output so it's auditable.

## Next

The plan is on disk. Review `PLAN.md` — especially the seam register and any
seam-touching subtasks. Then work the subtasks one at a time, in rank order
(respecting `## Blocked by`): in a session on the parent branch, run
**`/afk:execute {NNNN-slug}`** for each. Each run advances that subtask's status
in the tracker, drives it through design → develop → verify (every declared
tier green), commits, pushes, and updates the Draft MR — then stops at CR/Merge
for you.

If an `E2E-PLAN.md` drove a `## Feature smoke gate`, the terminal
`NNNN-smoke-e2e` build subtask authors its specs last (it's blocked by
everything). Once **every** subtask is `done`, run **`/afk:smoke-test`** as the
feature-completion gate: it runs the integrated browser journeys against a
running app and, only on green, stamps `Feature: complete` in PLAN.md. That suite
then serves CI / scheduled / manual sanity runs.

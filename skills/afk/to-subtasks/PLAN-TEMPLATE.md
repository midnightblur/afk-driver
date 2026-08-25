# PLAN.md (the index)

````
# Execution Plan — {Feature Name}

> Parent ticket: {TICKET-ID}   Mode: cited | uncited
> Sources: [PRD](../PRD.md){cited: · [SDD](../SDD.md) · [ADRs](../adr/)}
> Branch (for /afk:execute): mvu/afk/{ticket-id-lower}
> Last updated: {YYYY-MM-DD} (status column maintained by /afk:execute)
> Feature: in-progress   <!-- /afk:smoke-test stamps "complete (smoke green …)" iff a smoke gate exists -->
> Review policy: lean   <!-- lean | full — slice review-gate roster; semantics owned by skills/afk/review/SKILL.md "Gate policy". Seeded lean; flip to full by hand for the full roster on every slice; absent (older plans) reads full -->

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

Status values: `pending` → `designing` → `developing` → `verifying` → `reviewing` → `done`,
or `blocked(<reason>)`. <!-- status set: lockstep copy — owned by /afk:execute (progress-tracker status column) -->
`/afk:execute` advances the row it is working and writes
the date in the header; everything else in PLAN.md is yours to edit.

## Preflight   <!-- created on first /afk:preflight run only — omit entirely until then -->
<!-- lockstep copy: column shape `# | Step | Status | Cycle | Evidence` is owned
     jointly by /afk:preflight (sole writer) and the mission-control renderer's
     gates section (skills/afk/mission-control/scripts/mc/sections/gates.py) — a
     column rename here is a same-commit change in both places -->

`/afk:preflight` is this section's sole writer (progress tracker + smoke gate
above stay untouched by it); re-run skips rows already `green`, resuming at
the first non-`green` row. `Cycle` reflects the shared 2-cycle fix cap
(counted across PF-2/PF-4/PF-7, not per row); PF-3's cell instead counts its
review settle-loop rounds (cap 10 — owned by
`skills/afk/review/SETTLEMENT.md`; lockstep copy here).

| # | Step | Status | Cycle | Evidence |
|---|------|--------|-------|----------|
| 1 | PF-1 merge target branch + ancestry guard, push | pending | — | — |
| 2 | PF-2 validations (mechanical fix, shared cap) | pending | 0/2 | — |
| 3 | PF-3 fresh-context review of the integrated diff (settle loop) | pending | 0/10 | — |
| 4 | PF-4 seam check (`/afk:verify-seams final`) | pending | — | — |
| 4b | PF-4b understanding artifact (advisory, never parks) | pending | — | — |
| 4c | PF-4c open workflow lessons (advisory, never parks) | pending | — | — |
| 4d | PF-4d product-debt homed in its CLAUDE.md (shared cap) | pending | — | — |
| 5 | PF-5 ship evidence (MC snapshot commit + MR evidence block) | pending | — | — |
| 6 | PF-6 launch ci-wait (background) | pending | — | — |
| 7 | PF-7 CI outcome routing (Draft→Ready on green) | pending | 0/2 | — |

## Feature smoke gate   <!-- this FULL shape iff a VERIFICATION-PLAN.md exists; otherwise emit the "## Feature smoke gate (minimal)" section per SMOKE-GATE.md instead — never neither -->

> Gate: /afk:smoke-test   Suite: 11700-payable/verification   Target env: local | staging
> Run (ui-e2e): cd 11700-payable/verification/ui-e2e && npm run smoke   (full incl. env-limited: npm run smoke:all)
> Run (api): cd 11700-payable/verification/api && node --test
> Source: ../VERIFICATION-PLAN.md   Built by: NNNN-smoke-e2e (UI) · NNNN-smoke-api (API) — terminal, blocked by all
> Last run: — (date + target; maintained by /afk:smoke-test)

Run history: <!-- append-only; one line per run, appended by /afk:smoke-test -->

Integrated verification scenarios that decide "feature complete", seeded from
`VERIFICATION-PLAN.md` (one row per scenario, both modalities). A `ui-e2e` row
traces to a PRD User Story and maps to a `Scenario` in the ui-e2e Gherkin catalog;
an `api` row traces to an SDD §3 row / PRD Acceptance Criterion and maps to a
`node:test` in `verification/api`. `/afk:smoke-test` runs them against a running
app and owns the Status column + the header `Feature:` line; the rows themselves
are seeded here. An `env-limited` scenario (e.g. `@sap`, GL-post) carries that
flag from `VERIFICATION-PLAN.md` — the gate excludes it from its green verdict.
`Requires target` likewise carries over verbatim (`any` when the plan names no
target class) — the gate records an incompatible-target row `target-mismatch`,
never `pass`.

| # | Scenario (integrated) | Modality | Traces to | Spec | Requires target | Status |
|---|-----------------------|----------|-----------|------|-----------------|--------|
| 1 | <journey in plain language> | ui-e2e | PRD User Story N | ui-e2e/features/<f>.feature ▸ "<scenario>" | any | pending |
| 2 | <call → asserted envelope> | api | SDD §3 row "..." · PRD AC k | api/<f>.test.mjs ▸ "<test>" | any | pending |
| 3 | <journey, env-gated> | ui-e2e | PRD User Story M | ui-e2e/features/<f>.feature ▸ "<scenario>" | non-secure-context http origin | env-limited |
````

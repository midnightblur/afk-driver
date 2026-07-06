---
name: to-subtasks
description: Slice a PRD (and the accompanying SDD + ADRs, when present) into a local, reviewable execution plan on disk — a plan/ directory with a PLAN.md index (solution map, seam register, live progress tracker) and one NNNN-slug.md contract per subtask. No Jira: subtasks are local artifacts the human reviews and `/afk:execute` works one at a time. Cited mode (PRD + SDD) carries binding design refs, typed Produces/Consumes contracts, and a per-subtask seam list; uncited mode (PRD only) is lighter and human-gated. Every subtask declares tiered verification (static → unit → integration → api → e2e/browser). Use when you have a PRD (and optionally an SDD) and want to plan the work.
---

# afk:to-subtasks — slice a PRD (+ SDD/ADRs) into a local execution plan

Emits a `plan/` directory sibling to the PRD — all on disk, no tracker writes:

```
{TICKET-ID}/
  PRD.md  SDD.md  adr/…
  plan/
    PLAN.md          # index: solution map, seam register, progress tracker
    0001-{slug}.md   # one contract per subtask, in rank order
    0002-{slug}.md
    …
```

`PLAN.md` is the human-facing index (solution map, seams, progress tracker). The per-subtask files are the binding contracts `/afk:execute` parses. This skill (emitter) and `/afk:execute` (parser + progress writer) are lockstep — change a section here, change the parser there, in the same commit.

## Two modes, set by what's on disk

| On disk | Mode | What the plan carries |
|---|---|---|
| PRD **+ SDD + ADRs** | **cited** | binding design refs, typed `## Produces`/`## Consumes` graph, per-subtask `## Seams` (SDD §9b), citation-tagged Acceptance |
| PRD, **no SDD** | **uncited** | PRD-derived Goal/Scope/Acceptance, tiered Verification; no binding contract |

Cited mode is default whenever an `SDD.md` sits next to the PRD. Uncited mode is for small features / bugs / refactors / tooling where an SDD would be overkill — and it is **human-gated**: never decide on your own that the design warrants no SDD (see "Design-doc optionality").

## Arguments

- `prd_path` — the PRD (`.../{TICKET-ID}/PRD.md` or `tasks/{TICKET-ID}/PRD.md`).
- `sdd_path` *(optional)* — defaults to the PRD's sibling `SDD.md`. Present → cited mode.
- `ticket_id` — parent Enhancement/Bug key (e.g. `P2P-1220`), used only to label the plan and the eventual branch. **Nothing is written to Jira.**
- `skip_design_docs` *(optional, default false)* — human override to slice uncited even though an SDD might be warranted.
- `verification_plan_path` *(optional)* — defaults to the PRD's sibling `VERIFICATION-PLAN.md`. Its presence is the smoke-gate trigger (Process step 3).

## Process

1. **Read the sources.** `ctx_read` the PRD (mode=full) and the parent ticket description for context (target branch, components). In cited mode also read `SDD.md` (full) and every `adr/{requirements,design}/NNNN-*.md` (mode=signatures). The set of `(SDD section IDs, §9b seam rows, ADR IDs)` is your **citation pool** — every cited subtask references at least one entry. Also check for a sibling `VERIFICATION-PLAN.md`; if present, read it (full) — its `## UI Journeys` and `## API Scenarios` drive the smoke gate + build subtasks (step 3). Delegate this read set + citation-pool build to an `afk-reader` subagent that returns the pool with `file#anchor` citations — don't pull the full sources into your own context, per `DELEGATION.md` (plugin root).

2. **Refuse-to-slice gate (cited mode).** A plan built on an unstable SDD ships the instability into every subtask. Before slicing, scan the SDD + every ADR and **refuse on any hit** — print offenders, bounce to `/afk:grill-solution` + `/afk:to-sdd`:
   - **Executor-blocking markers** — the canonical blocker set `/afk:to-sdd` Step 7 enforces (`\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`, `\?\?\?`, `<TBD>`/`<TODO>`/`<placeholder>`/`<fill>`/`<\?>`, `\[\?\]`, `_?FILL[_-]?IN_?`, `\(decide later\)`/`\(unresolved\)`/`\(open\)`, unsubstituted template literals like `<TICKET-ID>`/`{Feature Name}`), plus §13 Open-Questions rows marked `Blocks executor? = yes`. Skip code-block contents (real generics `<T>`, nullable `Foo?` are not blockers).
   - **Library-version pins** — every pin the SDD/ADR cites (`Spring Boot 3.2.4`, `Vue 3.4`, …) must match the build manifest (`pom.xml` + BOM / `build.gradle` / `package-lock.json` / `pyproject.toml`). A divergent pin means a fictional API surface — refuse, unless the SDD labelled it `"inherited from {BOM}; not a direct pin"` (the documented escape hatch).

   Run both scans via `afk-reader` — the same child that built step 1's citation pool, or a second one spawned in parallel in the same message — returning pass/fail + cited hits, per `DELEGATION.md` (plugin root).

   Uncited mode skips this gate — the human has accepted the PRD as sole source of truth.

3. **Slice into subtasks.** A good subtask is independently buildable (no dependency on an unlanded sibling except via `## Blocked by`), bounded by a clear Scope (one or two globs), verifiable on its own, sized for one `/afk:execute` sitting (~1 hour). In cited mode, **slice along SDD §8 module boundaries** — one subtask per module's public interface. Splitting a §8 module means the SDD is too coarse: bounce, don't invent a split that contradicts §8. Aim for 4–10 subtasks; more than 10 means the PRD is too big or the slice too fine.

   **Detect the verification plan.** If a `VERIFICATION-PLAN.md` sits next to the PRD (from `/afk:grill-verification` → `/afk:to-verification-plan`), **automatically** append a **terminal** build subtask **per modality the plan carries** — `NNNN-smoke-e2e` for the `## UI Journeys`, `NNNN-smoke-api` for the `## API Scenarios` (omit when that section is the "deferred" placeholder) — each `## Blocked by` **every** other subtask, per the templates in [SMOKE-GATE.md](SMOKE-GATE.md). The specs land as reviewed `/afk:execute` work; the integrated gate that *runs* them is `/afk:smoke-test`, after these subtasks are `done` (not part of this skill). No `VERIFICATION-PLAN.md` → no build subtasks, but the plan still gets the **minimal** gate section per [SMOKE-GATE.md](SMOKE-GATE.md) — a plan never ships gate-less.

   **Carry the accepted staples.** Each staple the PRD accepted (traceable to `{service}/STAPLES.md`) is an obligation on this feature, not a suggestion — turn it into Acceptance bullets on the owning subtask, and in cited mode a `## Seams` row wherever the SDD named one (the staple's registry **Reference** is the exemplar to copy). A staple the PRD accepted but that appears in no subtask is a slice gap — fix the slice, don't drop it.

   **Always seed the harness-sync subtask.** For every feature, append a single terminal `NNNN-sync-harness` documentation subtask, `## Blocked by` **every** other subtask, per [HARNESS-SYNC.md](HARNESS-SYNC.md). It keeps the CLAUDE.md harness current so the next agent discovers the shipped feature, and makes the **final** staples-registry call (register a candidate new staple / advance an existing staple's Reference to this feature); it delegates the write to `/afk:claude-md`. Emit it unconditionally — it is not gated on any artifact.

4. **Write each subtask file** `plan/NNNN-{slug}.md` in rank order, using the contract below. `NNNN` is the zero-padded rank; `{slug}` a short kebab title. The subtask's **id** is `NNNN-{slug}` — what `## Blocked by`, `## Consumes`, and the tracker reference (no Jira keys anywhere).

5. **Write `PLAN.md`** (the index) using the PLAN template below: the solution map, the seam register (cited), and the progress tracker seeded with every subtask at status `pending`. `/afk:execute` owns the tracker's status column from here on. Also seed `plan/JOURNAL.md` with its header line per [JOURNAL-FORMAT.md](JOURNAL-FORMAT.md) — the append-only event log the execution skills write to.

6. **Validate the slice** (see "Validation"). Cited mode runs the contract-graph + anchor-quality + Acceptance-citation + seam-coverage checks; all must pass before the plan is considered emitted. Uncited mode runs only the Verification-tier and Scope sanity checks.

7. **Update the ticket index.** Upsert this skill's row(s) in the ticket folder's `INDEX.md` (the plan row: subtask count, mode, pointer to `plan/PLAN.md` for live status) per `skills/afk/to-prd/INDEX-FORMAT.md`. Create the file per that format if it doesn't exist yet.

8. **Output.** Print the plan path and a one-line-per-subtask summary (id, title, tiers, seams touched, blocked-by) so the human can review before any execution. Flag every seam-touching subtask explicitly — those rows are worth a careful human read. Also state in one plain-language sentence per subtask *why the slice is cut there* (the boundary it follows) — the slicing rationale otherwise lives nowhere.

## Subtask contract (`plan/NNNN-{slug}.md`)

Write each subtask file using the contract template in [SUBTASK-CONTRACT.md](SUBTASK-CONTRACT.md) — `/afk:execute` parses its section headings exactly, so keep them verbatim.

### Choosing verification tiers

Pick the tiers the change actually demands — don't pad, don't under-cover:

- **static** is always present: compiles/lints and greps the `## Produces` anchors so the declared symbols exist. A pure rename / config / docs subtask may be static-only.
- **unit** whenever the subtask adds behavior worth asserting in isolation.
- **integration** for cross-module wiring, persistence, or framework-pickup (e.g. the liquibase-hibernate7 entity-pickup check for a JPA entity, or a §9b seam-test asserting on the framework's real serialized/generated output).
- **api** when the subtask's contract is an **endpoint** an API/MCP caller hits directly — assert the real response envelope (success **and** error/empty) and the below-the-UI authz guard (no-token / bad-token / role-scoping), over REST with no browser. Author it as a `node:test` `*.test.mjs` in `verification/api/` (using `../core` for auth/base-URL/poll), per `11700-payable/verification/api/AUTHORING.md` — or run a disposable probe that `import`s `../core` for an inner-loop check. A subtask exposing a protected endpoint must carry this tier; the UI test can't see the raw envelope or the guard a UI caller never trips.
- **e2e/browser** for user-visible flows — a Cucumber+Playwright `Scenario` in `11700-payable/verification/ui-e2e` that drives the actual UI. A backend-only subtask omits this; a UI subtask must not.

A subtask that **implements** a §9b seam must carry the seam's test as a Verification row (unit or integration tier) asserting on the framework's real output, not our DTO — it's the only test that covers the boundary.

### Feature smoke gate (driven by `VERIFICATION-PLAN.md`)

Seed the gate per [SMOKE-GATE.md](SMOKE-GATE.md) — read it before step 3. A `VERIFICATION-PLAN.md` drives the full gate + per-modality build subtasks; its absence drives the minimal gate (no build subtasks). Every plan gets exactly one of the two.

### Harness sync (always)

Every plan ends with a terminal `NNNN-sync-harness` documentation subtask that syncs the CLAUDE.md harness for the shipped feature (delegating the write to `/afk:claude-md`), `## Blocked by` every other subtask. Emit it for every feature. See [HARNESS-SYNC.md](HARNESS-SYNC.md).

## PLAN.md (the index)

Write `PLAN.md` (header, solution map, seam register, progress tracker, and the feature smoke gate — full or minimal per [SMOKE-GATE.md](SMOKE-GATE.md)) using the template in [PLAN-TEMPLATE.md](PLAN-TEMPLATE.md).

## Validation

Run before declaring the plan emitted. **Cited mode** runs (a)–(g); **uncited mode** runs (e), (f), and (g). Check **(g)** always runs — it validates whichever gate shape the plan carries.

Run the detailed checks (a)–(g) in [VALIDATION.md](VALIDATION.md).

## Hard rules

- **No tracker writes.** This skill only writes files under `plan/`. It creates no Jira issue, sets no label, opens no branch. (`/afk:execute` self-creates the branch.)
- **The plan round-trips.** `/afk:execute` parses these exact section headings; if you add/rename/reorder a section, update the `/afk:execute` parser in the same commit (lockstep).
- **Don't fabricate Acceptance.** Every bullet traces to the PRD or (cited) the SDD/an ADR; cited bullets carry a resolving citation tag (validation (c)).
- **Don't invent a public interface.** Cited interfaces come from SDD §8 verbatim; a missing one is a design gap → bounce to `/afk:grill-solution`.
- **Verification is part of the plan, not an afterthought.** Every subtask declares the tiers it needs and the exact commands; `static` is mandatory, and the highest tier the change demands (up to e2e/browser) must be present.
- **Seam-implementing subtasks carry the seam-test** as a Verification row asserting on the framework's real output, not our DTO.
- **JPA-entity subtasks verify liquibase-hibernate7 pickup** (core-services Java only): a `## Produces` `.java` file with `@Entity` / `@MappedSuperclass` / `@Embeddable` must list an integration-tier row running the documented pickup check (`mvn -pl {module} compile liquibase:diff …` then grep the diff for the entity/column) — not just a unit test against the entity in isolation.
- **Uncited mode is human-approved per ticket.** Never decide on your own that the design needs no SDD.
- **The smoke gate's shape is artifact-driven; its presence is not optional.** A `VERIFICATION-PLAN.md` drives the full gate (never half-emit — Process step 3 / [SMOKE-GATE.md](SMOKE-GATE.md) define the per-modality rule; never invent scenarios without the plan); its absence drives the minimal gate. This skill only seeds + slices; running the gate is `/afk:smoke-test`'s job.
- **The harness-sync subtask is always emitted.** Every plan ends with a terminal `NNNN-sync-harness` doc subtask (per [HARNESS-SYNC.md](HARNESS-SYNC.md)) blocked by every other subtask. It delegates the write to `/afk:claude-md`; this skill only seeds it. Never omit it.

## Design-doc optionality

Not every ticket warrants an SDD; the human decides. New complex feature (≥2 modules / new pattern / non-trivial txn or data) → SDD **required**, refuse to slice cited-less unless `skip_design_docs=true`. Small enhancement / bug fix / refactor / tooling → uncited is fine. When no `SDD.md` is on disk and `skip_design_docs` is unset, **ask** before proceeding:

> *No SDD found at `{path}`. Slice from the PRD alone (uncited), or pause and run
> `/afk:grill-solution` + `/afk:to-sdd` first?*

Record the human's choice in the output so it's auditable.

## Next

The plan is on disk. Review `PLAN.md` — especially the seam register and any seam-touching subtasks. Then work the subtasks one at a time, in rank order (respecting `## Blocked by`): in a session on the parent branch, run **`/afk:execute {NNNN-slug}`** for each. Each run advances that subtask's status in the tracker, drives it through design → develop → verify (every declared tier green), commits, pushes, and updates the Draft MR — then stops at CR/Merge for you.

If a `VERIFICATION-PLAN.md` drove a `## Feature smoke gate`, the terminal build subtasks author their specs last (each blocked by everything). Once **every** subtask is `done`, run **`/afk:smoke-test`** as the feature-completion gate: it runs the integrated scenarios against a running app and, only on green, stamps `Feature: complete` in PLAN.md. That suite then serves CI / scheduled / manual sanity runs.

The plan's dead-last subtask is always `NNNN-sync-harness`: run it after the feature has landed to sync the CLAUDE.md harness so the next agent discovers the feature.

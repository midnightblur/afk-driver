---
name: to-sdd
description: Turn the current conversation context into a Software Design Document (SDD) plus per-decision ADRs and publish them next to the PRD. SDD sections are organized top-down by architecture layer (L1 system topology -> L8 tactical patterns) and EVERY layer ships with the appropriate visualization (Mermaid diagram, table, or chart) so reviewers can grasp the design at a glance. Use after `/afk:grill-solution` (or equivalent design conversation) when the user wants to materialize the design as artifacts. Does NOT interview — synthesizes what is already known.
---

This skill takes the current conversation context, the PRD, and the codebase understanding, and produces:

1. A single `SDD.md` organized layer-by-layer (L1 -> L8), with **mandatory visualizations** per section.
2. One design ADR per non-trivial decision under `adr/design/NNNN-kebab-title.md`, each with at least one diagram or table.

Do NOT interview the user — just synthesize what you already know. If a critical-logic concern is unresolved, STOP and tell the user to run `/afk:grill-solution` first; do not invent decisions.

## Process

1. **Locate the PRD.** Default path: `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md` (service-scoped) or `tasks/{TICKET-ID}/PRD.md` (cross-cutting tooling). Read it with `ctx_read` (mode=full). The SDD lands in the SAME folder as the PRD; design ADRs land in its `adr/design/` subfolder.

2. **Re-read the ticket's existing ADRs** — the design ADRs in the sibling `adr/design/` (to avoid contradicting prior design decisions) and the requirement ADRs in `adr/requirements/` (behavioural constraints you must honour, owned by `/afk:to-prd`). Do not read or write repo-wide `docs/adr/` — all ADRs are ticket-local. If you must reverse a prior **design** ADR, write a new one that explicitly **Supersedes** it and list it in §13 Reversed Decisions. Never edit an `adr/requirements/` ADR — if a requirement decision blocks the design, that's a `design-conflict` to route back, not a thing to overwrite here.

3. **Use the project's domain glossary.** Match the vocabulary used in the PRD and the relevant `GLOSSARY.md` (if present — start from the root `GLOSSARY-MAP.md` to find the owning service's glossary, per `/afk:grill-requirements`).

4. **Apply the triviality cutoff.** ADR-worthy = (non-obvious for the stack) AND (≥2 real alternatives) AND (reversal is expensive). Skip ADRs for "we use HTTPS / UTF-8 / JSON".

5. **For layers with nothing project-specific to say, write one line: "Inherited / default."** Do NOT delete the section — its presence proves the layer was considered.

6. **Write SDD.md using the template below.** Each section's `Required visuals:` annotation is binding — if you cannot produce the visual, the section is not done.

7. **Refuse-to-publish gate.** Before writing `SDD.md` or any ADR, scan the
   draft (prose / table cells / diagram labels — NOT fenced real code) for
   executor-blocking markers. If any appear, do NOT write: list each
   offender with its §-location verbatim (`§4 L3 — row "events table"` reads
   `Retention: TBD`) and bounce to `/afk:grill-solution`.

   Blocker tokens (this is the canonical set; `/afk:to-subtasks`'s
   refuse-to-slice gate re-scans it): `\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`, `\?\?\?`,
   `<TBD>` / `<TODO>` / `<placeholder>` / `<fill>` / `<\?>`, `\[\?\]`,
   `_?FILL[_-]?IN_?`, `\(decide later\)` / `\(unresolved\)` / `\(open\)`,
   and unsubstituted template literals (`<TICKET-ID>`, `<NNNN>`,
   `<service>`, `{Feature Name}`). Real generics (`<T>`), optional-type
   markers (`Foo?`), and a stray `?` in a signature are NOT blockers.

   Also scan §13: a row with `Blocks executor? = yes` in L2-L7 is a blocker
   (L1/L8 may pass if scoped). Don't demote a blocker to a §13 row to sneak
   it past the gate — that defeats the purpose.

8. **Library-version pin cross-check.** Any version pin the SDD/ADR names
   (Spring Boot, Hibernate, Vue, axios, … — anything `\d+\.\d+`) is verified
   against the build manifest before writing. The Grounding rule catches a
   library's *existence*; this catches a fictional *version* of a real
   library, which silently poisons every behaviour assumption downstream.

   | Stack | Manifest |
   |-------|----------|
   | Maven | `pom.xml` (+ parent / BOM POMs) |
   | Gradle | `build.gradle(.kts)`, `gradle.properties`, `libs.versions.toml` |
   | Node | `package.json` + `package-lock.json` (resolved wins) |
   | Python | `pyproject.toml`, `requirements.txt`, `Pipfile.lock` |

   - Quote the resolved pin with its source line (`Spring Boot 3.2.4 —
     pom.xml:42`) so drift shows in `git diff`.
   - Manifest differs from the draft → STOP and bounce; don't silently
     match the draft to the manifest (intent may be "we're upgrading,"
     which changes the manifest first).
   - Not directly pinned (transitive / BOM-managed) → label
     `"inherited from {BOM}; not a direct pin"`; never hard-code a
     transitive version as if pinned.
   - A behaviour claim gated on a version threshold ("X since vN",
     "removed in vN+1") → verify against a primary source (release notes /
     JEP / RFC), cite the identifier inline, then write the decision.

   Refuse-to-publish (same as Step 7) if any pin lacks a manifest citation
   or contradicts it.

8b. **Framework-seam cross-check.** Step 8 verifies the version pin; this
   verifies the *behavior* at that pin. For each §9b framework row, confirm
   what it does to our value (and which annotations it honors) against the
   framework source / docs (`get-api-docs` where available), not memory.
   Unverifiable → label `unverified premise`; if the design depends on it,
   it's a §13 blocker → bounce to `/afk:grill-solution`. Every framework row
   names a seam-test or the seam isn't done.

9. **Emit design ADRs** into the `adr/design/` subfolder. Numbering is local
   to `adr/design/` (start at `0001`), independent of the `adr/requirements/`
   numbering. ADRs are subject to the same Step 7 refuse-to-publish gate AND
   the Step 8 library-version cross-check — apply both before writing any
   `adr/design/NNNN-*.md` file.

10. **Splice a `## SDD` pointer into the parent Jira ticket description.** Never modify `## Implementation Notes (auto-maintained)`.

## Visualization rules

**Every non-trivial layer ships with the visual that carries its signal** —
a reviewer should grasp the design from shape, not prose. Skip the visual
only where the layer is one-line "inherited/default."

**Toolkit (use Mermaid for diagrams — never ASCII):**

| Diagram type | Mermaid block | Best for |
|--------------|---------------|----------|
| Context / topology | `flowchart` or `C4Context` | L1 system, deployment |
| Service interaction | `flowchart LR` | L2 service map |
| Sequence (cross-service / cross-aggregate flow) | `sequenceDiagram` | L2 contract calls, L6 use-case flows, sagas |
| Entity-relation | `erDiagram` | L3 data, L5 domain |
| State machine | `stateDiagram-v2` | L5 aggregate lifecycle, L6 saga state |
| Class / pattern shape | `classDiagram` | L8 patterns (interfaces + impls + relations) |
| Module dependency DAG | `flowchart TB` | L7 modules |
| Quadrant (trade-off) | `quadrantChart` | ADR alternative comparison |
| Pie / mini-stat | `pie` | NFR allocation, latency budget split |
| Timeline | `timeline` | rollout / migration phases |
| Tables | GitHub-flavored MD | NFRs, retry budgets, failure matrix, schema columns |

**Diagram quality rules:**
- Label every node and edge. Unlabeled arrows = rejected.
- Keep one diagram to one concern. If a diagram has >12 nodes, split it.
- Caption every diagram with one sentence stating what to take away.
- Tables must have units in the header (`Latency p95 (ms)`, not `Latency p95`).
- Numbers, not adjectives. "p95 < 200 ms" not "fast".

## SDD template

<sdd-template>

# SDD — {Feature Name}

> Parent PRD: `{relative path to PRD.md}`
> Status: Draft | Approved | Superseded
> Last updated: {YYYY-MM-DD}

## §0 Binding Contract

This SDD and its accepted ADRs are **binding** on implementing agents and reviewers.

**Required visual:** the lock-vs-latitude table below.

| Aspect | Locked by SDD/ADR | Executor latitude |
|--------|-------------------|-------------------|
| Pattern choice | ✅ | ❌ |
| Module public interface | ✅ | ❌ |
| API contract / schema | ✅ | ❌ |
| Aggregate boundary | ✅ | ❌ |
| Txn / idempotency strategy | ✅ | ❌ |
| External-seam contract (§9b: framework I/O shape, field source-of-truth, enforcement point, failure surface) | ✅ | ❌ |
| File / package layout *within* a named module | ❌ | ✅ |
| Private helper extraction | ❌ | ✅ |
| Internal naming, control flow | ❌ | ✅ |
| Test fixture structure | ❌ | ✅ |

**Conflict procedure.** If an executor finds a binding decision wrong / infeasible / contradicting reality, exit the subtask with `design_conflict` status quoting the SDD section + the conflict. Route back to `/afk:grill-solution` for a new ADR (Status: Accepted, Supersedes: NNNN). Do not override silently.

## §1 Context Summary

One paragraph. WHY this design exists. Reference the PRD for the WHAT.

**Required visual:** none (orientation only).

---

## §2 L1 — System Topology

Monolith vs microservices, sync vs event-driven backbone, multi-tenancy, deployment model. Almost always one line: "Inherited from {existing system}."

**Required visual:** if the feature touches more than one deployable unit, a `C4Context` or `flowchart` showing where this feature lives in the wider system. Otherwise: one-line statement of inheritance.

## §3 L2 — Service Boundaries & Integration

Which service owns what. Where the seam falls. Integration style. Versioning posture.

**Visuals (those that carry signal for this feature):**

1. `flowchart LR` — services as nodes, edges labeled with integration style (REST / gRPC / async-event / shared DB) + the message name.
2. `sequenceDiagram` — one per non-trivial cross-service interaction.
3. **API contract table** — surface, method, request shape ref, response shape ref, error codes, version. Cite OpenAPI / proto file paths; do not inline schemas that will rot.

## §4 L3 — Data Architecture

For each piece of state.

**Visuals (those that carry signal for this feature):**

1. **State table** — one row per piece of state:

   | State | Datastore | Partitioning | Replication | Retention | Schema-evolution policy | PII? |
   |-------|-----------|--------------|-------------|-----------|--------------------------|------|

2. `erDiagram` — cross-state relations (FK, reference-by-id, denormalization edges). Even single-table designs benefit from one entity box.
3. **Cache topology diagram** (`flowchart`) if a cache is in play, showing read-through / write-behind / TTL per layer.

## §5 L4 — Cross-Cutting & Quality Attributes

**Required visuals (per concern present):**

| Concern | Required visual |
|---------|-----------------|
| AuthN flow | `sequenceDiagram` showing token issuance + propagation |
| AuthZ rules | table — resource × principal-attribute × allowed-action |
| Idempotency | table — surface, key shape, dedup window, side-effect ledger |
| Retry + timeout | table — call, attempts, backoff (numbers), timeout (ms) |
| Rate limit | table — surface, limit, window, enforcer |
| Sync vs async | `sequenceDiagram` per long-running op + a one-row table per op with the latency budget that drove the choice |
| Feature flags | table — flag key, default, rollout plan, cleanup date |
| Observability | table — signal (log/metric/trace/alert), what it detects (cite §7 row) |

## §6 L5 — Domain Model

**Visuals (those that carry signal for this feature):**

1. `erDiagram` — aggregates, entities, value objects, relations. Mark aggregate roots.
2. **Invariants table** — invariant text, owner aggregate, guardian method.
3. `stateDiagram-v2` — per aggregate with non-trivial lifecycle. Terminal states marked.
4. **Domain events table** — event name, emitter aggregate, consumers, payload schema ref.

## §7 L6 — Process & Coordination

For each top use case from the PRD.

**Visuals (those that carry signal for this feature):**

1. `sequenceDiagram` — actors + aggregates + external services as participants. Mark txn boundaries with `Note over ...: TXN START / COMMIT`.
2. **Use-case detail table** — trigger, txn boundary strategy (single-txn / saga / outbox / 2PC / accept-eventual), consistency model per read path, concurrency control.
3. `stateDiagram-v2` — for each saga / outbox flow.
4. **Failure & recovery matrix** (consolidated for the feature):

   | Failure point | Detection signal | Automatic recovery | Manual recovery | Owner |
   |---------------|------------------|--------------------|-----------------|-------|

## §8 L7 — Module Decomposition

**Visuals (those that carry signal for this feature):**

1. `flowchart TB` — module-dependency DAG. Edges point from dependent to dependency. **Cycles are a bug.** Group by hex / onion / clean ring with `subgraph`.
2. **Module table** — module, purpose (one line), public interface (signature-level), depends on, owner aggregate from §6.

## §9 L8 — Tactical Patterns

**Required visuals (per pattern):**

1. **Patterns Applied table** — concern, pattern, ADR file:

   | Concern | Pattern | ADR |
   |---------|---------|-----|

2. `classDiagram` — interface + impls + how the pattern is wired (registry, factory, DI scope). One per non-trivial pattern.

## §9b External Seams & Failure Affordance

The seams where our code meets things we don't control — synthesized from
the External-seam rule's four checks in `/afk:grill-solution`. Capture, in
whatever table shape fits: each framework boundary (what it does to our
value at the pinned version + the **seam-test** that asserts on its real
output), each field contract's canonical source of truth, each relied-on
invariant's enforcement point (proven for the new caller), and the failure
affordance per violation class. If the feature has no external seam, say
so in one line rather than deleting the section.

**Required visual:** a table covering the seams present. The framework
rows' **seam-test** entry is mandatory — a test on the framework's real
output (serialized result / generated schema / surfaced error), not our
objects; that name is what `/afk:to-subtasks` cites in `## Acceptance`. E.g.:

| Boundary | Framework @ pin | What it does to our value | Failure surface | Seam-test |
|----------|-----------------|---------------------------|-----------------|-----------|

---

## §10 NFRs

**Required visual:** quantified table. Numbers, not adjectives.

| Concern | Target | Measurement | Owner |
|---------|--------|-------------|-------|
| Latency p95 (ms) | < 200 | server-side trace | service-X team |
| Throughput (rps) | ≥ 500 | load test Y | ... |
| Availability (%) | 99.9 | SLO dashboard Z | ... |

Add a `pie` chart for any concern with a budget split worth visualizing (e.g. p95 latency budget across hops).

## §11 Out of Scope

Bullet list. Cite PRD's Out of Scope and add design-level exclusions.

## §12 Reversed Decisions

**Required visual:** table.

| Prior ADR | Superseded by | Reason |
|-----------|---------------|--------|

## §13 Open Questions

**Required visual:** table.

| Question | Layer (L1-L8) | Blocks executor? | Owner | Target resolve date |
|----------|---------------|------------------|-------|---------------------|

If any row has `Blocks executor? = yes` in L2-L7, the design is NOT publishable — bounce back to `/afk:grill-solution`. L1 / L8 open questions may pass if scoped.

</sdd-template>

## ADR template

<adr-template>

# ADR-NNNN — {Decision Title}

> Status: Proposed | Accepted | Superseded by ADR-MMMM
> Date: {YYYY-MM-DD}
> Layer: L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8
> Context ticket: {TICKET-ID}

## Context

What forces are at play. Cite the SDD section.

## Decision

The chosen approach in one paragraph.

**Required visual:** one diagram showing the chosen shape (`classDiagram` for tactical patterns, `sequenceDiagram` for protocol decisions, `flowchart` for topology, `erDiagram` for data).

## Alternatives Considered

At least two. **Required visual:** comparison table OR `quadrantChart` plotting alternatives on two axes that mattered for THIS context.

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|

## Consequences

- **Positive** — what this enables.
- **Negative** — what this costs.
- **Follow-ups** — work this creates that is NOT in scope.

</adr-template>

## Hard rules

- **The Visualization rules are binding** — Mermaid only (never ASCII),
  every non-trivial layer carries its signal visual, labeled + captioned,
  tables with units, numbers not adjectives.
- **Do not invent decisions.** A section that can't be filled goes to §13
  and bounces to `/afk:grill-solution`; the Step 7 gate enforces this and is
  non-negotiable — don't paper over it by demoting a blocker to a §13 row.
- **No code or file paths in SDD/ADRs.** They rot.
- **Every ADR weighs ≥2 alternatives** and declares its layer (L1-L8).
- **§9b seams are binding.** Every framework seam names a seam-test that
  asserts on the framework's real output (not our objects) — that's the gap
  that makes green unit tests lie; every field contract cites its canonical
  source; every relied-on invariant proves it holds for the new caller. A
  seam that can't satisfy these is a §13 blocker → bounce to `/afk:grill-solution`.
- **Never modify** `## Implementation Notes (auto-maintained)` in the parent Jira ticket.

## AFK adaptation (core-services)

When the SDD belongs to an Enhancement / Bug in the AFK workflow:

- **File location.** `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md` and `.../adr/design/NNNN-*.md`. Service is derived from the Jira project key per the project's mapping (e.g. `P2P` → `11700-payable`).
- **Parent ticket splice.** Add or update a `## SDD` section in the Enhancement / Bug description:

  ```
  ## SDD

  Architecture lives in the repo at `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md`
  (this branch). Design ADRs in `.../adr/design/`.
  ```

  Leave `## PRD` and `## Implementation Notes (auto-maintained)` untouched.

- **Hand-off.** Each downstream subtask MUST cite the SDD section(s) and ADR(s) that constrain it, so the implementing agent has a binding contract — not just a feature ask.

## Next

After the SDD + ADRs land, you have a few choices:

- **Stakeholder review upcoming?** Run **`/afk:to-design-brief`** to synthesize a
  tight 1-2 page digest (one money-shot diagram + 5-10 row decision table +
  stakeholder-impact table). Strict synthesis — no new decisions.
- **End-user journeys need the settled solution?** Run **`/afk:grill-e2e`**
  *(optional)* to design the feature's e2e journeys against the now-settled
  technical design, emitting `E2E-PLAN.md`. (If the journeys were already clear
  from the PRD, this was likely done after `/afk:to-prd`.) Its plan makes
  `/afk:to-subtasks` add the feature smoke-test gate.
- **Slicing time?** Run **`/afk:to-subtasks`** to slice the PRD + SDD + ADRs
  into a local execution plan (`plan/PLAN.md` + per-subtask contracts) with
  typed `## Produces` / `## Consumes` and a per-subtask `## Seams` list. The
  slicing-time refuse gate re-runs the §13 / library-version checks defensively
  in case the SDD was hand-edited after this skill ran.

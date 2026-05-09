---
name: to-sdd
description: Turn the current conversation context into a Software Design Document (SDD) plus per-decision ADRs and publish them next to the PRD. SDD sections are organized top-down by architecture layer (L1 system topology -> L8 tactical patterns) and EVERY layer ships with the appropriate visualization (Mermaid diagram, table, or chart) so reviewers can grasp the design at a glance. Use after `/afk:architect-grill` (or equivalent design conversation) when the user wants to materialize the design as artifacts. Does NOT interview — synthesizes what is already known.
---

This skill takes the current conversation context, the PRD, and the codebase understanding, and produces:

1. A single `SDD.md` organized layer-by-layer (L1 -> L8), with **mandatory visualizations** per section.
2. One ADR per non-trivial decision under `adr/NNNN-kebab-title.md`, each with at least one diagram or table.

Do NOT interview the user — just synthesize what you already know. If a critical-logic concern is unresolved, STOP and tell the user to run `/afk:architect-grill` first; do not invent decisions.

## Process

1. **Locate the PRD.** Default path: `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md` (service-scoped) or `tasks/{TICKET-ID}/PRD.md` (cross-cutting tooling). Read it with `ctx_read` (mode=full). The SDD and ADRs land in the SAME folder as the PRD.

2. **Re-read existing ADRs in the area** — repo-wide `docs/adr/` and any sibling `adr/` next to the PRD. Do not contradict prior decisions silently; if you must, write a new ADR that explicitly **Supersedes** the old one and list it in §13 Reversed Decisions.

3. **Use the project's domain glossary.** Match the vocabulary used in the PRD and `CONTEXT.md` (if present).

4. **Apply the triviality cutoff.** ADR-worthy = (non-obvious for the stack) AND (≥2 real alternatives) AND (reversal is expensive). Skip ADRs for "we use HTTPS / UTF-8 / JSON".

5. **For layers with nothing project-specific to say, write one line: "Inherited / default."** Do NOT delete the section — its presence proves the layer was considered.

6. **Write SDD.md using the template below.** Each section's `Required visuals:` annotation is binding — if you cannot produce the visual, the section is not done.

7. **Refuse-to-publish gate (executor-blocking markers).** Before writing
   `SDD.md` to disk and before emitting any ADR, scan the full draft text
   for any of the patterns below. **If any appear in normal prose / table
   cells / diagram labels (NOT inside fenced code blocks containing real
   code), do NOT write the file.** Quote each occurrence with its
   section/anchor and bounce back to `/afk:architect-grill` to resolve the gap;
   re-run this skill afterwards.

   Hard-blocker patterns (case-sensitive unless noted):

   | Pattern | Notes |
   |---------|-------|
   | `\bTBD\b` | the canonical "to be decided" marker |
   | `\bTODO\b` | same — design is not done |
   | `\bFIXME\b` | known broken; not publishable |
   | `\bXXX\b` | placeholder convention |
   | `\?\?\?` | three or more `?` in a row outside code |
   | `<TBD>`, `<TODO>`, `<placeholder>`, `<fill>`, `<\?>` | angle-bracket placeholders |
   | `\[\?\]` | bracket-question placeholder |
   | `_?FILL[_-]?IN_?` | `FILL_IN` / `FILL-IN` / `_FILL_IN_` |
   | `\(decide later\)`, `\(unresolved\)`, `\(open\)` | parenthetical placeholders |
   | template literals like `<TICKET-ID>`, `<NNNN>`, `<service>`, `{Feature Name}` left unsubstituted | the synthesizer must fill these in |

   Generics like `<T>`, `<E extends X>`, optional type markers (`Foo?`),
   and emoji bullets are NOT blockers — only the patterns above. Be
   precise: a stray `?` inside a method signature is fine; `???` as a
   prose placeholder is not.

   **Also scan §13 Open Questions explicitly.** If any row has
   `Blocks executor? = yes` AND `Layer ∈ {L2, L3, L4, L5, L6, L7}`, the
   design is NOT publishable — same bounce. L1 / L8 open questions may
   pass if scoped (a topology question that ops will resolve, or a
   tactical-pattern decision that genuinely is executor latitude).

   When refusing, list every offender with its location verbatim
   (`§4 L3 Data — row "events table"` reads `Retention: TBD`) so the user
   knows exactly what `/afk:architect-grill` needs to nail down. Do NOT
   silently demote a blocker to a §13 row to make the gate pass — that
   defeats the purpose.

8. **Library-version pin cross-check.** Whenever the SDD draft (or any
   accompanying ADR) names a library version pin — Spring Boot, Hibernate,
   Vue, Quasar, Pinia, axios, Kafka client, ActiveMQ, vue-router,
   vue-i18n, @casl/ability, ts-jest, anything carrying a `\d+\.\d+`
   shape — verify the pin against the actual build manifest BEFORE
   writing the file. The Grounding rule (architect-grill) catches
   library-**existence** claims at interview time; this step catches
   library-**version** claims at synthesis time, because a fictional
   version of a real library is internally consistent with "we use
   {real lib}" — and poisons every behaviour assumption (API shape,
   deprecation, idempotency contract, default config) that flows from
   the SDD into ADRs and into SubTask Produces / Acceptance.

   How to verify, by stack:

   | Stack | Manifest |
   |-------|----------|
   | Maven Java/Kotlin | `pom.xml` (and the parent / BOM POMs it imports) |
   | Gradle | `build.gradle` / `build.gradle.kts`, `gradle.properties`, `libs.versions.toml` |
   | Node (Quasar / Vue / generic) | `package.json` `dependencies` + `package-lock.json` (resolved versions win over caret ranges) |
   | Python | `pyproject.toml`, `requirements.txt`, `Pipfile.lock` |

   For each version pin you intend to write:

   - `ctx_search` the manifest for the artifact (groupId/artifactId,
     package name, etc.) and quote the resolved pin alongside the
     citation: `"Spring Boot 3.2.4 (pinned in pom.xml line 42 via
     spring-boot-starter-parent)"`. The line citation makes drift
     visible in `git diff` when the pin moves.
   - If the manifest pin **differs** from what you were about to write,
     the design rests on a fictional version — STOP, surface the gap,
     and bounce back to the user. Do not silently change the draft to
     match the manifest; the user's stated intent might be "we are
     upgrading", in which case the manifest needs to change first.
   - If the manifest **doesn't pin** the artifact directly (transitive
     dep, BOM-managed, version inherited from parent POM /
     `dependencyManagement`), say so explicitly in the SDD:
     `"version inherited from {BOM-coordinates}; not a direct pin"`.
     Do **not** hard-code a transitive version into the SDD as if it
     were directly pinned — that's how upgrade work loses its actual
     constraint.
   - For runtime-only / system-level versions (JDK, Node, MySQL, OS) —
     check the equivalent runtime manifest (`pom.xml` `<java.version>`,
     `package.json` `engines`, `Dockerfile`, `.tool-versions`,
     `.nvmrc`). If unavailable from the repo, label as "**unverified
     premise** per user assertion" rather than pretending to verify.

   For runtime / SDK behaviour claims that depend on a version
   threshold ("X works since version N", "Y was removed in N+1"), this
   step is mandatory: verify against a primary source (release notes /
   JEP / RFC / changelog), cite the identifier inline, and only then
   write the dependent design decision. A wrong version threshold can
   invalidate every L4-L8 decision built on top.

   Refuse-to-publish triggers if any version pin in the draft would be
   written without a manifest citation OR with a citation that
   contradicts the manifest. Same outcome as Step 7: do not write,
   surface offenders verbatim, bounce back.

9. **Emit ADRs.** Numbering is local to the ticket folder (start at `0001`).
   ADRs are subject to the same Step 7 refuse-to-publish gate AND the
   Step 8 library-version cross-check — apply both before writing any
   `adr/NNNN-*.md` file.

10. **Splice a `## SDD` pointer into the parent Jira ticket description.** Never modify `## Implementation Notes (auto-maintained)`.

## Visualization rules

A document is only as useful as it is understandable. **Every layer ships with a visual.** Prose alone is rejected.

**Why visuals are mandatory:**
- Reviewers scan diagrams in seconds; prose takes minutes.
- Stakeholders absorb structure from shape, not sentences.
- Executors locate the binding constraint by pointing at a node, not by re-reading prose.

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
| File / package layout *within* a named module | ❌ | ✅ |
| Private helper extraction | ❌ | ✅ |
| Internal naming, control flow | ❌ | ✅ |
| Test fixture structure | ❌ | ✅ |

**Conflict procedure.** If an executor finds a binding decision wrong / infeasible / contradicting reality, exit the SubTask with `design-conflict` status quoting the SDD section + the conflict. Route back to `/afk:architect-grill` for a new ADR (Status: Accepted, Supersedes: NNNN). Do not override silently.

## §1 Context Summary

One paragraph. WHY this design exists. Reference the PRD for the WHAT.

**Required visual:** none (orientation only).

---

## §2 L1 — System Topology

Monolith vs microservices, sync vs event-driven backbone, multi-tenancy, deployment model. Almost always one line: "Inherited from {existing system}."

**Required visual:** if the feature touches more than one deployable unit, a `C4Context` or `flowchart` showing where this feature lives in the wider system. Otherwise: one-line statement of inheritance.

## §3 L2 — Service Boundaries & Integration

Which service owns what. Where the seam falls. Integration style. Versioning posture.

**Required visuals (all of):**

1. `flowchart LR` — services as nodes, edges labeled with integration style (REST / gRPC / async-event / shared DB) + the message name.
2. `sequenceDiagram` — one per non-trivial cross-service interaction.
3. **API contract table** — surface, method, request shape ref, response shape ref, error codes, version. Cite OpenAPI / proto file paths; do not inline schemas that will rot.

## §4 L3 — Data Architecture

For each piece of state.

**Required visuals (all of):**

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

**Required visuals (all of):**

1. `erDiagram` — aggregates, entities, value objects, relations. Mark aggregate roots.
2. **Invariants table** — invariant text, owner aggregate, guardian method.
3. `stateDiagram-v2` — per aggregate with non-trivial lifecycle. Terminal states marked.
4. **Domain events table** — event name, emitter aggregate, consumers, payload schema ref.

## §7 L6 — Process & Coordination

For each top use case from the PRD.

**Required visuals (all of):**

1. `sequenceDiagram` — actors + aggregates + external services as participants. Mark txn boundaries with `Note over ...: TXN START / COMMIT`.
2. **Use-case detail table** — trigger, txn boundary strategy (single-txn / saga / outbox / 2PC / accept-eventual), consistency model per read path, concurrency control.
3. `stateDiagram-v2` — for each saga / outbox flow.
4. **Failure & recovery matrix** (consolidated for the feature):

   | Failure point | Detection signal | Automatic recovery | Manual recovery | Owner |
   |---------------|------------------|--------------------|-----------------|-------|

## §8 L7 — Module Decomposition

**Required visuals (all of):**

1. `flowchart TB` — module-dependency DAG. Edges point from dependent to dependency. **Cycles are a bug.** Group by hex / onion / clean ring with `subgraph`.
2. **Module table** — module, purpose (one line), public interface (signature-level), depends on, owner aggregate from §6.

## §9 L8 — Tactical Patterns

**Required visuals (per pattern):**

1. **Patterns Applied table** — concern, pattern, ADR file:

   | Concern | Pattern | ADR |
   |---------|---------|-----|

2. `classDiagram` — interface + impls + how the pattern is wired (registry, factory, DI scope). One per non-trivial pattern.

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

If any row has `Blocks executor? = yes` in L2-L7, the design is NOT publishable — bounce back to `/afk:architect-grill`. L1 / L8 open questions may pass if scoped.

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

- **Every layer section must have its required visual.** A section without its diagram / table is not done.
- **Mermaid only — never ASCII art.** Per global response-style rule.
- **Caption every diagram** with one sentence stating the takeaway. A diagram without a caption forces reviewers to re-derive its meaning.
- **Label every edge and node.** Unlabeled arrows are rejected.
- **Tables must include units in headers.**
- **Numbers, not adjectives** — for every NFR, retry budget, timeout, latency target.
- **Do not invent decisions.** If a section cannot be filled, list it under §13 Open Questions and bounce to `/afk:architect-grill`. The Step 7 refuse-to-publish gate enforces this — a draft with `TBD` / `TODO` / `FIXME` / `???` / `<placeholder>` / `[?]` / `_FILL_IN_` / unsubstituted template literals, OR with any §13 row marked `Blocks executor? = yes` in L2-L7, is not written. The gate is non-negotiable; do NOT paper over it by demoting a blocker to a §13 row to make the scan pass.
- **No code or file paths in SDD/ADRs.** They rot.
- **Every ADR weighs ≥2 alternatives** and declares its layer (L1-L8).
- **Never modify** `## Implementation Notes (auto-maintained)` in the parent Jira ticket.

## AFK adaptation (core-services)

When the SDD belongs to an AFK-driven Enhancement / Bug:

- **File location.** `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md` and `.../adr/NNNN-*.md`. Service auto-derived from the Jira project key via `project_service_map`.
- **Parent ticket splice.** Add or update a `## SDD` section in the Enhancement / Bug description:

  ```
  ## SDD

  Architecture lives in the repo at `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/SDD.md`
  (this branch). ADRs in `.../adr/`.
  ```

  Leave `## PRD` and `## Implementation Notes (auto-maintained)` untouched.

- **Hand-off.** Each downstream SubTask MUST cite the SDD section(s) and ADR(s) that constrain it, so the implementing agent has a binding contract — not just a feature ask.

## Next

After the SDD + ADRs land, you have two choices:

- **Stakeholder review upcoming?** Run **`/afk:to-design-brief`** to synthesize a
  tight 1-2 page digest (one money-shot diagram + 5-10 row decision table +
  stakeholder-impact table). Strict synthesis — no new decisions.
- **Slicing time?** Run **`/afk:to-subtasks`** to slice the PRD + SDD + ADRs
  into AFK-eligible Jira SubTasks with typed `## Produces` / `## Consumes`
  contracts. The slicing-time refuse gate (`/afk:to-subtasks` Step 3) re-runs
  the §13 / library-version checks defensively in case the SDD was
  hand-edited after this skill ran.

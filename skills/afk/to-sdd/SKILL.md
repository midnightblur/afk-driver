---
name: to-sdd
description: Synthesizes settled design decisions into an SDD + design ADRs next to the PRD; no interview, local only. Use once design is settled and the user wants it materialized.
---

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this skill produces.

From the conversation context, the PRD, and codebase understanding, produce:

1. A single `SDD.md` organized layer-by-layer (L1 -> L9; L9 lands as §14), with **mandatory visualizations** per section.
2. One design ADR per non-trivial decision under `adr/design/NNNN-kebab-title.md`, each with ≥1 diagram or table.

Do NOT interview — synthesize what you know. Critical-logic concern unresolved → STOP, tell user to run `/afk:grill-solution` first; don't invent decisions.

Read the ticket folder's `GRILL-LOG.md` first — the solution grill checkpoints its locked layers, its L9 seam verdicts, and its **human sign-off register** there, and that log (not your memory of the conversation) is the source for §0's register. It is also how synthesis survives a compaction or a new session.

## Process

1. **Locate the PRD** in the ticket spec folder (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions"). Read with `ctx_read` (mode=full). SDD lands in the SAME folder as the PRD; design ADRs in its `adr/design/` subfolder.

2. **Re-read the ticket's existing ADRs** — design ADRs in sibling `adr/design/` (don't contradict prior design decisions) and requirement ADRs in `adr/requirements/` (behavioural constraints you must honour, owned by `/afk:to-prd`). Don't read or write repo-wide `docs/adr/` — all ADRs are ticket-local. To reverse a prior **design** ADR, write a new one that explicitly **Supersedes** it and list it in §12 Reversed Decisions. Never edit an `adr/requirements/` ADR — a requirement decision blocking the design is a `design-conflict` to route back, not overwrite here.

3. **Use the project's domain glossary.** Match the vocabulary in the PRD and the relevant `GLOSSARY.md` (if present — start from root `GLOSSARY-MAP.md` to find the owning service's glossary).

4. **Apply the triviality cutoff.** ADR-worthy = (non-obvious for the stack) AND (≥2 real alternatives) AND (reversal expensive). Skip ADRs for "we use HTTPS / UTF-8 / JSON".

5. **Layers with nothing project-specific to say → one line: "Inherited / default."** Do NOT delete the section.

6. **Write SDD.md using the template below.** Each section's `Required visuals:` annotation is binding — can't produce the visual → section not done.

7. **Refuse-to-publish gate.** Before writing `SDD.md` or any ADR, scan the draft (prose / table cells / diagram labels — NOT fenced real code) for executor-blocking markers. If any appear, do NOT write: list each offender with its §-location verbatim (`§4 L3 — row "events table"` reads `Retention: TBD`) and bounce to `/afk:grill-solution`.

   Blocker tokens (canonical set; `/afk:to-subtasks`'s refuse-to-slice gate re-scans it): `\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`, `\?\?\?`, `<TBD>` / `<TODO>` / `<placeholder>` / `<fill>` / `<\?>`, `\[\?\]`, `_?FILL[_-]?IN_?`, `\(decide later\)` / `\(unresolved\)` / `\(open\)`, and unsubstituted template literals (`<TICKET-ID>`, `<NNNN>`, `<service>`, `{Feature Name}`). Real generics (`<T>`), optional-type markers (`Foo?`), and a stray `?` in a signature are NOT blockers.

   Also scan §13: a row with `Blocks executor? = yes` in L2-L7 or L9 is a blocker (L1/L8 may pass if scoped). Don't demote a blocker to a §13 row to sneak it past the gate.

7b. **Human sign-off gate.** Transcribe §0's sign-off register from the grill log's signoff rows, then refuse to write on any of: a live human-locked aspect not `signed` or `n/a`; a `signed` row without the human's own wording; a section (§3 endpoint, §4 entity, §5 authz, §6 lifecycle, §7 side effect, §14 seam) carrying design the signature didn't cover. Name the aspect and bounce to `/afk:grill-solution`. Never sign, infer a signature, or promote `pending` on the human's behalf — the set and protocol live in `skills/afk/grill-solution/HUMAN-SIGNOFF.md`.

8. **Library-version pin cross-check.** Verify any version pin the SDD/ADR names (Spring Boot, Hibernate, Vue, axios, … — anything `\d+\.\d+`) against the build manifest before writing. The Grounding rule catches a library's *existence*; this catches a fictional *version* of a real library, which silently poisons every downstream behaviour assumption.

   | Stack | Manifest |
   |-------|----------|
   | Maven | `pom.xml` (+ parent / BOM POMs) |
   | Gradle | `build.gradle(.kts)`, `gradle.properties`, `libs.versions.toml` |
   | Node | `package.json` + `package-lock.json` (resolved wins) |
   | Python | `pyproject.toml`, `requirements.txt`, `Pipfile.lock` |

   - Quote the resolved pin with its source line (`Spring Boot 3.2.4 — pom.xml:42`) so drift shows in `git diff`.
   - Manifest differs from draft → STOP and bounce; don't silently match draft to manifest (intent may be "we're upgrading," which changes the manifest first).
   - Not directly pinned (transitive / BOM-managed) → label `"inherited from {BOM}; not a direct pin"`; never hard-code a transitive version as if pinned.
   - A behaviour claim gated on a version threshold ("X since vN", "removed in vN+1") → verify against a primary source (release notes / JEP / RFC), cite the identifier inline, then write the decision.

   Refuse-to-publish (same as Step 7) if any pin lacks a manifest citation or contradicts it.

   This cross-check is pure research: delegate to an `afk-reader` subagent returning a cited confirm/refute per pin — Step 8b's seam check runs as a parallel sibling in the same message — per `DELEGATION.md` (plugin root). The conversation synthesis stays inline.

8b. **Framework-seam cross-check.** Step 8 verifies the version pin; this verifies the *behavior* at that pin. For each §9b framework row, confirm what it does to our value (and which annotations it honors) against the framework source / docs (`get-api-docs` where available), not memory. Unverifiable → label `unverified premise`; if the design depends on it, it's a §13 blocker → bounce to `/afk:grill-solution`. Every framework row names a seam-test or the seam isn't done. Like Step 8, delegate per `DELEGATION.md` (a cited confirm/refute per §9b row).

9. **Emit design ADRs** into the `adr/design/` subfolder. Numbering is local to `adr/design/` (start at `0001`), independent of `adr/requirements/` numbering. ADRs are subject to the same Step 7 refuse-to-publish gate AND the Step 8 library-version cross-check — apply both before writing any `adr/design/NNNN-*.md` file.

10. **Update the ticket index.** Upsert this skill's rows in the sibling `INDEX.md` (`SDD`, `Design ADRs`) per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** `SDD.md` + every design ADR on disk, Steps 7 / 7b / 8 / 8b gates passed, `INDEX.md` rows upserted.

## Visualization rules

**Every non-trivial layer ships with the visual that carries its signal** — a reviewer grasps the design from shape, not prose. Skip the visual only where the layer is one-line "inherited/default."

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
- One diagram, one concern. >12 nodes → split it.
- Caption every diagram with one sentence stating the takeaway.
- Tables need units in the header (`Latency p95 (ms)`, not `Latency p95`).
- Numbers, not adjectives. "p95 < 200 ms" not "fast".

Render safety (the Mermaid constructs that break renderers) is owned by `skills/utils/draw-charts/SKILL.md` — follow it for every diagram.

## SDD template

Write SDD.md using the template in [SDD-TEMPLATE.md](SDD-TEMPLATE.md). Each section's `Required visuals:` annotation there is binding.

## ADR template

Write each design ADR using the template in [ADR-TEMPLATE.md](ADR-TEMPLATE.md).

## Hard rules

- **No code or file paths in SDD/ADRs.** They rot. Exception: *verification citations* — §3 contract-source paths and §14's "verified where" column cite files as evidence of a checked fact, not implementation guidance; required, not forbidden.

## Next

After the SDD + ADRs land:

- **Run `/afk:to-design-brief` by default** — the tight 1-2 page digest (one money-shot diagram + 5-10 row decision table + stakeholder-impact table) is the fastest way a human catches up on this design later; skip only when the user says so. Strict synthesis — no new decisions.
- **Verification scenarios need the settled solution?** Run **`/afk:grill-verification`** *(optional)* to design verification scenarios against the settled design, then **`/afk:to-verification-plan`** to write `VERIFICATION-PLAN.md`. With the SDD present, this run designs **both** modalities — UI journeys **and** API scenarios (which read the §3 API contract table and the §9b below-the-UI seams). (If only the UI journeys were clear, an earlier post-`/afk:to-prd` run may have designed those and deferred the API scenarios — re-run both skills now; `/afk:to-verification-plan` appends the API section.) Its plan makes `/afk:to-subtasks` add the feature smoke-test gate + per-modality build subtasks.
- **Slicing time?** Run **`/afk:to-subtasks`** to slice PRD + SDD + ADRs into a local execution plan (`plan/PLAN.md` + per-subtask contracts) with typed `## Produces` / `## Consumes` and a per-subtask `## Seams` list. The slicing-time refuse gate re-runs the §13 / library-version checks defensively in case the SDD was hand-edited after this skill ran.

---
name: to-sdd
description: Turn the current conversation context into a Software Design Document (SDD) plus per-decision ADRs and publish them next to the PRD. SDD sections are organized top-down by architecture layer (L1 system topology -> L8 tactical patterns -> L9 implementation seams, §14) and EVERY layer ships with the appropriate visualization (Mermaid diagram, table, or chart) so reviewers can grasp the design at a glance. Use once the design decisions are settled in conversation, when the user wants to materialize the design as artifacts. Does NOT interview — synthesizes what is already known.
---

From the current conversation context, the PRD, and codebase understanding, produce:

1. A single `SDD.md` organized layer-by-layer (L1 -> L9; L9 lands as §14), with **mandatory visualizations** per section.
2. One design ADR per non-trivial decision under `adr/design/NNNN-kebab-title.md`, each with at least one diagram or table.

Do NOT interview — synthesize what you already know. If a critical-logic concern is unresolved, STOP and tell the user to run `/afk:grill-solution` first; do not invent decisions.

## Process

1. **Locate the PRD.** Default path: `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md` (service-scoped) or `tasks/{TICKET-ID}/PRD.md` (cross-cutting tooling). Read with `ctx_read` (mode=full). SDD lands in the SAME folder as the PRD; design ADRs in its `adr/design/` subfolder.

2. **Re-read the ticket's existing ADRs** — design ADRs in sibling `adr/design/` (don't contradict prior design decisions) and requirement ADRs in `adr/requirements/` (behavioural constraints you must honour, owned by `/afk:to-prd`). Don't read or write repo-wide `docs/adr/` — all ADRs are ticket-local. To reverse a prior **design** ADR, write a new one that explicitly **Supersedes** it and list it in §12 Reversed Decisions. Never edit an `adr/requirements/` ADR — if a requirement decision blocks the design, that's a `design-conflict` to route back, not to overwrite here.

3. **Use the project's domain glossary.** Match the vocabulary in the PRD and the relevant `GLOSSARY.md` (if present — start from root `GLOSSARY-MAP.md` to find the owning service's glossary).

4. **Apply the triviality cutoff.** ADR-worthy = (non-obvious for the stack) AND (≥2 real alternatives) AND (reversal is expensive). Skip ADRs for "we use HTTPS / UTF-8 / JSON".

5. **For layers with nothing project-specific to say, write one line: "Inherited / default."** Do NOT delete the section.

6. **Write SDD.md using the template below.** Each section's `Required visuals:` annotation is binding — can't produce the visual → section not done.

7. **Refuse-to-publish gate.** Before writing `SDD.md` or any ADR, scan the draft (prose / table cells / diagram labels — NOT fenced real code) for executor-blocking markers. If any appear, do NOT write: list each offender with its §-location verbatim (`§4 L3 — row "events table"` reads `Retention: TBD`) and bounce to `/afk:grill-solution`.

   Blocker tokens (this is the canonical set; `/afk:to-subtasks`'s refuse-to-slice gate re-scans it): `\bTBD\b`, `\bTODO\b`, `\bFIXME\b`, `\bXXX\b`, `\?\?\?`, `<TBD>` / `<TODO>` / `<placeholder>` / `<fill>` / `<\?>`, `\[\?\]`, `_?FILL[_-]?IN_?`, `\(decide later\)` / `\(unresolved\)` / `\(open\)`, and unsubstituted template literals (`<TICKET-ID>`, `<NNNN>`, `<service>`, `{Feature Name}`). Real generics (`<T>`), optional-type markers (`Foo?`), and a stray `?` in a signature are NOT blockers.

   Also scan §13: a row with `Blocks executor? = yes` in L2-L7 or L9 is a blocker (L1/L8 may pass if scoped). Don't demote a blocker to a §13 row to sneak it past the gate — that defeats the purpose.

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

8b. **Framework-seam cross-check.** Step 8 verifies the version pin; this verifies the *behavior* at that pin. For each §9b framework row, confirm what it does to our value (and which annotations it honors) against the framework source / docs (`get-api-docs` where available), not memory. Unverifiable → label `unverified premise`; if the design depends on it, it's a §13 blocker → bounce to `/afk:grill-solution`. Every framework row names a seam-test or the seam isn't done.

9. **Emit design ADRs** into the `adr/design/` subfolder. Numbering is local to `adr/design/` (start at `0001`), independent of `adr/requirements/` numbering. ADRs are subject to the same Step 7 refuse-to-publish gate AND the Step 8 library-version cross-check — apply both before writing any `adr/design/NNNN-*.md` file.

10. **Splice a `## SDD` section into the parent Jira ticket description** (shape: [AFK-ADAPTATION.md](AFK-ADAPTATION.md) — a short human-readable digest + the repo path, not a bare pointer). Never modify `## Implementation Notes (auto-maintained)`.

11. **Update the ticket index.** Upsert this skill's rows in the sibling `INDEX.md` (`SDD`, `Design ADRs`) per `skills/afk/to-prd/INDEX-FORMAT.md`; create the file per that format if missing.

## Visualization rules

Apply the visualization rules in [VISUALIZATION.md](VISUALIZATION.md) — the Toolkit (Mermaid diagram-type table) and diagram-quality rules — when producing every non-trivial layer's visual.

## SDD template

Write SDD.md using the template in [SDD-TEMPLATE.md](SDD-TEMPLATE.md). Each section's `Required visuals:` annotation there is binding.

## ADR template

Write each design ADR using the template in [ADR-TEMPLATE.md](ADR-TEMPLATE.md).

## Hard rules

- **The Visualization rules are binding** — Mermaid only (never ASCII), every non-trivial layer carries its signal visual, labeled + captioned, tables with units, numbers not adjectives.
- **Do not invent decisions.** A section that can't be filled goes to §13 and bounces to `/afk:grill-solution`; the Step 7 gate enforces this and is non-negotiable — don't paper over it by demoting a blocker to a §13 row.
- **No code or file paths in SDD/ADRs.** They rot. Exception: *verification citations* — §3 contract-source paths and §14's "verified where" column cite files as evidence of a checked fact, not as implementation guidance; those are required, not forbidden.
- **Every ADR weighs ≥2 alternatives** and declares its layer (L1-L9).
- **§14 is synthesized, never invented.** Its seam rows come from the L9 seam walk in context (verified contracts + verdicts + accepted audit findings); a design whose L9 rows are missing or unverified bounces to `/afk:grill-solution` like any other gap.
- **§9b seams are binding.** Every framework seam names a seam-test that asserts on the framework's real output (not our objects) — the gap that makes green unit tests lie; every field contract cites its canonical source; every relied-on invariant proves it holds for the new caller. A seam that can't satisfy these is a §13 blocker → bounce to `/afk:grill-solution`.
- **Never modify** `## Implementation Notes (auto-maintained)` in the parent Jira ticket.

## AFK adaptation (core-services)

When the SDD belongs to an Enhancement / Bug in the AFK workflow, follow the file-location, parent-ticket-splice, and hand-off rules in [AFK-ADAPTATION.md](AFK-ADAPTATION.md).

## Next

After the SDD + ADRs land, your choices:

- **Run `/afk:to-design-brief` by default** — the tight 1-2 page digest (one money-shot diagram + 5-10 row decision table + stakeholder-impact table) is the fastest way any human catches up on this design later; skip it only when the user explicitly says so. Strict synthesis — no new decisions.
- **Verification scenarios need the settled solution?** Run **`/afk:grill-verification`** *(optional)* to design the feature's verification scenarios against the now-settled design, then **`/afk:to-verification-plan`** to write `VERIFICATION-PLAN.md`. Now that the SDD exists, this run can design **both** modalities — the UI journeys **and** the API scenarios (which read the §3 API contract table above and the §9b below-the-UI seams). (If only the UI journeys were clear, an earlier post-`/afk:to-prd` run may have designed those and deferred the API scenarios — re-run both skills now; `/afk:to-verification-plan` appends the API section.) Its plan makes `/afk:to-subtasks` add the feature smoke-test gate + the per-modality build subtasks.
- **Slicing time?** Run **`/afk:to-subtasks`** to slice the PRD + SDD + ADRs into a local execution plan (`plan/PLAN.md` + per-subtask contracts) with typed `## Produces` / `## Consumes` and a per-subtask `## Seams` list. The slicing-time refuse gate re-runs the §13 / library-version checks defensively in case the SDD was hand-edited after this skill ran.

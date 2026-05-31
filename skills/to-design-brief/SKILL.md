---
name: to-design-brief
description: Synthesize the existing PRD + SDD + ADRs into a tight 1-2 page DESIGN-BRIEF.md aimed at (a) technical stakeholders outside the team — security, ops, adjacent leads — and (b) humans pre-reading the SDD. One canonical diagram, 5-10 key-decision digest, stakeholder impact table. Strict synthesis: no new decisions; if a section can't be filled from the source docs, refuse and bounce back to `/afk:architect-grill` / `/afk:to-sdd`. Use when the user has a PRD + SDD (and ADRs) and wants a digestible briefing for stakeholder review or as a map before reading the full SDD.
---

This skill takes the PRD, SDD, and per-decision ADRs and emits a single
`DESIGN-BRIEF.md` — a tight 1-2 page synthesis aimed at:

- **Technical stakeholders outside the implementing team** (security, ops,
  adjacent leads, reviewers): they need enough to grasp impact and ask the
  right questions without reading the full SDD.
- **Humans pre-reading the SDD**: a map before the territory.

This is **not** a third design document. It is a digest — every claim must
trace back to the PRD, SDD, or an ADR. The brief never introduces a new
decision, alternative, or rationale.

Do NOT interview the user. If a brief section cannot be filled from the
source docs, STOP and tell the user to run `/afk:architect-grill` and re-emit
the SDD; do not invent.

## Process

1. **Locate the source docs.** Default paths (sibling layout):
   - PRD: `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/PRD.md`
   - SDD: `.../{TICKET-ID}/SDD.md`
   - ADRs: `.../{TICKET-ID}/adr/requirements/NNNN-*.md` (requirement-level, from `/afk:to-prd`) and `.../{TICKET-ID}/adr/design/NNNN-*.md` (design-level, from `/afk:to-sdd`)
   - The brief lands at `.../{TICKET-ID}/DESIGN-BRIEF.md` (sibling).

   Read PRD with `ctx_read` mode=full. Read SDD mode=full. Read each ADR
   mode=signatures (just need title, decision, alternatives count, layer).

2. **Refuse if the SDD is incomplete.** If SDD §13 Open Questions is
   non-empty with `Blocks executor? = yes` rows, do NOT emit a brief — the
   design is not stable enough to summarize. Tell the user to resolve via
   `/afk:architect-grill` first.

3. **Pick ONE money-shot diagram.** Choose the single diagram from the SDD
   that best conveys the feature's shape to a stakeholder seeing it cold.
   The right pick depends on the feature:

   - Cross-service / cross-context feature → SDD §3 service interaction
     `flowchart` or `sequenceDiagram`.
   - Single-service feature with multi-step coordination → SDD §7 happy-path
     `sequenceDiagram` (one use case, the most representative).
   - State-machine-heavy feature → SDD §6 aggregate `stateDiagram-v2`.
   - Module-restructuring feature → SDD §8 module dependency DAG.
   - Pattern-introduction feature → SDD §9 `classDiagram`.

   Embed it inline. Caption it with one sentence stating the takeaway.
   **Do not include more than one diagram.** The discipline is the point —
   if one diagram cannot carry the shape, the SDD is the right artifact,
   not the brief.

4. **Write the brief using the template below.** Hard length cap:
   400-800 words excluding the diagram and tables. If a draft runs long,
   compress; do not add more sections.

5. **Splice a `## Design Brief` pointer into the parent Jira ticket
   description** alongside `## PRD` and `## SDD`. Never modify
   `## Implementation Notes (auto-maintained)`.

## Template

<brief-template>

# Design Brief — {Feature Name}

> Parent ticket: {TICKET-ID}
> Sources: [PRD](./PRD.md) · [SDD](./SDD.md) · [ADRs](./adr/)
> Status: mirrors SDD status (Draft / Approved / Superseded)
> Last updated: {YYYY-MM-DD}
> Audience: technical stakeholders + humans pre-reading the SDD

## §1 Problem

One paragraph from the PRD's Problem Statement, in domain language. 3-5
sentences. No solution mentioned here.

## §2 Shape

3-7 sentences explaining what is being built and how it works at the
narrative level — the kind of explanation a senior engineer would give in
30 seconds at a whiteboard. Name the bounded contexts / services / modules
involved, the primary flow, and the key invariant the design protects.
Plain language; technical terms allowed where they shorten the explanation.

## §3 At a Glance

One Mermaid diagram (the money shot — see Process step 3 for selection
rules). Caption it with one sentence stating what to take away.

```mermaid
{the chosen diagram}
```

> {one-sentence caption}

## §4 Key Decisions

5-10 rows. Each row is the digest of an ADR — never duplicate the ADR's
full text. If you have more than 10 ADRs, pick the rows a stakeholder is
most likely to question or need to align on.

| # | Decision | Layer (L1-L8) | Why this, not the alternative | ADR |
|---|----------|---------------|--------------------------------|-----|
| 1 | {one phrase} | L3 | {rejected alt + the constraint that ruled it out} | `adr/0001-...md` |

The "Why" column must be one short sentence. If you cannot compress the
rationale to one sentence, that is signal the ADR's Context section needs
tightening — not a license to expand the brief.

## §5 Stakeholder Impact

What changes for each stakeholder group. Empty cells are valid — most
stakeholders are unaffected by most features.

| Stakeholder | What changes | What they need to do |
|-------------|--------------|----------------------|
| Security review | {e.g. new auth flow on /export endpoint} | {e.g. review ADR-0004 + threat-model the signed-URL path} |
| Operations | {e.g. new background-job queue} | {e.g. provision queue X, set alert on lag > Y} |
| Adjacent team {name} | {e.g. event schema change on `payment.posted`} | {e.g. consume new fields by date Z; old fields stay for 2 releases} |
| End users | {e.g. async PDF generation; download link instead of immediate response} | (none) |

If a row's "What changes" is "(none)", omit the row.

## §6 Out of Scope & Risks

- **Out of scope** — bullet list, lifted from PRD §Out of Scope + SDD §11.
  Stakeholders read this to confirm their concern is being deferred, not
  forgotten.
- **Risks** — the top 2-3 risks from the SDD's Failure & Recovery matrix
  or Open Questions list. Each risk: one phrase + the named recovery /
  mitigation. If the SDD has no risks worth surfacing, write
  "No design-level risks open at brief time" rather than padding.

## §7 Where to Go Next

- **Curious about the user-facing problem?** → `PRD.md`
- **Reviewing the full design?** → `SDD.md` (layered §2 L1 → §9 L8)
- **Auditing a specific decision?** → `adr/requirements/NNNN-*.md` (behaviour /
  scope) or `adr/design/NNNN-*.md` (solution — each cites its layer,
  alternatives, consequences)
- **Disagree with a decision?** → run `/afk:architect-grill` to draft a
  superseding ADR; do not edit the existing one in place.

</brief-template>

## Hard rules

- **Strict synthesis.** Every claim must trace back to PRD / SDD / an ADR.
  No new decisions, no new alternatives, no new rationale. If a section
  cannot be filled from sources, refuse — bounce to `/afk:architect-grill` +
  `/afk:to-sdd`.
- **Length cap: 400-800 words** excluding the diagram and tables. Long
  briefs are not briefs.
- **One diagram only.** Discipline forces you to pick the most useful one.
  More diagrams = read the SDD.
- **One sentence per "Why" row** in §4. Rationale that does not compress
  to one sentence belongs in the ADR, not here.
- **No code, no file paths inside the prose.** Pointers in §7 are the only
  exception, and they are stable filenames sibling to the brief.
- **Mirror the SDD status field.** A brief whose source SDD is Draft is
  itself Draft — stakeholders need to know whether they are reviewing a
  proposal or a decision.
- **Refuse on incomplete SDD.** If SDD §13 has open questions that block
  executors (L2-L7), do not emit a brief. The brief's value is showing
  shape; an SDD with shape-blocking gaps has no shape yet.

## AFK adaptation (core-services)

When the brief belongs to an AFK-driven Enhancement / Bug:

- **File location.** `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/DESIGN-BRIEF.md`. Service auto-derived from the Jira project key via `project_service_map`.
- **Parent ticket splice.** Add or update a `## Design Brief` section in the
  Enhancement / Bug description:

  ```
  ## Design Brief

  One-pager for stakeholder review at
  `{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/DESIGN-BRIEF.md`
  (this branch). Maps onto the full design in `SDD.md` and the user-facing
  motivation in `PRD.md`.
  ```

  Leave `## PRD`, `## SDD`, and `## Implementation Notes (auto-maintained)`
  untouched.

- **Re-emit on SDD change.** Briefs go stale silently — when the SDD or any
  ADR changes materially, re-run this skill. The `Last updated` field is
  the canary.

## Next

The brief is for stakeholder review, not for the executor — the binding
contract for AFK SubTasks is the SDD + ADRs, not the brief. After the brief
is published and stakeholders are aligned, run **`/afk:to-subtasks`** to slice
the PRD + SDD + ADRs into AFK-eligible Jira SubTasks. The brief itself is
not in the executor's reading list.

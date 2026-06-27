---
name: to-design-brief
description: Synthesize the existing PRD + SDD + ADRs into a tight 1-2 page DESIGN-BRIEF.md aimed at (a) technical stakeholders outside the team — security, ops, adjacent leads — and (b) humans pre-reading the SDD. One canonical diagram, 5-10 key-decision digest, stakeholder impact table. Strict synthesis: no new decisions; if a section can't be filled from the source docs, refuse and bounce back to `/afk:grill-solution` / `/afk:to-sdd`. Use when the user has a PRD + SDD (and ADRs) and wants a digestible briefing for stakeholder review or as a map before reading the full SDD.
---

This skill takes the PRD, SDD, and per-decision ADRs and emits a single
`DESIGN-BRIEF.md` — a tight 1-2 page synthesis aimed at:

- **Technical stakeholders outside the implementing team** (security, ops,
  adjacent leads, reviewers): they need enough to grasp impact and ask the
  right questions without reading the full SDD.
- **Humans pre-reading the SDD**.

This is **not** a third design document. It is a digest — every claim must
trace back to the PRD, SDD, or an ADR. The brief never introduces a new
decision, alternative, or rationale.

Do NOT interview the user. If a brief section cannot be filled from the
source docs, STOP and tell the user to run `/afk:grill-solution` and re-emit
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
   `/afk:grill-solution` first.

3. **Pick ONE money-shot diagram.** Choose the single diagram from the SDD
   that best conveys the feature's shape to a stakeholder. The right pick
   depends on the feature:

   - Cross-service / cross-context feature → SDD §3 service interaction
     `flowchart` or `sequenceDiagram`.
   - Single-service feature with multi-step coordination → SDD §7 happy-path
     `sequenceDiagram` (one use case, the most representative).
   - State-machine-heavy feature → SDD §6 aggregate `stateDiagram-v2`.
   - Module-restructuring feature → SDD §8 module dependency DAG.
   - Pattern-introduction feature → SDD §9 `classDiagram`.

   Embed it inline. Caption it with one sentence stating the takeaway.
   **Do not include more than one diagram.** If one diagram cannot carry
   the shape, the SDD is the right artifact, not the brief.

4. **Write the brief using the template below.** Hard length cap:
   400-800 words excluding the diagram and tables. If a draft runs long,
   compress; do not add more sections. The brief is a **repo-only
   artifact** — it does not touch the Jira ticket (see below).

## Template

Write the brief using the template in [BRIEF-TEMPLATE.md](BRIEF-TEMPLATE.md).

## Hard rules

- **Strict synthesis.** Every claim must trace back to PRD / SDD / an ADR.
  No new decisions, no new alternatives, no new rationale. If a section
  cannot be filled from sources, refuse — bounce to `/afk:grill-solution` +
  `/afk:to-sdd`.
- **Length cap: 400-800 words** excluding the diagram and tables.
- **One diagram only.** Pick the most useful one.
- **One sentence per "Why" row** in §4. Rationale that does not compress
  to one sentence belongs in the ADR, not here.
- **No code, no file paths inside the prose.** Pointers in §7 are the only
  exception, and they are stable filenames sibling to the brief.
- **Mirror the SDD status field.** A brief whose source SDD is Draft is
  itself Draft — stakeholders need to know whether they are reviewing a
  proposal or a decision.
- **Refuse on incomplete SDD.** If SDD §13 has open questions that block
  executors (L2-L7), do not emit a brief.

See [AFK-ADAPTATION.md](AFK-ADAPTATION.md) for the core-services AFK adaptation.

## Next

The brief is for stakeholder review, not for the executor — the binding
contract for AFK subtasks is the SDD + ADRs, not the brief. After the brief
is written and shared with stakeholders out of band, run **`/afk:to-subtasks`** to slice
the PRD + SDD + ADRs into a local execution plan. The brief itself is
not in the executor's reading list.

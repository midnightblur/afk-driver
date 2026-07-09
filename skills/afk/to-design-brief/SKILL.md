---
name: to-design-brief
description: Synthesize an existing PRD + SDD + ADRs into a tight 1-2 page DESIGN-BRIEF.md for technical stakeholders outside the team and humans pre-reading the SDD. Strict synthesis — no new decisions. Use when the user has a PRD + SDD and wants a digestible stakeholder briefing or a pre-SDD map.
---

Takes PRD, SDD, per-decision ADRs; emits one `DESIGN-BRIEF.md` — a tight 1-2 page synthesis aimed at:

- **Technical stakeholders outside the implementing team** (security, ops, adjacent leads, reviewers): enough to grasp impact and ask the right questions without reading the full SDD.
- **Humans pre-reading the SDD**.

**Not** a third design document. A digest — every claim traces back to the PRD, SDD, or an ADR. Never introduces a new decision, alternative, or rationale.

Do NOT interview. Brief section can't be filled from source docs → STOP, tell user to run `/afk:grill-solution` and re-emit the SDD; don't invent.

## Process

1. **Locate the source docs** in the ticket spec folder (path convention: `skills/afk/to-prd/SKILL.md`, "Monorepo conventions") — sibling layout: `PRD.md`, `SDD.md`, `adr/requirements/NNNN-*.md` (requirement-level, from `/afk:to-prd`), `adr/design/NNNN-*.md` (design-level, from `/afk:to-sdd`). Brief lands at `.../{TICKET-ID}/DESIGN-BRIEF.md` (sibling).

   Read PRD `ctx_read` mode=full. Read SDD mode=full. Read each ADR mode=signatures (title, decision, alternatives count, layer). Delegate this digestion to an `afk-reader` subagent returning a cited digest of the source docs, per `DELEGATION.md` (plugin root); the brief is written here, from that digest.

2. **Refuse if the SDD is incomplete.** SDD §13 Open Questions non-empty with `Blocks executor? = yes` rows → do NOT emit a brief; design not stable enough to summarize. Tell the user to resolve via `/afk:grill-solution` first.

3. **Pick ONE money-shot diagram.** The single SDD diagram best conveying the feature's shape to a stakeholder. Right pick depends on the feature:

   - Cross-service / cross-context feature → SDD §3 service interaction `flowchart` or `sequenceDiagram`.
   - Single-service, multi-step coordination → SDD §7 happy-path `sequenceDiagram` (one use case, most representative).
   - State-machine-heavy feature → SDD §6 aggregate `stateDiagram-v2`.
   - Module-restructuring feature → SDD §8 module dependency DAG.
   - Pattern-introduction feature → SDD §9 `classDiagram`.

   Embed inline. Caption with one sentence stating the takeaway. **No more than one diagram.** If one diagram can't carry the shape, the SDD is the right artifact, not the brief.

4. **Write the brief using the template below.** Hard length cap: 400-800 words excluding diagram and tables. Draft runs long → compress; don't add sections. The brief is a **repo-only artifact** — it doesn't touch the Jira ticket: shared with stakeholders out of band (link the repo file, paste into a review thread), and the ticket description stays with its other owners (`## PRD` via `/afk:to-ticket`, `## SDD` via `/afk:to-sdd`). Human present → render per LAVISH.md (RP-5, playbook `slides`) for a digest-slides walkthrough before sharing; markdown fallback and driven mode use the written `DESIGN-BRIEF.md` instead.

5. **Update the ticket index.** Upsert the `Design brief` row in the sibling `INDEX.md` per `skills/afk/to-prd/INDEX-FORMAT.md`.

**Done when:** `DESIGN-BRIEF.md` on disk within the length cap and the `INDEX.md` `Design brief` row upserted.

**Re-emit on SDD change.** Briefs go stale silently — SDD or any ADR changes materially → re-run this skill; the `Last updated` field is the canary.

## Template

Write the brief using the template in [BRIEF-TEMPLATE.md](BRIEF-TEMPLATE.md).

## Hard rules

- **Strict synthesis.** Every claim traces back to PRD / SDD / an ADR. No new decisions, alternatives, or rationale. Section can't be filled from sources → refuse; bounce to `/afk:grill-solution` + `/afk:to-sdd`.
- **One diagram only.** Pick the most useful.
- **One sentence per "Why" row** in §4. Rationale that doesn't compress to one sentence belongs in the ADR, not here.
- **No code, no file paths in the prose.** Pointers in §7 are the only exception — stable filenames sibling to the brief.
- **Mirror the SDD status field.** A brief whose source SDD is Draft is itself Draft — stakeholders need to know whether they're reviewing a proposal or a decision.

## Next

The brief is for stakeholder review, not the executor — the binding contract for AFK subtasks is the SDD + ADRs, not the brief. After the brief is written and shared out of band, run **`/afk:to-subtasks`** to slice PRD + SDD + ADRs into a local execution plan. The brief is not in the executor's reading list.

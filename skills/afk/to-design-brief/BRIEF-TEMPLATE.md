<brief-template>

# Design Brief — {Feature Name}

> Parent ticket: {TICKET-ID}
> Sources: [PRD](./PRD.md) · [SDD](./SDD.md) · [ADRs](./adr/)
> Status: mirrors SDD status (Draft / Approved / Superseded)
> Last updated: {YYYY-MM-DD}
> Audience: technical stakeholders + humans pre-reading the SDD

## §1 Problem

One paragraph from the PRD's Problem Statement, in domain language. 3-5
sentences. No solution here.

## §2 Shape

3-7 sentences: what is being built and how it works at the narrative level —
the explanation a senior engineer gives in 30 seconds at a whiteboard. Name
the bounded contexts / services / modules involved, the primary flow, and
the key invariant the design protects. Plain language; technical terms where
they shorten the explanation.

## §3 At a Glance

One Mermaid diagram (the money shot — see Process step 3 for selection
rules). Caption with one sentence stating the takeaway.

```mermaid
{the chosen diagram}
```

> {one-sentence caption}

## §4 Key Decisions

5-10 rows. Each row is the digest of an ADR — never duplicate the ADR's
full text. More than 10 ADRs → pick the rows a stakeholder is most likely
to question or need to align on.

| # | Decision | Layer (L1-L9) | Why this, not the alternative | ADR |
|---|----------|---------------|--------------------------------|-----|
| 1 | {one phrase} | L3 | {rejected alt + the constraint that ruled it out} | `adr/design/0001-...md` |

The "Why" column is one short sentence. Can't compress the rationale to one
sentence → signal the ADR's Context section needs tightening, not a license
to expand the brief.

## §5 Stakeholder Impact

What changes for each stakeholder group. Empty cells valid — most
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
  Stakeholders read this to confirm their concern is deferred, not forgotten.
- **Risks** — the top 2-3 risks from the SDD's Failure & Recovery matrix
  or Open Questions list. Each risk: one phrase + the named recovery /
  mitigation. No risks worth surfacing → write "No design-level risks open
  at brief time" rather than padding.

## §7 Where to Go Next

- **Curious about the user-facing problem?** → `PRD.md`
- **Reviewing the full design?** → `SDD.md` (layered §2 L1 → §9 L8 (+ §14 L9))
- **Auditing a specific decision?** → `adr/requirements/NNNN-*.md` (behaviour /
  scope) or `adr/design/NNNN-*.md` (solution — each cites its layer,
  alternatives, consequences)
- **Disagree with a decision?** → run `/afk:grill-solution` to draft a
  superseding ADR; do not edit the existing one in place.

</brief-template>

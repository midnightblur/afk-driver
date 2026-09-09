# ADR template

<adr-template>

# ADR-NNNN — {Decision Title}

> Status: Proposed | Decided by agent | Accepted | Superseded by ADR-MMMM
> Date: {YYYY-MM-DD}
> Audited: not yet | {YYYY-MM-DD}
> Layer: L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8 | L9
> Context ticket: {TICKET-ID}

## Context

What forces are at play. Cite the SDD section.

## Decision

The chosen approach in one paragraph.

**Required visual:** one diagram showing the chosen shape (`classDiagram` for tactical patterns, `sequenceDiagram` for protocol decisions, `flowchart` for topology, `erDiagram` for data).

## Alternatives Considered

≥2. **Required visual:** comparison table OR `quadrantChart` plotting alternatives on two axes that mattered for THIS context.

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|

## Consequences

- **Positive** — what this enables.
- **Negative** — what this costs.
- **Follow-ups** — work this creates that is NOT in scope.

</adr-template>

## The status line

This file owns the status-line grammar; `skills/afk/to-prd/ADR-FORMAT.md`
carries a synchronized copy at its own emitting site, and the two move in the
same commit.

`Decided by agent` is for a record the agent minted from a decision it took
rather than one the human made. It is not a lesser status — it is the honest
one, and it stays until a human has read the record and stamped `Audited` with
the date they read it. That stamp is what makes it `Accepted`.

Minting from a grill-time decision the human accepted: the accepted `Settled:`
row (`skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`) carries more scrutiny
than this record will — the human audited the decision, its alternatives, and
its evidence on the card — so write `Status: Accepted` and `Audited: {the
accept date from that row}`. The card was the audit; no second read is asked of
the human.

`Audited:` is written **only** on a record the agent decided; a human-decided
record omits the line. An `Accepted` record therefore still says who decided
it — by whether the line is there. Read by `/afk:retro`, which once `/afk:gc`
has deleted `GRILL-LOG.md` has no other source for that fact.

Proving provenance by a line's presence fails one way: a human-decided record
that carries `Audited:` reads as agent-decided. The error over-attributes to
the agent, so it reaches `/afk:retro` as noise, never as a missed signal —
which is why presence is enough here.

An unaudited record is not wrong; it is unreviewed. Writing `Accepted` on a
decision nobody audited is how an agent's call quietly becomes the team's,
which is the one thing this line exists to prevent.

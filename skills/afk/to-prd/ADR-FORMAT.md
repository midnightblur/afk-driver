# Requirements ADR Format

These are **requirement-level** ADRs — they record decisions about how the
feature must *behave* and what is in or out of scope (the *what / why*), not how
it is built (the *how* — that's the design ADRs owned by `/afk:to-sdd`).

Requirement ADRs live in the ticket-local `adr/requirements/` subfolder, sibling
to the PRD:

```
{service}/src/main/resources/specs/{year}r{release}/{TICKET-ID}/
├── PRD.md
└── adr/
    ├── requirements/        ← this skill (to-prd)
    │   ├── 0001-slug.md
    │   └── 0002-slug.md
    └── design/              ← /afk:to-sdd
        └── 0001-slug.md
```

Numbering is local to `adr/requirements/` and starts at `0001`. Scan the folder
for the highest existing number and increment by one.

## Template

```md
# {Short title of the decision}

> Layer: Requirements
> Context ticket: {TICKET-ID}

{1-3 sentences: what's the context, what did we decide, and why.}
```

That's it. A requirement ADR can be a single paragraph. The value is in
recording *that* a behavioural decision was made and *why* — not in filling out
sections. The `Layer: Requirements` line is the discriminator that keeps these
distinct from `/afk:to-sdd`'s `Layer: L1–L8` design ADRs in the sibling folder.

## Optional sections

Only include these when they add genuine value. Most requirement ADRs won't need
them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — useful when decisions are revisited
- **Considered Options** — only when the rejected alternatives are worth remembering
- **Consequences** — only when non-obvious downstream effects need to be called out

## When to emit a requirement ADR

All three of these must be true:

1. **Hard to reverse** — the cost of changing your mind later is meaningful
2. **Surprising without context** — a future reader will wonder "why does it behave this way?"
3. **The result of a real trade-off** — there were genuine alternatives and you picked one for specific reasons

If a decision is easy to reverse, skip it. If it's not surprising, nobody will
wonder why. If there was no real alternative, there's nothing to record beyond
"we did the obvious thing." The PRD's `## Implementation Decisions` section is
the broad list of every decision; a requirement ADR is the *elevated* subset
that passes all three tests above — extracted as a standalone, durable record.

### What qualifies

- **Behavioural boundaries.** "Cancellations are full-only, never partial." "A posting run is immutable once submitted."
- **Scope decisions.** "Out of scope: multi-currency — single company-code currency only for v1." The explicit no-s are as valuable as the yes-s.
- **Deliberate deviations from the expected behaviour.** Anything where a reasonable user would assume the opposite. These stop the next person from "fixing" something that was deliberate.
- **Constraints not visible in the feature.** "Response must be under 200ms because of the partner API contract." "We can't retain PII beyond 30 days for compliance."
- **Rejected behaviours when the rejection is non-obvious.** If you considered soft-delete and picked hard-delete for subtle reasons, record it — otherwise someone will suggest soft-delete again in six months.

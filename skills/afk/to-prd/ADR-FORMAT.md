# Requirements ADR Format

**Requirement-level** ADRs record how the feature must *behave* and what is in/out of scope (*what / why*) — not how it's built (*how* = design ADRs, `/afk-toolkit:to-sdd`). They live in ticket-local `adr/requirements/`, sibling to the PRD:

```
{ticket spec folder}/          ← path convention: SKILL.md "Monorepo conventions"
├── PRD.md
└── adr/
    ├── requirements/        ← this skill (to-prd)
    │   ├── 0001-slug.md
    │   └── 0002-slug.md
    └── design/              ← /afk-toolkit:to-sdd
        └── 0001-slug.md
```

Numbering is local to `adr/requirements/`, starts at `0001`. Scan the folder for the highest and increment.

## Template

```md
# {Short title of the decision}

> Layer: Requirements
> Context ticket: {TICKET-ID}

{1-3 sentences: context, what we decided, why.}
```

That's it — a requirement ADR can be one paragraph. The value is recording *that* a behavioural decision was made and *why*. The `Layer: Requirements` line discriminates these from `/afk-toolkit:to-sdd`'s `Layer: L1–L9` design ADRs in the sibling folder.

## Optional sections

Only when they add genuine value (most won't need them):
- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`) — when decisions get revisited
- **Considered Options** — when rejected alternatives are worth remembering
- **Consequences** — when non-obvious downstream effects need calling out

## When to emit a requirement ADR

All three must be true:
1. **Hard to reverse** — changing your mind later costs meaningfully.
2. **Surprising without context** — a future reader will wonder "why does it behave this way?"
3. **Result of a real trade-off** — genuine alternatives existed, you picked one for specific reasons.

Easy to reverse → skip. Not surprising → nobody wonders. No real alternative → nothing to record. The PRD's `## Implementation Decisions` is every decision; a requirement ADR is the *elevated* subset passing all three, extracted as a durable record.

### What qualifies

- **Behavioural boundaries.** "Cancellations are full-only, never partial." "A posting run is immutable once submitted."
- **Scope decisions.** "Out of scope: multi-currency — single company-code currency for v1." The no-s are as valuable as the yes-s.
- **Deliberate deviations** from expected behaviour — where a reasonable user assumes the opposite. Stops the next person "fixing" what was deliberate.
- **Constraints not visible in the feature.** "Response under 200ms — partner API contract." "No PII beyond 30 days — compliance."
- **Rejected behaviours when the rejection is non-obvious** (soft-delete considered, hard-delete picked for subtle reasons) — else it's re-suggested in six months.

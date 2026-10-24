# ADR-0010 — Developer settings move to the configuration document; a missing assignee or reviewer never stops a hands-off run

> Status: Accepted
> Date: 2026-10-19
> Layer: L4
> Context ticket: small-lane

## Context

`/afk:bug` documents five developer settings and a fail-closed rule (INV-026). Removing it needs a new home for them (AC-040). Made general, fail-closed would stop every hands-off ticket write and change spinoff behaviour. Decided R-7 D-40, R-8 C-17.

## Decision

The settings and their rule move to `CONFIG.md` with the same names and meaning. A missing assignee or reviewer is asked for when a person is present; a hands-off run files the ticket or opens the change unassigned and names it in its report. The literal value `none` counts as unset for both the assignee and the reviewer. The settings keep their K1 to K5 ids, which the dependency register cites.

| Situation | Missing assignee or reviewer |
|-----------|------------------------------|
| person present | asked in the session |
| hands-off run | left unset, named in the report |
| value `none` | treated as unset |

## Alternatives Considered

| Alternative | Pros | Cons | Reason rejected |
|-------------|------|------|-----------------|
| Keep fail-closed everywhere | strict | stops every hands-off out-of-slice ticket | C-17 |
| Silent unassigned | no prompt | the person never learns | C-17 |

## Consequences

- **Positive** — hands-off runs keep moving; nothing renames.
- **Negative** — a narrower fail-closed rule than today (HL-6).
- **Follow-ups** — none.

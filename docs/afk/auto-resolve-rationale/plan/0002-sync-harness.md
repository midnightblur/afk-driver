## Goal

Sync the AGENTS.md harness for automatic rationale-thread resolution, settle the staples registry, and emit the trace matrix. Run `/afk:agents-md` against this feature's net diff.

## Complexity

mechanical

## Design refs

(none — sliced from the PRD without an SDD, per human approval)

## Scope

- AGENTS.md
- STAPLES.md
- docs/afk/auto-resolve-rationale/plan/TRACE.md

## Seams

(none — no SDD seam register)

## Acceptance

- [ ] The nearest relevant AGENTS.md contains any durable guidance that clears the `/afk:agents-md` inclusion bar.
- [ ] The staples registry decision is explicit, including a no-op when no staple applies.
- [ ] The artifact is written through `/afk:agents-md`.
- [ ] `plan/TRACE.md` maps every PRD Acceptance Criterion to its subtask, commits, and proving test.

## Verification

| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep every PRD Acceptance Criterion identifier in `plan/TRACE.md` | the trace matrix is complete |

## Context excerpts

> (PRD Solution) "The rationale writer resolves each rationale thread before it records the batch receipt. Retries resolve an existing rationale thread without posting a duplicate."

## Parent PRD

../PRD.md

## Parent SDD

(none — uncited mode)

## Blocked by

0001-resolve-rationale-threads

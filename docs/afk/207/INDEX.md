# 207 — start here

afkv2 has no step that settles a new or changed screen before the design, and notes given in chat lose which element the developer meant. This ticket ports two skills from v1: `prototype`, which builds a clickable HTML mockup anchored to the real app, shown natively in lavish so the developer pins notes on its elements (chat is the fallback), and `design-system`, which keeps a per-frontend design catalog committed in the repository. The developer runs both at the keyboard; `propose-solution` and `propose-verification` read the settled `PROTOTYPE.md` when it exists.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | published to GitHub 2026-11-24 |
| Requirement ADRs | adr/requirements/ | 3 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 4 records |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION.md | draft |
| Plan | plan/PLAN.md | — |
| Smoke gate | plan/PLAN.md | — |
| Understanding | understanding/index.html | — |
| Design review plan | DESIGN-REVIEW-PLAN.md | — |
| Demo plan | DEMO-PLAN.md | — |

## Reading order

1. This file.
2. DESIGN-BRIEF.md if present, else the Problem Statement and User Stories of PRD.md.
3. SDD.md §0 and §1; the full document only to implement or review the design.
4. plan/PLAN.md: solution map and live progress.
5. plan/JOURNAL.md (tail): what happened lately.
6. plan/review/INDEX.md: what the quality checks found.

# P2P-2067 — start here

Teams need shared business terms to stay accurate as a feature moves from an idea to delivered behavior. This feature gives authors the relevant definitions, identifies language that changed, asks the responsible people to confirm the final meaning, and keeps the evidence with the merge request without changing CI.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 6 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 8 records |
| Design brief | DESIGN-BRIEF.md | present |
| Verification plan | VERIFICATION-PLAN.md | — |
| Plan | plan/PLAN.md | 8 cited subtasks; live status in plan |
| Smoke gate | plan/PLAN.md | minimal plugin regression and source gates |
| Understanding | understanding/index.html | — |
| Design review plan | DESIGN-REVIEW-PLAN.md | — |
| Demo plan | DEMO-PLAN.md | — |

## Reading order

1. This file.
2. DESIGN-BRIEF.md if present — the 1–2 page digest; else PRD.md's Problem Statement + User Stories.
3. SDD.md §0 (locked vs free) + §1 (why this design) — full document only if implementing or reviewing design.
4. plan/PLAN.md — solution map + live progress tracker.
5. plan/JOURNAL.md (tail) — what happened lately, in order.
6. plan/review/INDEX.md — what the quality gates found.
7. understanding/index.html — the interactive explainer of what was actually built, once generated.
8. Later: plan/TRACE.md (which commit satisfied which criterion), adr/ (why it's shaped this way).

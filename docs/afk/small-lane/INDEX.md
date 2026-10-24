# small-lane — start here

A small bug today has no light path. The diagnose step fixes code before anyone approves the fix, and a separate bug pipeline writes its own tickets. This feature adds a small lane. It proves the bug is real against the specs and reproduces it with a failing test. Then it proposes a fix, waits for approval, fixes test-first, collects proof and opens a merge request, with one skill that writes every ticket. It serves developers who fix bugs and agents who hit defects while they build a feature.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 7 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 11 records |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION-PLAN.md | — |
| Plan | plan/PLAN.md | 12 subtasks, cited — live status in the plan's progress tracker |
| Smoke gate | plan/PLAN.md | — |
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

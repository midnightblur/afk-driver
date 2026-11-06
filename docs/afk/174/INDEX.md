# 174 — start here

A grill page today shows one round of questions at a time, so the developer loses the picture of the whole topic, loses thoughts about other parts, cannot follow how the conversation moved, has no place for questions only other people can answer, and cannot show the page to a product owner or tester without confusing them. This feature turns every page into a living document of the whole topic: one section per part, always current, each with its own changes, with the round's questions on top and every note answered on its own. The grill gains questions for others, a section the developer shows on a shared screen, filtered by who to ask, where answers are ticked or written and then confirmed; the grill cannot end while one is open unless an assumption is accepted, and a finished grill can be called again when new facts arrive. The user is the developer running a grill, with product owners, testers, directors and other teams as readers in meetings.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 5 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 5 records |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION-PLAN.md | — |
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

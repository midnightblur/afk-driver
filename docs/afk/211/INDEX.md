# 211 — start here

A developer who uses afkv2 for real work in another repository cannot use an afkv2 change before it is released, reinstalled and loaded in a new session. /afkv2:dogfood opens an afkv2 agent in a side pane that builds the change in parallel and sends each milestone to the developer's work session, which applies it at once from the worktree, with no release or reload. The user is the developer who builds afkv2 while using it.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | published to GitHub 2026-11-25 |
| Requirement ADRs | adr/requirements/ | 3 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | — |
| Design ADRs | adr/design/ | — |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION.md | — |
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

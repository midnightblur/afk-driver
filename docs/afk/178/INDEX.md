# 178 — start here

The design skill shows its questions one layer at a time, so the developer never sees the whole design, the reasons behind each decision, or a second opinion. This feature gives the design page the grill's experience: living sections in design-level order with a picture per level, dedicated critical-part sections, decisions that cite their requirements and alternatives, a design-patterns section and a performance section, and 2 solution proposers (Claude and Codex) drafting in parallel in herdr panes, with every disagreement shown as a fork. The developer who runs the design skill is the user; the plan approval page also gains an estimate of the agent run time.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 3 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | — |
| Design ADRs | adr/design/ | — |
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

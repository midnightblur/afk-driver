# agent-team-topology — start here

A run today is one agent on one model, so work that needs independent thinking gets a single opinion nobody can check, a single provider's usage limit can halt it, and nothing records what the run started — a failed run can leave processes alive on the machine. This feature lets a run optionally use a team of agents, shaped by a pattern that says which roles exist, which model fills each, how long each lives and which roles may talk directly. One contact agent is the only one the person talks to and the only one that starts and stops the others; everything started is written to a manifest so cleanup can kill it; and roles may run on models from different providers, so one provider's limit moves work rather than stopping it. Team topology and multi-model are independent switches, and with neither turned on nothing changes.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 9 records |
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
2. DESIGN-BRIEF.md if present — the 1–2 page digest; else PRD.md's Problem Statement + User Stories.
3. SDD.md §0 (locked vs free) + §1 (why this design) — full document only if implementing or reviewing design.
4. plan/PLAN.md — solution map + live progress tracker.
5. plan/JOURNAL.md (tail) — what happened lately, in order.
6. plan/review/INDEX.md — what the quality gates found.
7. understanding/index.html — the interactive explainer of what was actually built, once generated.
8. Later: plan/TRACE.md (which commit satisfied which criterion), adr/ (why it's shaped this way).

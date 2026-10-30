# GitHub #153 — start here

afkv2 is the AFK 2.0 beta: a lighter rewrite of the AFK plugin that lets one developer take one ticket from a grill to a Draft change request on Claude Code or Codex. The agent builds it hands-off, and a human merges. Rules load from the plugin itself. Grill and design rounds run on pages drawn from data the agent writes, so the human can annotate anything and reopen any past session. The PRD is published into the Jira ticket after the developer's yes.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 7 records |
| Prototype | PROTOTYPE.md | — |
| SDD | SDD.md | draft |
| Design ADRs | adr/design/ | 8 records |
| Design brief | DESIGN-BRIEF.md | — |
| Verification plan | VERIFICATION-PLAN.md | — |
| Plan | plan-s1/PLAN.md … plan-s4/PLAN.md | 17 subtasks, cited, 4 plan folders (S1-S3 parallel, S4 chain smoke); live status in each PLAN.md |
| Smoke gate | plan-s1/PLAN.md … plan-s4/PLAN.md | minimal gate in each (no VERIFICATION-PLAN.md); plan-s3: red 2026-10-30 (minimal gate) |
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

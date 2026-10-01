# protected-branch-guard — start here

Developers run several AI agent sessions on one repository at once, and a session that forgets to move into its own worktree edits the same files and branch as another, or commits straight onto a protected branch. For every developer who installed the afk plugin, in every repository, each agent session now moves into its own linked worktree before its first change, and the plugin refuses edits and shell commands until it does. Protected branches come live from GitHub or GitLab. Every new worktree runs the repository's own registered setup scripts, and worktrees the plugin made are cleaned up once nothing in them is unsaved.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 8 records |
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

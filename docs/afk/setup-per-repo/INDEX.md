# setup-per-repo — start here

A developer who uses AFK in several local repositories configures all of them with one `/afk:setup` run from any folder. Setup keeps a list of the developer's repositories and, for each one, asks only for what is missing: the team's forge and tracker settings when the repository has no committed AFK file, and the developer's own forge account, assignees and reviewer. Agents create every new worktree under one folder per machine, each repository in its own subfolder, and a guard stops them from creating one anywhere else. Agents keep their working files in the repository, and the developer's note-taking app stays the developer's own.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 6 records |
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

# 158 — start here

After a piece of work merges, its run branch, run worktree, feature worktree and feature branches stay behind on the developer's machine and the remote, and a plain git removal refuses the orphan run branch and can delete an in-use Windows worktree part way. /afkv2:gc cleans up the one merged piece of work of the worktree it starts in: it lists what it will remove, waits for the developer's yes, refuses first on every risk, removes the run branch with no record kept, and gives the developer one command of its own for the session's own worktree. The user is the afkv2 developer at the end of the chain, or the agent in that developer's session after the developer's yes.

## Artifacts

| Artifact | Where | State |
|---|---|---|
| PRD | PRD.md | draft |
| Requirement ADRs | adr/requirements/ | 2 records |
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

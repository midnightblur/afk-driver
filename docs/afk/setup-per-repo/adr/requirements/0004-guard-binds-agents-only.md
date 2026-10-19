# The worktree root binds agents only

> Status: Accepted
> Audited: 2026-10-16
> Layer: Requirements
> Context ticket: setup-per-repo

The guard refuses an agent's worktree of a listed repository outside the root, with no agent-settable bypass. A developer can still create a worktree anywhere from their own terminal, because the requirement covers worktrees created by future agents only.

## Considered Options

- A hook that checks every user's worktree target: rejected, because it blocks the developer's own choices.

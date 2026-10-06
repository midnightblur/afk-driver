# A linked worktree has one live holder, or one team

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

Two agent sessions in one linked worktree collide as surely as two in the main checkout. The guard refuses an identified mutation in a linked worktree that another live session holds, unless both sessions belong to one group. This keeps the intent of [ADR-0001](0001-on-for-every-plugin-user.md): a linked worktree owned by its session or its team.

## Decision

- **Identity** is the harness process, written `pid:creation time` (`scripts/worktree_owner.py`, resolved as `AFK_WORKTREE_OWNER`, else the nearest non-shell ancestor). A session with no nameable owner is not checked.
- **Group** is `AFK_WORKTREE_GROUP` when set. Otherwise it is `herdr-tab:<HERDR_TAB_ID>` when `HERDR_ENV=1`, so agents a human starts in one herdr tab share a group with no setup. Otherwise there is no group. Two sessions share a group only when it is non-empty and equal.
- **The record** is `<common>/afk-occupancy/<worktree gitdir name>.json` with the path and a list of occupants (pid, creation time, group, session, `since`). It is separate from the cleanup owner records in `afk-worktrees/`, and cleanup never reads it.
- **The rule.** On an identified mutation in a linked worktree on an unprotected branch, the guard drops dead occupants and checks the rest. Another live occupant outside the session's group refuses the call, naming the occupant (session, pid, since) and the move. When none refuses, the session registers. A refused session is not registered: a registered refusal would block the holder on its next call.
- **Liveness** is `worktree_owner.state`. A live pid with another creation time is a recycled pid and counts as dead. An unreadable creation time is unknown and counts as occupied. A process that is gone is dead. Cleanup uses the same function, so a recycled owner pid now lets cleanup treat the owner as dead.
- **The lock.** Read, prune, decide and write happen under one cross-process lock, `<record>.lock`, created with `O_EXCL`, taken over after 10 seconds, waited on for at most 2 seconds. A busy record refuses with "occupancy record busy". A record that cannot be read or written names no occupant, so it allows.
- **SessionStart** (`hooks/protected-branch-occupancy.py`) registers the session first, under the same lock, then prints one advisory line when another live session holds the worktree. It never blocks.
- **The main checkout has no occupancy.** Every mutation there except the sync is refused, and the sync needs a clean tree, so a second session can only read; a session that moved away keeps its process alive and would block every later pull.
- **The hint.** A refusal for the session's own occupied worktree gets the normal move hint, not "write inside this worktree". A busy record says to retry in a moment, then move to a new worktree.
- **Stale takeover.** The lock's inode and modification time are read at the stale observation and read again before removal; a lock replaced in between stays. A swap between that last read and the removal is the residual window.

## Accepted gap

The group is a trust statement, not a proof: any process that sets the same `AFK_WORKTREE_GROUP` or runs in the same herdr tab joins the holder. A herdr tab that holds unrelated agents shares one group.

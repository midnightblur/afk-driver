# The protected-branch list is asked from the forge, with a cache of at most 5 minutes

> Status: Accepted, amended 2026-10-06
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

"Protected" means what GitHub or GitLab answered in the last 5 minutes. The remote's default branch, `main` and `master` are asked at every check. Only a definite forge answer is reused. When the forge cannot answer (no network, no login, other forge), the default branch, `main` and `master` count as protected and the session shows one notice. A cached answer lets an agent write to a branch for at most 5 minutes after the forge starts to protect it; a fixed name list misses release and environment branches.

## Considered Options

- Fixed names (`main`, `master`): rejected; misses every other protected branch.
- Forge list cached for one day: rejected; stale for up to a day.
- Forge list on every check, with fallback: chosen first, replaced by the amendment; costs one CLI token read and 2 forge requests per guarded action.
- Forge answer cached for at most 5 minutes, with the default branch, `main` and `master` asked live (chosen): bounds the stale window to 5 minutes for the other branches.

## Amended 2026-10-06 by the human

The first decision asked the forge at every check, with no cache. A guarded action in a linked worktree then cost about 0.6 s, almost all of it the `gh auth token` call and the 2 HTTPS requests. The human accepted a cache of at most 5 minutes for that cost. `AFK_PROTECTION_CACHE_TTL=0` restores the first behaviour.

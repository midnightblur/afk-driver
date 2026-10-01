# The protected-branch list is asked from the forge on every check

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

"Protected" means what GitHub or GitLab says at the moment of the check, with no cache. When the forge cannot answer (no network, no login, other forge), the default branch, `main` and `master` count as protected and the session shows one notice. A cached list lets an agent write to a branch protected after the cache filled; a fixed name list misses release and environment branches.

## Considered Options

- Fixed names (`main`, `master`): rejected; misses every other protected branch.
- Forge list cached for one day: rejected; stale for up to a day.
- Forge list on every check, with fallback (chosen): costs one forge request per guarded action.

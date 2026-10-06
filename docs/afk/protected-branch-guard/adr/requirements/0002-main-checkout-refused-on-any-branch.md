# The main checkout is refused on any branch

> Status: Accepted, with one exception: the base-branch fast-forward of ADR-0011 (the main checkout is still refused for every other mutation on any branch)
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

An agent session is refused in the main checkout even when that checkout sits on an unprotected feature branch. Two sessions in one folder collide whatever the branch is; a protected-branch rule alone would let a second session edit the first session's feature branch.

## Considered Options

- Refuse only on a protected branch: rejected; it misses the collision this feature exists to stop.
- Refuse on a protected branch or in the main checkout (chosen).

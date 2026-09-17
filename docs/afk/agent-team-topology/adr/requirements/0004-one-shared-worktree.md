# All agents share one worktree

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

Every agent in a run works in one worktree, created once per feature or bug — never one per agent. Isolation per agent is the obvious default and was rejected because a repository may be large enough that a copy per agent is untenable, and because a team that cannot see each other's files is not a team.

## Consequences

Shared git state needs an owner: it belongs to the contact agent, and each role owns its own output path. Write arbitration inside the shared worktree is a real cost of this choice and the design must answer it.

# One feature branch; only the builder commits

> Status: Accepted
> Audited: 2026-09-28
> Layer: Requirements
> Context ticket: agent-team-topology

A run's agents share one worktree on one feature branch, and only the agent filling the builder role commits and pushes, one builder at a time, each commit naming the role it came from. This replaces the earlier rule that every spawned agent pushes its own branch (ADR-0003): a worktree has exactly one checked-out branch, so one worktree per feature (ADR-0004) and a branch per agent cannot both hold. The human kept the one worktree and gave up per-agent branches, because every shipped pattern has a single builder and parallel branches would only add a merge step.

## Considered Options

- One worktree per committing agent, each on its own branch. Rejected: it breaks ADR-0004 and adds a merge step and a worktree per agent to create and clean up, for parallel builders no shipped pattern uses.

## Consequences

Roles other than the builder cannot publish in parallel; they write only under the run directory. Parallel builders stay impossible until this record is superseded.

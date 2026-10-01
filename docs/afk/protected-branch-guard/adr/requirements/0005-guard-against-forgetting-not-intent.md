# The guard stops agents that forget, not agents acting on purpose

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

The guard decides on the session's folder and each edit's target. An agent already in its own worktree that writes into another folder through a shell command is out of scope. Closing that gap for a harness run in full-bypass mode needs an operating-system sandbox, which ends full bypass and the agent's herdr access and has no ready tool on Windows; the problem to solve is sessions that forget to move.

## Considered Options

- Also seal other folders with a sandbox around full-bypass harnesses: rejected for the cost above.

## Consequences

A harness with its own worktree isolation still refuses most such writes; a harness in full-bypass mode keeps full bypass.

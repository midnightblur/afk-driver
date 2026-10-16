# A pattern whose role cannot be filled is refused at start

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

When a pattern declares a role that cannot be filled, the run refuses at start and names the role. The friendlier alternative — offer a reduced shape and continue — was offered and rejected: a debate with one side missing is not a debate, and a reader who asked for two models checking each other would receive one model's opinion labelled as a checked one.

## Consequences

Refusing needs a check at start, which sits awkwardly beside the rule that nothing predicts provider availability. The two are reconciled by scope: the start check asks whether a role can be filled at all, never how much quota remains.

# A role's result goes to its report target, not to the contact agent

> Status: Accepted
> Audited: 2026-09-29
> Layer: Requirements
> Context ticket: agent-team-topology

The pattern names each role's report target, and with none named the target is the agent that asked for the role. The result goes only there. The contact agent gets a copy of each finished, parked and exited message to keep the manifest, and reads a result only when it is the target. This replaces the rule that every role reports to the contact agent. A team run by an orchestrator talks to that orchestrator, so the human's screen shows only the orchestrator's reports, while the contact agent alone still keeps the manifest.

## Considered Options

- The result goes to the agent that asked, with a copy to the contact agent. Rejected: it fits a team run by an orchestrator only when the orchestrator asked for every agent.

## Consequences

The run, not the sender, routes a finished message, by the target the manifest and pattern name. When the target cannot be reached, the contact agent passes the result's location to a replacement agent or tells the human.

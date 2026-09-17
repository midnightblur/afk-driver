# Team agents are started one at a time, not through a transport's own team primitive

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

Agents are started individually, and the run manifest is the only record of a team. One supported transport ships its own team and swarm primitives, its own organisation chart and its own link permissions; declining them is surprising enough to record. They were declined because a pattern is data that must drive every transport identically — if team shape lives in one transport's chart, every pattern is written twice.

## Considered Options

- Use the transport's native team manifest. Rejected: its model would win wherever the two disagree, making the declared roles and talk edges advisory.
- Start individually but use its team-stop for teardown. Rejected: that command only knows teams its own team-start created, so with individual starts there is no team for it to stop.

## Consequences

Teardown on that transport is per recorded terminal rather than one team-wide call.

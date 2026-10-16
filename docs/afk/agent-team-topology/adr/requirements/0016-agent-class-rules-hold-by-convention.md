# Agent-class rules hold by convention

> Status: Accepted
> Audited: 2026-09-29
> Layer: Requirements
> Context ticket: agent-team-topology

The rules on which agent may start or stop agents, commit and push, open a change request, write the tracker or write configuration are stated in each agent's brief. No runtime check can tell one agent from another, so nothing refuses a break of these rules. No agent identity reaches any hook: the only signal is agent against human, and no hook sees a file read. The human kept every access rule, labelled with what really enforces it, rather than narrow the rules or build a role check that could not cover reads.

## Considered Options

- Narrow the access rules to the agent-or-human signal a hook can see. Rejected: it deletes rules worth stating.
- Build a role check at runtime, such as a commit gate. Rejected: an agent declares its own role, so a gate stops only an honest mistake, and no check covers file reads.

## Consequences

A start, stop, commit, change request or configuration write by the wrong agent is not refused. Review, or a human reading the diff, finds it after the work; no gate reads it. The run still refuses what it can see. Examples: an undeclared talk edge, a malformed start request, and a start request whose requester is not a live agent.

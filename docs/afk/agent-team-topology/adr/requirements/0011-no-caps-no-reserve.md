# No caps and no reserved share of the usage window

> Status: Accepted
> Audited: 2026-09-28
> Layer: Requirements
> Context ticket: agent-team-topology

No pattern carries an agent, message or spend limit, and no share of a provider's usage window is reserved for the contact agent. An earlier requirement promised that reserve, but it could not be kept: nothing can reserve part of a window it may not measure, and ADR-0001 forbids any quota check. The human chose to cap nothing and let practice show whether a limit is needed, rather than build limits that may never be used.

## Considered Options

- Restate the reserve as size caps on agents and messages. Rejected: a cap is not a reserve, and it adds a limit nobody has shown a need for.
- Read provider usage and hold team work back at a threshold. Rejected: it is the quota check ADR-0001 rules out.

## Consequences

A team can spend the usage window the contact agent needs to answer the human. The requirements state this in one sentence, and nothing enforces a share. A limit, if practice shows one is needed, is a new requirement.

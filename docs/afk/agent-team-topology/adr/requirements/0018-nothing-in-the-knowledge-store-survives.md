# Nothing in the knowledge store survives the run

> Status: Accepted
> Audited: 2026-09-24
> Layer: Requirements
> Context ticket: agent-team-topology

The knowledge store is excluded from version control and deleted with the run, and nothing in it is promoted to another record first. Each run detects its environment again, as detection reads the session it is in, not the machine. This supersedes ADR-0002, whose consequence promoted qualified environment facts into a durable register before deletion.

## Considered Options

- Promote qualified environment facts into the repository's steering files before deletion (ADR-0002). Rejected: those files are prose an agent reads, no program reads a fact back from them, and promotion forces an order on deletion.

## Consequences

Deleting the store needs no ordering guard. A later run finds again what an earlier run found.

# The knowledge store is not durable and is never committed

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

The record agents write as they work serves the run's own agents and nothing else: it is excluded from version control and deleted with the run's other artifacts. A reader expects the opposite — that what several models learned is worth keeping — so the decision is recorded. It was made because the requirements, design and decision records are already the durable record, and a second, agent-written store competing with them clutters the repository with material nobody curates.

## Consequences

Environment facts worth keeping are promoted into the durable register before deletion, and only qualified ones, so the harness does not fill with run detritus. Everything else is gone when the run ends, by design.

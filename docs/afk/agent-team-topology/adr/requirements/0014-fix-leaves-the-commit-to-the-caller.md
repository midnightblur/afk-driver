# afk-lite under /afk:fix leaves the commit to the caller

> Status: Accepted
> Audited: 2026-09-28
> Layer: Requirements
> Context ticket: agent-team-topology

When afk-lite runs for `/afk:fix`, it ends where `/afk:fix` ends today: changes left uncommitted in the working tree and an `OUTCOME:` line. The caller commits, as it does today. This is the one exception to ADR-0010, under which the builder role commits. `/afk:fix` is called from inside other gates, and each caller owns its commit step.

## Considered Options

- The team's builder commits on the feature branch and opens the Draft change request, and `/afk:fix`'s callers stop committing after it. Rejected: it changes three callers for one pattern.

## Consequences

The earlier requirement that afk-lite runs to a Draft change request no longer holds under `/afk:fix`. The builder role inside `/afk:fix` writes code and tests but does not commit.

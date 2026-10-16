# The /afk:bug publisher and fixer keep today's grants as pane agents

> Status: Accepted
> Audited: 2026-09-30
> Layer: Requirements
> Context ticket: agent-team-topology

As pane agents, the `/afk:bug` publisher and fixer keep the rights they have today, as 2 stated exceptions to the spawned-agent rules. The publisher creates 1 bug ticket, moves it once to Dev-Pending and adds evidence comments to that ticket. The fixer commits, pushes, opens 1 Draft change request and marks it ready, only on its own fix branch, and never merges. Both rights hold by convention (ADR-0016). The grants of `/afk:bug` do not change, and every other spawned agent stays denied.

## Considered Options

- The publisher and the fixer only return results, and the contact agent writes the tracker, commits, pushes and opens the change request. Rejected: more of `/afk:bug` changes, and the contact agent does every fixer's git work.

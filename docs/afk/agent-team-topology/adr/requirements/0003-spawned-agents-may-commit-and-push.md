# A spawned agent may commit and push its own branch

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

A spawned agent commits and pushes its own branch; it does not open the change request, and no agent merges. A reader reasonably assumes autonomous agents are kept away from the remote, and an earlier draft of these requirements banned pushing outright. That ban was overturned deliberately: keeping local and remote in sync is what makes an interrupted run recoverable, the work lands on feature branches, and merging — which stays with the human — is the guard that makes the write access safe.

## Consequences

The ban was also unenforceable as written, because no limit is imposed on a spawned agent's freedom. Stating the permission honestly is better than stating a rule nothing upholds.

# Role agents are pane agents by default

> Status: Accepted
> Audited: 2026-09-28
> Layer: Requirements
> Context ticket: agent-team-topology

Whenever the plugin is enabled and a pane transport is found, every agent that does a role's work starts as a pane agent: one that writes a plugin artifact, code or a ledger, or returns a gate verdict. An agent that only reads and returns text to its parent is a helper subagent, started by a pane agent for itself to keep its own context small; the plugin's named helper types and model tiers still apply to it. One configuration key switches role agents back to subagents. The human set this direction: role agents are visible and own their context, and a subagent cannot write a report file, because the harness refuses it.

## Considered Options

- Every agent the plugin starts is a pane agent, digesters and test runners included. Rejected: many short panes for one-paragraph digests, against the human's words that subagents are helpers.
- Pane agents only when the human picks a team pattern. Rejected: it keeps the report block and contradicts the direction.
- Pane agents only when the repository's configuration turns them on. Rejected: the default stays subagents.

## Consequences

A session with the plugin enabled changes behaviour with no configuration, wherever a pane transport exists. The earlier rule, that with nothing configured the plugin behaves as before, now holds only with the switch set back or no pane transport. Every spawn step that starts a role agent changes, and only the contact agent starts pane agents, so a role agent waits for the contact agent's turn to end.

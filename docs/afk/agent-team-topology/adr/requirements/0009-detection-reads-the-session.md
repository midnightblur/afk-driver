# Detection reads the session, and a disabled setting is reported as fixable

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

Detection reports which tools are usable in the session the human and agents occupy, not which are installed on the machine. It locates a tool's command in the user profile rather than trusting the command path alone, and it never asks a tool's background service whether team control is possible. A tool whose command is present but whose required setting is disabled is reported as a named fixable setting, not as missing.

Each clause comes from a failure made while writing these requirements: a tool installed and licensed was reported unusable because only the command path and the installation directory were checked, while its command sat in the user profile; and its background service deliberately exposes no team-control verb, so asking it would answer no for a tool that can.

## Consequences

A detector that knows specific locations and specific error text is more brittle than one asking the command path. That is accepted: the failure it prevents is silent and misleads the user about their own machine, while the failure it risks is loud and fixable.

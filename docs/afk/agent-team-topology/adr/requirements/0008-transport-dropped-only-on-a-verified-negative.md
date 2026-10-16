# A transport is dropped only on a verified negative

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

A supported transport is removed only when a verified capability check shows it cannot do what the feature needs — never because no evidence of the capability was found. One transport ships graded surface-verified and trial-pending: its commands were read from the installed binary's own help but have never been run, because the trial needs the desktop application open with a setting enabled.

This rule exists because the opposite was done and was wrong. That transport was twice reported unusable: once from an unexamined report that its command was absent from the command path, and once from an activity log that records the calls that happened to be made rather than the capabilities on offer. Both were absence of evidence presented as evidence of absence, on a machine where the tool is installed and licensed.

## Consequences

This deliberately bends the standing rule that every unproven claim is trialled before requirements are settled, once, by explicit human decision. A later failing trial edits the transport's requirements; it does not automatically drop the transport, because the present symptom is a disabled setting rather than a missing capability.

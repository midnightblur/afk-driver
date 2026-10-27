# Finalize definitions before settlement

> Status: Accepted
> Audited: 2026-10-19
> Layer: Requirements
> Context ticket: P2P-2067

Definitions can remain provisional when a merge request becomes Ready. Every affected definition must have final owner state before `/afk:settle-change` settles the change.

## Considered Options

- Require owner finalization before Ready.
- Allow normal review to finalize definitions, then block settlement until complete.

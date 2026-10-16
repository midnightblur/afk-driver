# Cleanup does not rely on agents registering what they start

> Status: Accepted
> Audited: 2026-09-17
> Layer: Requirements
> Context ticket: agent-team-topology

Cleanup must kill a background process an agent started and never recorded. The original requirement assumed closing an agent took its descendants with it, so a manifest of registered processes was a safety net over an operating-system guarantee. A live trial refuted that assumption: a headless parent exited cleanly with status 0, and both a child and a grandchild kept running until killed by hand.

## Consequences

The manifest is not a net over something else — it is one of two mechanisms, alongside an operating-system job owning each agent's process tree. This is recorded so nobody restores the simpler registration-only design on the reasonable-sounding grounds that closing a parent ought to be enough. It is not, on this platform, and that is measured rather than assumed.

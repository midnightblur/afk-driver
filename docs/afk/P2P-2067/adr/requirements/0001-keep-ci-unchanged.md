# Keep CI unchanged

> Status: Accepted
> Audited: 2026-10-19
> Layer: Requirements
> Context ticket: P2P-2067

AFK skills enforce the glossary lifecycle without CI changes. This preserves the owning team's boundary but accepts that a human can merge without running AFK.

## Considered Options

- Add a required merge check that recomputes glossary fingerprints.
- Keep enforcement inside AFK and record the bypass risk.

## Consequences

`/afk:settle-change` can refuse settlement, but the forge does not prevent a manual merge.

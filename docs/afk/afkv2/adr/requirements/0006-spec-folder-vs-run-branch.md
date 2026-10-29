# The spec folder merges with the change; the run branch holds run files only

> Status: Accepted
> Audited: 2026-10-29
> Layer: Requirements
> Context ticket: GitHub #153

The feature's spec folder sits on the feature branch and merges with the change. It holds the grill log, the PRD and requirement ADRs, the SDD and design ADRs, the page documents and INDEX.md. The orphan run branch holds only run files: the plan folder, journal, decision ledger and review telemetry. Why: the owner keeps the PRD and the page documents apart from run files (GRILL-LOG V-6 note, W-3; decision 73).

## Consequences

- In a repository the team does not own, the spec folder merges into that team's code. The good-guest rule applies to it.

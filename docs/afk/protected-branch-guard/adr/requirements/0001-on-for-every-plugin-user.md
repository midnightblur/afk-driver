# The guard is on for every plugin user in every repository

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

Agents of a developer who installed the afk plugin must work in a linked worktree owned by their session or their team (ADR-0013) in every repository, including repositories with no afk configuration, with no opt-in step. The failure it prevents — two forgotten sessions sharing one checkout — happens precisely where nobody thought to opt in, so a per-repository opt-in would not reach it.

## Considered Options

- Off by default, per-repository opt-in in `.afk/config.yaml`: rejected; it fails in the repositories where nobody remembered.
- On for all plugin users (chosen): delivered as a managed behavior plus plugin hooks; a developer without the plugin is never affected.

## Consequences

Every plugin user sees refusals after upgrade; the changelog marks the release as a behaviour change, and it ships only after live runs pass on every supported harness and herdr.

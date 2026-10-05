# Repositories register worktree setup scripts in their hooks manifest

> Status: Accepted
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

A repository registers its own worktree setup scripts as a `WorktreeCreated` event in `.afk/hooks.json`; the plugin runs them once per new worktree, after copying files and setting up the build. The scripts are tracked in git but run only through the plugin, so a developer without the plugin is never affected. A failing script leaves the worktree in place and prints a warning naming it: a half-set-up worktree is still usable, and removing it would destroy the session's place to work.

## Considered Options

- A fixed script path the plugin looks for: rejected; runs unregistered code and gives no order.
- Remove the worktree when a script fails: rejected; one broken script would block every session.

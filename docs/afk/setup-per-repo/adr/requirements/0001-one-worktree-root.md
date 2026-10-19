# One worktree root per machine

> Status: Accepted
> Layer: Requirements
> Context ticket: setup-per-repo

Agents create every new worktree of every listed repository under one root folder per machine, not under a folder per repository. A harness can have only one worktree path setting (the Codex app has one root), and one root also makes setup shorter. The root lives only in the machine file and must be absolute and outside every repository.

## Considered Options

- A worktree folder per repository, beside its main checkout: rejected, because a harness with one path setting cannot follow it.

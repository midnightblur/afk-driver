# Two clones of one remote are two repositories

> Status: Accepted
> Audited: 2026-10-16
> Layer: Requirements
> Context ticket: setup-per-repo

A repository is one clone: its main checkout and that checkout's worktrees. A second clone of the same remote is a separate entry in the repository list, with its own settings and its own short name under the root. Settings are not keyed by remote URL.

## Considered Options

- Key settings by remote URL, so every clone of one remote shares them: rejected, because two clones can serve different accounts or work.

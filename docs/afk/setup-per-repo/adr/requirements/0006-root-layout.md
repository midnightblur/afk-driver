# Inside the root: repository short name, then worktree name

> Status: Accepted
> Audited: 2026-10-16
> Layer: Requirements
> Context ticket: setup-per-repo

A new worktree lands at `<root>/<repository short name>/<worktree name>`. The short name is the main checkout folder name unless it clashes, and setup refuses a short name whose folder it did not make for that repository. The Codex app makes its own folders in the same root, so this check keeps its folders apart.

## Considered Options

- Flat names with a repository prefix, such as `<repository>-<worktree>`: rejected, because a folder per repository keeps each repository's worktrees apart by path.

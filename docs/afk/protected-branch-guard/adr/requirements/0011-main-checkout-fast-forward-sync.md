# The main checkout may fast-forward its base branch

> Status: Accepted
> Supersedes: ADR-0002 (the main checkout is still refused for every mutation on every branch, except this sync)
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

An agent in the main checkout may run `git pull --ff-only` on a clean base branch. Agents had to leave the main checkout only to bring it up to date, and the pull is the one mutation that cannot collide with another session: it needs a clean tree, and git's own `index.lock` serializes two pulls. Every other mutation of the main checkout is refused on any branch, as ADR-0002 decided.

## Decision

- **The allowed form** is `git pull --ff-only`, or with `<remote> <branch>` that equal the configured upstream. Output flags (`-q`, `--quiet`, `-v`, `--verbose`, `--progress`, `--no-progress`) and `-p`, `--prune`, `--no-prune` are accepted. Any other option (`--rebase`, `-s`, `--no-ff`, a second `--ff-only`) makes the pull a plain mutation. Composition around the pull is allowed.
- **The conditions** are checked before the pull and each failure names itself in the refusal: the session resolves the pull to the main checkout; HEAD is on a branch (not detached or unborn); no merge, cherry-pick, revert, bisect, rebase or sequencer operation is in progress; the branch is the base branch (the remote default from `scripts/protected-lookup.py`, else `main` or `master`); the branch has an upstream; the tracked tree and index are clean (untracked files are allowed).
- **The authorization** is a one-shot record `<common>/afk-session/sync-<session key>.json` holding the branch, the old commit, the upstream ref, and an expiry 120 seconds ahead. The guard writes it only when the whole command line passes.
- **The backstop consumes it.** In `hooks/git-backstop.py`, a reference-transaction update of the base branch (and a hex `HEAD` line) passes only when a live record has the same branch and old commit, the new commit descends from the old, and the new commit equals the upstream ref's commit now. The record survives `prepared` and is deleted at `committed` or `aborted`. `hooks/branch-name-gate.sh` forwards both phases, and only when a `sync-*.json` exists, reading the folder from `$GIT_DIR` (and `commondir`) with no subprocess. A guard or hook run deletes an expired or unreadable record on sight.
- A pull into a linked worktree is a plain mutation judged by that worktree's branch.
- The sync is metered like any allowed shell call ([ADR-0012](0012-change-meter-and-quarantine.md)): a fast-forward alone leaves no listed path changed; `git pull --ff-only && make` is checked after the call.
- A human's pull is never gated.

## Considered Options

- Refuse every pull in the main checkout (ADR-0002 as written): rejected; it forces a worktree for a read-mostly update.
- Allow any `git pull`: rejected; a merge or rebase pull changes the tree in ways that can collide.
- Register the pulling session as a main-checkout occupant: rejected; a session that moved away keeps its process alive and would block every later pull.

## Accepted gap

A failed pull leaves its record live until expiry, 120 seconds. In that window a raw (unhooked) `git reset --hard <upstream>` at the same old commit also passes the backstop. The guard refuses `reset` first, so only a path outside the hooks reaches this. The git hook cannot know the session key, so any live record matching the branch and old commit applies.

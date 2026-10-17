# A change meter detects what the recognizer cannot see; a quarantine holds the session until it is undone

> Status: Superseded by ADR-0014
> Layer: Requirements
> Context ticket: protected-branch-guard (provisional, no ticket)

[ADR-0010](0010-refuse-mutations-not-syntax.md) lets opaque and unknown commands run in a guarded checkout. The **change meter** (a before-and-after snapshot of each guarded checkout around a shell call) finds a change such a command made. A **quarantine** (a hold on the session that changed a guarded checkout) then refuses the session's tool calls until the change is undone. Detection comes after the call. It reduces the damage; it does not prevent the first write.

## Decision

- **What is watched.** Every guarded checkout an allowed shell call can enter: the session's own folder plus each folder a literal `cd`, `pushd`, `Set-Location`, `git -C` or `env -C` names (the recognizer's folder tracking). The checkouts are the main checkout (any branch) and a linked worktree on `main`, `master` or the remote default branch when the protection verdict says protected.
- **The snapshot** is `git status --porcelain=v1 -z --untracked-files=normal`, plus per listed path: a content hash for a regular file up to 8 MiB, size and modification time for a larger file, the link target for a symlink, and the modification time for a collapsed untracked folder. A rewrite with identical content is no change. The PreToolUse guard writes it for an allowed shell call; the PostToolUse handler `hooks/protected-branch-meter.py` compares and never blocks.
- **The pre record** is one file per call in `<temp>/afk-guard-pre/`, named by session, call id and a digest of the working folder, and it carries one snapshot per watched checkout, each with its root. The call id is the harness's `tool_use_id` when the event carries one, else a sha1 of the command text. The post handler looks up the id, then the oldest record of the session with the same command hash, so parallel calls each compare with their own snapshot. A record older than 1 hour is deleted on sight. The H-2 PreToolUse envelope carries `tool_use_id` (`providers/CONFORMANCE.md` P0-c). Whether either harness's PostToolUse event carries it is unverified live; a post event that finds no record by id uses the command-hash path.
- **The fast path.** A call whose every segment is a known non-writer with no redirect target skips the snapshot: common readers (`cat`, `ls`, `grep`, `find` without write actions, `echo`, `sort` and `uniq` without an output file, `jq`, `stat` and similar), read-only git verbs (`status`, `log`, `diff`, `show`, `branch` without a name, `remote -v`, `worktree list`, `rev-parse`, `ls-files`, `fetch` and similar), the read routes of `gh` and `glab`, `herdr`, and PowerShell `Get-*`, `Select-String`, `Test-Path`, `Resolve-Path`. It is an optimization only: an unknown program is always metered. The post handler returns at once when no pre record exists.
- **The hold.** When a path differs, the handler injects the paths and the recovery as context and writes `<common>/afk-session/<session>.<root digest>.quarantine`, one per watched checkout. While any listed path still differs from its snapshot entry, the guard refuses every tool call of that session in that checkout, except inspection (`git status`, `diff`, `log`, `show`), moving into a worktree, and the named recovery. The hold lifts when no listed path differs. `AFK_ALLOW_PROTECTED=1` lifts it.
- **The recovery** runs from any folder, because the session must move first: `git -C <root> restore --staged --worktree -- <paths>` for a path that was clean before the call, `rm -- <root>/<path>` for a new untracked path, `git -C <root> rm -f -- <path>` for a new staged path (each line is rooted at the held checkout, so it runs verbatim from any folder), and `cp` of a changed file out to a place outside every guarded checkout. The message gives the order: move into a worktree, copy the changed files there, then restore the checkout. Printed paths are shell-quoted.
- **Work that was already dirty** belongs to a human. Before each metered call the snapshot keeps the bytes of every listed file up to 8 MiB under `<common>/afk-session/blobs/<sha256>`, written only when absent. For a path already dirty before the call, the message prints a `cp` that copies those bytes back, says a human runs these lines in their own terminal and an agent never runs them, and says the index state is not restored. It never prints a restore to HEAD for such a path, and the agent never runs it. A blob unused for 24 hours is deleted on sight.
- A sync ([ADR-0011](0011-main-checkout-fast-forward-sync.md)) is metered.

## Accepted gaps

- Ignored files, and the contents of a collapsed untracked folder (the folder keeps its modification time only).
- A folder that holds a linked worktree: cutting a worktree changes it, so it is dropped from the snapshot, and a file created directly in it is not seen.
- Background work (`run_in_background`, `Monitor`): the process writes after the compare ran.
- Non-shell tools are not metered.
- A linked worktree on a protected branch with another name than `main`, `master` or the remote default is not metered. The guard still refuses identified mutations there. Metering it would need the forge protection verdict (about 0.6 s) on every shell call in every correctly placed worktree.
- A file over 8 MiB that was dirty before the call has no saved copy.

## Cost

Measured on a throwaway repository on Windows, median of 7 runs of the PreToolUse guard plus the PostToolUse handler for a read in the main checkout: `git status` 287 ms before the fast path and 179 ms after; `ls` 280 ms and 191 ms. The floor is two Python starts.

## Considered Options

- Refuse unknown commands in a guarded checkout: rejected ([ADR-0010](0010-refuse-mutations-not-syntax.md)).
- Recover with `git stash`: rejected. A stash takes work that was not the agent's.
- Meter only the session folder: rejected. A session in a worktree that runs `cd <main> && npm install` changes the main checkout.

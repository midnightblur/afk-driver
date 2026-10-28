midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 4 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-009-worktree-failure-paths/COVERAGE.json

## Answer

Creation never rolls back. In `scripts/create-worktree`, every hard failure exits 1 with `ERROR=` on stderr (`:68`). Success prints `WORKTREE_PATH=` as the last stdout line (`:516`).
- **Before `git worktree add`** (`:126-399`): nothing is left, except the parent folder made by `mkdir -p` (`:405`).
- **A failed add**, observed on git 2.53 in the repository's own test temp repo: the new branch stays. No worktree folder, no `.git/worktrees` entry and no owner record are made, and the lock is released.
- **A failure after the add** leaves the worktree registered, its folder and its branch. Name mode also leaves:
  - the exclude lines (`:435-442`);
  - the owner record (`:443`);
  - partial copies (`:449-479`);
  - no `afk-copied.json`.
- **Five steps only warn**, then exit 0: the owner record (`:445`), the copied-file hashes (`:485`), provisioning (`:495`), the IDE open (`:502`), and the `WorktreeCreated` scripts (`:513`).
- **Branch mode** writes no lock, no owner record and no exclude lines (`:433`).
- **No `ERROR=` line** (inferred from the code):
  - after a kill: SIGKILL or TerminateProcess runs no script code;
  - after a `set -u` abort, which only an unset `HOME` reaches (`:245`).
  A failure inside a command substitution can print a second `ERROR=` line; `afk-move.py:115` reads the last one.
- **The harness hook** (`worktree-create.sh:28-30`): a non-zero exit, or `run-hook.py`'s exit 0 with no path after the deadline (`:614-618`), fails the creation. The `claude` hooks reference says so. The harness names no cleanup (inferred: none). `codex` has no such hook.
- **Other callers:**
  - The H-2 move retries under the same name after 180 s (`h2_move.py:91-93`).
  - `afk-launch.py:76` reports "no worktree was made" even after a successful add.
  - npm's exit 4 still leaves a `provisioned` marker (`npm/worktree-provision.sh:91,140`; `worktree-provision:161-163`).
- **Cleanup:** none, unless an owner record exists. Then the prune at session start handles it.

`scripts/remove-worktree.py` keeps a worktree; it never refuses one. "The remover refuses a changed or busy worktree" is refuted.
- **Uncommitted changes, or commits no other branch or remote holds:** it keeps the worktree, writes `kept.json`, and prints resume and remove commands (`:334-336`, `:236-248`).
- **Another live or unknown owner:** `--path` prints one stderr line and writes no `kept.json` (`:402-405`). `--prune` skips it silently (`:439`).
- **No owner record** (branch mode, plain git): never touched (`:397-407`).
- **`--force`** skips both checks (`:334`, `:402`).
- **Exit codes:** 0 for every handled call, 2 for a malformed one (`:507`; the docstring says 1), and 1 for `--force` run from inside the worktree.
- It never reads occupancy records. Commits that also sit on another local branch do not count as unpushed (`:202`).

Other removers:
- **The guard** refuses an agent's `git worktree remove` when the worktree has changes, when another session occupies it, or when a flag is passed and no ignored files remain (`protected_branch_guard.py:462-476`, `:628`). It does not check unpushed commits.
- **`/afk:gc`** skips a worktree whose verdict is `dirty` or `unmerged` (`gc-check.sh:176-186`).
- **`settle-change/SKILL.md:102`** gives a cleanup that the guard refuses.

Tests: create-worktree 26/26, worktree-provision 37/37 and gc-check 26/26 smoke checks pass. pytest: 136 passed, 15 failed, 1 skipped. The 8 failures read all fail at `git worktree add` because the temp path is too long. The other 7 were not read.

## Frontier
- B14: harness cleanup of leftovers (inferred none); bash EXIT trap on SIGTERM; grandchildren after the 900 s timeout (`afk-move.py:111`).

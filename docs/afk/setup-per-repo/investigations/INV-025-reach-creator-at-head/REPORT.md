midnightblur/afk-driver@55b4098acbc039fa5506695c4e4ea6dc1fdeb56c · partial · boundaries 12/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-025-reach-creator-at-head/COVERAGE.json

## Answer (HEAD 55b4098; the worktree holds uncommitted placement edits, read from a clean clone)

**Creator callers and what they read.**
- `hooks/worktree-create.sh:26` runs `--name <name> --session <id> --provision-detached`. It reads the exit status and the last `WORKTREE_PATH=` line (`:28`), never `ERROR=`. It prints the bare path (`:33`). On exit 0 with no path it exits 1 (`:30-31`).
- `hooks/hooks.json:80-90` is the only registration: `run-hook.py --deadline 570`, timeout 600. A value event passes stdout only on exit 0 with non-empty stdout (`hooks/run-hook.py:99,613-628`). A missing handler file returns 0 with empty stdout (`:1043-1045`).
- `scripts/afk-launch.py:57-62` runs `--name session-<hex>`. It reads the last `WORKTREE_PATH=` line and the exit status; the error text is the whole stderr.
- `scripts/afk-move.py:109-116` runs `--repo --name --session`. It reads the last `WORKTREE_PATH=` line, the exit status and the last `ERROR=` line on stderr.
- The creator calls itself in `--finish` mode, detached through `h2_move.spawn`, and reads nothing back (`scripts/create-worktree:576-590`).
- Skills: `skills/afk/bug/SKILL.md:67`, `skills/utils/settle-change/SKILL.md:70-72`, `skills/afk/execute/SKILL.md:16`, `SAFETY.md:45`.

**h2_move callers.** The guard's `owner_key` calls `owner_env` and reads `AFK_WORKTREE_OWNER` (`protected_branch_guard.py:389-396`). `h2_hint` calls `plan` and reads `error`, `pane` and `path`; it runs only for H-2 harnesses (`:447-465,582`). The creator and `remove-worktree.py:364-368` call `spawn`. Only `plan` calls `owner_is_dead` (`h2_move.py:96`).

**How it works.**
- `--name` puts the worktree in `<main>/<AFK_WORKTREE_FOLDER | provider worktree_folder | .claude/worktrees>/<name>` (`create-worktree:262-269`).
- `--branch/--dir` uses `--parent` as given. Otherwise it uses `resolve worktreeBasePath`, which gives the developer value or else `<main>-worktrees`. The last fallback is `~/repo-worktrees` (`:279-296`).
- Every failure writes `ERROR=` to stderr and exits 1 (`:74,79-80`). A failing `$(...)` prints 2 `ERROR=` lines.
- `plan` puts the worktree in `<root>/<folder>/session-<8 hex>` (`h2_move.py:74-86`), the same folder rule without the `..` check.

**Design statements contradicted.**
- "The creator runs git only after every check passed" is false. It runs read-only git during the checks. It also runs `git worktree prune` and mkdirs the parent and the lock before the base, taken-name and branch checks (`:437-499`).
- "The hook exits non-zero with empty stdout on a creator failure" holds for the hook itself. But a failure after `git worktree add` leaves the worktree on disk (`:513,567`).
- "Every code caller reads the `WORKTREE_PATH=` line" holds for the 3 production callers. The `--finish` self-call and the acceptance tests do not read it.
- Documents refuted: `CONFIG.md:263`, `skills/afk/setup/MANIFEST.md:1003`, the creator header `:63`, and the `ERROR=` read in `skills/afk/bug/SKILL.md:67`.

## Frontier
- B14: the claude harness reading the hook's stdout; consuming repositories' WorktreeCreated scripts; the herdr pane that receives `/cd`; whether `hooks/tests/hook-smoke.sh:348-364` starts a real afk-move run under codex (inferred).

## Unverified / partial
- B1 is partial. Its universe leaves out `docs/afk/*/investigations/**`: a whole-tree pass returns 28394 hits, which is past the 20000 ceiling.
- Seed claim c-c0a81676, not load-bearing: the name forms hold every reference. The agent counter-search found sites that carry no name form: `protected_branch_guard.py:582` and `run-hook.py:1043`.

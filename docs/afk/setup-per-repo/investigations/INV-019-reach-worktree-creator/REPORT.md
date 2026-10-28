midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 4 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-019-reach-worktree-creator/COVERAGE.json

## Answer

**create-worktree (Q1).** Arguments `scripts/create-worktree:102-128`; mode split `:157-170` (`--name` excludes `--branch/--dir`, opens no IDE).
- `--name` folder `:220-229`: `<main checkout>/<FOLDER>/<name>`; FOLDER = `AFK_WORKTREE_FOLDER`, else provider `worktree_folder` (claude `.claude/worktrees`, codex `.codex/worktrees`), else `.claude/worktrees`. `--parent` is ignored. Branch from `git.branch-template`.
- `--branch/--dir` folder `:238-255`: `--parent` as given (relative stays relative), else `afk-config.py resolve worktreeBasePath` (`afk-config.py:803-837`), else `$HOME/repo-worktrees`; existing folder refused.
- Exits: every refusal `ERROR=` on stderr + exit 1 via `error_exit`/ERR trap (`:68-74`); success `WORKTREE_PATH=` last stdout line (`:516`). Warn-only: owner record, hashes, provisioning (`:495`), WorktreeCreated scripts (`:511-513`, both modes). No rollback after `git worktree add`. Exports `AFK_WORKTREE_OP=1` (`:75`), read by `branch-name-gate.sh:65`, `precommit-gates.sh:44`.

**create-worktree callers (Q2) and what they read.**
- `hooks/worktree-create.sh:25-32` (`--name --session`): last `WORKTREE_PATH=` → bare path. Registered only `hooks/hooks.json:80-90` (deadline 570 s); `run-hook.py:949-958` adds owner, `:614-618` exits 0 empty past deadline. Harness: non-zero or missing path fails creation (code.claude.com/docs/en/hooks). No `codex` entry.
- `scripts/afk-launch.py:57-63` (`--name session-<hex>`): last `WORKTREE_PATH=`. `scripts/afk-move.py:109-116` (`--repo --name`): `WORKTREE_PATH=` stdout, last `ERROR=` stderr → marker.
- Skills: `skills/afk/bug/SKILL.md:67-68` (branch mode, `--no-open`, last line `WORKTREE_PATH=`/`ERROR=`), `skills/utils/settle-change/SKILL.md:70-72` (last-line `WORKTREE_PATH`), `skills/afk/execute/SKILL.md:16` (`--no-open`, reads nothing), `SAFETY.md:43` (`--name`), `AGENTS.md:199`. Inference: settle-change and execute imply branch mode. `ERROR=` is on stderr, so a stdout-only "last line" read misses it.
- Non-callers: `genericity-gate.sh:96` scans it; `.gitattributes:13` pins LF; `change_meter.py:391-393` allows it by path under a hold.

**h2_move.** `plan()` `h2_move.py:66-100`: `<main>/<AFK_WORKTREE_FOLDER | provider worktree_folder | .claude/worktrees>/session-<8 hex>` — a second copy of the creator's folder rule (`create-worktree:225-226`). `.move` marker per session, reused <180 s or while path exists, reset on dead owner; `AFK_MOVE_SPAWN=0` skips; else detached `afk-move.py`. Callers: `protected_branch_guard.py:352` (`owner_env`), `:410` (`plan`, `codex`/H-2 refusals only, reads `path`/`error`/`pane`), `scripts/remove-worktree.py:364-368` (`spawn`, from `worktree-remove.sh`/`worktree-prune.sh`), which also reads markers `:253`.

**decide.** Only caller `main()` `protected_branch_guard.py:738` ← `hooks/protected-branch-guard.py:51`, registered direct in `hooks/hooks.json:73` and `hooks/hooks.codex.json:73`. `git worktree add`: no operation (`shell_mutations.py:456-457`) → allowed (`:599-601`), refused only under a change-meter hold (`:582-591`). `git worktree move` (`shell_mutations.py:393-399`) refused for unresolvable target, guarded/held source, any option, guarded/held destination (`:622-639`); the hint is `retirement_hint` (remove wording). Refusals exit 0 with deny JSON. `AFK_ALLOW_PROTECTED=1` skips `decide` (`:736`).

**Tests.** create-worktree: `test_create_worktree_name.py`, `test_protected_branch_acceptance.py`, `test_hook_failures.py:443`, `test_native_contract_events.py`, `test_bench_hooks.py`, `create-worktree-smoke.sh` (not in CI, `tests.yml:63-67`). Guard: `test_shell_mutations.py:44,58`, `test_protected_branch_acceptance.py:505-508` (allowed move only). h2: `test_h2_move.py`, `test_run_hook.py:389,440`. Unguarded: every move refusal cause, add/move under a hold, `--branch` default parent, `--name` under `codex`.

**Documents the code refutes.** `CONFIG.md:235` (setup scripts run in both modes); `skills/afk/setup/MANIFEST.md:1003` (misses `h2_move.py:77` as an `AFK_WORKTREE_FOLDER` reader); header `create-worktree:57` (absolute path) vs relative `--parent`.

## Frontier
- B14: `claude` reading the WorktreeCreate stdout (rule cited from vendor docs, not exercised); consuming repositories' WorktreeCreated scripts; harness reading the guard's deny output; herdr pane receiving `/cd`.

## Unverified (4, none load-bearing)
- c-2fa6f5cb: seed claim that the name forms hold every reference; the agent counter-search found paths no name form carries (`remove-worktree.py:364-368`, `branch-name-gate.sh:65`, `git-backstop.py:87`, `install-git-hooks.sh:101`).
- c-458ca8e3, c-ab285d8b, c-7f555cf9: harness-side readers (deny output, `/cd` line, WorktreeCreate envelope fields, where a harness tool lands when the hook fails): outside this repository.

midnightblur/afk-driver@2e934894cd49ae1aa0a9d3ecf37de2ae2d2e20e3 · closed-with-frontier · boundaries 13/14 · unverified 3 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-014-seam-worktree-guard/COVERAGE.json

## Answer

| Seam | Verdict | Behaviour changes others depend on |
|---|---|---|
| (a) `create-worktree` placement + exit 3 | reworked, listed repositories only | `.claude/worktrees` landing (`test_create_worktree_name.py:76,89`); `worktreeBasePath` in branch/dir mode (bug K3 `skills/afk/bug/CONFIG.md:30,39,69`, `SKILL.md:67`; setup H6 `MANIFEST.md:196-197`); `--parent` and `AFK_WORKTREE_FOLDER` overrides; folder exclude line `:437` |
| (b) `h2_move.plan()` path | reworked, listed only | `AFK_WORKTREE_FOLDER` override (`test_h2_move.py:220-221`); H-2 hint path (`protected_branch_guard.py:410-417`) |
| (c) guard add/move refusal | extends | none in repository: no skill prose tells agents to run a bare `git worktree add` (`execute/SKILL.md:16` forbids it) |
| (d) owner, occupancy, remover | extends | none; 2 waiter defects for a worktree outside the main checkout |

- Exit contract: `error_exit` always exits 1 and the ERR trap (`create-worktree:68,73`) catches a failed `$(...)`, so exit 3 needs its own path. Callers pass any non-zero through (`worktree-create.sh:30`, `afk-move.py:115`, `afk-launch.py:62`, `run-hook.py:636`).
- Probe: `--parent wts` exits 0 with a relative `WORKTREE_PATH=wts/d` inside the main checkout (header `:57` promises absolute). AC-051 must refuse it.
- Guard: `shell_mutations.py:384,456-457` classifies only `move`/`remove`; add needs a new operation kind. Not `git_mutates`: that would refuse unlisted repositories (AC-055). `:622-625` refuses an unresolvable target; a new add target never resolves. `_git_positionals` (`:331`) keeps values of `-b`, `-B`, `--reason`. `resolve()` (`:200-211`) does not follow links.
- Landmines: `AFK_ALLOW_PROTECTED=1` returns before `decide()` (`protected_branch_guard.py:736`), so it lifts the new refusal. Any exception after an identified mutation refuses (`:602,744`): placement must answer "not listed" before it can fail. The name `placement` is taken (`protected_branch_guard.py:209`). `developer.worktreeRoot` fails `validate` until added to `DEVELOPER_KEYS` (`afk-config.py:73,633`; `test_setup_developer_values.py:167`). `remove-worktree.py:364` loads `spawn` from `h2_move.py`. `remove-worktree.py:339` forces removal and deletes the branch: the design's no-force removal needs its own path.
- Remover defects outside the main checkout: waiter leaves `.wait` 24 h (`remove-worktree.py:361,381,389`); `--path` on a vanished folder exits 0 silently (`:393`).
- Tests: every worktree test uses an unlisted temp repository and the real HOME (`test_create_worktree_name.py:57`, `test_h2_move.py:29-33`, `test_protected_branch_guard.py:56`, `bench-hooks.py:126`). `create-worktree-smoke.sh` is not in CI (`tests.yml:63-67`). Only `test_shell_mutations.py:44` pins a plain add; it stays green.
- Same-commit duties: `FRESHNESS.md:58-59,79`; `SAFETY.md:25`; `hooks/README.md:107-111`; `PROVIDERS.md:46`; `MANIFEST.md:1020`; `CAPABILITIES.md:35`; `.gitattributes` line for a new `scripts/` module.
- Timing (temp repo, temp HOME): guard decision on `git worktree add ../x` median 437 ms. Added load of `afk-config.py` by path + 10-line machine file + 3-entry list: median 1.85 ms warm, 12.8 ms without bytecode cache; cold max 56.6 ms (1 of 21 over 50 ms). `load()` 128 ms. One git process 191 ms median: placement must start none. No bench budget covers the guard (`bench-hooks.py:46,180`).

## Frontier
- B14 `hooks/hooks.json:85`: `claude`'s reaction to a WorktreeCreate exit 3 (AC-052 premise). In-repo, `worktree-create.sh:30` passes the code through.
- `create-worktree:512`: WorktreeCreated scripts in consuming repositories reading `AFK_WORKTREE_PATH`.

## Unverified (none load-bearing)
- Name forms: aliases `afk_worktree_owner`, `afk_h2_move`, `owner_under_test`, `afk_owner` and wire `AFK_CFG_DEVELOPER_WORKTREEBASEPATH`, `WorktreeCreate` searched; other slots not applicable (scripts invoked by path; no wire name).
- HOME readers: 66 lines whole-tree; only `create-worktree:245` changes.
- Which 2 tests `PRD.md:200` means: the PRD names no file.
- A second Windows drive: not exercised (one drive on this machine).

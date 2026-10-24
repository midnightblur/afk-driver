# INV-014 — a fix on a feature branch, and what stops two runs colliding

feat-small-lane@d346cfb · partial · ledger: COVERAGE.json (1943 nodes, 54 claims)

## Answer

A fix can land on an existing feature branch. The only collision guard is per-worktree occupancy: nothing locks a branch, a ticket or a spec folder, and `git push` is not guarded.

- **create-worktree** (`scripts/create-worktree`):
  - `--branch <existing>` attaches to that branch and ignores `--base` (`:22, :407-414`).
  - `--name X --base <feature>` makes a template-named branch at the feature tip (`:389-396, :428`).
  - `--name` alone starts at the session HEAD.
  - It refuses an existing template branch (`:398`), `--name` combined with `--branch`/`--dir` (`:158`), and a branch already checked out elsewhere (`:413-414`; git refuses it too).
  - Every plugin caller uses `--name`.
- **Held branches.** "Held" means a live occupant record per worktree, `<common>/afk-occupancy/<gitdir>.json` (`hooks/lib/occupancy.py:32-51, :91-123`).
  - The guard refuses a mutation in the main checkout, in a protected-branch worktree, or in a worktree another live session holds (`protected_branch_guard.py:284-325, :575, :592`).
  - The backstop ignores occupancy (`git-backstop.py:33-36, :79-84`).
  - `git push` is not a mutation (`shell_mutations.py:23, :386-433`).
  - `git update-ref refs/heads/<held>` run from your own worktree moves another worktree's branch.
- **Cherry-pick** is allowed in the session's own worktree on an unprotected branch, and refused in the main checkout, a protected worktree, or another session's worktree (`shell_mutations.py:331-373`).
- **Getting a fix onto a feature branch today.**
  - `/afk:bug`: the fixer bases on the MR target of the current branch, works in its own worktree and opens a Draft MR. The retest uses a confirmed local merge or a pull (`bug/SKILL.md:65-68, :77, :86-90`; `FIXER-PROMPT.md:18-31`).
  - `/afk:smoke-test` never fixes (`:53, :80, :87`).
  - `/afk:execute` commits what `/afk:fix` edited in place (`execute/SKILL.md:16, :61-67`; `fix/SKILL.md:107`).
- **Two runs at once.**
  - Occupancy is enforced in code: an O_EXCL lock with a 2 s wait and a 10 s stale takeover (`occupancy.py:54-80`).
  - The SessionStart hook is advisory.
  - `/afk:bug`'s single fixer is enforced by skill text only.
  - Nothing guards the same ticket or spec folder.
  - `plan-status.sh` rewrites PLAN.md with no lock.
  - A missing occupancy record fails open (`protected_branch_guard.py:316-325`).

## Findings

- Inferred: a bug that exists only in feature code gets an `/afk:bug` fixer based on `main`, which returns `blocked` (`FIXER-PROMPT.md:26-27`).
- Inferred: preflight PF-1 runs `git merge origin/{target}` (`preflight/SKILL.md:62`), which contradicts `SAFETY.md:21`.
- Plugin defects, out of scope here:
  - `git push` is unguarded.
  - `update-ref` from your own worktree moves another worktree's branch.
  - `--ignore-other-worktrees` puts one branch in two worktrees.
- Untested: `--branch <existing>`, the `:398` refusal, and fail-open on a missing owner.

## Unverified

- B3, B5, B6, B7, B10 had no method, and the B1 alias forms were not enumerated.
- Whether a shell write to `.claude/bugs/` passes the guard.
- 1 of 379 tests failed: `test_an_ignored_file_a_setup_script_creates_keeps_the_worktree_on_removal`. Not triaged.
- Plugin defect: `merge_fragments.py` seed nodes conflict with every tracer node.

## Frontier

B14: git's refusals were probed on git 2.53.0.windows.2 only; other repositories were not checked.

Written by the orchestrator from the investigation's reply; the investigation's own REPORT.md write was refused.

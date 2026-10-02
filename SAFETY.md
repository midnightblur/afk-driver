# SAFETY.md — write boundaries

One home for database writes, Git writes, and change landing.

## Database writes

Run read-only database queries without a permission turn. Before any write,
show the exact statement and target. Get explicit consent for that statement.

## Git safety

Repository rules define protected branches. Do not create autonomous commits
on a protected branch without explicit authority.

Remove only the exact stale Git index lock. First prove that no Git process
owns it. Leave an active or uncertain lock unchanged and report the blocker.

## Change landing

Use one branch and one Draft change by default. Split only for independent
delivery or review. Do not merge the target branch locally.

## Worktree per session

An agent changes a repository only from a linked worktree on an unprotected
branch. The main checkout counts as protected on every branch. A branch is
protected when the forge says so (a protection setting or a ruleset); when the
forge does not answer, the remote's default branch, `main` and `master` count.
In a linked worktree a detached or unborn HEAD passes; a folder outside Git
and `AFK_ALLOW_PROTECTED=1` set by a human at launch pass everywhere. The tool-call guard
(`hooks/protected-branch-guard.py`) enforces the rule first; the installed git
hooks (`hooks/git-backstop.py`) refuse an agent's commit and branch move
again. The tool-call guard allows its conservative set of single read-only
commands before the move. Move a refused session with the harness's worktree tool, else
`${AFK_PLUGIN_ROOT}/scripts/create-worktree --name <name>`.

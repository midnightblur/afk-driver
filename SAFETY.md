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

An agent changes repository files only from a linked worktree that its session
or its team owns, on an unprotected branch. In the main checkout or a worktree
of a protected branch, a shell command runs only when the guard proves it
read-only, or is a plugin script mode that writes nothing there; any other
command is refused before it runs (ADR-0014). A folder change the guard cannot
read refuses every later unproven command, in any checkout. Run builds, tests
and scripts from your worktree. Elsewhere, the guard refuses a mutation
by the resource it changes (ADR-0010). Guarded resources: the main checkout on
every branch, a worktree of a protected branch, and a worktree that another
live session outside your group holds (ADR-0013). The main checkout may
fast-forward its base branch with `git pull --ff-only` (ADR-0011). For a
repository in the repository list, the guard refuses an agent's `git worktree
add`, `git worktree move` destination or creator `--parent`/`--dir` outside
`<root>/<short name>`. In every repository it refuses an agent command that sets
`AFK_WORKTREE_FOLDER` or `AFK_ALLOW_PROTECTED`.

A branch is protected when the forge says so (a protection setting or a
ruleset); when the forge does not answer, the remote's default branch, `main`
and `master` count. A forge answer for any other branch is reused for at most
5 minutes. A detached or unborn HEAD in a linked worktree passes; a
folder outside Git passes every rule but the variable refusal above, and
`AFK_ALLOW_PROTECTED=1` set by a human at launch passes everywhere.

Move a refused session with the harness's worktree tool, else
`${AFK_PLUGIN_ROOT}/scripts/create-worktree --name <name>`.
Team sessions share a worktree through `AFK_WORKTREE_GROUP` (`PROVIDERS.md`).
Mechanics: `PROVIDERS.md` "Protected-branch guard".

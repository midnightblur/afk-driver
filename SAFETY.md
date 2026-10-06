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
or its team owns, on an unprotected branch. Reads, composed commands, unknown
programs and tools that touch no repository run anywhere; the guard refuses a
mutation by the resource it changes (ADR-0010). Guarded resources: the main
checkout on every branch, a worktree of a protected branch, and a worktree that
another live session outside your group holds (ADR-0013). The main checkout may
fast-forward its base branch with `git pull --ff-only` (ADR-0011).

A branch is protected when the forge says so (a protection setting or a
ruleset); when the forge does not answer, the remote's default branch, `main`
and `master` count. A forge answer for any other branch is reused for at most
5 minutes. A detached or unborn HEAD in a linked worktree passes; a
folder outside Git and `AFK_ALLOW_PROTECTED=1` set by a human at launch pass
everywhere.

A shell call can change a guarded checkout in a form the guard cannot read. The
meter reports the changed paths after the call and holds the session until it
runs the printed recovery (ADR-0012). Move a refused session with the harness's
worktree tool, else `${AFK_PLUGIN_ROOT}/scripts/create-worktree --name <name>`.
Team sessions share a worktree through `AFK_WORKTREE_GROUP` (`PROVIDERS.md`).
Mechanics: `PROVIDERS.md` "Protected-branch guard".

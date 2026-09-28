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

midnightblur/afk-driver@5b626636dc59ab48cdf9287e1e59556110cd2f8c · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: docs/afk/setup-per-repo/investigations/INV-026-guard-worktree-rule/COVERAGE.json

## Answer (HEAD 5b62663)

**What breaks.**
- `hooks/lib/protected_branch_guard.py:640-645,763`: `unproven()` lets the plugin's creator call pass whatever its options. With the rule, `--parent` or `--dir` outside `<root>/<short name>` of a listed repository is refused.
- `hooks/lib/shell_mutations.py:602-603`: `git_mutates` returns False for `worktree add`, so the guard reaches `return 0` at `protected_branch_guard.py:854` for a plain add in a linked worktree. The rule must run before that point.
- `protected_branch_guard.py:884-890`: a move destination is judged only against protected branches and occupants today.
- `shell_mutations.py:354` and `read_only.py:21`: a leading `NAME=` is dropped before the read-only proof, and `export` counts as read-only. So an inline `AFK_ALLOW_PROTECTED` or `AFK_WORKTREE_FOLDER` passes everywhere today.
- `refusal()` at `protected_branch_guard.py:436-439` and the fault path at `:971-972` add the `AFK_ALLOW_PROTECTED` bypass line. The new refusal must call `deny()` (`:427`) directly.

**Who runs these today.** No agent-facing text tells an agent to run a bare add or move, or the creator with `--parent`. `skills/afk/execute/SKILL.md:16` forbids the bare add; `skills/afk/bug/SKILL.md:67` passes no `--parent`. Every other add or creator call runs inside a script or hook (`scripts/create-worktree:617-629`, `hooks/worktree-create.sh:26`, `scripts/afk-move.py:114`, `scripts/afk-launch.py:57`), which the guard never judges. Nothing sets either variable inline in an agent command; tests pass them through the subprocess environment.

**Tests that pin today's pass.** No guard-level test feeds the guard `git worktree add`. The pins are module level: `scripts/tests/test_shell_mutations.py:33,44`. The backstop test `scripts/tests/test_protected_branch_acceptance.py:1035` runs git directly. Creator `--name` pins (`test_protected_branch_guard.py:905,1491`) and the unlisted move pin (`test_protected_branch_acceptance.py:515`) stay green. Launch-flag tests stay green because `main()` returns before `decide`. `test_existing_worktree_outside_root.py:409` compares twins that both flip (inferred). The launch sentence in `refusal()` is pinned by `test_protected_branch_guard.py:844`. Unguarded at HEAD: the creator's own add on an existing branch (`scripts/create-worktree:617`), its `--track` add (`:625`) and the forced-move cause (`protected_branch_guard.py:884`).

**Documents that go stale.** `AGENTS.md:201,230`, `hooks/README.md:109`, `README.md:851-858`, `SAFETY.md:23-30`, `docs/afk/protected-branch-guard/adr/requirements/0014-refuse-unproven-shell-commands-before-they-run.md:22`, `docs/afk/protected-branch-guard/PRD.md:60`, and `SAFETY.md:41` ("pass everywhere": the inline-variable refusal has no placement condition, inferred from `SDD.md:134` and `decide` having no early return outside Git). A delta re-read found `skills/afk/setup/MANIFEST.md:1003` stays true: it names who reads the variable, not who may set it.

**Design statements contradicted.** `PRD.md:200`, `SDD.md:132,711`, `adr/design/0002-one-placement-guardian.md:43` and plan `0006-worktree-guard.md:36` say two existing tests pin "a plain add passes the guard". Neither is a guard test.

**Smoke tier.** `hooks/tests/hook-smoke.sh:348-365` runs the H-2 refusal with the real home and no `AFK_MOVE_SPAWN=0`, so under codex `h2_move.plan` reads the real `~/.afk` and can start `afk-move.py` detached. Its verdict does not change: `touch changed` is no worktree command.

## Frontier
- B14: how claude and codex consume the deny JSON and what their own worktree tools run; the developer's real `~/.afk` files; consuming repositories' agents and scripts.

## Unverified / partial
- None left open: a delta pass settled the 36 conflicting nodes, ran the name-form check for every wire and alias form (13 new nodes, all the different provider key `worktree_folder`), and closed B1.
- `AFK_WORKTREE_OP=1` stays settable inline by an agent and skips the commit backstop and the branch-name gate (`hooks/precommit-gates.sh:44`, `hooks/branch-name-gate.sh:65`). A new question, outside this seam.

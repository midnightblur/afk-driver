midnightblur/afk-driver@17ec3223985388dab50ffdc5d04b1b1f27dc99ce · partial · boundaries 13/14 · unverified 4 (load-bearing 3) · ledger: docs/afk/setup-per-repo/investigations/INV-001-worktree-landing/COVERAGE.json

## Answer

Code-driven creation (the WorktreeCreate hook, the guard's H-2 move, `afk-launch.py`) always runs `create-worktree --name`. That mode puts the worktree in `<main checkout>/<worktree_folder>/<name>` and never reads `developer.worktreeBasePath`. No folder value can place it outside the main checkout. Branch mode (`--branch/--dir` without `--parent`) is the only reader of `worktreeBasePath`. `/afk:settle-change` must use branch mode, and so must `/afk:execute` when its branch exists. For `/afk:bug` dispatch the prose names no mode, so its landing is inferred. A plain `git worktree add` passes the guard and lands where its argument says. No hook or script checks where a worktree lies. A worktree nested in the main checkout misleads 6 tools. A relative or `~` base lands inside the main checkout, skips setup, and exits 0.

## Sites

- `--name` callers: `hooks/worktree-create.sh:25`, `scripts/afk-launch.py:57`, `scripts/afk-move.py:109` (from `hooks/lib/h2_move.py:97`). These are the only code callers.
- Folder: `scripts/create-worktree:222-228`; `:227` refuses an absolute or `..` folder. `h2_move.py:77-78` names the path with no shape check; `afk-move.py:115-116` then fails.
- Branch mode: `scripts/create-worktree:238-249`, `:254`. `--name` refuses `--branch` (`:158`) and an existing branch (`:398`).
- Skills: `skills/utils/settle-change/SKILL.md:70,87`; `skills/afk/execute/SKILL.md:16`; `skills/afk/bug/SKILL.md:67` resolves the base first and names only `--no-open`.
- Plain `git worktree add`: `hooks/lib/shell_mutations.py:456-457` (pinned by `scripts/tests/test_shell_mutations.py:44`); `hooks/git-backstop.py:39-40` (pinned by `test_protected_branch_acceptance.py:1029-1036`).
- No location check: `hooks/run-hook.py:1029`, `scripts/remove-worktree.py:82-87,108`, `scripts/worktree_owner.py:250`, `skills/afk/gc/scripts/gc-check.sh:160-168` (finds the worktree by branch).
- Path spelling: a space in the path degrades Maven provisioning (`adapters/build-gate/maven/worktree-provision.sh:114-118`).
- Relative or `~` base, probed: `<repo>/rel-wt/…` or `<repo>/~/…`, provisioning fails (`create-worktree:495`), `WorktreeCreated` skipped (`:512`), exit 0. `afk-config.py:829-838` does not check the shape.
- Nested worktree, probed: `scripts/glossary_usage.py:111`, `skills/afk/agents-md/scripts/mechanical_check.py:72`, `hooks/native-contract-gate.sh:442` (exit 2), `skills/utils/report-issue/scripts/redact.py:341`, `skills/afk/setup/scripts/ancestor_instruction_files.py:88` (exit 1), `hooks/lib/nested_steering.py:229`.
- Not affected: the commit-time gates judge a tree checked out from the index (`hooks/plugin-source-gates.sh:180`); `test_plugin_source_gates.py:438-477` pins them from a sibling worktree.
- Tests: none pins the nested case, directly or through a wrapper (`plugin-source-gates.sh`, `precommit-gates.sh`, `publish.sh`, `nested-steering.sh`).
- Cleanup only for `--name`: `create-worktree:433-445`, `remove-worktree.py:9-11`.
- Docs the code refutes: `docs/afk/setup-per-repo/GRILL-LOG.md:8,17,58,61`, `docs/afk/protected-branch-guard/PRD.md:23,139,212`, `CONFIG.md:136,235`, `skills/afk/setup/MANIFEST.md:214`, `skills/afk/bug/CONFIG.md:43-46`, `scripts/afk-config.py:808-810`. `GLOSSARY.md:324-326` (uncommitted) and `GRILL-LOG.md:33,60,64` state planned design no code implements.
- Machine state: `resolve worktreeBasePath` here returns `<work-repo>`, another repository.

## Frontier

- `hooks/worktree-create.sh:19`, `docs/afk/protected-branch-guard/PRD.md:111`: which harness routes fire WorktreeCreate and honor its path is harness behavior.
- `docs/afk/setup-per-repo/GRILL-LOG.md:15,67`: how `claude` and the `codex` app place and trust their own worktrees is outside this repository.
- B14: other repositories, deployment manifests and live consumers.

## Unverified

- Harness behavior, outside this repository: Claude creation routes and subagent isolation (`c-3a16d3e8`); a `codex` native worktree (`c-dde2db70`); where a harness tool lands when the hook fails (`c-288d7e16`); the recorded no-prompt probe, not rerun (`c-8db28af3`).
- Inferences: the `/afk:bug` dispatch mode (`c-cb05c389`); which variables each harness exports (`c-971f93d5`); Claude loading `hooks/hooks.json` by default (`c-ac61471e`); the Windows encoding failure in `nested_steering.py`, not run through `run-hook.py` (`c-0cbc3281`).
- The seed's pending check for B1 (a name form with no simple name) is complete: delta K supersedes it with the case-blind queries fragment G ran (`q-719a17a2`, `q-19ce120a`).

# Decisions — auto-taken hands-off (protocol + grammar: DECISIONS.md, workflow plugin root). Newest last.

## D-1 — How to re-take the ground of the safe writer seam
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — re-run INV-010 whole (its 9 subjects, type Q1, every settings writer) vs B — a fresh Q3 run on the moved names only (`_atomic_write_locked`, `_target_lock`, `write_if_unchanged`, `InstallError`, `update_locked`, `SafeWriteError`)
- Chosen: B — `git diff 2e93489 288b4b3` is empty for `install_block.py`, its tests and its callers (`developer_values.py`, `setup_secrets.py`, `set_instruction_files.py`, `hook-smoke.sh`); the ground diff's drift lies in files other INV-010 subjects hit, which later slices own
- Supersedes: none
- To reverse: run /afk:investigate on the INV-010 question at the branch head and compare its claims with SDD §14 row "safe writer"

## D-2 — Where the adversarial gate probes in a repository that runs no app
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — report `env_unreachable` and park the slice vs B — probe the shipped module and CLI at runtime with the repository's interpreter in a scratch folder, blind to the diff and tests
- Chosen: B — the slice's promises are behaviour of a library call and a CLI, observable by running them; A parks every slice of a repository that declares no app, which the run's invoker ruled out
- Supersedes: none
- To reverse: re-run Step 10.5 against a provisioned app instance once the repository declares one

## D-3 — What to do with stray copies of other worktrees inside this worktree
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — stop with `test_fail`, since `test_model_tier_gate.py::test_committed_tree_agrees_with_the_tier_table` scans the ignored `.claude/worktrees/` copies and fails on their old `AGENTS.md` vs B — move those 9 ignored, unregistered copies (962 KB) to the session scratch folder and re-run
- Chosen: B — `git worktree list` registers none of them, git ignores them, no tracked file changes, and the gate passes on the tree without them; the failure is not in the slice's code
- Supersedes: none
- To reverse: move the 9 folders back into this worktree's `.claude/worktrees/`

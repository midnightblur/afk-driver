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

## D-4 — How to clear the red unit tier that predates the first slice
- 2026-10-27 · decided by /afk:autopilot (run orchestrator)
- Options: A — make the review-id check and the redactor skip `investigations/*/COVERAGE.json` vs B — mask the quoted fixture values (test secrets, one review id) in the five ledgers that quote them vs C — park the whole plan for a human
- Chosen: B — the failures come from this branch's own spec commit, not plugin code; masking changes evidence text only, which the coverage validator checks for presence, and all five ledgers keep their verdicts; A changes two scanners' behaviour and belongs in its own reviewed change
- Supersedes: none
- To reverse: revert the ledger-masking commit on the branch

## D-5 — Correct the caller list D-1 cites
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — leave D-1's caller list as written vs B — record the real callers and re-check the diff on them
- Chosen: B — `developer_values.py`, `setup_secrets.py` and `set_instruction_files.py` never load `install_block.py`; its real callers are `hooks/tests/hook-smoke.sh`, `skills/afk/setup/SKILL.md`, `skills/afk/setup/MANIFEST.md` (CLI runs) and `scripts/behavior_registry.py` (`REQUIRED_INSTALL_TESTS`); `git diff 2e93489 288b4b3` on them touches no installer call line or required test name, so D-1's choice holds
- Supersedes: D-1 "Chosen" caller list `developer_values.py`, `setup_secrets.py`, `set_instruction_files.py`, `hook-smoke.sh`
- To reverse: none needed; D-1's option B stands on the corrected list

## D-6 — Fix a stale test docstring under the "installer tests unchanged" bullet
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — keep `scripts/tests/test_install_block.py` byte-identical vs B — update one docstring that names the removed `_LOCK_MAX_ATTEMPTS` constant, no assertion touched
- Chosen: B — the Acceptance bullet guards the installer contract the assertions pin; a docstring that names a constant the slice removed is a stale artifact (`FRESHNESS.md` "no artifact goes stale")
- Supersedes: none
- To reverse: revert the docstring lines in `_run_holder_contender`

## D-7 — Correct INV-023's busy-swap exit code
- 2026-10-27 · decided by /afk:execute (0001-safe-writer)
- Options: A — rewrite INV-023's `REPORT.md` vs B — leave the ledger untouched and record the correction here
- Chosen: B — `/afk:investigate` is the single writer of a ledger; the old `main()` (`git show 288b4b3:skills/afk/setup/scripts/install_block.py`, lines 334 and 359) already caught `OSError`, so a busy swap exited 2 before the slice too; the only caller-visible change is up to 10 retries at 50 ms and the message `target file swap stayed busy: <path>`
- Supersedes: INV-023 `REPORT.md` "instead of a traceback (exit 1)"
- To reverse: none needed; a fresh `/afk:investigate` run would carry the corrected line

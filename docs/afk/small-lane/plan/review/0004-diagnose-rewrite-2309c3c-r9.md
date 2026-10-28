# Review — 0004-diagnose-rewrite round 9

- policy: lean · delta round 9 (2309c3c..7dd349d) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 2 medium, 1 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: 7dd349d8d805638f3118d8c1847c9b0c4278909b
- counts: crit=0 high=0 med=2 low=1

## r-001 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The named removal does nothing for a worktree step 3 matched by folder name alone (no owner record): remove-worktree.py touches only worktrees that have a record, and it exits 0 without a word.

- Why: Step 3 matches a worktree 'by its folder or by its record', and worktrees cut with `create-worktree --branch/--dir` or plain `git worktree add` have no record. The person runs the command, sees exit 0, and the next run ends `blocked` again with no explanation.
- Fix: Name the removal only for a record-holding worktree (record `<git common dir>/afk-worktrees/<name>.json` exists); for a folder-only match, name `git worktree remove <path>` plus deleting the branch, or say the script will not act on it.
- Concern: delta-sweep (New defect in the change)

## r-002 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
The blocked reason offers `--force` removal for a case it says may be 'someone else's work', but drops the script's own warning that `--force` discards uncommitted work and skips the check for another live session.

- Why: `--force` skips both assess() and other_owner(), so following the reason as written can wipe a live colleague's or session's uncommitted changes. The script's own keep message labels the same command 'remove (discards that work)'.
- Fix: Say in the reason that the command discards any uncommitted work there and removes it even while another session uses it, and tell the person to use it only on a worktree they know is a stopped diagnose run.
- Concern: delta-sweep (New defect in the change)

## r-003 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
The command runs the .py script bare, with no `afk-python` prefix. That breaks the invocation form every other skill uses and the form the script prints for itself.

- Why: The script depends on its `#!/usr/bin/env afk-python` shebang, which PowerShell does not honor. The sibling `/afk:fix` step and remove-worktree.py's own messages both write `afk-python <script>`.
- Fix: Write `afk-python ${AFK_PLUGIN_ROOT}/scripts/remove-worktree.py --path <path> --force` (and the same in D-24's Options).
- Concern: delta-sweep (Smell introduced by the change)

# Review — 0004-diagnose-rewrite round 11

- policy: lean · delta round 11 (507d029..8c6ffa2) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: scope-and-impact (Scope grep clean; only plan files outside Scope), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface), agents-md-compliance (no new instruction chain) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level finding at medium or above)
- verdict: advisory — 0 high, 0 medium, 3 low
- Gate outcome: r-001 and r-002 fixed; r-003 deferred to the feature gate (low compliance, lean policy)
- head: 8c6ffa22985c6699a3d94236d18c83d80fd02417
- counts: crit=0 high=0 med=0 low=3

## r-001 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
With no owner record, the text gives no rule for the branch `create-worktree --name` would create. The only rule step 4 gives ("filled from `git.branch-template`") is wrong for some templates.

- Why: `create-worktree` fills `{user}` with the git user name and uses `worktree-<name>` when the template has no other placeholder, so a branch filled by hand can name a branch that does not exist; the retry then stops again at step 4 with "branch exists".
- Fix: point at the script's rule (`branch_for_name` in `scripts/create-worktree`).
- Concern: delta-sweep, refactor-safety (New defect in the change; open question)

## r-002 · low · correctness · `skills/utils/diagnose/SKILL.md:34`
With no owner record, the reason names the branch for deletion even when that branch holds a committed `DIAGNOSIS.md` that step 4 resumes as a re-run.

- Why: step 4 cuts a worktree onto such a branch, so the retry does not need it gone.
- Fix: name the branch only when step 4 would not resume it as a re-run.
- Concern: delta-sweep (New defect in the change)

## r-003 · low · compliance · `docs/afk/small-lane/plan/JOURNAL.md:83`
Two earlier autopilot journal lines use an event and a subject outside the journal format, and their plain-terms clause carries finding ids.

- Why: `JOURNAL-FORMAT.md` lists the autopilot events and the subject tokens; `done` and `—` are not among them.
- Fix: use a listed event and subject in later lines; the journal is append-only, so the earlier lines stay.
- Concern: delta-sweep (Documented-rule breach in changed lines)

# Review — 0004-diagnose-rewrite round 5

- policy: lean · delta round 5 (1e91f66..fc15fc0) · activated: delta-sweep, refactor-safety (pre-existing lines modified) · skipped: fix-owner specialists (no critical or high in round 4), scope-and-impact (Scope grep clean), test-veracity (no test code), logic-correctness and code-quality (delta under 150 lines and 6 files), api-contract (no public surface) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level-only finding at medium or above)
- verdict: blocking — 0 high, 3 medium, 1 low
- Gate outcome: blocking; every finding goes to remediation in this settle loop
- head: fc15fc08ca18279fc7b372dd24fc91dfa2fff576
- counts: crit=0 high=0 med=3 low=1

## r-001 · medium · correctness · `skills/afk/fix/SKILL.md:39`
Possible in-place regression: fix now picks its worktree with `git -C <spec folder> rev-parse --show-toplevel`, which returns a different repository's top when an outside spec folder (an obsidian vault) is itself a git repository, so the 'outside the repository' branch never fires.

- Why: In-place callers (execute Step 8, the /afk:bug fixer limited to `{WORKTREE_PATH}`) relied on the old 'linked worktree fix runs in' rule; under this rework a git-tracked vault sends the test-first fix into the vault repository instead of the caller's worktree (inferred from adapters/notes/obsidian CONTRACT 'dir and path are under obsidian.vault, not under the repository'; not exercised).
- Fix: Decide 'inside the repository' by matching the folder's `git rev-parse --git-common-dir` to this repository's (or the toplevel appearing in `git worktree list`), else take the worktree-on-Diagnosis-branch route.
- Concern: refactor-safety,delta-sweep (reworked control flow in an existing method (behaviour-preservation risk))

## r-002 · medium · correctness · `skills/afk/fix/SKILL.md:39`
For a spec folder outside the repository (Obsidian vault) the cut-a-worktree guard `git cat-file -e <Diagnosis branch>:<DIAGNOSIS.md path>` can never pass, so once the diagnosis worktree is gone fix stops `blocked` with a false reason although the failing test is committed on the branch and the diagnosis is readable in the vault.

- Why: The vault path is not a path inside any branch, so the delta's only route for an outside spec folder with no worktree is a wrong `blocked` claiming a handed-over worktree kept the file uncommitted.
- Fix: For a spec folder outside the repository, test the failing test's path on the Diagnosis branch (or skip the DIAGNOSIS.md check) before cutting the worktree.
- Concern: delta-sweep,refactor-safety (New defect in the change)

## r-003 · medium · correctness · `skills/utils/diagnose/SKILL.md:34`
A record-only re-run (no DIAGNOSIS.md yet) sets Base to the base branch at `git merge-base <base branch> HEAD`, which is wrong when the first run cut the worktree from a non-base branch tip; the owner record stores no base, so the original start point is lost.

- Why: Phase 2 then reproduces on 'a clean copy of the Base', a base-branch commit that lacks the feature branch's code, which can turn a real bug into V-5 cannot reproduce and records a wrong Base for fix's 'naming the branch and the Base'.
- Fix: Take the Base commit as the worktree's HEAD (diagnose commits nothing before Phase 7) and the Base branch from the invoker's starting-branch answer, else ask, else `blocked`.
- Concern: delta-sweep,refactor-safety (New defect in the change)

## r-004 · low · compliance · `skills/utils/diagnose/SKILL.md:34`
The delta narrows D-18's re-run detection (a folder named for the work id now also needs a DIAGNOSIS.md) and adds a new Base rule for a record-only re-run, but no ledger entry records either; D-19 covers only fix's worktree and D-18 still states the old detection.

- Why: Executors read the ledger before working a slice and will build on D-18's recorded call, which the skill no longer follows.
- Fix: Append a D-20 entry superseding D-18's "a worktree folder named for the work id" and recording the record-only re-run Base rule.
- Concern: delta-sweep (Documented-rule breach in changed lines)

# Review — 0007-ship-script round 1

- policy: lean · full-unit round 1 (2cfd96b..e5dff91) · activated: spec-fidelity, scope-and-impact, test-veracity, refactor-safety (modified lines), logic-correctness (complex; downstream consumer 0008) · skipped: api-contract, domain-alignment (no trigger) · deferred: code-quality, agents-md-compliance, design-quality, resilience (→ feature gate)
- verified: 0 upheld / 0 downgraded / 0 dropped (no design-level concern ran)
- verdict: blocking
- Gate outcome: all 13 fixed in place (f001-f013); D-47 records the proof-step inputs, the tracked-job IOU on 0008 and the conformance note
- head: e5dff919b7eec23a0d12d2ac65e494047693ec84
- counts: crit=0 high=1 med=10 low=2

## r-001 · high · test · `scripts/tests/test_ship.py:328`
No test ever lets `git push` meet a remote tip it does not contain, so adding `--force` to the push in `_push` passes all 48 tests. I ran that mutant on a copy, and the test named `test_open_never_forces_over_a_remote_fix_branch_it_does_not_contain` passed too, because the read-first check stops the step before any push runs.

- Why: docs/afk/small-lane/plan/0007-ship-script.md Acceptance: "Land fetches, checks the push is a fast-forward and pushes with upstream set by plain git, never forced, refusing a protected target; a non-fast-forward refusal is reported to the caller"; SDD §9b row "Feature-branch push": "remote refuses a non-fast-forward".
- Fix: Add a test in which the remote tip moves between the read-first `ls-remote` and the push. For example, wrap `ship._git` so the first `ls-remote` answers empty, then push a stranger commit from a second clone. Assert that the remote tip is still the stranger commit, nothing is listed, and the status is not-fast-forward or blocked. The `--force` mutant must then fail.
- Concern: test-veracity

## r-002 · medium · spec · `skills/afk/fix/scripts/ship.py:20`
The bullet says Ready runs `ci-wait` as a tracked background job, but the script runs it in the foreground for up to 5700 s and only tells its caller, in the docstring, to run the step as a tracked job. No consumer carries that duty: the 0008 contract never mentions a background or tracked job, and `.claude/wiring-ious.md` has no line for it.

- Why: docs/afk/small-lane/plan/0007-ship-script.md Acceptance: "Ready runs `ci-wait` as a tracked background job polling every 180 s for at most 5400 s"; SDD.md §5: "| CI wait (`ci-wait`) | 1 tracked background job | poll every 180 | 5400 |" and "**Sync vs async.** CI wait runs as a tracked background job, like `/afk:preflight` (D-29)."
- Fix: Hand the tracked-job duty to an anchored consumer. Either add an Acceptance or Produces line to docs/afk/small-lane/plan/0008-standalone-fix.md (SHIPPING.md: run `ship.py ready` as a tracked background job), or record a wiring IOU anchored to 0008 that names `ship.py ready`. A docstring-only instruction is not enough.
- Concern: spec-fidelity

## r-003 · medium · spec · `skills/afk/fix/scripts/ship.py:573`
SDD §8 defines the interface as step name + diagnosis path in, step result out. The proof step also requires `--proof P-1=PATH --proof P-2=PATH`, and `--evidence-link` whenever a ticket exists, and refuses without them. The plan's decision ledger records no such widening: D-45 and D-46 cover only the ground re-check, the marker token and the allow-file line.

- Why: SDD.md §8: "| ship script (beside fix) | named steps open, proof, ready, land | step name + diagnosis path in → step result; skips listed steps |"; contract Acceptance: "Implements the public interface of SDD §8 row \"ship script (beside fix)\" unmodified"; Conflict procedure: "Never override off the record." SDD §4 lets the step find the files without arguments: "Proof files before upload | untracked folder in the fix worktree; names carry the diagnosis id, the kind and the step".
- Fix: Choose one. (a) Derive P-1 and P-2 from the proof-file naming in SDD §4, so proof takes only step + diagnosis path. (b) Record a plan/DECISIONS.md entry with a `Supersedes:` line that quotes the §8 interface cell and names the added proof-step inputs, so 0008 builds against the real signature.
- Concern: spec-fidelity

## r-004 · medium · spec · `skills/afk/fix/scripts/ship.py:554`
Land checks only `protected-lookup`, never whether Base is a feature branch. When the forge says the repository's base branch is unprotected, as on a repository with no branch protection, `ship.py land` on a diagnosis whose Base is `main` fast-forward-pushes the fix straight onto `main`. That push bypasses any change. A developer can run the script by hand, so reaching this does not depend on /afk:fix routing.

- Why: SDD.md §5 AuthZ: "| Merge | nobody | everybody | structural: no forge adapter has a merge verb |"; SAFETY.md "Change landing": "Use one branch and one Draft change by default ... A fix landed on a feature branch is covered by that feature's one Draft change." (that covers a feature branch only); SDD.md §3 /afk:fix row: "for a diagnosis started from a feature branch: the pushed commit and that branch, no ticket, no change"; scripts/protected-lookup.py:228-232 returns a definite forge answer `protected: false` for an unprotected branch, with no fallback to main/master.
- Fix: In step_land, refuse when the target equals the repository's base branch (`git.base-branch` through afk-config, or the remote's default branch) as well as when it is protected. Add a test: an unprotected `main` Base is refused with nothing pushed.
- Concern: spec-fidelity

## r-005 · medium · scope · `adapters/forge/gitlab/forge.sh:422`
GitLab change-reviewers now sends a different glab command line (`--reviewer +name,...`). The live conformance record still says the whole GitLab forge set, change-reviewers included, was proven against a real merge request. The new form has run only against the stub CLI, and no Scope entry, DECISIONS widening or wiring IOU marks the conformance row for a re-run.

- Why: The record proves the old command line, not this one. When the earlier slice changed a tracker verb, it marked that verb in the same file as stub-tested only, pending a live run: providers/CONFORMANCE.md:95 "`tracker_attach` (added later), the Markdown bodies and the refusals are stub-tested only and need a live run before release". The contract's Verification table proves change-reviewers only by a stub (docs/afk/small-lane/plan/0007-ship-script.md:58 "GitLab change-reviewers sends a `+` name").
- Fix: Record a DECISIONS entry that adds providers/CONFORMANCE.md to Scope. Then add a note to the `forge / gitlab` row saying `change-reviewers` (`+` names) is stub-tested only and needs a live run before release. Otherwise, run the verb once against a real merge request and update the row's evidence.
- Concern: scope-and-impact

## r-006 · medium · test · `scripts/tests/test_ship.py:486`
The ci-wait tests check only that a result is `draft` and contains "stays Draft". The reason is checked only for no CI. On a copy I deleted the red, the timeout and the unreadable branch of `route_ci` one at a time, and each mutant passed every ci_wait test, the real-GitLab-adapter tests included; every answer then fell into "ci-wait answer not understood". Making green ignore the exit code (`if status == "success"`) also passed.

- Why: docs/afk/small-lane/plan/0007-ship-script.md Acceptance: "routes on exit code and stdout together: green → change-ready ...; red, timeout, unreadable, and no CI (exit 3 at once) → the change stays Draft and the step reports the reason".
- Fix: In the parametrized test, map each CI_ANSWERS case to its expected reason prefix ("CI failed", "CI canceled", "CI still running", "CI status unreadable", "no CI", "ci-wait answer not understood") and assert it. In test_ci_wait_through_the_gitlab_adapter_routes_each_answer, assert the reason as well as the status. Add one case where the exit code and the status disagree on green, such as `(1, {"status": "success"})`.
- Concern: test-veracity

## r-007 · medium · test · `scripts/tests/test_ship.py:159`
`FakeForge.add` takes a `state` argument, but no test passes anything other than `opened`. The guard that blocks a closed, merged or locked change therefore has no test: setting `NOT_WRITABLE = set()` passed all 48 tests on a copy. Removing the proof step's `_change_by_number` lookup of the listed change also passed every proof test, so a proof comment on a merged change would go unnoticed.

- Why: Checklist "Happy-path-only — multi-branch acceptance logic with one sunny test; missing negative ... cases"; skills/afk/fix/scripts/ship.py:358 blocks with "reopen it or remove its Outside writes entry by hand", a production branch that no test exercises.
- Fix: Add tests that list a change the stub holds as `state="merged"` (or closed) and run proof and ready on it. Assert the result is `blocked` with the state in the reason, and that `forge.writes() == []`.
- Concern: test-veracity

## r-008 · medium · correctness · `skills/afk/fix/scripts/ship.py:588`
run_ship_step catches only Stop, so an exception raised after a write leaves the script with a traceback, no JSON and exit 1, and the docstring defines exit 1 as 'refused (nothing written)'. Probe: a diagnosis with no `## Outside writes` heading passes check_diagnosis (ok=True), then open pushes the branch and creates the Draft, and append_outside_write raises ValueError. A re-run finds the change by branch and raises the same error again, so rationale-post never runs and nothing is ever listed.

- Why: ship.py:32-36 "refused (nothing written); ... Exit 0 for done, skipped, draft and no-change, 1 for refused, 2 for not-fast-forward and blocked." and ship.py:31 "Prints one JSON object: `step`, `status`, `reason` and the step's details."
- Fix: Before the first write, check that the diagnosis has an Outside writes part and that each entry the step will append passes entry_problem (refuse if not). Also add `except Exception as error:` in run_ship_step that returns `{"status": "blocked", "reason": ...}`, so a failure after a write (PermissionError from replace_text, ValueError, or TimeoutExpired from _resolve_setting at ship.py:207) is reported as blocked with JSON and exit 2.
- Concern: logic-correctness

## r-009 · medium · correctness · `skills/afk/fix/scripts/ship.py:371`
_change_by_branch is documented as returning None when there is no change, but it passes any closed or merged change the by-branch lookup returns to _writable, which raises blocked. On proof's feature-branch path, a Base branch whose only change is closed or merged therefore ends `blocked` instead of `no-change` with the text for the run report. On open's path the advice to 'remove its Outside writes entry by hand' names an entry that does not exist, because that path runs only when no change is listed. Inferred, not checked against gh source: `gh pr view <branch>` falls back to the newest closed or merged PR when none is open. forge_ledger's twin of this lookup already handles that answer.

- Why: SDD.md:119 "feature-branch fix: one comment on that branch's open change, else the run report"; the repo's own lookup with the same contract treats a closed or merged answer as no open change: forge_ledger.py:1861-1867 "The open change for `tracked`, or None when the forge confirms there is none." ... `if str(view.get("state") or "").lower() in NOT_WRITABLE: return None`
- Fix: In _change_by_branch, return None when the answer's state is in NOT_WRITABLE, matching forge_ledger._writable_change. Keep the _writable block for _change_by_number, where a listed change is closed or merged.
- Concern: logic-correctness

## r-010 · medium · correctness · `skills/afk/fix/scripts/ship.py:477`
Proof treats `missing: true` from change-view as proof that the Base branch has no open change and exits 0 with `no-change`. The GitLab adapter sets `missing` on any stderr that contains `404` or `not found`. A project lookup failure therefore turns proof into a silent `no-change`, and on the feature-branch path proof is the first forge call (land is plain git), so the broken forge goes unnoticed. Failing input: `gitlab.remote` names a project the token cannot read, and glab answers with a 404 Project Not Found error (exact glab wording unverified).

- Why: adapters/forge/gitlab/CONTRACT.md:67 "`change-view` answers `missing: true` in its error only when `glab` says no merge request exists for the reference."; SDD.md:119 "one comment on that branch's open change, else the run report" (only when no open change exists, not when the lookup failed).
- Fix: Narrow the GitLab adapter's missing pattern to the merge-request phrases (`no open merge requests?|merge request .*not found`) and drop the bare `404|not found`, so that CONTRACT.md:67 holds. Alternatively, before returning no-change, have proof confirm that the forge answers for a known reference (for example auth-status), and block otherwise.
- Concern: logic-correctness

## r-011 · medium · correctness · `adapters/forge/gitlab/forge.sh:420`
The pre-existing GitLab `change-reviewers` verb now sends a different argument to glab (`+name` per reviewer, add semantics instead of replace) for every caller, including the untouched bug fixer, but the only proof of the new argument is the stub test that records argv; the conformance register still lists GitLab `change-reviewers` as live-proven, a proof made against the old replace form.

- Why: providers/CONFORMANCE.md:98 "| forge / gitlab | the same set, with `thread-resolve` supported | one draft merge request on the monorepo |" (the set at :97 includes `change-reviewers`); the same register's own convention for a verb changed after the live run is "stub-tested only and need a live run before release" (providers/CONFORMANCE.md:95). The refactor-safety checklist rates a behaviour change in a helper with callers outside its home module by its regression coverage; a stub that echoes argv cannot show glab accepts `+a,+b` as add-without-replace.
- Fix: Either round-trip `change-reviewers` with a `+` name on one disposable GitLab draft merge request (check the existing reviewer stays) before merge, or amend providers/CONFORMANCE.md row 98 to say GitLab `change-reviewers` (the `+` add form) is stub-tested only and needs a live run before release, recording the out-of-Scope file in a decision entry.
- Concern: refactor-safety

## r-012 · low · test · `scripts/tests/test_ship.py:658`
The command-line test is named "exits by status" but checks only refused → 1. On a copy, mapping `blocked` to exit 1 still passed.

- Why: skills/afk/fix/scripts/ship.py:35-36 docstring: "Exit 0 for done, skipped, draft and no-change, 1 for refused, 2 for not-fast-forward and blocked."
- Fix: Parametrize the test over one status from each exit class, such as a draft from forge `none` and blocked from a diagnosis listing a change the forge cannot view, or call `main()` with `run_ship_step` monkeypatched to return each status, and assert the exit code from `EXIT`.
- Concern: test-veracity

## r-013 · low · correctness · `skills/afk/fix/scripts/ship.py:340`
The push read-back finds an earlier push only when the remote tip equals HEAD. Suppose an earlier land pushed HEAD but its listing was lost, and someone has since pushed on top. The re-run then reports `not-fast-forward ... nothing pushed` and sends the caller to rebase and run every tier, although HEAD is already on the target. A probe on a real bare remote confirmed this. Open's push has the same gap: it blocks with 'did not take effect' when the remote fix branch already contains HEAD.

- Why: ship.py:34-35 "not-fast-forward (the Base branch moved: rebase once, run every tier, then land again)"; outside_writes.py:50-52 "`read_back()` answers ... an adapter answer object when it found the write". Here the write took effect, but the read-back reports a failure.
- Fix: In read_back, before the `moved` branch, return `{"ok": True, "commit": head}` when `git merge-base --is-ancestor head tip` succeeds (HEAD is already contained in the remote tip).
- Concern: logic-correctness

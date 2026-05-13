## Goal

Refactor `runner.py` to depend on `IssueTracker` and `Scm` Protocols (not concrete `JiraClient` / `GitLabClient`), wire in `repo_clone_manager` for multi-repo GitHub mode, and add the per-(repo, parent) outer grouping loop. Per-repo failure isolation: clone-fail or transient repo error skips that repo and continues; auth-level errors halt the whole run.

## Design refs

- SDD: `../SDD.md` §3 — runner depends on protocols, never concretes.
- SDD: `../SDD.md` §7 use-case 2 sequenceDiagram — per-sub-issue execution flow.
- SDD: `../SDD.md` §7 use-case detail table — strict serial; logical txn = sub-issue run.
- SDD: `../SDD.md` §7 failure-recovery matrix — per-repo skip-on-error rows.
- SDD: `../SDD.md` §8 module table row "runner (modified)".
- ADR: `../adr/0003-multi-repo-discovery-and-auto-clone.md` — per-repo failure isolation.
- ADR: `../adr/0004-phase-transition-verify-after-write.md` — runner reacts to `PhaseTransitionError`.

## Scope

- `src/afk_driver/runner.py`
- `tests/test_runner.py`
- `tests/scenarios/` (new fixtures for multi-repo cases)

## Acceptance

- [ ] `Runner.__init__` accepts `tracker: IssueTracker` and `scm: Scm` instead of `JiraClient` and `GitLabClient` — concrete-type imports removed from `runner` (SDD §8 row "runner (modified)")
- [ ] All Jira/GitLab-specific call sites in `runner` go through Protocol method names (e.g. `tracker.start_designing(key)` not `tracker.transition(key, "Start Designing")`) (SDD §6 phase-label state machine)
- [ ] When `Backend` is GitHub multi-repo, runner adds an outer per-repo loop wrapping the existing per-parent loop; before each repo's parents are processed, `repo_clone_manager.ensure_clone(owner, repo, root)` is called (ADR-0003 flowchart)
- [ ] Per-repo errors (clone-fail, missing default branch) are caught, recorded as `RepoFailed` in the run record, and the runner continues to the next repo (ADR-0003 flowchart "skip_repo")
- [ ] Auth-level errors (raised by `tracker` / `scm` pre-flight calls) propagate up and halt the whole run (PRD §"Pre-flight checks" — auth halts)
- [ ] On `PhaseTransitionError` (from ADR-0004), the runner aborts the affected parent (leaves it in current state), records the abort in the run record, and continues to the next parent — does NOT halt the whole run unless the error is auth-level (ADR-0004 — "halt many parents in succession is acceptable")
- [ ] Within a parent, the existing strict-serial sub-task processing is preserved; phase transitions follow the linear sequence `start_designing` → `start_developing` → `request_cr_merge` (SDD §6 phase-label state machine)
- [ ] Existing per-parent rebase-conflict semantics preserved: leaves parent at `afk:cr-merge` for human, posts comment, halts processing of remaining parents in that repo (SDD §7 failure-recovery matrix row "Final rebase conflict")
- [ ] Existing tests in `test_runner.py` continue to pass after the protocol substitution (Jira+GitLab path unchanged from caller's perspective) (PRD §"Backend abstraction" — "byte-for-byte unchanged")
- [ ] New tests cover: GitHub auto-detect from cwd, GitHub multi-repo mode (mock `gh search` returning issues across two repos, verify per-repo grouping + auto-clone calls), per-backend pre-flight failure paths (PRD §"Testing Decisions" — runner extension scenarios)
- [ ] Tests pass via `pytest tests/test_runner.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/runner.py#class Runner:` — refactored to accept `(tracker: IssueTracker, scm: Scm)` plus `repo_clone_manager`.
- `src/afk_driver/runner.py#def _drain_repo(self, repo_coords)` — new outer-loop method for multi-repo mode (private but distinctive).
- `src/afk_driver/runner.py#class RepoFailed:` — new run-record entry for per-repo failures.

## Test command

```
pytest tests/test_runner.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 02-legacy-adapters-conform
- 03-repo-clone-manager
- 04-github-issues-client
- 05-github-pr-client
- 06-backend-select-and-config

## Consumes

- 02-legacy-adapters-conform `src/afk_driver/jira_client.py#class JiraClient(IssueTracker):` — Jira impl runner can accept via Protocol.
- 02-legacy-adapters-conform `src/afk_driver/gitlab_client.py#class GitLabClient(Scm):` — GitLab impl runner can accept via Protocol.
- 03-repo-clone-manager `src/afk_driver/repo_clone_manager.py#def ensure_clone(owner: str, repo: str, root: Path) -> Path:` — clone entrypoint runner calls per-repo.
- 04-github-issues-client `src/afk_driver/github_issues_client.py#class GitHubIssuesClient(IssueTracker):` — GitHub impl runner can accept via Protocol.
- 04-github-issues-client `src/afk_driver/github_issues_client.py#class PhaseTransitionError(RuntimeError):` — error type runner catches and routes to per-parent abort.
- 05-github-pr-client `src/afk_driver/github_pr_client.py#class GitHubPrClient(Scm):` — GitHub PR impl runner can accept via Protocol.
- 06-backend-select-and-config `src/afk_driver/backend_select.py#class Backend:` — dataclass runner unpacks for tracker + scm + repo_coords.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->

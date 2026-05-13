## Goal

Build the `backend_select` composition-root factory and extend `config` with a `[github]` section + per-repo `.afk-driver.toml` loader. `backend_select.resolve(cwd, config)` inspects the cwd's git remote, returns a `Backend` dataclass holding the chosen `IssueTracker` + `Scm` instances + repo coordinates. Config gains `[github] mode` (`cwd` | `all-repos`), `auto_clone_root`, `default_target_branch_fallback`; per-repo loader merges `<repo>/.afk-driver.toml` into the effective config.

## Design refs

- SDD: `../SDD.md` §3 row "backend_select" — auto-detect rule with `mode = "all-repos"` override.
- SDD: `../SDD.md` §3 — "single dispatch point at composition root".
- SDD: `../SDD.md` §4 state table rows "Driver config" / "Per-repo overrides" — TOML schema + forward-compat policy.
- SDD: `../SDD.md` §5 feature-flags table — `[github] mode`, `[per-repo] forbidden_patterns`.
- SDD: `../SDD.md` §8 module table rows "backend_select" / "config".
- SDD: `../SDD.md` §9 Strategy classDiagram — `BackendSelect ..> Backend`.
- ADR: `../adr/0003-multi-repo-discovery-and-auto-clone.md` — `mode = "all-repos"` semantics.

## Scope

- `src/afk_driver/backend_select.py`
- `src/afk_driver/config.py`
- `tests/test_backend_select.py`
- `tests/test_config.py`

## Acceptance

- [ ] `class Backend` dataclass exposes `tracker: IssueTracker`, `scm: Scm`, `repo_coords: RepoCoords` (SDD §9 Strategy classDiagram)
- [ ] `def resolve(cwd: Path, config: DriverConfig) -> Backend` is the only public function on `backend_select` (SDD §8 row "backend_select")
- [ ] When `config.github.mode == "all-repos"`, returns a GitHub Backend regardless of cwd (cwd inspection is short-circuited) (ADR-0003)
- [ ] When `mode == "cwd"` (default), inspects `git -C {cwd} remote get-url origin`; `github.com` host → GitHub Backend; configured GitLab host → Jira+GitLab Backend; unknown host → raises `BackendResolutionError` with the URL in the message (SDD §3 — auto-detect rule)
- [ ] `config.toml` `[backend_select] gitlab_host` and `force_backend` keys honoured (SDD §5 feature-flags table)
- [ ] `[github]` section parsed with defaults: `mode = "cwd"`, `auto_clone_root = "{worktree_root}/github"`, `default_target_branch_fallback = ["{repo-default}"]` (SDD §4 state table row "Driver config")
- [ ] Per-repo `<repo>/.afk-driver.toml` loader merged via `def load_per_repo(repo_root: Path, base: DriverConfig) -> DriverConfig`; per-repo overrides global, global overrides built-in (SDD §4 state table row "Per-repo overrides")
- [ ] Per-repo schema-evolution policy: unknown keys ignored (forward-compat); missing keys → built-in default (SDD §4 state table row "Per-repo overrides")
- [ ] Existing `config.toml` keys (`project_service_map`, `target_branch_field`, `dev_cr_merge_gate_*`, etc.) ignored when active backend is GitHub — surfaced as a no-op rather than an error (PRD §"Backend matrix" — Nakisa-only fields don't apply on GitHub)
- [ ] Tests cover: github.com remote → GitHub; configured GitLab host → Jira; unknown host → raise; `force_backend` override wins over auto-detect; `mode = "all-repos"` short-circuits cwd inspection; missing `origin` remote → raise with clear message; per-repo TOML merge precedence (PRD §"Testing Decisions" — backend_select coverage list)
- [ ] Tests pass via `pytest tests/test_backend_select.py tests/test_config.py` (SDD §10 NFRs)

## Produces

- `src/afk_driver/backend_select.py#def resolve(cwd: Path, config: DriverConfig) -> Backend:` — composition-root entrypoint.
- `src/afk_driver/backend_select.py#class Backend:` — dataclass holding `(tracker, scm, repo_coords)`.
- `src/afk_driver/backend_select.py#class BackendResolutionError(RuntimeError):` — raised when remote URL is unrecognised.
- `src/afk_driver/config.py#def load_per_repo(repo_root: Path, base: DriverConfig) -> DriverConfig:` — per-repo TOML merge.
- `src/afk_driver/config.py#class GithubConfig:` — sub-dataclass for the `[github]` section.

## Test command

```
pytest tests/test_backend_select.py tests/test_config.py
```

## Parent PRD

`tasks/github-backend/PRD.md`

## Parent SDD

`tasks/github-backend/SDD.md`

## Blocked by

- 01-protocols
- 02-legacy-adapters-conform
- 04-github-issues-client
- 05-github-pr-client

## Consumes

- 01-protocols `src/afk_driver/tracker_protocol.py#class IssueTracker(Protocol):` — Protocol Backend.tracker conforms to.
- 01-protocols `src/afk_driver/scm_protocol.py#class Scm(Protocol):` — Protocol Backend.scm conforms to.
- 02-legacy-adapters-conform `src/afk_driver/jira_client.py#class JiraClient(IssueTracker):` — concrete IssueTracker for Jira backend.
- 02-legacy-adapters-conform `src/afk_driver/gitlab_client.py#class GitLabClient(Scm):` — concrete Scm for GitLab backend.
- 04-github-issues-client `src/afk_driver/github_issues_client.py#class GitHubIssuesClient(IssueTracker):` — concrete IssueTracker for GitHub backend.
- 05-github-pr-client `src/afk_driver/github_pr_client.py#class GitHubPrClient(Scm):` — concrete Scm for GitHub backend.

## Conflict procedure

If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, exit with `design-conflict` status quoting the SDD section + the conflict. Do NOT override silently. Route back to `/afk:architect-grill` for a superseding ADR.

## Implementation Notes (auto-maintained)

<!-- AFK appends one bullet per completed SubTask -->

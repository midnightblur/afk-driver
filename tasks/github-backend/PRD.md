## Service: tasks

# AFK GitHub Backend — PRD

## Problem Statement

AFK currently runs against exactly one tracker/SCM pair: Jira + GitLab, hard-baked into `jira_client.py`, `gitlab_client.py`, and the SubTask/Enhancement vocabulary throughout `runner.py` and the skills. The user wants to use AFK on personal GitHub repos as well — not by replacing the Nakisa workflow, but by adding GitHub Issues + GitHub PRs as a parallel backend that AFK can pick up automatically when the work happens to live on GitHub.

The friction without this:

- **AFK is locked to one employer's tooling.** The user's personal projects sit outside the only place AFK can drive overnight work.
- **The driver assumes a single Jira project, a single GitLab repo, and Jira-only custom-field gates** (Target Branch, SRED eligibility, time estimation, A+ Clarity rationale). None of those concepts exist on GitHub Issues, and the Nakisa-specific gates are noise on personal repos.
- **The skills (`to-prd`, `prd-to-subtasks`, `afk-go`) speak Jira-only.** Even the artefact path (`{service}/src/main/resources/specs/...`) is a Nakisa convention that has no analogue in a single-repo personal project.

The goal is to extend AFK so the same grill→PRD→SubTasks→AFK overnight loop works against GitHub Issues + GitHub PRs, with the same morning digest, the same scope-enforcer safety rails, and the same opt-in label semantics — without disturbing the Jira+GitLab path the user relies on for paid work.

## Solution

A backend abstraction layer plus a GitHub implementation:

- **Per-run backend selection.** When the driver starts (or a skill is invoked), it inspects the current working directory's git remote: `github.com` → GitHub backend, configured GitLab host → Jira+GitLab backend. Multi-repo GitHub mode is selected explicitly via config when AFK should drain queues across the user's whole GitHub account rather than one cwd repo.
- **Two narrow protocols** — `IssueTracker` and `Scm` — that `runner.py` and the skills depend on. The existing Jira and GitLab modules conform to these protocols. New modules `github_issues_client` and `github_pr_client` are the GitHub-side implementations, both shelling out to `gh` (with `gh api` for sub-issue operations the CLI doesn't natively expose).
- **GitHub model mapping** mirrors the Jira shape using GitHub-native primitives:
  - Parent Enhancement → top-level GitHub Issue.
  - SubTask → GitHub sub-issue (native parent/child relationship via REST, GA 2024).
  - Workflow phase → mutually-exclusive labels `afk:pending`, `afk:designing`, `afk:developing`, `afk:cr-merge`. (GitHub Issues has no native multi-phase workflow — only `open`/`closed` plus `state_reason`. Verified against the official REST docs.)
  - Target Branch custom field → label `target:{branch}` on the parent issue.
  - Opt-in → the same `afk-agents` label used on Jira.
  - PR (Draft) → one Draft PR per parent issue, target derived from the parent's `target:` label or repo default.
- **Multi-repo discovery.** When configured for all-account mode, the driver runs `gh search issues --owner @me state:open label:afk-agents label:afk:pending` to find work. Repos not yet cloned locally are auto-cloned into `worktree_root/github/{owner}/{repo}/`; per-Enhancement worktrees nest inside that clone.
- **Skills branch internally.** `to-prd`, `prd-to-subtasks`, `afk-go` keep their names and entry points; each detects the backend and dispatches to the appropriate tracker/SCM operations.
- **Nakisa-specific gates are dropped on the GitHub path.** No SRED eligibility, no time-estimation custom field, no A+ Clarity option, no cross-module marker comments, no liquibase forbidden-pattern defaults. All of these remain in force on the Jira backend; on GitHub they default to "off" but can be re-enabled per-repo via a checked-in `.afk-driver.toml`.

The morning digest is unified across both backends in a single file, with backend and repo columns added so the user can tell at a glance which run-items came from where.

## User Stories

### Choosing a backend

1. As the user, I want AFK to detect from the current repo's git remote whether to use Jira+GitLab or GitHub, so that I don't have to remember to flip a flag when I switch projects.
2. As the user, I want to override the auto-detected backend via config, so that I can force a specific backend in edge cases (e.g. a GitHub mirror of a primarily-GitLab repo).
3. As the user, I want a "scan all my GitHub repos" mode that I opt into via config, so that I can drain personal-project queues across many small repos without running the driver inside each one.
4. As the user, I want existing Jira+GitLab behaviour to be byte-for-byte unchanged when the auto-detect picks Jira, so that adding GitHub support cannot regress my paid-work AFK lane.

### Authoring features on GitHub

5. As the user, I want to grill a feature idea with `grill-me` exactly as I do today, so that the design phase is identical regardless of where the issue eventually lives.
6. As the user, I want `to-prd` to write the PRD to a configurable per-repo path (default `.afk/specs/{issue-number}/PRD.md`), so that personal repos don't inherit the Nakisa `{service}/src/main/resources/specs/...` convention.
7. As the user, I want `to-prd` on GitHub to either (a) attach to a parent issue I created in advance, or (b) create the parent issue itself from the PRD title and summary when no issue key is provided, so that the workflow accommodates both planning styles.
8. As the user, I want the parent GitHub issue's body to gain a `## PRD` section pointing to the PRD file in the repo, so that anyone reading the issue can find the design without git access.
9. As the user, I want `prd-to-subtasks` on GitHub to create one native sub-issue per slice (using GitHub's parent/child relationship, not task-list checkboxes), so that each SubTask has its own comment thread, label, and close lifecycle.
10. As the user, I want each generated sub-issue to carry the same Goal/Scope/Acceptance/Test-command Markdown block in its body, so that the agent has the same enforceable contract on either backend.
11. As the user, I want each generated sub-issue to carry the `afk-agents` label and an initial `afk:pending` phase label, so that the driver picks them up the same way it picks up Jira SubTasks.

### Running AFK on GitHub

12. As the user, I want one driver invocation that drains both my Jira+GitLab queue (when run inside a Nakisa worktree) and my GitHub queue (when run with the all-account flag), so that I have one mental model for "go AFK overnight" across both worlds.
13. As the user, I want the GitHub queue discovered via a single `gh search issues` call (open + `afk-agents` + `afk:pending` + assignee = me), so that other people's issues and unlabelled drafts are invisible.
14. As the user, I want sub-issues grouped by parent issue, with parents already in flight (any sub-issue past `afk:pending`) preferred over fresh parents, so that the same "finish what's started" priority rule applies.
15. As the user, I want the GitHub backend to enforce the same strict-serial, one-fresh-Claude-session-per-SubTask, 1-hour-cap rules as the Jira backend, so that runtime safety properties are identical.

### Repo and worktree mechanics on GitHub

16. As the user, I want repos that aren't cloned locally yet to be auto-cloned into `worktree_root/github/{owner}/{repo}/` on first encounter, so that I don't have to manually pre-clone every repo I might one day open an issue against.
17. As the user, I want one git worktree per GitHub parent issue, named conventionally under the repo's clone, so that the same worktree-per-Enhancement model applies and build caches are reused across an issue's sub-issues.
18. As the user, I want the AFK branch named `afk/issue-{N}` and the Draft PR titled `[#{N}] {issue title}`, so that PRs are easy to scan in `gh pr list` and the convention mirrors the GitLab side.
19. As the user, I want the AFK branch based off the parent issue's `target:{branch}` label value, falling back to the repo's default branch when the label is absent, so that release-line repos still get correct routing without forcing the label on single-line repos.
20. As the user, I want the driver to refuse to start a parent issue when the resolved target branch doesn't exist in the cloned repo, so that AFK never silently bases work off the wrong branch.
21. As the user, I want the per-issue rebase onto the target branch to happen only once, after the last sub-issue is done, so that mid-stream conflicts cannot cascade across sub-issues (mirroring the Jira rule).

### GitHub lifecycle

22. As the user, I want each sub-issue's phase label transitioned in lock-step with the existing Jira SubTask lifecycle: `afk:pending` → `afk:designing` (PRD-reading) → `afk:developing` (editing) → `afk:cr-merge` (PR opened/updated), so that observers can see exactly which phase is in flight.
23. As the user, I want phase-label transitions implemented as "remove all other afk:* labels, add the new one" in a single `gh` call, so that there is no observable mid-state with two phase labels.
24. As the user, I want the parent issue's phase label to follow the same progression (Pending → Developing on first sub-issue pickup, → CR/Merge after the last sub-issue completes successfully), so that the parent issue is a real rollup status the way the Jira Enhancement is.
25. As the user, I want the driver to refuse to start the first sub-issue if the parent isn't on `afk:pending`, so that I can't accidentally double-trigger AFK on an in-flight feature.
26. As the user, I want the driver to close each sub-issue with `state_reason=completed` after success, so that closed sub-issues are distinguishable from `not_planned` ones in the issue history.
27. As the user, I want the parent issue closed implicitly on PR merge via `Closes #{parent}` lines in the PR body, so that the human merge is the explicit gate that closes the parent — not an AFK auto-close.
28. As the user, I want each abort to leave a comment on the sub-issue explaining why and to revert the sub-issue's phase label back to `afk:pending`, so that the next AFK pass can retry without manual cleanup.

### PR mechanics on GitHub

29. As the user, I want exactly one Draft PR per parent issue, opened on the first sub-issue's commits, kept Draft until I flip it Ready, so that morning review on GitHub is the same one-PR-per-feature experience as on GitLab.
30. As the user, I want the PR body to carry a sub-issue checklist between marker comments (same `<!-- afk:subtasks:start -->` / `:end` scheme as GitLab), so that the splice logic in `section_splice` is reused unchanged.
31. As the user, I want the PR body to include `Closes #{parent}` and `Closes #{sub}` lines for every sub-issue that lands, so that the merge auto-closes the whole tree.
32. As the user, I want the parent issue's body to gain a `## Implementation Notes (auto-maintained)` block (same marker scheme), updated with one bullet per completed sub-issue, so that the audit trail on the parent ticket is identical to the Jira side.
33. As the user, I want CI failure on the Draft PR to be ignored by the driver (continue to next sub-issue), mirroring the GitLab rule, so that flaky pipelines don't stall the night.

### Safety rails on GitHub

34. As the user, I want the same `Scope:` glob enforcement on every commit, so that the safety-rail core (`scope_enforcer`) is backend-agnostic.
35. As the user, I want the forbidden-pattern list to default to empty on GitHub, with per-repo override via `.afk-driver.toml`, so that personal repos aren't subject to Nakisa-specific liquibase/UpgradeGroup rules they have no use for.
36. As the user, I want the cross-module marker-comment requirement to be off by default on GitHub (no module concept on most personal repos), with the option to re-enable per-repo if a personal monorepo emerges, so that the rule travels with the repo's actual structure.
37. As the user, I want the SRED / time-estimation / A+ Clarity custom-field gates to be skipped entirely on the GitHub path (they have no GitHub equivalent), so that the `Dev-CR/Merge` transition logic doesn't try to populate fields that don't exist.
38. As the user, I want pre-flight checks to run a backend-appropriate auth probe (Jira: `JIRA_API_TOKEN` env + reachable; GitHub: `gh auth status` clean), so that the driver fails fast with a clear message instead of mid-run.

### Observability

39. As the user, I want a single morning digest covering both backends in one file, with backend and repo columns added, so that I don't have to read two reports after a mixed-backend night.
40. As the user, I want every per-sub-issue log preserved on disk in the same path scheme as Jira sub-task logs (just keyed by `{owner}-{repo}-issue-{N}` instead of Jira key), so that troubleshooting is uniform.
41. As the user, I want the digest to render GitHub PR links as clickable URLs and the parent + sub-issue numbers as `owner/repo#N` so I can copy-paste them into chat without ambiguity.

### Configuration

42. As the user, I want all GitHub-side settings to live under a `[github]` section in the same `~/.afk-driver/config.toml`, so that I have one config file rather than two.
43. As the user, I want each repo to be able to override scope/forbidden/PRD-path settings via a checked-in `.afk-driver.toml` in its root, so that team repos can tighten or loosen the defaults without touching my personal config.
44. As the user, I want the existing Jira-only config keys to keep their current names and defaults, so that loading an unmodified config file produces identical behaviour to today on the Jira backend.

## Implementation Decisions

### Backend abstraction

- **Two narrow protocols** are introduced: `IssueTracker` (parent + sub-task CRUD, phase transitions, comment posting, description-block splicing, target-branch read) and `Scm` (find/open Draft PR/MR, update description, splice description block). Concrete tradeoff: thin protocols beat fat ones — anything Jira-only or GitHub-only stays on the concrete client and never reaches the protocol surface.
- **`runner.py` and the three skills (`to-prd`, `prd-to-subtasks`, `afk-go`) depend on the protocols, never on concrete clients.** A single `backend_select` call at entrypoint resolves the concrete pair from `(cwd, config)`.
- **Auto-detect rule:** parse `git remote get-url origin` from cwd; if hostname matches `github.com` → GitHub; if it matches the configured GitLab host → Jira+GitLab; otherwise raise. Multi-repo GitHub mode is selected by an explicit config entry `[github] mode = "all-repos"`, which overrides cwd inspection and forces backend = GitHub.
- **Backend-dispatch lives inside the existing skill files** (single skill name per role), not in parallel `to-prd-gh` skills. Each skill has a small backend-detection preamble and branches its body.

### GitHub data model

- **Parent issue ↔ Jira Enhancement; native sub-issue ↔ Jira SubTask.** Sub-issue creation and listing go through `gh api` (`POST /repos/{owner}/{repo}/issues/{N}/sub_issues`, `GET /repos/{owner}/{repo}/issues/{N}/sub_issues`), since the native `gh` CLI doesn't yet expose sub-issue commands. Verified against the GitHub REST docs (`docs.github.com/en/rest/issues/sub-issues`) and the [cli/cli#10298](https://github.com/cli/cli/issues/10298) tracking issue.
- **Phase labels** are mutually exclusive: `afk:pending`, `afk:designing`, `afk:developing`, `afk:cr-merge`. Transition implementation: a single `gh issue edit --remove-label afk:pending,afk:designing,afk:developing,afk:cr-merge --add-label afk:{new}` call so there's no observable two-label intermediate state.
- **Opt-in label** is `afk-agents` (identical name to the Jira side). Distinct namespace from phase labels — `afk-agents` is a presence flag, `afk:*` are state labels.
- **Target branch label** is `target:{branch-name}` on the parent issue. Absent → fall back to repo default branch (`gh repo view --json defaultBranchRef`). The driver refuses to start work if the resolved branch doesn't exist locally after `git fetch`.
- **Issue body conventions** mirror the Jira description conventions verbatim: a `## PRD` section pointing to the PRD file, an `## Implementation Notes (auto-maintained)` block bounded by the existing `<!-- afk:notes:start -->` / `<!-- afk:notes:end -->` markers, and the Goal/Scope/Acceptance/Test-command Markdown block on sub-issue bodies. The `section_splice` and `subtask_template` modules are reused unchanged.

### Module breakdown

**New:**

- **`tracker_protocol`** — `IssueTracker` protocol declaration. Pure type module, no I/O.
- **`scm_protocol`** — `Scm` protocol declaration. Pure type module, no I/O.
- **`github_issues_client`** — implements `IssueTracker` via `gh` CLI + `gh api`. Owns: search-issues queue queries, sub-issue CRUD, label add/remove (incl. mutually-exclusive phase swap), comment posting, issue body splicing through `section_splice`, target-branch label read, repo default-branch lookup. Injected `GhRunner` callable for test stubbing, mirroring `gitlab_client`'s `GlabRunner`.
- **`github_pr_client`** — implements `Scm` via `gh` CLI. Owns: `gh pr list --search` for find-by-parent, `gh pr create --draft`, `gh pr edit --body` for description splice. Same injected-runner pattern.
- **`backend_select`** — pure function `resolve(cwd, config) -> Backend` returning a small dataclass holding the chosen tracker and SCM constructors plus repo coords (owner/repo for GitHub, project/path for GitLab). Side-effect-free aside from the single `git remote get-url` subprocess.
- **`repo_clone_manager`** — idempotent wrapper over `gh repo clone`. Given `(owner, repo)`, returns the local clone path under `worktree_root/github/{owner}/{repo}/`, cloning if absent and `git fetch`ing if present. Refuses to operate if the destination exists but is not a git repo.

**Modified:**

- **`runner`** — accepts injected `IssueTracker` and `Scm` instances; the existing Jira/GitLab specifics in pre-flight, queue grouping, and lifecycle calls are replaced by protocol calls. Multi-repo GitHub mode adds a per-(repo, parent) outer grouping; the inner per-parent loop is unchanged.
- **`config`** — adds a `[github]` TOML section with `mode` (default `cwd`), `auto_clone_root` override, `default_target_branch` override. The `dev_cr_merge_gate_*` settings are gated to the Jira backend at use-time. New: per-repo `.afk-driver.toml` loader (PRD path, forbidden patterns, cross-module enable flag) merged into the effective config when the active backend's repo root contains one.
- **`cli`** — entrypoint resolves the backend via `backend_select` before constructing the runner; multi-repo mode toggles a different worktree-root layout. Per-backend auth pre-flight (Jira: token + reachability; GitHub: `gh auth status`).
- **`digest_writer`** — adds `backend` and `repo` columns to per-parent and per-sub-task rows; emits a single unified file even when both backends ran in the same invocation.
- **Skills (`to-prd`, `prd-to-subtasks`, `afk-go`)** — each gets a backend-detection preamble. On GitHub: `to-prd` writes the PRD to the configured per-repo path (default `.afk/specs/{N}/PRD.md`) and updates the parent issue's `## PRD` section; `prd-to-subtasks` creates GitHub sub-issues with the structured body and `afk-agents`/`afk:pending` labels; `afk-go` reads the parent + sub-issue, drives the four phase-label transitions, opens/updates the Draft PR, and updates the parent's auto-maintained block.

**Unchanged:**

- `subtask_template`, `scope_enforcer`, `worktree_manager`, `jira_section`, `section_splice`. The first three are backend-agnostic by construction; the last two are pure marker-block utilities that already serve both Jira descriptions and GitLab MR descriptions and will serve GitHub issue bodies + PR bodies identically.

### Configuration shape

Additions to `~/.afk-driver/config.toml`:

- `[github]`
  - `mode` — `cwd` (default; backend auto-detected from cwd's git remote) or `all-repos` (forces GitHub backend, queue discovered via `gh search issues --owner @me`).
  - `auto_clone_root` — directory under which `{owner}/{repo}` clones are placed. Default: `{worktree_root}/github`.
  - `default_target_branch_fallback` — ordered list to try when the parent issue lacks a `target:` label. Default: just `["{repo-default}"]`, where `{repo-default}` is resolved per-repo via `gh repo view`.
- `[backend_select]`
  - `gitlab_host` — hostname pattern for the Jira+GitLab path (default = the user's Nakisa host).
  - `force_backend` — optional override (`jira` | `github`).

Per-repo `.afk-driver.toml` (checked into individual repos, GitHub side):

- `spec_root` — overrides default `.afk/specs/{N}/PRD.md`.
- `forbidden_patterns` — extends the global empty default for repos that need them.
- `cross_module_marker_template` + `module_resolver` — opt in to cross-module marker enforcement on a per-repo basis if the repo grows multi-module.

### Backend-by-backend behaviour matrix

| Concern | Jira+GitLab (existing) | GitHub (new) |
|---|---|---|
| Parent ticket type | Jira Enhancement (or Bug) | GitHub Issue |
| Sub-task type | Jira SubTask (id 10003) | GitHub native sub-issue |
| Phase tracking | Jira workflow status | Mutually-exclusive `afk:*` labels |
| Opt-in flag | `afk-agents` label | `afk-agents` label |
| Target branch | `customfield_13706` value mapped to git branch | `target:{branch}` label, repo default fallback |
| PRD path | `{service}/src/main/resources/specs/{year}r{release}/{ENH-ID}/PRD.md` | `.afk/specs/{N}/PRD.md` (per-repo overridable) |
| Branch name | `mvu/afk/{ENH-ID}` | `afk/issue-{N}` |
| PR/MR title | `[{ENH-ID}] {summary}` | `[#{N}] {title}` |
| Description splice | `<!-- afk:notes:start --> ... <!-- afk:notes:end -->` | identical |
| SubTask close | Transition to `Dev-CR/Merge` (4 custom fields populated) + later human merge | `gh issue close --reason completed` (no field gates); parent closed by PR `Closes #N` |
| Cross-module marker | Required outside home module | Off by default; per-repo opt-in |
| Forbidden patterns | UpgradeGroup, PreDbMigration, liquibase | Empty by default; per-repo opt-in |
| Multi-target | One repo per Jira project | Multi-repo via `mode = "all-repos"` |

### Pre-flight checks (additions)

- **Jira+GitLab path:** unchanged.
- **GitHub path:** `gh auth status` exits 0; `gh repo view` succeeds for each repo discovered in the queue (or for cwd in `mode = "cwd"`); the sub-issues REST endpoint responds 200 to a probe call against any one queued repo (catches orgs that haven't enabled the feature).

## Testing Decisions

A good test for this change exercises the **observable contract**: did the right `gh` call get issued with the right arguments, did the right phase label end up on the issue, did the right PR body get spliced. It does not assert on internal call ordering, intermediate dataclass shapes, or which protocol method dispatched to which concrete impl.

Tests should run on the user's Windows machine with no network — `gh` and `git` invocations are stubbed at the injected-runner boundary, identical to how the existing `gitlab_client` and `worktree_manager` tests operate.

**Modules covered by tests:**

- **`github_issues_client`** — unit tests with a stubbed `GhRunner`. Coverage: queue search call shape, parent + sub-issue CRUD, sub-issue REST envelope (success, 404, malformed JSON), phase-label swap atomicity (verify single `gh issue edit` call with both `--remove-label` and `--add-label`), comment posting (success + idempotency on repeated identical content), issue body splicing for `## PRD` section and `## Implementation Notes (auto-maintained)` block (delegates to `section_splice`, but verify the wire call), target-branch label read with default-branch fallback, error path when label is malformed.
- **`github_pr_client`** — unit tests with a stubbed `GhRunner`. Coverage: find-by-branch (single result, none, multiple → error), find-by-parent (search-result filtering for title-contains, mirroring `gitlab_client.find_open_mr_by_parent_key`), open-draft-PR (idempotent re-open), PR description splice (delegates to `section_splice`), PR body `Closes #N` line management.
- **`backend_select`** — pure-function tests over fixture cwds + config dicts. Coverage: github.com remote → GitHub; configured GitLab host → Jira+GitLab; unknown host → raise; `force_backend` config override wins; `mode = "all-repos"` short-circuits cwd inspection; missing `origin` remote → raise with clear message.
- **`repo_clone_manager`** — integration-ish tests with a stubbed `gh repo clone` runner against a tmp dir. Coverage: clone-when-absent, no-op when already cloned (verify `git fetch` is called instead), refuse-when-destination-is-not-git, clone failure surfaces as a typed error.

**Modules excluded from tests:**

- **Skill dispatch logic.** Skills are Markdown + Claude orchestration; testing the dispatch branch is testing the skill runner, not the AFK code. The protocol implementations are tested at the client level; the skills' use of them is exercised via the `runner` integration suite.
- **`tracker_protocol`** and **`scm_protocol`** — pure type declarations.

**Modules whose tests get extended (not new modules):**

- **`runner`** — add scenarios for: GitHub auto-detect from cwd, GitHub multi-repo mode (mock `gh search` returning issues across two repos, verify per-repo grouping + auto-clone calls), per-backend pre-flight failure paths, mixed-run digest emission.
- **`config`** — add scenarios for: `[github]` section parsing with defaults, per-repo `.afk-driver.toml` merge precedence (per-repo overrides global; global overrides built-in defaults), Jira-only fields ignored when active backend is GitHub.
- **`digest_writer`** — golden-file additions for: GitHub-only run, mixed Jira+GitHub run, multi-repo GitHub run with three repos.

**Prior art:**

- `tests/test_gitlab_client.py` is the template for `test_github_pr_client.py` (injected runner, fixture stdout/stderr, error-path coverage).
- `tests/test_jira_client.py` is the template for `test_github_issues_client.py` (HTTP-style transport stub adapted to subprocess stub; error envelope coverage).
- `tests/test_worktree_manager.py` is the template for `test_repo_clone_manager.py` (real tmp dir, stubbed external CLI).
- `tests/test_runner.py` is the template for the cross-cutting integration scenarios (mocked tracker + SCM, real `worktree_manager`, golden digest assertions).

## Out of Scope

- **GitHub Projects v2 integration.** Phase tracking uses labels, not a Projects board's Status column. Projects v2 needs GraphQL + per-repo project provisioning; labels need neither. Future iteration if it ever pays for itself.
- **GitHub Issue Types (the 2025 classification feature).** The sub-issue parent/child relation is the sole signal for "this is a SubTask". Issue Types are an orthogonal classification AFK ignores.
- **GitHub Actions integration.** AFK does not read CI status or wait for green builds, on either backend. CI failure on the Draft PR is tolerated; the morning review is the gate.
- **Cross-org GitHub repos.** Multi-repo mode scans repos owned by `@me`. Org repos the user is a member of (but doesn't own) are out of scope; the user can switch into one explicitly via `mode = "cwd"` from inside that repo's clone.
- **GitHub Apps / fine-grained PAT installation flows.** The driver assumes `gh auth status` is clean; how the user authenticated `gh` is the user's problem.
- **Migrating existing Jira PRDs to GitHub.** No bulk-import tool. Each new GitHub Enhancement is authored from scratch via `to-prd`.
- **Mixed-backend single Enhancement.** A parent issue lives entirely on one backend; sub-tasks all share the parent's backend. No "Jira parent with GitHub sub-issues" or vice versa.
- **Removing or refactoring the existing Jira-only paths.** The protocol abstraction is an additive layer; `jira_client` and `gitlab_client` keep their current public interfaces. Concrete callers in `runner` are migrated to the protocol but the underlying modules don't shrink.
- **Multi-account GitHub.** One `gh` auth context per driver invocation. Switching between two GitHub accounts requires switching `gh auth` outside AFK.

## Further Notes

- **Why protocols, not duck typing.** Python lets `runner` accept any object with the right attributes, but explicit `Protocol` declarations make the contract surface visible (and grep-able) in one place. When the second tracker exists, the first tracker's accidental shape is no longer the contract by default.
- **Why `gh` CLI + `gh api` rather than PyGithub or raw REST.** `gh` already handles auth, refresh, host overrides, enterprise hosts, and pagination. `gh api` exposes the full REST surface for the few endpoints (sub-issues) the CLI doesn't yet wrap. Adopting PyGithub would add a dependency for capabilities AFK already has via subprocess. Adopting raw REST via `urllib` would re-implement the auth handling that `gh` does well.
- **Why mutually-exclusive labels rather than one Status field.** Labels work with zero per-repo setup. The cost is that a buggy run could leave two phase labels on an issue; the mitigation is the single-call swap (`gh issue edit --remove-label X,Y,Z --add-label W`) and a label-reconciliation pass at pre-flight that warns if any issue carries more than one `afk:*` label.
- **Why the per-repo `.afk-driver.toml` (rather than only a global config).** Personal monorepos (when they exist) need different forbidden-patterns / cross-module / spec-root settings from one-feature personal repos. Putting per-repo settings in the repo lets them travel with the repo and survive driver re-installs.
- **Why drop SRED / time-estimation / A+ Clarity on GitHub.** These are Nakisa workflow validator gates required for the Jira `Dev-CR/Merge` transition. GitHub has no such gates. Re-implementing them as labels would be ceremony for ceremony's sake on personal repos.
- **The morning digest is still the killer feature.** Cross-backend rows must distinguish `owner/repo#N` (GitHub) from `P2P-1234` (Jira) at a glance. If the digest mis-attributes a row, AFK is worse than not-AFK on whichever backend got dropped.
- **Implementation order:** ship `tracker_protocol` + `scm_protocol` first (no behaviour change), then migrate `runner` to depend on them while keeping `jira_client`/`gitlab_client` as the only impls (no behaviour change, but exposes any leaky concrete dependencies). Then add `github_issues_client` + `github_pr_client` + `backend_select` + `repo_clone_manager` + tests. Skill dispatch comes last, because it's the smallest surface and the easiest to verify by hand.
- **Verification log:** GitHub native states (`open`/`closed`) and `state_reason` values (`completed`/`not_planned`/`duplicate`/`reopened`/`null`) confirmed against `docs.github.com/en/rest/issues/issues`. Sub-issues REST surface (`/sub_issues` add/list/remove) confirmed against `docs.github.com/en/rest/issues/sub-issues` and the GitHub changelog entry from December 2024. Native `gh` CLI lacks first-party sub-issue commands (verified via `cli/cli` issue #10298) — `gh api` covers the gap without adding a third-party extension dependency.

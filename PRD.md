# AFK Workflow for core-services — PRD

## Problem Statement

Adapting Matt Pocock's "AFK Claude Code" workflow (grill-me → write-PRD → PRD-to-issues → Ralph loop → QA feedback) to the core-services environment is non-trivial. The reference workflow assumes a small TypeScript app, GitHub Issues, GitHub PRs, Docker sandboxes, and full agent autonomy — none of which translate cleanly to a 50-microservice Maven monorepo on Windows, with Jira as the issue tracker, GitLab as the SCM, and durable user rules that forbid unsupervised commits, off-scope edits, and direct DB changes.

Without an adapted workflow, the user faces three concrete problems:

- **Wasted overnight cycles.** Ideas that are ready to implement sit idle until the user is at the keyboard, because there is no safe path for an agent to execute them unattended.
- **Workflow-tool drift.** Each new feature is started ad hoc — a different mix of grilling, planning, ticket creation, branching, and review — so quality and traceability vary per feature.
- **Existing safety rules are at odds with autonomy.** "User makes commits themselves," "stop after each phase," "never alter DB directly" are correct defaults but, applied uniformly, eliminate the AFK regime entirely. The user wants a carve-out, not a rule deletion.

## Solution

A labelled AFK lane on top of the existing Jira/GitLab/Maven setup, where:

- **Day shift (synchronous, human-driven):** the user runs grill-requirements to harden a feature idea, then writes a PRD per Enhancement to a per-ticket spec directory, then slices that PRD into Jira SubTasks tagged with an opt-in label.
- **Night shift (asynchronous, agent-driven):** a Python driver picks up labelled SubTasks via JQL, drives one Claude Code session per SubTask inside a per-Enhancement git worktree, opens a single Draft Merge Request per Enhancement, and transitions Jira tickets along the standard core-services workflow (Dev-Pending → Dev-Designing → Dev-Developing → Dev-CR/Merge).
- **Morning review (synchronous, human-driven):** the user reads a markdown digest of the night's work, opens the Draft MR(s) in GitLab, marks them Ready when satisfied, and merges. Failed or aborted SubTasks are bounced back to Dev-Pending with explanatory comments.

Existing safety rules remain the default for normal sessions; the AFK lane is the only place where they are explicitly relaxed in narrow, auditable ways (commits, pushes, MR creation), with hard guardrails (path allowlists, forbidden-file patterns, time caps) replacing the user's manual oversight.

## User Stories

### Authoring features

1. As the user, I want to grill an idea against an LLM until the design tree is resolved, so that I enter implementation with no ambiguity.
2. As the user, I want a single skill that turns my grilling conversation into a PRD on disk, so that I do not retype the same context.
3. As the user, I want the PRD stored at the existing per-ticket spec convention path, so that Product/QA can find it the same way they find any spec.
4. As the user, I want the parent Jira Enhancement's description to link to the PRD file, so that anyone reading the ticket can navigate to the spec without git access.
5. As the user, I want a separate skill that slices a PRD into Jira SubTasks under the Enhancement, so that the AFK driver has clean atomic units to pick up.
6. As the user, I want each generated SubTask to carry a structured Goal/Scope/Acceptance/Test-command block in its description, so that the agent has an enforceable contract.
7. As the user, I want every Enhancement to have at least one SubTask even when trivial, so that the AFK contract is uniform — the loop only ever picks up SubTasks.
8. As the user, I want to mark a SubTask as AFK-eligible by adding one well-known label, so that opt-in is granular and explicit.

### Running AFK

9. As the user, I want one command that drains my AFK queue overnight, so that I can walk away and trust progress.
10. As the user, I want the driver to discover work via a JQL filter (assignee=me, label=afk-agents, status=Dev-Pending, type=SubTask), so that other people's tickets are invisible to AFK.
11. As the user, I want SubTasks grouped by parent Enhancement and Enhancements drained one at a time, so that I wake up to *finished* features rather than scattered partial commits across many tickets.
12. As the user, I want the driver to prefer Enhancements that already have any SubTask past Dev-Pending, so that started work finishes before new work starts.
13. As the user, I want strict serial execution (one SubTask in flight at a time), so that I can reason about state without parallel-agent failure modes.
14. As the user, I want each SubTask to run in a fresh Claude Code session, so that prior SubTasks' context does not pollute later ones.
15. As the user, I want the driver to enforce a wall-clock cap per SubTask (1 hour), so that runaway sessions cannot consume an unbounded portion of the night.

### Worktree, branch, and MR mechanics

16. As the user, I want one git worktree per Enhancement (not per SubTask), so that build caches are reused across SubTasks of the same feature and I can inspect the in-flight state in one place.
17. As the user, I want a single branch per Enhancement, with one commit (or a few) per SubTask, so that review happens at the feature granularity, not the slice granularity.
18. As the user, I want exactly one Draft Merge Request per Enhancement, opened on first-SubTask commits, updated as further SubTasks land, so that the morning review is "open one MR, see the whole feature."
19. As the user, I want the AFK branch to be based off the parent Enhancement's declared Target Branch (a Jira custom field) at the moment AFK begins, never off my in-flight feature branches, so that AFK respects the release-branch routing intended for the Enhancement and can never poison work I am currently doing.
20. As the user, I want the Target Branch pulled and rebased into the AFK branch only once — after the Enhancement's last SubTask completes — so that mid-stream conflicts cannot cascade across SubTasks.
21. As the user, I want the driver to stop entirely when a final rebase produces conflicts, so that I never wake up to an automated conflict resolution I did not approve.
22. As the user, I want the driver to refuse to start an Enhancement whose Target Branch field is empty, so that AFK never has to guess where the work belongs.

### Jira lifecycle

23. As the user, I want each SubTask to follow Dev-Pending → Dev-Designing → Dev-Developing → Dev-CR/Merge mirroring the project's standard workflow, so that Jira reflects real progress in real time.
24. As the user, I want the parent Enhancement to transition Dev-Pending → Dev-Developing on the first SubTask pickup, with the MR link attached, so that the parent ticket is a true rollup of the work.
25. As the user, I want the parent Enhancement to transition to Dev-CR/Merge after the last SubTask is done, so that the Enhancement ticket signals reviewability.
26. As the user, I want the driver to refuse to pick up the first SubTask if the parent Enhancement is not in Dev-Pending, so that I cannot accidentally double-trigger AFK on a feature already past initial implementation.
27. As the user, I want the parent Enhancement's `## Implementation Notes (auto-maintained)` block updated with one terse bullet per completed SubTask (key, summary, MR number, commit count, test result), so that the ticket holds an accurate audit trail without burying the description.

### Safety rails

28. As the user, I want SubTask `Scope:` globs to be the sole gate on what AFK is allowed to touch, so that approval happens at SubTask-authoring time (when I am present) and runtime enforcement is purely mechanical.
29. As the user, I want a hard scope check on every commit's diff against the SubTask's declared Scope path globs, so that scope creep is caught before it ships.
30. As the user, I want every cross-module edit (any path outside 11700-payable, when working in a P2P-rooted Enhancement) to carry a JIRA-prefixed marker comment AFK adds automatically, so that future maintainers in the affected module know why the foreign edit exists.
31. As the user, I want a hard forbidden-file check for `UpgradeGroup*.java`, `PreDbMigration*`, and any liquibase changelog/changeset files, so that AFK can never write a database migration unattended.
32. As the user, I want SubTasks that touch JPA entities to be allowed (since liquibase-hibernate7 auto-generates the diff migration), so that ordinary entity changes still flow through AFK.
33. As the user, I want CI failure on the Draft MR to be ignored by the driver (continue to next SubTask), so that flaky pipelines do not stall the evening's queue.
34. As the user, I want local test/build failure to trigger up to 3 retries, then abort the SubTask back to Dev-Pending with the failing output as a comment, so that real failures do not get silently committed.
35. As the user, I want any SubTask that requires a database changeset to be skipped automatically, so that AFK never tries to write SQL it should not.
36. As the user, I want the driver to refuse to start any work if pre-flight checks fail (required tools missing, GITLAB_TOKEN missing, repo root not a directory), and to skip individual parents whose ticket-level prerequisites are missing (fixVersions, Target Branch, mid-state status), so that AFK starts from a known-good state every time without halting the whole pass on one bad parent.
37. As the user, I want my existing global rules (no autonomous commits, phase gates, no DB writes, run read-only commands myself) to remain the default outside the AFK lane, so that ordinary sessions are unaffected.

### Observability and recovery

38. As the user, I want a markdown morning digest summarising every Enhancement and SubTask AFK touched, with outcomes and MR links, so that I can triage the night's work in under 60 seconds.
39. As the user, I want full per-session logs preserved on disk, so that when the digest flags an unexpected outcome, I can read the actual transcript.
40. As the user, I want each per-SubTask abort to leave a clear comment on the Jira SubTask explaining why, so that I do not need to read logs to triage most failures.
41. As the user, I want the driver to be idempotent across runs — re-invoking after an abort should not double-process a SubTask, should not transition a ticket twice, and should not duplicate Implementation Notes bullets, so that I can safely re-run AFK without fear.

## Implementation Decisions

### Workflow shape

- **AFK opt-in is per-SubTask, via a single Jira label.** The label name is `afk-agents`. Inheriting from parent Enhancement is explicitly rejected — each slice is opted in individually.
- **Parent ticket type is Enhancement.** SubTasks (issuetype `SubTask`, id 10003 in P2P) are the unit of AFK execution. Even trivial Enhancements must be sliced into at least one SubTask.
- **Trigger is an external Python driver script** (`afk-driver`), not a skill alone. The driver spawns one fresh Claude Code session per SubTask; the per-SubTask logic lives in the `afk-go` skill that those sessions invoke.
- **Strict serial execution for v1.** No parallel agent sessions. Parallelism is a future expansion; the contract is designed not to preclude it but does not require it.

### PRD location and discovery

- **PRD path convention** follows the existing core-services per-ticket spec convention: rooted under the relevant service, organised by year/release, scoped by Enhancement key.
- **Service is derived from the Jira project key** via a driver-config mapping. The default mapping is `P2P → 11700-payable`. Future projects map to other services as the AFK lane is extended; meta-tooling Enhancements (like the AFK build-out itself) declare `## Service: tasks` in the Enhancement description, which routes the PRD to the repo-root `tasks/` directory.
- **Year and release are auto-derived** from the parent Enhancement's `fixVersions`. If `fixVersions` is missing, AFK refuses to start work on that Enhancement.
- **Target Branch (Jira `customfield_13706`) is required** on the parent Enhancement. AFK refuses to start without it. The value is mapped to a git branch name via the driver's `target_branch_map` config.
- **Per-Enhancement override** is possible via a `## Service` line in the Enhancement description — used when a P2P Enhancement's primary work happens outside 11700-payable, or for tooling Enhancements with no service home.
- **Parent Enhancement description carries a `## PRD` link** to the file path; the existing `## Implementation Notes (auto-maintained)` block convention is preserved unchanged in semantics, with AFK as a new producer of bullets in that block.

### Jira contract

- **JQL filter for AFK-pickable SubTasks** combines: assignee = current user, label = `afk-agents`, status = `Dev-Pending`, issuetype = `SubTask`. Ordered by Jira rank. The component allowlist that earlier drafts considered has been removed — assignee+label scoping is sufficient at the JQL stage, and the per-SubTask Scope-globs enforcement is the runtime safety net.
- **Cross-Enhancement priority:** SubTasks are grouped by parent Enhancement; Enhancements with at least one SubTask past `Dev-Pending` are preferred over fresh Enhancements ("finish what's started"). Within an Enhancement, SubTasks drain in rank order.
- **SubTask lifecycle:** `Dev-Pending` → (Start Development) → `Dev-Designing` → `Dev-Developing` → (Request CR & Merge) → `Dev-CR/Merge`. The `Dev-Designing` state is used as the "agent is reading the PRD and planning" phase; `Dev-Developing` is the "agent is editing files" phase.
- **Parent Enhancement lifecycle (driver-managed):** Enhancement is `Dev-Pending` at the moment the first AFK SubTask is picked up; transitions to `Dev-Developing` then with the MR link attached; transitions to `Dev-CR/Merge` after the last SubTask completes successfully. AFK refuses to start the first SubTask if parent is not in `Dev-Pending`.
- **SubTask abort semantics:** if a SubTask fails after retries, it is transitioned back to `Dev-Pending` with an explanatory comment, and the driver moves to the next SubTask in the same Enhancement. The parent Enhancement is not transitioned back; it remains `Dev-Developing`.
- **Final-rebase conflict semantics:** the Enhancement is left in `Dev-Developing`, the MR is left in Draft, a comment on the Enhancement records the conflict, and the driver exits without touching further Enhancements.

### SubTask description contract

The SubTask description carries a structured Markdown template with these fields, all required:

- **Goal** — single-sentence summary of the slice.
- **Scope** — list of path globs the SubTask is permitted to touch. Hard-enforced by the scope enforcer module.
- **Acceptance** — bullet checklist of "definition of done" criteria the agent uses to decide it is finished.
- **Test command** — exact shell command to run for green-bar verification.

The description also reserves an `## Implementation Notes (auto-maintained)` block, which the driver appends to on SubTask completion. Optional fields (Forbidden, Hints, Skip-if) are not part of v1 — project-level forbidden patterns live in the driver config.

### Sandbox and SCM mechanics

- **Sandbox = git worktree per Enhancement plus Claude Code permission scoping.** No Docker. The trade-off versus full container isolation is accepted: existing per-worktree JDK conventions and the user's existing memory rules already isolate enough state for v1.
- **Worktree path** is conventional and stable per Enhancement key.
- **Branch convention** is `mvu/afk/{ENH-ID}`, single branch per Enhancement, based off the parent Enhancement's **Target Branch** (Jira `customfield_13706`) at AFK start. The Target Branch value (e.g. `MASTER`, release-branch identifiers) is mapped to the corresponding git branch via the driver's `target_branch_map` config (default: `MASTER → master`).
- **MR convention:** one Draft MR per Enhancement, titled `[{ENH-ID}] {Enhancement summary}`, targeted at the same Target Branch the AFK branch was based off, opened after the first SubTask's commits. CI runs on Draft MRs are tolerated.
- **Target Branch is pulled into the AFK branch only once,** after the Enhancement's last SubTask completes. No mid-stream rebases.
- **Commit-per-SubTask** prefix convention: `[{SUBTASK-KEY}] {message}`. The MR description carries a checklist of the Enhancement's SubTasks linking to Jira.

### Cross-module edits

- **Home module is implied by Jira project.** P2P Enhancements live in `11700-payable` by default; SubTasks under them are expected to touch `11700-payable/**`.
- **Cross-module edits are pre-approved at SubTask-authoring time, not runtime.** A SubTask's `Scope:` glob list is the explicit confirmation: if `11999-common/src/...` is in the list, the human (you) approved that edit when reviewing/creating the SubTask. The runtime enforcer simply verifies the diff stays inside declared Scope.
- **AFK adds a JIRA-prefixed marker comment** on every file edited outside the home module. The comment names the SubTask key and one-line context, mirroring the existing memory rule for cross-team 11xxx care. Failure to add the marker on a cross-module file is a scope violation.
- **Cross-module SubTasks remain rare by construction:** because Scope must be declared up-front in the SubTask description, the human is forced to think about cross-module impact during PRD slicing.

### Module breakdown

The Python driver is decomposed into these modules. Interfaces are described by their responsibility, not by signature, so they remain durable as the implementation evolves.

- **`jira_client`** — encapsulates all Jira interactions: JQL queries, transition listing and execution, description editing scoped to the auto-maintained block, comment posting. Uses the existing Jira MCP from inside the spawned Claude session for transitions and description edits; uses direct REST for the driver's own queries.
- **`gitlab_client`** — encapsulates `glab` invocations: opening, updating, and querying a Draft MR. Idempotent at the operation level (re-opening an already-open MR is a no-op).
- **`worktree_manager`** — owns the per-Enhancement worktree lifecycle: create from master, validate clean state, switch active SubTask context, perform the post-last-SubTask rebase. Refuses to operate on a dirty or wrong-branch worktree.
- **`subtask_template`** — round-trip parser/emitter for the Goal/Scope/Acceptance/Test-command Markdown. The single source of truth for what a SubTask description means; both `prd-to-subtasks` (emitter) and `afk-go` (consumer) reach the description through this module's contract.
- **`scope_enforcer`** — pure function over a `git diff`, a SubTask's Scope globs, the driver's forbidden-pattern list, and the home module of the parent Enhancement. Returns either "clean" or a structured list of violations: out-of-scope paths, forbidden-pattern hits, and cross-module files lacking the JIRA-prefixed marker comment. This is the safety-rail core; it is the difference between "AFK is bounded" and "AFK is a foot-gun."
- **`digest_writer`** — writes the L4 morning markdown digest from a structured run record.
- **`runner`** — main orchestration loop. Owns queue grouping, Enhancement selection, pre-flight checks, per-SubTask Claude session spawning with timeout, lifecycle transitions, and rollup of run results into the structure consumed by `digest_writer`.

### Skills

- **`to-prd`** — adapted from the existing skill. The substantive change is the destination: PRD is written to the per-ticket spec convention path on disk, and the parent Enhancement description gets a link to that path. The interview/synthesis behaviour is unchanged.
- **`prd-to-subtasks`** — new skill. Consumes the PRD file and the parent Enhancement key; produces N Jira SubTasks under the Enhancement with the structured description template, the `afk-agents` label, and rank ordering that reflects the slicing decisions.
- **`afk-go`** — new skill. Consumes a single SubTask key. Reads the parent Enhancement's PRD and the SubTask's structured description, performs the Designing→Developing→CR/Merge lifecycle, runs the Test command, pushes commits, manages the MR, and updates the parent's Implementation Notes. Returns a structured outcome (success/aborted/skipped + reason) the driver consumes.

### Configuration

The `afk-driver` reads a single config file owned by the user (not checked into the repo), containing:

- The Jira-project → home-module mapping (default: `P2P → 11700-payable`).
- The Jira Target Branch field id (default: `customfield_13706`) and the value → git-branch mapping (default: `MASTER → master`).
- The forbidden-file pattern list (`UpgradeGroup*.java`, `PreDbMigration*`, liquibase changelogs/changesets).
- The cross-module marker-comment template, parametrised by `{SUBTASK-KEY}` and `{summary}`.
- The wall-clock cap per SubTask (default 1 hour).
- The retry count for local test/build failures (default 3).
- Paths for worktrees, logs, and the digest output.
- The **Dev-CR/Merge gate-field map** — Jira custom-field IDs the workflow validator demands before transition `251` (Dev-Developing → Dev-CR/Merge) is accepted on a SubTask, paired with default payloads the runner sends via `jira_edit` ahead of the transition. Defaults reflect the user's standing rule "not eligible for SRED unless I say otherwise":
  - `merge_request_link` → `customfield_12700` (string; runtime value = the open MR URL, no default).
  - `sred_eligibility` → `customfield_14005` (cascade; default `{"value": "SRED not eligible", "child": {"value": "Straightforward Implementation"}}`).
  - `time_estimation` → `customfield_14006` (single select; default `{"value": "Low: 10 and < 80 hours"}`).
  - `sred_rationale` → `customfield_14003` (ADF rich-text; runner wraps the configured plain-text default — `"Internal tooling, no technological uncertainty."` — into the ADF doc shape Jira requires).
  Both the field-ID map and the default payloads are individually overridable via `config.toml` (e.g. for a per-SubTask custom rationale, or to point at a different validator-controlled field if the Jira admin renumbers it).

## Testing Decisions

A good test for this system exercises external behaviour (does the right Jira transition occur, does the diff stay in scope, does the digest reflect outcomes correctly) and avoids implementation details (which functions were called, which intermediate state existed). Tests should be runnable on the user's Windows machine without an active Jira/GitLab connection — anything talking to a real network is mocked at the client boundary.

Modules covered by tests:

- **`subtask_template`** — unit tests covering parse/emit round-trips, malformed input handling, and missing-required-field detection. The parser is the contract between human-authored and machine-authored SubTask descriptions; brittleness here breaks both directions.
- **`scope_enforcer`** — unit tests with fixture diffs covering: pure in-scope diff in home module (clean), single out-of-scope file (violation), mixed in-scope and out-of-scope, forbidden-pattern hit (e.g. an `UpgradeGroup*.java`), JPA entity edit (allowed), liquibase changelog (forbidden), cross-module file with marker comment (clean), cross-module file without marker comment (violation). Pure function, easy fixtures, mandatory coverage given this is the safety rail.
- **`worktree_manager`** — integration tests against a temporary git repo: create-when-absent, idempotent-when-present, refuse-on-dirty, rebase-conflict path. Real git, no Jira/GitLab involved.
- **`runner`** — integration tests with `jira_client` and `gitlab_client` mocked. Cover: empty queue exit, single Enhancement single SubTask happy path, single Enhancement multi-SubTask drain, in-progress-Enhancement priority over fresh Enhancement, parent-Enhancement-not-in-Dev-Pending refusal, post-last-SubTask rebase conflict path.

Modules excluded from tests:

- **`jira_client`** and **`gitlab_client`** — thin wrappers over external CLI/MCP. Smoke tests only via the `runner` integration suite. Unit-testing them in isolation tests the mock more than the wrapper.
- **`digest_writer`** — covered by golden-file assertions reachable from the `runner` integration tests; no dedicated suite.

Prior art in the repo:

- The unit-testing conventions in `unit-testing.md` (JUnit 5, ApprovalTests, `JsonApprovals.verifyJson`) are Java-side. Python tests for `afk-driver` follow standard `pytest` idioms with `pytest`-style fixtures; ApprovalTests parallels could be used for the digest golden files via `approvaltests` (Python port) but are optional.
- The existing `build-scripts/` directory is the closest stylistic precedent for Python tooling in this repo.

## Out of Scope

- **Parallel AFK agents.** v1 is strictly serial. The module decomposition does not preclude parallelism, but no work goes into supporting it.
- **Docker sandboxing.** v1 uses git worktrees with permission scoping. Docker is reserved for a future iteration if shared-state incidents justify the build-cost penalty.
- **Scheduled / cron-driven AFK.** v1 trigger is manual invocation. The `schedule` skill could be wired up later but is not part of this PRD.
- **A QA-from-MR skill** (Matt's QA feedback step). v1 does manual MR review. The slot exists in the workflow diagram but no skill is built.
- **Cross-team 11xxx automation.** AFK on cross-team services beyond the user's allowlist is rejected by JQL. The existing memory rule for cross-team care (JIRA-prefixed marker comments, separate commits, minimal diffs) continues to apply only outside AFK.
- **Repos beyond core-services.** No multi-repo support. AFK is single-repo.
- **DB migration authoring.** AFK never writes `UpgradeGroup*.java`, `PreDbMigration*`, or liquibase changelogs/changesets. Enhancements that require these are not AFK candidates.
- **Automatic conflict resolution on the post-last-SubTask rebase.** Conflicts halt the driver; humans resolve.
- **MR auto-promotion to Ready.** AFK leaves MRs in Draft; the human flips to Ready as the explicit review-pass gate.
- **Implementation of the `to-prd` skill from scratch.** v1 adapts the existing skill rather than rewriting it.

## Further Notes

- **Why this is a PRD, not just a plan in `tasks/todo.md`.** The grilling session resolved many independent design branches (label, lifecycle, branch shape, scope rails, etc.) that need to be persisted as a single artefact for future-you and the LLM to refer to. Future SubTasks for building this system will reference this PRD; placing it in `tasks/` keeps it adjacent to existing planning artefacts but distinguishable from active task lists.
- **The SubTask issuetype exists in P2P** (id 10003, hierarchy level −1) but is not in active use; the most recent live examples are several years old and Closed. Using SubTasks for AFK is a slight revival of an existing-but-dormant convention rather than a brand-new ticket type, which means no Jira-admin work is needed.
- **Project→service mapping is convention, not a Jira field.** The driver maps `P2P → 11700-payable` as a known-by-everyone shorthand: P2P is the Procure-to-Pay project, which lives in the payable service. As AFK extends to other Jira projects, each new mapping is a one-line config addition — no need to backfill a Jira `components` field across hundreds of historical tickets.
- **The SubTask workflow has not been independently verified.** Available transitions were inspected on Bug and Enhancement issuetypes (P2P-1218, P2P-1207). The first real AFK SubTask creation should query its own transitions via `mcp__jira__jira_transitions` to confirm the expected `Start Development` and `Request CR & Merge` transitions exist; the PRD assumes they do.
- **Memory rules outside the AFK lane are unchanged.** "User makes commits themselves," "stop after each phase," "never alter DB directly," "run read-only commands yourself," and the cross-team 11xxx rules continue to govern ordinary sessions. AFK is the explicit, labelled, narrow-scoped exception.
- **The morning digest is the killer feature.** If the digest is wrong, AFK is worse than not having AFK — silent failure at scale. `digest_writer` deserves disproportionate care relative to its size.
- **Implementation order inside this PRD's eventual SubTasks should put the safety rails first.** Build `subtask_template` and `scope_enforcer` (and their tests) before `runner` invokes anything that could mutate Jira or git state. The point of TDD here is not green bars; it is "the safety rail exists before the thing it guards."

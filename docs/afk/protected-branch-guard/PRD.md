# PRD — protected-branch guard: one linked worktree per agent session

Provisional slug `protected-branch-guard` (no tracker item yet). Decisions settled 2026-09-29 over 4 decision rounds.

## Problem Statement

A developer runs several agent sessions on one repository at the same time.

- A session that stays in the main checkout (the folder the repository was cloned into) changes the same files and moves the same branch as another session. The developer must remember to tell every agent to use a worktree, and forgets.
- An agent that works directly on a protected branch commits where only reviewed changes belong.
- A new worktree lacks what the repository needs to work in it (for example IDE run configurations). Each repository does this setup by hand or with a personal script.

## Solution

For every agent of a developer who installed the afk plugin, in every repository:

- Before its first change, the agent moves into its own linked worktree on its own branch. The session continues there with no human step where the harness allows it (catalog `M`).
- The plugin enforces the rule. It refuses every edit and every shell command while the session sits on a protected branch or in the main checkout (catalog `P`).
- The plugin learns which branches are protected from GitHub or GitLab (catalog `S`).
- Every new worktree is made one way: branch name checked, personal files copied, build set up, and the repository's own registered setup scripts run.
- The plugin removes the worktrees it made once they hold nothing unsaved.
- A human who needs an agent on a protected branch sets one variable at launch.

## Catalog

### H — harness classes

Requirements name a harness by what its agent can do. `PROVIDERS.md` maps each supported harness to its class.

| ID | Class | Agent can move its own session | Native folder switch that keeps the conversation |
|----|-------|-------------------------------|--------------------------------------------------|
| H-1 | self-moving | yes: a native worktree tool the agent calls; the harness asks the plugin's worktree-creation hook for the folder | human command only |
| H-2 | fixed-folder | no: a folder change inside one shell command does not carry to the next | human command only (`/cd`), refused while a turn runs |

### P — session placement and verdict

A guarded action is an edit or a shell command (catalog `A`). The verdict applies to the session's working directory and, for an edit, also to the target file's location.

| ID | Checkout | Branch | Verdict |
|----|----------|--------|---------|
| P-1 | main checkout | protected | refuse |
| P-2 | main checkout | not protected | refuse |
| P-3 | linked worktree | protected | refuse |
| P-4 | linked worktree | not protected | allow |
| P-5 | outside any git repository | — | allow |
| P-6 | any | any, with `AFK_ALLOW_PROTECTED=1` set at launch | allow |

### A — guarded actions

| ID | Action | In P-1..P-3 |
|----|--------|-------------|
| A-1 | file edit, file write, notebook edit, patch apply | refused |
| A-2 | shell command, in any shell the harness offers, including background commands | refused |
| A-3 | built-in file read and search tools | allowed |
| A-4 | the harness's native worktree tool (H-1) | allowed |

### S — where the protected-branch list comes from

Asked on every check; no cache ([ADR-0004](adr/requirements/0004-protected-list-asked-live.md)).

| ID | Forge | Source | Match |
|----|-------|--------|-------|
| S-1 | GitHub | the repository's protected branches, as the forge lists them | exact name |
| S-2 | GitLab | the project's protected-branch patterns, every page | exact name or wildcard pattern |
| S-3 | fallback: no network, no forge login, or forge not GitHub/GitLab | the remote's default branch, `main`, `master` | exact name |

The forge comes from the repository's afk configuration when present, else from the remote address.

### M — how a session reaches its worktree

| ID | Harness class and start | Move | Human step |
|----|-------------------------|------|------------|
| M-1 | H-1, any start (terminal, IDE, desktop, herdr) | the agent calls the native worktree tool with a new name; the plugin's worktree-creation hook makes the worktree; the session continues in it | none |
| M-2 | H-2, started through the plugin's launch command | the command makes the worktree, then starts the harness in it | none |
| M-3 | H-2, started another way, inside a herdr pane | the refused agent types `/cd <worktree>` into its own pane; the conversation is kept | none (unverified premise: an H-2 agent's keystrokes into its own herdr pane run `/cd` once its turn ends) |
| M-4 | H-2, started another way, outside herdr | the refusal prints the exact `/cd <worktree>` line | the human types that line |

## User Stories

1. As a developer running several agent sessions on one repository, I want each session to move into its own worktree without my telling it, so that no two sessions change the same files or branch.
2. As a developer, I want agents kept off the branches my forge protects.
3. As a repository maintainer, I want to register setup steps that every new worktree runs, tracked in git, with no effect on developers who do not use the plugin.
4. As a developer who must let an agent work on a protected branch, I want one switch at launch that allows it for that session only.

## Acceptance Criteria

Guard:

- [ ] AC-001 For every row of catalog `P`, a guarded action (A-1, A-2) from a session in that placement gets the row's verdict, on every supported harness.
- [ ] AC-002 An edit whose target file lies in a P-1..P-3 location is refused, even when the session itself sits in a P-4 worktree.
- [ ] AC-003 A refusal names its cause (the protected branch by name, or "main checkout") and the move for the session's harness class from catalog `M`.
- [ ] AC-004 In a P-1..P-3 placement, A-3 and A-4 actions succeed.
- [ ] AC-005 A patch apply in a P-1..P-3 placement is refused; the same patch from a P-4 worktree whose targets all lie in that worktree is allowed.
- [ ] AC-006 The guard is active in a repository with no afk configuration, for every developer who installed the plugin.

Protected branches:

- [ ] AC-007 A GitHub branch the forge lists as protected yields verdict "protected"; a branch it does not list yields "not protected".
- [ ] AC-008 A GitLab branch matching any protected pattern, exact or wildcard, on any page of the list, yields "protected"; a branch matching none yields "not protected".
- [ ] AC-009 When the forge cannot answer (S-3 conditions), exactly the default branch, `main` and `master` yield "protected", and the session shows one notice naming the fallback.
- [ ] AC-010 A branch protected on the forge after the session started is refused at the next guarded action.

Moving and worktree creation:

- [ ] AC-011 An H-1 session refused under P-1..P-3 that calls the native worktree tool with a new name continues in a new linked worktree, with no approval prompt in any permission mode, and its next guarded action there is allowed.
- [ ] AC-012 An H-2 session started through the plugin's launch command from a P-1..P-3 placement starts in a new linked worktree, and herdr still detects the agent's kind.
- [ ] AC-013 An H-2 session refused inside herdr ends in its new worktree with its conversation kept and no human keystroke (unverified premise: see M-3).
- [ ] AC-014 An H-2 session refused outside herdr prints a `/cd` line that, typed as shown, moves the session into its new worktree with the conversation kept.
- [ ] AC-015 Every new worktree, whichever path made it, has a branch that matches the repository's branch pattern; a name that does not match is rejected before any worktree exists.
- [ ] AC-016 Every new worktree carries the files the repository's worktree copy list names.
- [ ] AC-017 A session started in an existing linked worktree on an unprotected branch works in place and makes no new worktree.
- [ ] AC-018 Two sessions that start at the same moment from one main checkout end in 2 different worktrees on 2 different branches.
- [ ] AC-019 Worktrees the plugin places inside the repository folder do not appear in the main checkout's `git status`.

Repository setup scripts:

- [ ] AC-020 Every script the repository registers for the `WorktreeCreated` event runs once per new worktree, in declaration order, and receives the worktree folder and branch.
- [ ] AC-021 A registered script that fails leaves the worktree in place and prints a warning naming the script.
- [ ] AC-022 A registered script whose path resolves outside the repository is not run, and a warning names it.
- [ ] AC-023 A developer without the plugin runs no registered script and meets no guard.

Git backstop:

- [ ] AC-024 An agent's commit on a protected branch or in the main checkout is refused by git; the same commit typed by a human succeeds.
- [ ] AC-025 An agent's branch move (checkout, switch, reset, merge, rebase) in the main checkout is refused by git; the same command typed by a human succeeds.

Override:

- [ ] AC-026 A session launched with `AFK_ALLOW_PROTECTED=1` gets verdict "allow" for every placement; a session launched without it in the same checkout at the same time is still refused.

Cleanup:

- [ ] AC-027 A plugin-made worktree whose session ends with no uncommitted change and no unpushed commit is removed; its branch is deleted when it has no commit of its own.
- [ ] AC-028 A plugin-made worktree whose session ends with an uncommitted change or an unpushed commit is kept, and the session's last output names the resume command and the remove command.
- [ ] AC-029 A stale plugin-made worktree is pruned only when its owner process is gone and it holds no uncommitted change and no unpushed commit; a worktree the plugin did not make is never removed.

Behavior line:

- [ ] AC-030 After `/afk:setup`, the managed behavior block in each user instruction file carries the worktree rule, and the setup drift check reports it current.

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Change files or run shell commands (story 1, 2) | agent session in a P-4 worktree; any session with the launch override | agent session in P-1..P-3 without the override | one repository checkout | catalog `P`, catalog `A` |
| Commit or move a branch (story 1, 2) | human at a terminal; agent in a P-4 worktree | agent in P-1..P-3 without the override | one repository | AC-024, AC-025 |
| Register worktree setup scripts (story 3) | repository maintainer, by committing the registration | developer without the plugin (never runs them) | one repository | script path inside the repository (AC-022) |
| Set the launch override (story 4) | human who starts the harness | agent session (cannot set it for itself mid-session) | one launched process tree | variable set before launch |

## Implementation Decisions

Behavioural decisions with a record:

- Every plugin user, every repository, on by default: [ADR-0001](adr/requirements/0001-on-for-every-plugin-user.md).
- The main checkout is refused on any branch, not only on protected branches: [ADR-0002](adr/requirements/0002-main-checkout-refused-on-any-branch.md).
- Every shell command is refused in P-1..P-3, not only commands that look like writes: [ADR-0003](adr/requirements/0003-refuse-every-shell-command.md).
- The protected-branch list is asked from the forge on every check: [ADR-0004](adr/requirements/0004-protected-list-asked-live.md).
- Protection covers sessions that forget; deliberate writes into another folder are out of scope: [ADR-0005](adr/requirements/0005-guard-against-forgetting-not-intent.md).
- An H-1 session moves with its native worktree tool; no launch wrapper for H-1: [ADR-0006](adr/requirements/0006-self-moving-harness-moves-natively.md).
- A refused H-2 agent inside herdr moves itself by typing `/cd` into its own pane: [ADR-0007](adr/requirements/0007-fixed-folder-agent-self-types-cd-in-herdr.md).
- Repositories register setup scripts as a `WorktreeCreated` event in their own repository hooks manifest; a failing script warns: [ADR-0008](adr/requirements/0008-repository-setup-scripts-registered-in-hooks-manifest.md).

Other decisions:

- A harness's own "start in a worktree" option is not used when it makes a worktree with no branch.
- The H-1 worktree-creation hook routes every worktree that harness makes (agent tool, launch option, subagent isolation) through the plugin's one worktree-creation path, under a folder inside the repository hidden through the clone's local exclude file.
- The rule reaches agents two ways: a new row in the managed behavior registry (instruction) and plugin hooks plus installed git hooks (enforcement).
- The forge adapter family gains a protected-branch read for GitHub and GitLab; the verb set today has none.
- `PROVIDERS.md` gains the harness-to-class mapping of catalog `H`; `providers/CONFORMANCE.md` gains the live proof of AC-011..AC-014.
- Ships only after live runs pass on every supported harness and herdr; the changelog marks it as a behaviour change for every plugin user.
- Replaces the repository-only guard prototype on branch `worktree-main-checkout-guard` (`.afk/hooks/main-checkout-guard.sh`).
- No staple applies: this repository has no `STAPLES.md`.

Modules:

| Module | Responsibility | Interface |
|--------|----------------|-----------|
| protected-lookup | catalog `S`: find the forge, read its protected list, match wildcards, fall back | branch + checkout → protected yes/no + source |
| session-guard | catalogs `P` and `A`: verdict per tool call, every harness's tool shapes, override, class-specific move instruction | tool-call envelope → allow, or refuse + reason |
| worktree-create | the one creation path: branch check, file copy, build setup, setup scripts, owner record, lock; the H-1 worktree-creation hook calls it | name + base → worktree folder |
| setup-scripts | `WorktreeCreated` event in the repository hooks manifest; runs registered scripts | worktree folder + branch → per-script result |
| git-backstop | agent-only refusal of commits and branch moves in P-1..P-3 | git hook verdict |
| worktree-cleanup | remove on clean end, keep and explain on dirty end, prune stale | worktree → removed / kept + commands |
| fixed-folder-move | the plugin's launch command (M-2); in-herdr `/cd` self-move (M-3) | launch arguments → H-2 harness running in a worktree |
| behavior-line | registry row delivered by the existing setup transport | registry row |

## Testing Decisions

Test external behaviour: the verdict for an envelope, the answer for a branch, the worktree that exists afterwards. Never the internals.

| Module | Strategy | Prior art |
|--------|----------|-----------|
| protected-lookup | test-first; forge answers stubbed at the adapter boundary, plus one live read per forge | `scripts/tests/test_forge_adapters.py` |
| session-guard | test-first; one case per catalog `P` row × each harness's envelope shape, throwaway repositories with nested linked worktrees | `scripts/tests/test_main_checkout_guard.py` (prototype) |
| worktree-create | test-first; disposable repositories, concurrent start, branch-pattern rejection | `scripts/tests/create-worktree-smoke.sh` |
| setup-scripts | test-first; failing, missing and outside-repository scripts | `scripts/tests/test_run_hook.py` |
| git-backstop | test-first; agent versus human environment | `hooks/tests/hook-smoke.sh` (envelope fixtures in `hooks/tests/envelopes/`) |
| worktree-cleanup | test-first; clean, dirty, stale and foreign worktrees | — |
| fixed-folder-move | live runs on every supported harness and herdr (AC-012..AC-014) | `providers/CONFORMANCE.md` live-proof rows |
| behavior-line | the existing behavior registry gate | `scripts/tests/test_behavior_registry.py` |

## Out of Scope

- An agent already in its own worktree writing into another folder on purpose ([ADR-0005](adr/requirements/0005-guard-against-forgetting-not-intent.md)).
- An operating-system sandbox, and any change to a harness's full-bypass mode.
- A harness's own worktree option that makes a worktree with no branch.
- A per-repository switch that turns the guard off; the only override is per launch.
- Harnesses the plugin does not support.

## Further Notes

Assumptions this PRD rests on:

- (unverified premise: an H-2 agent's keystrokes into its own herdr pane run `/cd` once its turn ends) — AC-013, M-3, ADR-0007. The H-2 harness's `/cd` requires an idle session (read in its source). Live-prove before building the self-move.
- (unverified premise: herdr still detects the agent's kind when the plugin's launch command starts an H-2 harness) — AC-012.
- (unverified premise: the H-2 harness's `/cd` accepts a new worktree without a separate trust step) — it refuses an untrusted folder (read in its source); whether a worktree inherits its repository's trust is unchecked. AC-013, AC-014.
- (unverified premise: a developer without admin rights can read the protected list) — GitHub was read as repository owner; GitLab was read on one project with the reader's own role. AC-007, AC-008.

Evidence behind the design: two agent proposals, critiques and final positions, the live H-1 hook trial, harness source reads with versions, and the decision record of all 4 rounds. They live in the session scratchpad (`worktree-debate/`), not in this repository; the SDD carries the harness versions.

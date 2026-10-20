# PRD — protected-branch guard: one linked worktree per agent session

Provisional slug `protected-branch-guard` (no tracker item yet). Decisions settled 2026-09-29 over 4 decision rounds. Revised 2026-10-06: the guard refuses identified mutations, not shell syntax ([ADR-0010](adr/requirements/0010-refuse-mutations-not-syntax.md) to [ADR-0013](adr/requirements/0013-linked-worktree-occupancy.md)). Revised 2026-10-09: in a guarded placement, a shell command runs only when the guard proves it read-only, and the guard refuses before the change, never after it ([ADR-0014](adr/requirements/0014-refuse-unproven-shell-commands-before-they-run.md)).

## Problem Statement

A developer runs several agent sessions on one repository at the same time.

- A session that stays in the main checkout (the folder the repository was cloned into) changes the same files and moves the same branch as another session. The developer must remember to tell every agent to use a worktree, and forgets.
- An agent that works directly on a protected branch commits where only reviewed changes belong.
- A guard that refuses harmless commands (a pipe, a redirect to the null device) trains agents to work around it.
- A new worktree lacks what the repository needs to work in it (for example IDE run configurations). Each repository does this setup by hand or with a personal script.

## Solution

For every agent of a developer who installed the afk plugin, in every repository:

- Before its first change, the agent moves into its own linked worktree on its own branch. The session continues there with no human step where the harness allows it (catalog `M`).
- The plugin enforces the rule. It refuses a mutation whose resource is guarded: the main checkout, the worktree of a protected branch, or a worktree another live session holds (catalog `P`). Reads, composed reads and tools that touch no repository run anywhere.
- In the main checkout or the worktree of a protected branch, a shell command runs only when the plugin proves it read-only. Every other command is refused before it runs.
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

A guarded action is an identified mutation (catalog `A`). The verdict applies to the resource the mutation changes: for an edit, each target file's location; for a shell command, each literal path or repository the recognizer finds ([ADR-0010](adr/requirements/0010-refuse-mutations-not-syntax.md)). A shell segment that runs in a P-1..P-3 resource is also a guarded action unless the allow-list proves it read-only (A-6, [ADR-0014](adr/requirements/0014-refuse-unproven-shell-commands-before-they-run.md)). Any other call is allowed.

| ID | Resource the mutation changes | Branch | Verdict |
|----|-------------------------------|--------|---------|
| P-1 | main checkout | protected | refuse |
| P-2 | main checkout | not protected | refuse, except P-7 |
| P-3 | linked worktree | protected | refuse |
| P-4 | linked worktree no other live session outside the session's group holds | not protected | allow |
| P-5 | a path outside any git repository | — | allow |
| P-6 | any | any, with `AFK_ALLOW_PROTECTED=1` set at launch | allow |
| P-7 | main checkout, by `git pull --ff-only` that meets the conditions of [ADR-0011](adr/requirements/0011-main-checkout-fast-forward-sync.md) | base branch | allow |
| P-8 | linked worktree another live session outside the session's group holds ([ADR-0013](adr/requirements/0013-linked-worktree-occupancy.md)) | not protected | refuse |

### A — guarded actions

| ID | Action | Verdict |
|----|--------|---------|
| A-1 | file edit, file write, notebook edit, patch apply | judged at every target |
| A-2 | shell command with an identified mutation: a recognized git verb or file writer with a literal target | judged at the resource |
| A-3 | shell command the allow-list proves read-only: a read, a composition of reads, a redirect to the null device, a forge read, a herdr command | allowed in every placement |
| A-4 | built-in file read and search tools; a tool with no path-like key | allowed |
| A-5 | the harness's native worktree tool (H-1) and the plugin's `scripts/create-worktree` | allowed |
| A-6 | shell command with a segment the allow-list cannot prove read-only (an unlisted program, a write flag, an opaque target) that runs in a P-1..P-3 resource | refused before it runs (AC-033); outside those resources an unrecognized program is allowed |

### S — where the protected-branch list comes from

A definite forge answer is reused for at most 5 minutes. The remote's default branch, `main` and `master` are asked at every check ([ADR-0004](adr/requirements/0004-protected-list-asked-live.md)).

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

- [ ] AC-001 For every row of catalog `P`, a guarded action (A-1, A-2) whose resource lies in that row gets the row's verdict, on every supported harness.
- [ ] AC-002 An edit whose target lies in a P-1..P-3 or P-8 resource is refused, even when the session sits in a P-4 worktree. An edit whose target lies outside every repository is allowed, even from a main-checkout session.
- [ ] AC-003 A refusal names its cause (the protected branch by name, "main checkout", or the occupant), the resource it protects, and a move for the session's harness class from catalog `M` that the session can run.
- [ ] AC-004 In every placement, A-3, A-4 and A-5 actions succeed.
- [ ] AC-005 A patch apply with a target in a P-1..P-3 or P-8 resource is refused; the same patch from a P-4 worktree whose targets all lie in that worktree is allowed.
- [ ] AC-006 The guard is active in a repository with no afk configuration, for every developer who installed the plugin.

Protected branches:

- [ ] AC-007 A GitHub branch the forge lists as protected yields verdict "protected"; a branch it does not list yields "not protected".
- [ ] AC-008 A GitLab branch matching any protected pattern, exact or wildcard, on any page of the list, yields "protected"; a branch matching none yields "not protected".
- [ ] AC-009 When the forge cannot answer (S-3 conditions), exactly the default branch, `main` and `master` yield "protected", and the session shows one notice naming the fallback.
- [ ] AC-010 A branch protected on the forge after the session started is refused at every guarded action that starts 5 minutes or more after the change; the remote's default branch, `main` and `master` are refused at the next guarded action.

Moving and worktree creation:

- [ ] AC-011 An H-1 session refused under P-1..P-3 that calls the native worktree tool with a new name continues in a new linked worktree, with no approval prompt in any permission mode, and its next guarded action there is allowed.
- [ ] AC-012 An H-2 session started through the plugin's launch command from a P-1..P-3 placement starts in a new linked worktree, and herdr still detects the agent's kind.
- [ ] AC-013 An H-2 session refused inside herdr ends in its new worktree with its conversation kept and no human keystroke (unverified premise: see M-3).
- [ ] AC-014 An H-2 session refused outside herdr prints a `/cd` line that, typed as shown, moves the session into its new worktree with the conversation kept.
- [ ] AC-015 Every new worktree, whichever path made it, has a branch that matches the repository's branch pattern; a name that does not match is rejected before any worktree exists.
- [ ] AC-016 Every new worktree carries the files the repository's worktree copy list names.
- [ ] AC-017 A session started in an existing linked worktree on an unprotected branch that no other live session outside its group holds works in place and makes no new worktree.
- [ ] AC-018 Two sessions that start at the same moment from one main checkout end in 2 different worktrees on 2 different branches.
- [ ] AC-019 Worktrees the plugin places inside the repository folder do not appear in the main checkout's `git status`.

Repository setup scripts:

- [ ] AC-020 Every script the repository registers for the `WorktreeCreated` event runs once per new worktree, in declaration order, and receives the worktree folder and branch.
- [ ] AC-021 A registered script that fails leaves the worktree in place and prints a warning naming the script.
- [ ] AC-022 A registered script whose path resolves outside the repository is not run, and a warning names it.
- [ ] AC-023 A developer without the plugin runs no registered script and meets no guard.

Git backstop:

- [ ] AC-024 An agent's commit on a protected branch or in the main checkout is refused by git; the same commit typed by a human succeeds.
- [ ] AC-025 An agent's branch move (checkout, switch, reset, merge, rebase) in the main checkout is refused by git, except the fast-forward of AC-036; the same command typed by a human succeeds.

Override:

- [ ] AC-026 A session launched with `AFK_ALLOW_PROTECTED=1` gets verdict "allow" for every placement; a session launched without it in the same checkout at the same time is still refused.

Cleanup:

- [ ] AC-027 A plugin-made worktree whose session ends with no uncommitted change and no unpushed commit is removed; its branch is deleted when it has no commit of its own.
- [ ] AC-028 A plugin-made worktree whose session ends with an uncommitted change or an unpushed commit is kept, and the session's last output names the resume command and the remove command. Where the harness shows no session-end output, the report appears at the next session start.
- [ ] AC-029 A stale plugin-made worktree is pruned only when its owner process is gone (a pid reused by another process counts as gone) and it holds no uncommitted change and no unpushed commit; a worktree the plugin did not make is never removed.
- [ ] AC-031 In every placement, a command the allow-list proves read-only (a read, a composition of reads, a redirect to the null device) runs; a command with an identified mutation of a guarded resource is refused before execution.

Shell recognition and faults:

- [ ] AC-032 A command line joined by `&&`, `||`, `;`, `|`, `&` or a newline, or continued across lines, is judged per segment. A folder change inside a group or a pipeline does not carry to later segments. A literal target that resolves into a guarded resource is refused; outside a P-1..P-3 resource, an opaque target (variable, substitution, glob) passes.
- [ ] AC-041 A call with no identified mutation and no unproven segment is allowed when the verdict cannot be computed. An identified mutation, or an unproven segment, inside a git work tree is refused with the fault named.

Refusal before the call:

- [ ] AC-033 In a P-1..P-3 resource, a shell command with a segment the allow-list cannot prove read-only is refused before it runs, and the refusal names that segment and the move. A loop that moves files through its loop variable is refused, and no file moves.
- [ ] AC-034 Each allow-list form runs in a P-1..P-3 resource, and its mutating twin is refused: `find -delete`, `sed -i`, `curl -o`, a redirect into a file.
- [ ] AC-035 A segment whose literal folder or literal targets lie outside every P-1..P-3 resource runs from a session that sits in one. A P-4 worktree is unaffected.

Main checkout sync:

- [ ] AC-036 `git pull --ff-only` on a clean base branch in the main checkout succeeds and moves the branch. A dirty tree, divergence, a wrong branch, no upstream, a detached or unborn HEAD, an operation in progress, an expired authorization, or a mismatched commit is refused with the condition named.

Occupancy:

- [ ] AC-037 A second live session outside the holder's group is refused a mutation in an occupied linked worktree, and the refusal names the occupant. The holder is never refused. A refused session is not registered.
- [ ] AC-038 Sessions with the same non-empty `AFK_WORKTREE_GROUP`, or in one herdr tab (`HERDR_ENV=1` and the same `HERDR_TAB_ID`), share a worktree.
- [ ] AC-039 A dead occupant is dropped. A recycled pid counts as dead. An unreadable creation time counts as occupied. Cleanup never reads the occupancy record.
- [ ] AC-040 A session that starts in an occupied worktree sees one advisory line and is not blocked.

Behavior line:

- [ ] AC-030 After `/afk:setup`, the managed behavior block in each user instruction file carries the worktree rule, and the setup drift check reports it current.

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Change files or run shell commands (story 1, 2) | agent session whose mutations land in a P-4 resource; any session with the launch override | agent session whose identified mutation lands in P-1..P-3 or P-8, or whose unproven shell segment runs in P-1..P-3, without the override | one repository checkout | catalog `P`, catalog `A` |
| Commit or move a branch (story 1, 2) | human at a terminal; agent in a P-4 worktree; agent's base-branch fast-forward in the main checkout | agent in P-1..P-3 without the override | one repository | AC-024, AC-025, AC-036 |
| Register worktree setup scripts (story 3) | repository maintainer, by committing the registration | developer without the plugin (never runs them) | one repository | script path inside the repository (AC-022) |
| Set the launch override (story 4) | human who starts the harness | agent session (cannot set it for itself mid-session) | one launched process tree | variable set before launch |

## Implementation Decisions

Behavioural decisions with a record:

- Every plugin user, every repository, on by default: [ADR-0001](adr/requirements/0001-on-for-every-plugin-user.md).
- The main checkout is refused on any branch, not only on protected branches: [ADR-0002](adr/requirements/0002-main-checkout-refused-on-any-branch.md).
- Mutations are refused by the resource they change, not by command shape: [ADR-0010](adr/requirements/0010-refuse-mutations-not-syntax.md), superseding [ADR-0009](adr/requirements/0009-allow-conservative-read-only-shell-commands.md).
- The main checkout may fast-forward its base branch: [ADR-0011](adr/requirements/0011-main-checkout-fast-forward-sync.md).
- In a P-1..P-3 resource, a shell command runs only when the allow-list proves it read-only, and every other command is refused before it runs: [ADR-0014](adr/requirements/0014-refuse-unproven-shell-commands-before-they-run.md), superseding [ADR-0012](adr/requirements/0012-change-meter-and-quarantine.md).
- A linked worktree has one live holder, or one team: [ADR-0013](adr/requirements/0013-linked-worktree-occupancy.md).
- The protected-branch list is asked from the forge, with a cache of at most 5 minutes that never holds the default branch, `main` or `master`: [ADR-0004](adr/requirements/0004-protected-list-asked-live.md).
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
| shell-mutations | A-2: the literal paths a shell command line changes | command + folder → resources |
| main-sync | P-7: sync conditions, the authorization record | pull command → allow or refuse |
| read-only | A-3, A-6: the allow-list of read-only shell forms | shell segment → proven or not |
| occupancy | P-8: the live holders of a linked worktree | session + worktree → holder or none |
| git-backstop | agent-only refusal of commits and branch moves in P-1..P-3; consumes the sync authorization | git hook verdict |
| worktree-cleanup | remove on clean end, keep and explain on dirty end, prune stale | worktree → removed / kept + commands |
| fixed-folder-move | the plugin's launch command (M-2); in-herdr `/cd` self-move (M-3) | launch arguments → H-2 harness running in a worktree |
| behavior-line | registry row delivered by the existing setup transport | registry row |

## Testing Decisions

Test external behaviour: the verdict for an envelope, the answer for a branch, the worktree that exists afterwards. Never the internals.

| Module | Strategy | Prior art |
|--------|----------|-----------|
| protected-lookup | test-first; forge answers stubbed at the adapter boundary, plus one live read per forge | `scripts/tests/test_forge_adapters.py` |
| session-guard | test-first; one case per catalog `P` row × each harness's envelope shape, throwaway repositories with nested linked worktrees | `scripts/tests/test_protected_branch_guard.py`, `test_protected_branch_acceptance.py` |
| shell-mutations | test-first; one case per recognized form and per opaque form | `scripts/tests/test_shell_mutations.py` |
| main-sync | test-first; a real `git pull --ff-only` through the installed hooks, one refusal per condition | `scripts/tests/test_main_sync.py` |
| read-only | test-first; one case per listed form beside its mutating twin | `scripts/tests/test_read_only.py` |
| occupancy | test-first; live helper processes as identities, herdr variables, a racing pair | `scripts/tests/test_occupancy.py` |
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
- A write that a listed program makes through its environment or configuration, or that a program started outside every P-1..P-3 resource makes into one ([ADR-0014](adr/requirements/0014-refuse-unproven-shell-commands-before-they-run.md) lists the gaps).

## Further Notes

Assumptions this PRD rests on:

- (unverified premise: an H-2 agent's keystrokes into its own herdr pane run `/cd` once its turn ends) — AC-013, M-3, ADR-0007. The H-2 harness's `/cd` requires an idle session (read in its source). Live-prove before building the self-move.
- (unverified premise: herdr still detects the agent's kind when the plugin's launch command starts an H-2 harness) — AC-012.
- (unverified premise: the H-2 harness's `/cd` accepts a new worktree without a separate trust step) — it refuses an untrusted folder (read in its source); whether a worktree inherits its repository's trust is unchecked. AC-013, AC-014.
- (unverified premise: a developer without admin rights can read the protected list) — GitHub was read as repository owner; GitLab was read on one project with the reader's own role. AC-007, AC-008.

- (unverified premise: the hook processes of both harnesses inherit `HERDR_ENV` and `HERDR_TAB_ID`) — AC-038. The H-2 PreToolUse hook receives `HERDR_*` (`providers/CONFORMANCE.md` P0-c); the H-1 hook is unverified.

Evidence behind the design: two agent proposals, critiques and final positions, the live H-1 hook trial, harness source reads with versions, and the decision record of all 4 rounds. They live in the session scratchpad (`worktree-debate/`), not in this repository; the SDD carries the harness versions.

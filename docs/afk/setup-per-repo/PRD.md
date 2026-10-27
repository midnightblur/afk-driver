# PRD — setup-per-repo

## Problem Statement

A developer works in several local repositories with AFK. Today:

- Agents put every new worktree inside the main checkout, not in a folder the developer chose.
- `/afk:setup` configures only the repository the session stands in, except some personal values.
- Setup does not remember the developer's repositories, so each run asks for the paths again.
- One machine holds one Jira sign-in and one sign-in per forge host. A repository cannot name its own GitHub account.
- Forge and tracker settings live in the committed AFK file. A repository whose team does not use AFK has no committed file, and several plugin parts then refuse to work.
- The note-taking setting decides where the requirements document goes. A developer's choice of note-taking app can move a repository's working files out of the repository.

## Solution

From any folder, `/afk:setup` keeps a **repository list** (the stored list of main checkouts setup manages). For each listed repository it asks only what is missing: the team settings when the repository has no committed AFK file, and the developer's personal settings and accounts. Each setting has one owner (catalog S). The answers apply to the main checkout and every worktree of that repository.

Setup asks once per machine for the **worktree root** (the one folder for all new agent worktrees). Agents create every new worktree of a listed repository at `<root>/<repository short name>/<worktree name>`, and a guard refuses an agent's worktree anywhere else. Worktrees that already exist stay where they are and keep working.

Each repository names the forge account agents act as, with its change assignee (the forge account set as assignee on every change the plugin opens), reviewer and work item assignee. Each Jira site has one account. Agents write their working files into the repository's spec folder. The note-taking app holds only **developer notes** (the developer's own notes, kept per machine).

## Catalog

### S — setting owners

Owner rule (ADR [0002](adr/requirements/0002-setting-ownership.md)):

- **team**: read from the committed AFK file when the repository has one, and not overridable there. With no committed file, setup keeps it in the repository personal file (the developer's own settings for one repository, never committed).
- **personal**: lives only in the developer's own files. A committed value is ignored with a warning.
- **machine**: lives only in the developer's machine file (`~/.afk/config.yaml`). A value in any repository file is ignored with a warning.

| ID | Setting | Owner | Note |
|----|---------|-------|------|
| S-01 | forge kind (GitHub, GitLab) | team | |
| S-02 | forge remote (which git remote is the forge) | personal | asked only when the clone has more than 1 remote; else empty, and the CLI derives the project |
| S-03 | tracker kind (Jira, GitHub issues, none) | team | |
| S-04 | Jira site address | team | today read with the sign-in; moves to the settings |
| S-05 | Jira project, work item types, status names | team | |
| S-06 | GitHub issues repository and status labels | team | |
| S-07 | git base branch, branch pattern, branch template | team | base branch should stay `auto`, not name a remote |
| S-08 | spec folder | team | where agents write working files (ADR [0003](adr/requirements/0003-notes-per-machine.md)) |
| S-09 | build gates and their settings, verification tiers, service map, investigation boundaries, review paths, repository hooks, setup extras, plugin-issue repository | team | |
| S-10 | files a new worktree copies from the main checkout | personal | |
| S-11 | forge account for the repository | personal | also covers push sign-in and commit email |
| S-12 | Jira account | personal | one per Jira site, shared by every repository on that site |
| S-13 | change assignee, reviewer, work item assignee | personal | |
| S-14 | commit email, IDE | personal | |
| S-15 | worktree root | machine | ADR [0001](adr/requirements/0001-one-worktree-root.md) |
| S-16 | note-taking app, Notion parent page, Obsidian vault | machine | ADR [0003](adr/requirements/0003-notes-per-machine.md) |

A secret is never a setting. It is stored once per host and account by the vendor tool or a secret store.

### R — worktree root rules

| ID | Rule | Outcome on failure |
|----|------|--------------------|
| R-01 | the root is an absolute path | setup refuses it, names the rule |
| R-02 | the root and none of its parents is inside any git repository | setup refuses it, names the repository |
| R-03 | the root exists | setup creates it |
| R-04 | the root path has no space | setup accepts it and warns when a listed repository builds with Maven: its worktrees share the default Maven cache |
| R-05 | a repository's short name is its main checkout folder name | on a clash with another listed repository, setup asks for another short name |
| R-06 | the short name's folder under the root is absent or was made by setup for that repository | setup asks for another short name |
| R-07 | the root is checked on every read | agents refuse to create a worktree and name the failed rule |

## User Stories

1. As a developer, I want to run `/afk:setup` from any folder and have it walk every listed repository asking only what is missing, so that all my repositories are configured in one run.
2. As a developer, I want agents to create every new worktree under my one worktree root, each repository in its own folder, so that worktrees never land inside a checkout.
3. As a developer, I want each repository to name the forge account agents act as, with its assignees and reviewer, so that changes in a personal project use my personal account.
4. As a developer, I want to add a new clone to the list in the same run, and remove or repoint an entry whose folder is gone.
5. As a developer, I want to change one value of one repository alone.
6. As a developer on a repository with no committed AFK file, I want the plugin to work from my personal file alone, so that nothing of mine is shared with a team that does not use AFK.
7. As a developer with the `codex` app, I want setup to tell me to point the `codex` worktree root at the same root.

## Acceptance Criteria

### Repository list

- [ ] AC-001 Setup run from any folder offers the repository list, with add and remove.
- [ ] AC-002 On add, setup asks the developer to paste a path. It does not suggest folders.
- [ ] AC-003 A path to a main checkout is added. A path to a worktree adds that worktree's main checkout.
- [ ] AC-004 A bare clone, a folder that is not a git repository, and a path already in the list are refused, each with its reason.
- [ ] AC-005 Two clones of one remote are two entries (ADR [0005](adr/requirements/0005-two-clones-two-repositories.md)).
- [ ] AC-006 An entry whose folder is gone is reported, and setup offers remove or a new path.
- [ ] AC-007 The list survives a new session and a reboot. A list entry is never written to any repository file.

### Setup walk

- [ ] AC-010 For each listed repository, setup asks only for settings that have no value at their owner (catalog S). A run with nothing missing asks nothing and reports every repository complete.
- [ ] AC-011 Setup can change one setting of one repository without asking anything else.
- [ ] AC-012 Every per-repository setup step acts on the repository it is given, whatever the current folder is.
- [ ] AC-013 The secret step runs in the developer's own terminal, never in an agent shell.
- [ ] AC-014 Setup never writes a per-worktree value. When a value in `.afk/config.local.yaml` overrides a value setup manages, setup warns and names both.
- [ ] AC-015 A value setup writes is read by the main checkout and every worktree of that repository.

### Setting owners

- [ ] AC-020 For every team setting in catalog S, a repository with a committed AFK file reads the committed value. A personal-file value for it is ignored with a warning naming the setting.
- [ ] AC-021 For every team setting, a repository with no committed AFK file reads the value from the repository personal file. Setup asks for it there.
- [ ] AC-022 For every personal setting, a committed value is ignored with a warning naming the setting.
- [ ] AC-023 For every machine setting, a value in any repository file is ignored with a warning naming the setting.
- [ ] AC-024 When a repository gains a committed AFK file, the next setup run deletes, without asking, each personal-file copy of a team setting the committed file holds a real value for. It keeps every copy while a worktree of the repository is on a branch without the committed file. The report lists each deleted setting, file and value, and each kept copy with its reason.
- [ ] AC-025 A repository with no committed AFK file passes every plugin check that today requires that file: the commit gates, the setup check for the AFK file, `init`, the developer-values step and the behavior registry.
- [ ] AC-026 The forge remote is asked only when the clone has more than 1 remote. With 1 remote it stays empty, and agents still open changes on the correct project.
- [ ] AC-027 `jira.credentials-env` either selects the Jira credentials it names or is removed from the schema. A value that is accepted and never read fails this criterion.

### Accounts

- [ ] AC-030 Setup saves a forge account for a repository only when the forge host accepts it. A refused or unreachable host saves nothing, names the cause and leaves the other repositories to continue (unverified premise: gh can hold several accounts per host and select one per command; glab holds one account per host).
- [ ] AC-031 Recovery after AC-030: a later setup run for that repository alone saves the account once the host accepts it.
- [ ] AC-032 After it saves the account, setup suggests that account as the change assignee and the work item assignee.
- [ ] AC-033 Agents in a repository act as that repository's forge account, and set its change assignee, reviewer and work item assignee. An unset or `none` change assignee opens the change with no assignee.
- [ ] AC-034 When the repository's push sign-in or commit email does not match its forge account, setup warns and names both values.
- [ ] AC-035 Every repository on one Jira site uses that site's one Jira account. Two sites can use two accounts (unverified premise: a Jira API token belongs to one Atlassian account; the harness passes the tracker server its stored sign-in and picks one tracker entry across scopes).
- [ ] AC-036 An existing machine-wide Jira sign-in becomes the sign-in for its site. Setup asks which listed repositories use that site.
- [ ] AC-037 Existing machine-wide assignee and reviewer values are shown for each repository to confirm. The answers go to that repository's personal file.

### Worktree root

- [ ] AC-040 Setup asks for the root once per machine and suggests `repo-worktrees` in the home folder.
- [ ] AC-041 For every rule in catalog R, a root or short name that fails the rule gets that row's outcome.
- [ ] AC-042 Until the developer confirms a root, agents use the suggestion if it passes catalog R. If it fails, agents refuse to create a worktree and say to run setup.
- [ ] AC-043 An existing machine-wide worktree base value becomes the root if it passes catalog R. If it fails, agents refuse to create a worktree until setup is answered.
- [ ] AC-044 A worktree root in any repository file is ignored with a warning.
- [ ] AC-045 When a harness asks to trust the root, setup trusts it once, and a worktree in any subfolder needs no further trust prompt (unverified premise: `claude` and `codex` extend folder trust to subfolders).
- [ ] AC-046 When the `codex` app is installed, setup shows the step to set its worktree root to the same root (unverified premise: the `codex` app keeps its worktrees under its own root, movable only in its settings screen, and names its own folders there).

### Worktree creation

- [ ] AC-050 Every agent route that creates a worktree of a listed repository puts it at `<root>/<short name>/<worktree name>`. This covers the plugin's worktree creator in every mode and the harness worktree tool (unverified premise: `claude` moves worktrees only through its worktree-create hook; the harness creates and isolates worktrees through that hook).
- [ ] AC-051 A relative or `~` path never lands a worktree inside the main checkout. The creator refuses it, and the exit status says so.
- [ ] AC-052 When the plugin's worktree-create hook fails, the harness tool creates no worktree outside the root (unverified premise: where a harness tool lands when its hook fails or is missing).
- [ ] AC-053 An agent's `git worktree add` or `git worktree move` for a listed repository whose real target is outside `<root>/<short name>` is refused. The refusal names the root folder.
- [ ] AC-054 After a refusal, the agent creates the worktree under the root or asks the developer. No agent-settable bypass exists.
- [ ] AC-055 A worktree of a repository that is not in the list is not checked.
- [ ] AC-056 The developer can create a worktree anywhere from their own terminal (ADR [0004](adr/requirements/0004-guard-binds-agents-only.md)).

### Existing worktrees

- [ ] AC-060 A worktree that already exists outside the root keeps working with every plugin hook, gate and script, and is cleaned up as before.
- [ ] AC-061 Setup lists worktrees that sit inside another repository. It offers to remove each one that is clean and idle, and keeps every other one.

### Agent working files

- [ ] AC-070 Agents write every working file for a work item (requirements, designs, plans, reports) into the repository's spec folder, whatever note-taking app is chosen.
- [ ] AC-071 The note-taking app choice moves no agent working file out of the repository.

### Session scope

- [ ] AC-080 A session reads only its own repository's settings and accounts. Only a setup run the developer asks for reads or writes another listed repository.

## Access & validation policy

Data scope is by repository (one main checkout and its worktrees) and by machine. This plugin has no company or vendor scope.

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Edit the repository list (US 1, 4) | developer; agent session only to record the developer's in-session answer | teammate; agent session on its own initiative | machine | AC-003, AC-004 |
| Set team settings without a committed file (US 6) | developer | teammate; agent session on its own initiative | repository | catalog S owner rule |
| Set personal settings and accounts (US 3, 5) | developer; agent session records a non-secret value only as the developer's answer | teammate; agent session for any secret | repository; Jira account per site | AC-030, AC-034 |
| Store a secret | developer, in their own terminal | agent session; teammate | per host and account | never in a repository file |
| Set the worktree root (US 2, 7) | developer | agent session on its own initiative; teammate | machine | catalog R |
| Create a worktree of a listed repository (US 2) | agent session under the root; developer anywhere | agent session outside `<root>/<short name>` | repository | AC-053 |
| Read settings and accounts in a session | agent session, own repository | agent session for another listed repository, outside a setup run the developer asked for | repository | AC-080 |
| Write agent working files | agent session, into the spec folder | agent session, into the note-taking app | repository | AC-070 |

A teammate sees only the committed AFK file and never any value from catalog S rows marked personal or machine.

## Implementation Decisions

| Module | Responsibility |
|---|---|
| M1 Repository list | machine-wide store of main checkouts: add, remove, list, check entries, map a worktree path to its main checkout |
| M2 Settings reader | resolves each setting by its catalog S owner; warns on every ignored value; uses the repository personal file when no committed file exists |
| M3 Setup walk | `/afk:setup` from any folder: iterates the list, asks only missing values, targets one repository per step |
| M4 Account check | checks a forge account with its host and a Jira account with its site; suggests assignees; compares push sign-in and commit email |
| M5 Worktree root | catalog R checks, short names, the `<root>/<short name>/<worktree name>` layout for every creation route |
| M6 Placement guard | refuses an agent's worktree add or move for a listed repository that lands outside its root folder |
| M7 No-committed-file support | every part that requires the committed AFK file also accepts the repository personal file |
| M8 Agent file placement | agent working files always go to the spec folder; the note-taking app holds only developer notes |
| M9 Setup cleanup | lists worktrees inside another repository; shows the `codex` root step |

- One worktree root per machine: ADR [0001](adr/requirements/0001-one-worktree-root.md). Layout repository then worktree: ADR [0006](adr/requirements/0006-root-layout.md).
- Setting owners: ADR [0002](adr/requirements/0002-setting-ownership.md), catalog S.
- Notes per machine, agent files in the repository: ADR [0003](adr/requirements/0003-notes-per-machine.md).
- Guard binds agents only: ADR [0004](adr/requirements/0004-guard-binds-agents-only.md).
- One repository is one clone: ADR [0005](adr/requirements/0005-two-clones-two-repositories.md).
- The Jira site address moves from the sign-in store to the team settings (S-04). The token stays in the sign-in store.
- The machine-wide `worktreeBasePath` stops being a per-repository value. It becomes the root only through AC-043.
- `jira.credentials-env`: the SDD picks working or removed (AC-027).
- An unreadable `.git` file or common directory crashes the config reader and the tracker server today (INV-004). M2 must report it instead.
- Staples: none. This plugin has no staples registry.

## Testing Decisions

- Test external behaviour: setting values resolved per owner, files written by setup, exit statuses and refusal texts, where worktrees land. Do not test internal helpers.
- All nine modules get automated tests. M3 and M9 get tests for the scripts they call.
- Every test runs on Windows and on Linux before push.
- Worktree tests cut real worktrees in temporary repositories: inside a checkout, beside it, under a root, with a relative or `~` path, with a space in the path. No test covers a nested worktree today.
- Guard tests follow the existing shell-mutation and protected-branch acceptance tests. Two existing tests pin "a plain `git worktree add` passes the guard". M6 reverses them for listed repositories.
- Settings tests follow the existing config-reader tests. One test per catalog S owner class, plus the no-committed-file path.
- Account checks use stub forge and tracker hosts. Live checks before build: harness trust for subfolders (AC-045), harness hook routes (AC-050, AC-052).

## Out of Scope

- Moving existing worktrees into the root (AC-060 keeps them in place).
- Checking worktrees the developer creates from their own terminal (ADR [0004](adr/requirements/0004-guard-binds-agents-only.md)).
- Keying settings by remote URL rather than by clone (ADR [0005](adr/requirements/0005-two-clones-two-repositories.md)).
- Any feature that writes developer notes for the developer.
- Per-repository folders for developer notes.

## Further Notes

Assumptions this PRD rests on (user-acknowledged, outside this repository):

- gh holds several accounts per host and selects one per command; glab holds one account per host (AC-030).
- A Jira API token belongs to one Atlassian account (AC-035).
- The harness passes the tracker server its stored sign-in and picks one tracker entry when user, project and plugin scope each define one (AC-035).
- gh and glab choose the host, and so the account, for calls that name no host (AC-030, AC-033).
- `claude` moves worktrees only through its worktree-create hook; the harness creates worktrees and isolates subagents through it (AC-050).
- Where a harness tool puts a worktree when that hook fails or is missing (AC-052).
- `claude` and `codex` extend folder trust to subfolders (AC-045).
- The `codex` app keeps its worktrees under its own root, movable only in its settings screen, and names its own folders there (AC-046).

Evidence: investigations INV-001 to INV-004 under `investigations/`, all re-run on the investigation tool fix (PR #113, Draft). The grill log holds every settled decision and its round.

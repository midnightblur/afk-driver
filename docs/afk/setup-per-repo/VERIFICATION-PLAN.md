# Verification Plan — setup per repository

> Parent ticket: setup-per-repo   Sources: [PRD](PRD.md) · [SDD](SDD.md)
> Suite: one black-box acceptance test file under `scripts/tests/` (pytest), plus the live-run rows marked env-limited (GRILL-LOG Verification grill, R-1 V-1)   Built per: the black-box pattern of `scripts/tests/test_protected_branch_acceptance.py`
> Run: the `unit` tier this feature adds to `.afk/config.yaml` (R-1 V-2); every automated row runs on Windows and Linux before push
> Status: draft (built by NNNN-smoke-e2e / NNNN-smoke-api; run by /afk:smoke-test)

This repository has no running app, no browser suite and no REST suite. A "UI journey" here is an end-to-end flow through the entry points a developer or a harness reaches. An "API scenario" is a contract check of one command, hook or guard rule: its exit status and its printed lines. Each test works in a sandbox: a temporary home folder, temporary git repositories, and stand-in `gh`, `glab` and Jira on `PATH`. The test plays the agent and passes the developer's answers to the scripts setup runs. An agent session is the agent detector switched on; the developer is the detector switched off.

## UI Journeys

| # | Journey (plain business language) | Actor | Traces to | Env-limited? | Requires target |
|---|-----------------------------------|-------|-----------|--------------|-----------------|
| U1 | Setup over 3 repositories from outside them: asks only what is missing, reports complete / asked / failed, goes on after one fails | developer | PRD User Story 1 · AC-001, AC-010, AC-012, AC-014, AC-015, AC-030, AC-031 | no | any |
| U2 | Every agent route puts a worktree under root/short name; every agent route outside is refused naming the folder | agent session; developer | PRD User Story 2 · AC-042, AC-050–AC-056, AC-060 | no | any |
| U3 | Forge account saved only after the host accepts it; every forge call then acts as it | developer; agent session | PRD User Story 3 · AC-026, AC-030, AC-032–AC-034 | no | any |
| U4 | Repository list: add a pasted path, refuse bad paths, two clones apart, repair a gone folder | developer | PRD User Story 4 · AC-002–AC-007; PRD catalog R R-05, R-06 | no | any |
| U5 | Change one setting of one repository; nothing else asked | developer | PRD User Story 5 · AC-011 | no | any |
| U6 | No committed AFK file: works from the personal file; a later committed file deletes the copies it replaces | developer; teammate | PRD User Story 6 · AC-020–AC-022, AC-024, AC-025 | no | any |
| U7 | `codex` app installed: setup shows the step naming the root; not installed: shows nothing | developer | PRD User Story 7 · AC-046 | no | any |
| U8 | Jira sign-in per site; only the developer's own terminal stores one | developer; agent session | AC-013, AC-027, AC-035, AC-036 | no | any |
| U9 | Upgrade from the previous release: misplaced values stop counting, setup offers each move, old worktree base used only while it passes the rules | developer | AC-023, AC-037, AC-043, AC-044, AC-061 · ADR design 0007 | no | any |
| U10 | Worktree root asked once, suggested in the home folder, each root rule gives its outcome | developer | PRD User Story 2 · AC-040, AC-041, AC-045 | no | any |
| U11 | An ordinary session reads only its own repository and writes working files only into its spec folder | agent session | AC-070, AC-071, AC-080 | no | any |
| L1 | Two real GitHub accounts on one host: setup saves the second, calls act as it | developer | AC-030, AC-033 | env-limited (live run, real accounts) | any |
| L2 | GitHub Enterprise Server host: calls carry the token in `GH_ENTERPRISE_TOKEN` | developer | AC-033 · SDD §9b gh host row | env-limited (no host reachable; stays unrun until one is) | any |
| L3 | Real GitLab host with one login: a different account is refused at setup | developer | AC-030 · SDD §9b glab rows | env-limited (live run) | any |
| L4 | Real Jira site: its sign-in loads in each repository on it; a second real site where available | developer | AC-035, AC-036 | env-limited (live run; second site) | any |
| L5 | `claude` worktree tool lands under the root; hook exit 3 creates no worktree | agent session | AC-050, AC-052 | env-limited (real `claude` session) | any |
| L6 | Trust the root once in `claude` and in `codex`; a worktree in a subfolder raises no trust prompt | developer | AC-045 | env-limited (real harnesses) | any |
| L7 | Worktree placement on a second Windows drive | agent session | AC-050 | env-limited (skip with the reason when no second drive) | Windows with a second drive |

### U1 — setup over several repositories
- **Given** a sandbox home folder, a confirmed root, 3 listed repositories: A complete; B with no committed AFK file and no forge kind; C whose stand-in forge host refuses the account
- **When** run the walk from the home folder; answer B's forge kind; make C's host accept and run setup for C alone; run the full walk again
- **Then** A asks nothing; B asks only the forge kind, the value lands in B's personal file and is read from B's main checkout and from a worktree of B; C shows `failed` with the cause and the rerun command, nothing is saved for C, B still finishes; the rerun for C saves the account; the last full run asks nothing and reports all 3 complete; a value in B's per-worktree local file that overrides a value setup manages draws a warning naming both
- **Persistence reverify**: read B's forge kind and C's account back through the settings reader in a new process, from B's main checkout and from a worktree of B
- **Requires target**: any
- **Alt/error paths**: C's host unreachable (timeout) gives the same `failed` row
- **Reuses**: `make_repo` and the `home` fixture pattern (scripts/tests/test_setup_developer_values.py); `Stubs` gh/glab shim (scripts/tests/test_protected_branch_acceptance.py)

### U2 — worktree placement
- **Given** a confirmed root; repository A listed with short name `a`; repository Z not listed; an agent session
- **When** create a worktree by name; by branch with a parent under the root; through the worktree-create hook; through the move helper. Then try `git worktree add` to a folder beside the checkout, inside it, with a relative path and a `~` path; `git worktree move` out of the root; the creator with a parent outside; the same command with `AFK_WORKTREE_FOLDER` set in front of it. Then the same add in Z, and in A with the agent detector off. Then run the commit gate in an old worktree outside the root and clean it up
- **Then** the 4 routes print a path under root/a and the folder exists; every outside attempt is refused — the creator with exit 3 and a line naming the rule and `/afk:setup`, the guard with its refusal naming root/a and the two ways forward; a refused attempt creates nothing; Z's add and the developer's add pass; the old worktree passes its gate and is removed as before; with no confirmed root the suggestion is used when it passes the rules, else creation is refused with an instruction to run setup; a failing worktree-create hook (stand-in harness) creates no worktree outside the root
- **Persistence reverify**: `git worktree list` from the main checkout shows only the worktrees the passing routes made
- **Requires target**: any
- **Alt/error paths**: the live harness half is L5
- **Reuses**: `create()` (scripts/tests/test_create_worktree_name.py); guard `run()` (scripts/tests/test_protected_branch_guard.py); `fake_harness` recorder (scripts/tests/test_protected_branch_acceptance.py)

### U3 — forge account per repository
- **Given** a stand-in gh with 2 accounts on one host, its default login different from the account named; a stand-in glab with one login
- **When** name the second account for A; accept the suggested change and work item assignees; set a reviewer; open a change and a work item through the adapters; set the change assignee to `none` and open another change; name an account the host refuses for B; for a GitLab repository name an account other than glab's login; give A a push sign-in for a different account; remove A's account token and open a change
- **Then** A's account is saved after the host check and both assignees are suggested from it; the calls carry that account's token (`GH_TOKEN` for github.com, `GH_ENTERPRISE_TOKEN` for an Enterprise Server host) and the saved assignee and reviewer; `none` opens with no assignee; B saves nothing and names the cause; GitLab saves nothing and names the signed-in account; the push sign-in mismatch warns naming both; with the token gone the call fails with `account not available` and never uses the default login; a clone with 1 remote is never asked for the forge remote and still reaches the right project, a clone with 2 remotes is asked
- **Persistence reverify**: read A's account and assignees from a new process; B's personal file holds no account
- **Requires target**: any
- **Alt/error paths**: the live halves are L1, L2, L3
- **Reuses**: `stub()` / `forge()` (scripts/tests/test_forge_adapters.py)

### U4 — the repository list
- **Given** an empty list
- **When** paste a main checkout path; a worktree's path; a bare clone; a plain folder; a path already listed; add a second clone of the same remote with the same folder name; try a short name whose folder under the root setup did not make; delete one listed checkout folder and run setup, pick a new path, then remove; read the list from a new process
- **Then** the main checkout is added; the worktree path adds its main checkout; the 3 bad paths are refused, each with its reason; the second clone is a second entry and setup asks for another short name; the foreign folder also makes setup ask for another name; the missing folder is reported with remove and new path offered, and both work; a new process reads the same list; no repository file holds a list entry
- **Persistence reverify**: the new-process read is the reverify
- **Requires target**: any
- **Alt/error paths**: none
- **Reuses**: `make_repo`

### U5 — change one setting
- **Given** A and B complete
- **When** run setup for A by short name naming the change assignee; repeat with a path to a worktree of A; run it with an unknown short name; then with the path of an unlisted repository
- **Then** only A's change assignee changes, nothing else is asked, B is untouched; the worktree path resolves to A; the unknown name is refused with the list of names; the unlisted path is offered for adding
- **Persistence reverify**: read A's and B's settings from a new process; only A's assignee differs from before
- **Requires target**: any
- **Alt/error paths**: none
- **Reuses**: `cli()` (scripts/tests/test_setup_developer_values.py)

### U6 — no committed AFK file
- **Given** repository A with no `.afk/config.yaml`
- **When** run setup for A and answer the team settings; run the commit gates, the setup check, `init`, the developer-values step and the behavior registry; commit an AFK file with a real forge kind and tracker kind but no spec folder, keep one worktree on a branch from before that commit, run setup; move that worktree to a branch with the file, run setup again; put the change assignee in the committed file and the forge kind in the personal file
- **Then** team settings land in A's personal file and are read from it; every listed check passes with no committed file; the first run after the commit deletes nothing and lists each kept copy with the reason; the second run deletes, without asking, each copy the committed file holds a real value for, lists setting, file and value, and keeps the spec folder copy; the committed assignee and the personal forge kind are each ignored with a warning naming the setting; a teammate's clone of A sees no personal or machine value in any committed file
- **Persistence reverify**: read A's personal file and merged settings from a new process after each run
- **Requires target**: any
- **Alt/error paths**: none
- **Reuses**: `make_repo`; `_empty_home` / `_home_with` (scripts/tests/test_afk_config_init.py)

### U7 — the `codex` app step
- **Given** a stand-in `codex` app install; then none
- **When** run setup
- **Then** with the install, setup shows the step to point the `codex` app's worktree root at the root and names the root path; without it, setup shows nothing about the `codex` app
- **Persistence reverify**: n/a — setup writes nothing for this step
- **Requires target**: any
- **Alt/error paths**: the real `codex` app screen is a live check (L6 covers its trust half); how setup detects the install is in Gaps surfaced
- **Reuses**: none known

### U8 — Jira sign-in per site
- **Given** today's one machine-wide Jira sign-in for site one; A and B on site one, C on site two
- **When** run setup and answer which repositories use site one; run the secret step for site two in a terminal; call the tracker tools from A, B and C; run the secret step from an agent session, with piped input, and with no argument; run it for a site whose name key matches site one's; leave a partial sign-in in the first source; change the harness settings file while the step waits; keep `jira.credentials-env` in a committed file
- **Then** the existing sign-in becomes site one's, and `jira.site` lands in the personal file of each chosen repository without a committed file; site two's sign-in is stored under its per-site names with one backup and owner-only access on Linux; tracker calls from A and B use site one's account, from C site two's; the agent and piped runs are refused with the reason; the bare run prints the 3 commands; the matching key is refused naming both sites; the partial source is skipped and named in the error; the changed settings file makes the step refuse and change nothing; validate warns `jira.credentials-env was removed; delete this key`
- **Persistence reverify**: load each repository's sign-in in a new process; the harness file after the refused run is byte-identical to before
- **Requires target**: any
- **Alt/error paths**: the live half is L4
- **Reuses**: `TestCreds` patterns (scripts/tests/test_tracker_jira.py); `FakeJira` (scripts/tests/test_tracker_registration.py)

### U9 — upgrade from the previous release
- **Given** a machine file with a passing worktree base, tracker settings, assignee and reviewer; a repository personal file with a worktree base; a worktree root in a repository file; worktrees nested inside another repository — one clean and idle, one with changes, one clean with a live session, one clean with no session record
- **When** run validate; create a worktree; run setup and answer each offer; stop a run after it writes the root and before it deletes the old key; repeat from the start with a worktree base that fails the rules
- **Then** validate says the file is valid and lists one warning per ignored value naming setting, file and rule; the worktree lands under the old base while no root is confirmed; setup writes the root, reads it back, then offers per repository to delete the old key; the machine assignee and reviewer are shown per repository to confirm, answers go to each personal file; the root in a repository file is ignored with a warning; of the nested worktrees, the clean idle one and the clean unknown one (marked unknown) are offered, removal uses no force and keeps the branch, the other two are kept; the stopped run leaves both keys and the new one wins; with the failing base, creation is refused until setup is answered
- **Persistence reverify**: read the machine file and each personal file from a new process after each offer; `git branch` still lists the removed worktrees' branches
- **Requires target**: any
- **Alt/error paths**: none
- **Reuses**: `owner.snapshot` / `owner.creation_time` monkeypatch pattern (scripts/tests/test_worktree_owner.py)

### U10 — the worktree root
- **Given** no root
- **When** run setup and accept the suggestion; run it again; then try, one at a time: a relative root; a root inside a repository; a root whose parent is inside a repository; a root that does not exist; a root with a space while a listed repository builds with Maven; then turn the confirmed root into a repository and create a worktree
- **Then** the root is asked once and the suggestion is `repo-worktrees` in the home folder; the relative root is refused naming the rule; both inside cases are refused naming the repository; the missing root is created; the space is accepted with a warning about the shared Maven cache; after the root becomes a repository, creation is refused naming the failed rule; setup shows the step to trust the root
- **Persistence reverify**: read `worktreeRoot` from a new process after the accept
- **Requires target**: any
- **Alt/error paths**: the real trust prompt is L6
- **Reuses**: the `home` fixture pattern

### U11 — an ordinary agent session
- **Given** A and B listed with different accounts; the machine's note-taking app set to Notion, then Obsidian, then none
- **When** in a session in A, read every setting through the reader and resolve the spec folder, once per app setting; search the plugin for callers of the list's read-all call
- **Then** only A's values appear, none of B's; the spec folder resolves inside A for all 3 app settings; only setup scripts call the read-all call
- **Persistence reverify**: n/a — read only
- **Requires target**: any
- **Alt/error paths**: none
- **Reuses**: `run()` (scripts/tests/test_afk_config.py)

### L1–L7 — live-run rows
- **Given** the real harness, account, host or drive the row names, and a throwaway home folder
- **When** the developer runs the matching automated journey's steps by hand (L1, L2, L3 → U3; L4 → U8; L5 → U2; L6 → U10 and U7; L7 → U2)
- **Then** the same observables as the matching journey
- **Persistence reverify**: as the matching journey
- **Requires target**: as the table row
- **Alt/error paths**: none
- **Reuses**: the matching journey's steps

## API Scenarios

| # | Scenario (call → asserted contract) | Surface (method + path) | Traces to | Env-limited? |
|---|-------------------------------------|-------------------------|-----------|--------------|
| A1 | each repository step runs in its main checkout; a failed step records `failed`, reason, rerun command; the walk goes on | setup walk step scripts | SDD §3 row "`/afk:setup` (no argument)" · §14 setup walk · AC-012, AC-010 | no |
| A2 | short name / main checkout / worktree / subfolder path select the repository; unlisted path offered; unknown name refused with the names | list lookup behind `/afk:setup repo` | SDD §3 row "`/afk:setup repo`" · AC-011 | no |
| A3 | success last line `WORKTREE_PATH=`, exit 0; root rule failure exit 3 `ERROR=worktree root: …- run /afk:setup`; other failure exit 1 `ERROR=` | `create-worktree --name` | SDD §3 row "`create-worktree --name`" · AC-041, AC-050, AC-051 | no |
| A4 | agent parent outside root/short name exit 3 `ERROR=parent … is outside …`; developer anywhere | `create-worktree --branch --dir --parent` | SDD §3 row "`create-worktree --branch …`" · AC-051, AC-053, AC-056 | no |
| A5 | bare path only, exit 0; creator failure non-zero, empty stdout | worktree-create hook | SDD §3 row "worktree-create hook" · AC-050, AC-052 | no |
| A6 | outside or unresolvable target refused with the exact refusal text, no bypass line; inside, unlisted, developer, launch flag pass | guard on `git worktree add` / `move` | SDD §3 row "command guard on `git worktree add` and `git worktree move`" · AC-053–AC-056 | no |
| A7 | creator `--parent` / `--dir` outside refused with the same text | guard on the creator call | SDD §3 row "command guard on the creator call" · AC-053 | no |
| A8 | `AFK_WORKTREE_FOLDER` / `AFK_ALLOW_PROTECTED` set in any form the existing variable rule reads → refused naming the variable | guard on inline variables | SDD §3 row "command guard on inline variables" · AC-054 | no |
| A9 | confirmed root exit 0; suggestion plus stderr note; neither passes exit 1 with the rule | `afk-config.py resolve worktreeRoot` | SDD §3 row "`afk-config.py resolve worktreeRoot`" · AC-040, AC-042, AC-043 | no |
| A10 | `configuration is valid` plus one warning per ignored value, exit 0; unknown key refused; removed-key warning | `afk-config.py validate` | SDD §3 row "`afk-config.py validate`" · AC-020–AC-023, AC-027, AC-044 | no |
| A11 | ignored values absent; all else unchanged; owner table pinned against CONFIG.md | `afk-config.py get / effective / export-shell / resolve` | SDD §3 row "`afk-config.py get`, `effective` …" · AC-020–AC-023 | no |
| A12 | account token present exit 0; missing → `account not available`, no default-login call; unset as today; token variable per host kind | `auth-status` verb, both forge adapters | SDD §3 row "forge sign-in check" · AC-030, AC-033 | no |
| A13 | helper returns host and account, never a token; every verb, branch protection, GitHub Issues act as the account; reporter keeps default login | forge account helper and wrappers | SDD §14 row "forge wrappers" · AC-033 | no |
| A14 | trusts every account on the host plus `--trust`; failing login lookup → review commands exit 2 | review ledger `forge_ledger` | SDD §5 row "trust a comment author" · §14 row "review ledger" · AC-033 | no |
| A15 | runs only with a terminal on input and output and no agent session; every other run refused with the reason; no secret printed | `setup_secrets.py jira / forge / longpaths` | SDD §3 row "`setup_secrets.py` …" · AC-013, AC-035 | no |
| A16 | first complete source for `jira.site`; partial skipped and named; per-site names and key derivation; refusals name site and folder | Jira sign-in load and tracker server tools | SDD §3 row "tracker server tools" · §14 row "Jira sign-in load" · AC-035, AC-036 | no |
| A17 | lock, hand text, write back; changed file refused; lock past 2000 ms fails naming the file; Windows swap retries 10 × 50 ms | safe writer | SDD §14 row "safe writer" · §6 failure matrix · AC-007 | no |
| A18 | one key to its owner's file; special first characters quoted; heading with a note reused; wrong-file key refused; no `schema` line | settings writer | SDD §14 row "settings writer" · AC-010, AC-021 | no |
| A19 | normalized path; duplicate refused; marker first under the list lock; stopped add completed; removal keeps or deletes the marker; read-all only from setup | repository list module | SDD §14 / §5 L5 list invariants · AC-003–AC-007, AC-080 | no |
| A20 | runs when the reader says set up or `.afk` exists; no Python on the commit path | commit gates configuration test | SDD §14 row "commit gates `config.yaml` test" · AC-025 | no |
| A21 | fills the committed file from the personal file's team values; never writes the personal file; never run in another repository | `afk-config.py init` | SDD §14 row "`afk-config.py init`" · AC-024, AC-025 | no |
| A22 | suggested path equals the creator's path; placement loaded only when planning a move | move helper `h2_move` hint | SDD §14 row "move helper" · AC-050 | no |

### A1 — setup walk steps
- **Given** 2 sandbox repositories and a third folder as the start folder
- **When** run the walk's step scripts; force a failure in the first repository's step
- **Then** each step's working folder and project folder is its repository's main checkout; the failure records `failed`, the reason and the rerun command, and the second repository runs; machine steps run once; no repository row in the register is a chained shell line
- **Persistence refetch**: n/a — the report is the answer; written values are refetched in U1
- **Auth/authz**: agent on its own initiative is instruction-only (signed HL-3); no below-the-instructions refusal exists to assert
- **Reuses**: `cli()`; `preflight()` (scripts/tests/test_setup_secrets_repo_root.py)

### A2 — setup for one repository
- **Given** A listed; Z not listed
- **When** look up a short name; the main checkout path; a worktree path; a subfolder path; Z's path; an unknown short name
- **Then** the first 4 select A; Z is offered for adding; the unknown name is refused with the list of names
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — developer-only command, no refused caller below the instructions
- **Reuses**: `make_repo`

### A3 — creator by name
- **Given** a listed and an unlisted repository; a root per failing rule
- **When** `create-worktree --name` in each case: each root rule that can fail on read (relative, `~`, inside a repository, parent inside a repository, short-name folder made for another repository); a bad name; a git failure; an existing destination
- **Then** success: last stdout line `WORKTREE_PATH=<path>`, exit 0, listed at root/short name/name, unlisted inside the main checkout; each root rule: exit 3, `ERROR=worktree root: <rule> <reason> - run /afk:setup`, and the error trap's own message absent; bad name and git failure: exit 1, `ERROR=<reason>`; existing destination refused, no worktree or branch left
- **Persistence refetch**: `git worktree list` and `git branch` after each refused run show nothing new
- **Auth/authz**: same answers for agent and developer; the agent refusals are A4
- **Reuses**: `create()`

### A4 — creator by branch with a parent
- **Given** a listed repository; the agent detector on, then off
- **When** `create-worktree --branch --dir --parent` with a parent inside, outside, `~` and relative forms resolving inside and outside
- **Then** agent inside: success; agent outside (any form, after being made absolute): exit 3, `ERROR=parent <path> is outside <root>/<short name>` plus the fixing command, nothing created; developer: any parent works as today; unlisted repository unchanged
- **Persistence refetch**: `git worktree list` shows nothing new after a refusal
- **Auth/authz**: permitted developer anywhere, agent under root/short name; refused agent elsewhere
- **Reuses**: `create()`

### A5 — worktree-create hook
- **Given** a stand-in harness envelope
- **When** run the hook with a passing root; with a failing root; with a git failure
- **Then** pass: stdout is exactly one line, the path, exit 0; fail: non-zero exit, empty stdout
- **Persistence refetch**: `git worktree list` shows nothing new after a failure
- **Auth/authz**: n/a — harness-only caller
- **Reuses**: `fake_harness` recorder

### A6 — guard on worktree add and move
- **Given** A listed, Z not; the agent detector on
- **When** guard envelopes: add outside; add with `-b`, `-B`, `--orphan`, `--reason` in each parsed position; add through `-C`; add through a link pointing outside; add with the target in a variable; move to outside; the same inside; Z; the detector off; a session launched with `AFK_ALLOW_PROTECTED=1`
- **Then** each refused answer is `refused to create a worktree outside the worktree root. Cause: <target> is outside <root>/<short name>. Move: create it under <root>/<short name>, or ask the developer.` with no bypass line; inside, Z, detector off and the launch flag pass; the existing tests that pin a plain worktree add as passing are found and reversed for listed repositories
- **Persistence refetch**: n/a — read only
- **Auth/authz**: refused agent outside; permitted agent inside, developer, launch-flag session
- **Reuses**: guard `run()`; `run_in_process`

### A7 — guard on the creator call
- **Given** A listed; the agent detector on
- **When** guard envelopes running `scripts/create-worktree` with `--parent` outside, `--dir` outside, both inside; Z; detector off
- **Then** the two outside calls are refused with A6's text; the others pass
- **Persistence refetch**: n/a — read only
- **Auth/authz**: refused agent outside; permitted agent inside and developer
- **Reuses**: guard `run()`

### A8 — guard on the two variables
- **Given** the agent detector on
- **When** guard envelopes, per variable (`AFK_WORKTREE_FOLDER`, `AFK_ALLOW_PROTECTED`): set in front of the command; behind `env`; `export` or `declare` then the command in one call; `setx`; a PowerShell `env:` assignment; inside `bash -c`; a search that only prints the name; a session the developer launched with `AFK_ALLOW_PROTECTED=1`
- **Then** each setting form is refused and the refusal names the variable; the search passes; the launched session still lifts every guard rule
- **Persistence refetch**: n/a — read only
- **Auth/authz**: refused agent for every setting form; the form set follows `hooks/lib/lavish_direct.py` (assignment or export, the declare words, the PowerShell form)
- **Reuses**: `scripts/tests/test_lavish_direct.py` cases as the form list

### A9 — root lookup
- **Given** sandbox machine files
- **When** `afk-config.py resolve worktreeRoot` with: a confirmed root; no root and a passing suggestion; no root and a failing suggestion; a confirmed root that now fails a rule
- **Then** confirmed: the path, exit 0; suggestion: the path, exit 0, a note on stderr; neither passes: exit 1, the failed rule on stderr; no plugin caller still asks for `resolve worktreeBasePath`
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — any caller
- **Reuses**: `run()` (scripts/tests/test_afk_config.py)

### A10 — validate
- **Given** sandbox files: clean; one value at each wrong place (personal committed, machine in a repository file, team in the machine file, team in the personal file while a committed file exists); an unknown key; `jira.credentials-env`; the keys `jira.site`, `developer.worktreeRoot`, `developer.forgeAccount`
- **When** `afk-config.py validate`
- **Then** `configuration is valid` then one warning line per ignored value (setting, file, rule), exit 0; the unknown key refused as today; `jira.credentials-env was removed; delete this key`; the 3 new keys pass
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — any caller
- **Reuses**: `run()`

### A11 — readers
- **Given** A10's sandbox files
- **When** `get`, `effective`, `export-shell`, `resolve`
- **Then** no ignored value in any answer; the existing reader tests stay green unchanged; a test pins the owner table against `CONFIG.md`
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — any caller
- **Reuses**: scripts/tests/test_afk_config.py

### A12 — forge sign-in check
- **Given** stand-in gh and glab recording every call
- **When** `auth-status` on each adapter: account set and token present; account set and token missing; no account set; a github.com host; an Enterprise Server host; a GitLab host
- **Then** present: exit 0; missing: `account not available`, non-zero, and no recorded call with the default login; unset: answer as today; github.com: `GH_TOKEN`; Enterprise Server: `GH_ENTERPRISE_TOKEN`; GitLab: `GITLAB_HOST` set and the account check is `glab api --hostname <h> user`
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — any caller; the account is the subject
- **Reuses**: `stub()` / `forge()` (scripts/tests/test_forge_adapters.py); `logged_in_cli()` (scripts/tests/test_protected_lookup.py)

### A13 — forge account helper and wrappers
- **Given** stand-in gh with 2 accounts
- **When** call the helper; then each forge verb, the branch-protection lookup and the GitHub Issues adapter; the plugin-issue reporter
- **Then** the helper's answer holds no token; each call carries the account's token; branch protection keys its cache by account (2 accounts, 2 entries); the reporter uses the default login
- **Persistence refetch**: the branch-protection cache read back holds one entry per account
- **Auth/authz**: n/a — the account is the subject
- **Reuses**: `stub()`

### A14 — review ledger trust
- **Given** a stand-in adapter holding 2 accounts on one host
- **When** run ledger commands over comments by account 1, account 2, a third author, and the third author named with `--trust`; then with the login lookup failing on GitHub
- **Then** accounts 1 and 2 count; the third counts only with `--trust`; the cache and rationale scope include the account; the failing lookup makes the review commands exit 2
- **Persistence refetch**: n/a — read only
- **Auth/authz**: trusted set is every account on the host plus `--trust`; every other author refused
- **Reuses**: `FakeAdapter` (scripts/tests/test_forge_ledger.py)

### A15 — secret step
- **Given** a pseudo-terminal; a sandbox harness settings file
- **When** `setup_secrets.py jira --site`, `forge --host --account`, `longpaths` in a terminal with the detector off; then with piped input; output not a terminal; the `claude` agent marker; the `codex` agent marker; a second site whose key matches another's; the harness file changed while the step waits; no argument
- **Then** permitted runs write the sign-in, keep one backup, set owner-only access on Linux, and a rerun replaces the value; each refused run names its reason; the matching key names both sites; the changed file is refused and nothing changes; the bare run prints the 3 commands and writes nothing; the token is in neither stdout nor stderr in any run
- **Persistence refetch**: read the harness file after each run; the refused runs leave it byte-identical
- **Auth/authz**: permitted developer in their own terminal; refused every agent shell and piped input
- **Reuses**: `preflight()` (scripts/tests/test_setup_secrets_repo_root.py)

### A16 — Jira sign-in load
- **Given** stand-in sites; sign-ins in each source order
- **When** load for: the existing 3 names on their own site; per-site names for a second site; a site host with dots and dashes; a partial first source and a complete second; no complete source; then call the tracker tools with no complete source
- **Then** the first complete source wins; the partial is skipped and named in the error; the key is the host in capitals with every other character an underscore; the refusal names the site and the folder read, in the load and in the tracker tools; the rewritten mixed-source test replaces the old one
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a — the sign-in is the subject
- **Reuses**: `TestCreds` (scripts/tests/test_tracker_jira.py)

### A17 — safe writer
- **Given** a target file; a second process as the other writer
- **When** a normal update; the owner-only option; a change between read and write; a lock held 2500 ms; on Windows a file held open 200 ms; an installer call that fails
- **Then** the normal update keeps the file mode; owner-only sets owner-only access on Linux; the change is refused, nothing changed; the held lock fails within the 2000 ms wait, names the file, leaves no temp file; the held Windows file is replaced after retries (10 × 50 ms); the installer's callers see the installer's own error type
- **Persistence refetch**: re-read the target after each run; refused runs leave it byte-identical
- **Auth/authz**: n/a — library call
- **Reuses**: scripts/tests/test_install_block.py (the atomic-write cases)

### A18 — settings writer
- **Given** sandbox owner files
- **When** write one key of each owner kind; a value starting with a special character; into a file with an existing heading and note; a machine-owned key aimed at a repository file; a safe-writer failure
- **Then** each key lands in its owner's file only; the special value reads back unchanged; the heading is reused, not duplicated; the misaimed key is refused; the personal file has no `schema` line; the safe-writer failure is caught and named
- **Persistence refetch**: read each value back through the settings reader in a new process
- **Auth/authz**: n/a — setup-only writer; agent initiative is instruction-only (signed HL-3)
- **Reuses**: `cli()`

### A19 — repository list module
- **Given** an empty list and a root
- **When** add a path; the same path in another case and with a trailing separator; a duplicate; an add stopped after the marker, then a new add; remove with a worktree left in the folder; remove with the folder empty; repoint a short name; search callers of the read-all call
- **Then** case and separator variants are one entry; the duplicate is refused; the stopped add leaves a marker the next add reuses; removal keeps the marker while a worktree remains and deletes the empty folder and its marker otherwise; repoint moves the entry; only setup scripts call read-all
- **Persistence refetch**: read the list and markers from a new process after each step
- **Auth/authz**: n/a — setup-only writer; agent initiative is instruction-only (signed HL-3)
- **Reuses**: `make_repo`

### A20 — commit gates configuration test
- **Given** a repository with only a personal file; one with only an `.afk` folder of repository hooks; one with neither
- **When** run the commit gate
- **Then** the first two run their gates; the third skips; no Python process starts on the commit path; one test pins both answers
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a
- **Reuses**: scripts/tests/test_plugin_source_gates.py pattern

### A21 — init
- **Given** a repository whose personal file holds team values
- **When** `afk-config.py init`
- **Then** the new committed file carries those values; the personal file is unchanged; the walk's register has no row that runs `init` for a listed repository
- **Persistence refetch**: read the new committed file and the personal file after the run
- **Auth/authz**: n/a
- **Reuses**: scripts/tests/test_afk_config_init.py

### A22 — move helper hint
- **Given** a session refused in the main checkout; an ordinary command
- **When** run the move helper on each
- **Then** its suggested path equals `create-worktree`'s `WORKTREE_PATH` for the same name in the same sandbox; on the ordinary command it reads no new file
- **Persistence refetch**: n/a — read only
- **Auth/authz**: n/a
- **Reuses**: `fake_harness` recorder

## Aspect coverage

One verdict per aspect: triggered → points at the row(s) proving it; non-triggered → records why it's N/A. Role-based and data-scoped access each owe a proving row in **both** modalities.

<!-- aspect set below: lockstep copy — owned by skills/afk/grill-verification/SKILL.md (aspect table) -->

| Aspect | Verdict | Proving rows | Env-limited? |
|--------|---------|--------------|--------------|
| Role-based access | triggered (always) — roles: developer in their own terminal, agent session, teammate; editing the list and writing team settings on the agent's own initiative are instruction-only per signed HL-3 | U2, U3, U8, U6 (teammate); A4, A6, A7, A8, A14, A15 | no |
| Data-scoped access | triggered — scope is one repository and one machine; no company or vendor scope | U11, U6, U1; A16, A19 | no |
| Input validation | triggered | U10, U4, U5, U8; A2, A3, A4, A10, A15, A18 | no |
| Envers audit trail | N/A — no database table or entity; the feature stores files only (SDD.md:285-291) | — | — |
| Deep-link / URL-state sync | N/A — no web page; the surfaces are commands, hooks and the guard (SDD.md:123) | — | — |
| Accepted staples | N/A — this plugin has no staples registry; the PRD accepted none (PRD.md:192) | — | — |
| External-state gate recheck (TOCTOU) | triggered — forge token removed after setup checked it; a session starting before removal; the harness rewriting its settings file; a confirmed root later becoming a repository. Accepted window: a branch change between the copy-deletion check and the deletion in the same run (undo: the report lists each deleted value) | U3, U9, U8, U10; A12, A15 | no |
| Concurrency | applies | A17, A15 | no |
| Idempotency | applies | U1, U4, U8; A19 | no |
| Pagination / sorting | N/A — no surface returns results in pages | — | — |
| State-machine transition guards | applies — forge account unset → saved; root migration both keys → new wins; Jira sign-in absent → stored → replaced | U3, U9, U8; A12 | no |
| Error-envelope shape | applies | A3, A4, A5, A6, A8, A9, A10, A12 | no |
| Time budgets | applies — counts gate (no new file read on any command other than add and move; no network call on add and move); the 50, 10 and 20 ms times are reported in the informational bench only (R-2 C-23) | A22, A6 | no |

## Instance enumeration

| Requirement | Instance (component / surface) | Covered by | Exclusion (verified how) |
|-------------|--------------------------------|------------|--------------------------|
| AC-050 every agent route that creates a worktree | `create-worktree --name` | U2, A3 | — |
| | `create-worktree --branch --dir --parent` | U2, A4 | — |
| | worktree-create hook (`claude`) | U2, A5, L5 | — |
| | move helper `h2_move` | U2, A22 | — |
| | launch helper | — | calls `create-worktree --name` and reads its `WORKTREE_PATH=` line (SDD.md:129, INV-001) |
| | `/afk:settle-change`, `/afk:execute` | — | call `create-worktree --branch --dir --parent` (SDD.md:130) |
| | raw `git worktree add` / `move` | U2, A6 | — |
| | creator call through the shell | A7 | — |
| | `codex` worktree tool | A6, U7 | `codex` is covered by the guard plus the shown setup step (SDD.md:85) |
| AC-041 every rule in catalog R | R-01 absolute | U10, A3 | — |
| | R-02 not inside a repository | U10, A3 | — |
| | R-03 exists | U10 | — |
| | R-04 no space | U10 | — |
| | R-05 short name unique | U4 | — |
| | R-06 short-name folder made by setup | U4, A3 | — |
| | R-07 checked on every read | U10, A9 | — |
| AC-020–AC-023 every setting in catalog S (S-01–S-16) | each row of the owner table | A11 (owner table pinned against `CONFIG.md`, every row) | — |
| | one value per misplaced kind | A10, U6, U9 | — |
| AC-025 every plugin check that requires the committed file | commit gates | U6, A20 | — |
| | setup check for the AFK file | U6 | — |
| | `init` | U6, A21 | — |
| | developer-values step | U6 | — |
| | behavior registry | U6 | — |
| AC-012 every per-repository setup step | `setup_secrets` row | A1 | — |
| | `developer_values` row | A1 | — |
| | `install-git-hooks` row | A1 | — |
| Every forge call acts as the account (AC-033) | `auth-status` | A12 | — |
| | every forge verb | A13 | — |
| | branch protection | A13 | — |
| | GitHub Issues adapter | A13 | — |
| | review ledger | A14 | — |
| | plugin-issue reporter | A13 | keeps the default login by design (SDD.md:717) |
| AC-060 every plugin hook, gate and script on an existing worktree outside the root | commit gate | U2 | — |
| | cleanup (worktree removal) | U2 | — |
| | the other hooks, gates and scripts | — | enumerated from the code by subtask 0005, which tests each member or records its exclusion (plan approval R-1 O-1) |

## Gaps surfaced

- The final gate expects a running app and browser and REST suites this repository lacks (`skills/afk/smoke-test/SKILL.md:12`, `:39`). This plan's gate runs pytest through the `unit` tier. Follow-up: draft a plugin issue for the smoke-test skill; publish only after the human approves the exact text (R-1 G-1).
- The design does not say where the secret step writes when `CLAUDE_CONFIG_DIR` moves the harness settings file (SDD.md:579). The A15 test sets it and expects the step to follow it or refuse; the building subtask settles which and records it (R-1 G-2).
- CI does not run `scripts/tests/create-worktree-smoke.sh` or `scripts/tests/worktree-provision-smoke.sh` (`.github/workflows/tests.yml:62-67`). This feature's creator checks live in the pytest acceptance file. Spinoff candidate: run both scripts in CI (R-1 G-3).
- The design does not say how setup detects an installed `codex` app (U7, SDD.md:551). The building subtask settles the detection and records it (R-1 J-7).
- The design does not state the exit status of a bare secret-step run (SDD.md:139). A15 checks the 3 commands are printed and nothing is written; the building subtask settles the status (R-2 G-4).
- AC-060 says every plugin hook, gate and script keeps working on an existing worktree outside the root. The grill proved the commit gate and cleanup only. Decided at plan approval (R-1 O-1): subtask 0005 lists every member from the code, records the list in `plan/DECISIONS.md`, and tests each one on a worktree outside the root or records its exclusion with the reason.
- Correctness tests for a separate git folder and a submodule join A6 and A3; the guard's 50 ms budget is not gated for them (R-1 E-8, SDD.md:724).

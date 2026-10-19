# Grill log — setup-per-repo

Checkpoint of interactive grill sessions. Working state, updated as decisions lock;
superseded when the synthesized artifacts (PRD / SDD / VERIFICATION-PLAN) land.

## Requirements grill

- Ledger: new agent worktrees land only where developer.worktreeBasePath points → refuted (INV-001) — counterexample `scripts/create-worktree:228`: every agent and harness path uses `--name` and lands inside the main checkout — re-settled: verified as current behaviour; requirement corrected to the worktree root (R-4 S-4R, WR-1, DA-4R)
- Ledger: worktrees outside the configured folder keep working with every plugin hook and script → verified in-repo, outside facts unverified-external (user acknowledged R-7 F-3) (INV-001 partial 13/14 re-fold 2026-10-16; in-repo: commit gates are location-free `hooks/plugin-source-gates.sh:180`, a nested worktree misleads six tools, a space in the path makes Maven provisioning skip its own cache and warn (degraded, builds work) `adapters/build-gate/maven/worktree-provision.sh:113-119`, a plain `git worktree add` passes the guard `hooks/lib/shell_mutations.py:456-457`; outside facts: harness worktree creation and subagent isolation c-3a16d3e8, Codex app worktrees c-dde2db70, where a harness tool lands when the hook fails or is absent c-288d7e16; pending seed check completed by delta K on PR #113 1df735c)
- Ledger: only the developer-values step of /afk:setup can target a repository other than the current directory → verified (INV-002 closed-with-frontier 13/14, re-fold 2026-10-16) — `developer_values.py --repo PATH`; SessionStart H5 binds to the session cwd (`hooks/install-git-hooks.sh:44`)
- Ledger: no durable list of the developer's repositories exists → verified (INV-002) — the harness `~/.claude.json` projects map is read only inside the Jira credential walk (`adapters/tracker/jira/api.py:74-87`)
- Ledger: Jira credentials are one set per machine; jira.credentials-env is never read → verified (INV-003 13/14, in-repo `adapters/tracker/jira/api.py:107-127`); harness passes the tracker env block and picks one tracker entry across scopes (c-1630239b) → unverified-external (user acknowledged R-7 F-3)
- Ledger: gh and glab sign-in is per host in the CLI's own store, with no per-repository account choice → verified (INV-003, in-repo); gh/glab pick the host for host-less --repo, plain api calls and auth status (c-94386e72) → unverified-external (user acknowledged R-7 F-3)
- Ledger: a repository with no committed .afk/config.yaml can be configured through the shared overlay alone → refuted (INV-004) — reader accepts it, but `hooks/precommit-gates.sh:59`, H0, `init`, `developer_values.py:177` and `behavior_registry.py:227` need the committed file — re-settled: verified as current behaviour; requirement corrected so every part that looks for the committed file accepts the repository personal file (R-3 DA-1, R-6 OW-0)
- Ledger: gh holds several accounts per host since v2.40.0 and selects one per command via GH_TOKEN; glab holds one account per host; a Jira API token belongs to one Atlassian account; Claude Code moves worktrees only through a WorktreeCreate hook; the Codex app keeps its worktrees under $CODEX_HOME/worktrees, movable only in its settings screen → unverified-external (user acknowledged R-1 F-1)
- Staples: none — this plugin has no STAPLES.md registry
- Settled: pain — agents put every new worktree inside the main checkout, not in the developer's worktree folder (R-1 P-1)
- Settled: pain — setup configures only the repository the session stands in, except personal values (R-1 P-2)
- Settled: pain — setup does not remember the developer's repositories and re-asks the paths each run (R-1 P-4)
- Settled: actors — developer (runs setup, owns personal values and sign-ins); agent session (reads config, makes worktrees, opens changes, files work items, never writes a sign-in); teammate (sees only committed files) (R-1 A-1)
- Settled: forge kind and tracker kind are always private, per developer, in the repository personal file (R-1 S-1 = C) — which keys move with them re-asked R-2
- Settled: personal sign-in — each repository names its account; each secret stored once per host and account (R-1 S-2 = B) — scope re-asked R-2: P-3 marked not-a-pain, S-2 note "currently JIRA I only have one acc as it is from my employment. Github I use for personal projects and might use different acc for different repos"
- Settled: worktree folder rule covers the plugin creator and the Claude worktree tool; setup tells the developer to set the Codex app worktree root by hand; the command guard refuses an agent's worktree add whose target is outside the folder (R-1 S-3 = B)
- Settled: setup asks the worktree folder for every repository, suggesting <main checkout name>-worktrees beside it; until confirmed agents use that suggestion and setup reports it not confirmed (R-1 S-4)
- Settled: setup keeps a repository list in ~/.afk, offers it every run, allows add and remove; first run suggests folders agent tools opened before, records only picked ones (R-1 S-5)
- Settled: every per-repository setup step takes the repository as a target and works from any folder; the sign-in script still runs in the developer's own terminal (R-1 S-6)
- Settled: one repository = one clone (main checkout + its worktrees); a second clone of the same remote is separate (R-1 S-7)
- Settled: setup never writes per-worktree values; .afk/config.local.yaml stays for hand edits; setup warns when it overrides a repository value (R-1 S-8)
- Settled: glossary terms Worktree folder, Repository list, Personal sign-in, Change assignee, Repository personal file (R-1 T-1..T-5) — written to GLOSSARY.md
- Settled: accounts — forge account named per repository; Jira one account per Jira site; pain: GitHub may use a different account per repository (R-2 X-1 = A, resolves P-3)
- Settled: forge and tracker kinds and all their settings (remote, Jira project, issue types, transitions, GitHub issues repository and labels) are private; team rules (build gates, verification tiers, branch pattern and template, spec folder) stay committed (R-2 X-2 = A)
- Settled: committed forge and tracker values act as setup suggestions and keep working, reported not confirmed, until the developer confirms (R-2 X-3)
- Settled: stories — setup from any folder walks every listed repository asking only what is missing; add a new clone in the same run; stale entry → remove or new path; change one value alone; agents create every new worktree in the repository's folder; agents act as the repository's account with its assignees; setup shows the Codex app worktree-root step when Codex is installed (R-2 US-1..US-7)
- Settled: worktree folder rule binds agents only; the developer may create anywhere from their own terminal · decided-by agent R-2 · accepted 2026-10-16 · spec: user's first message limits the rule to future agents · reverse: add a git hook checking every user's worktree target (R-2 AC-1)
- Settled: the developer gives every value; an agent writes a non-secret value only as the developer's in-session answer and never handles a secret; a teammate sees none (R-2 AC-2)
- Settled: a guard refusal names the folder; the agent creates there or asks; only the developer creates elsewhere; no agent-settable bypass (R-2 AC-3)
- Settled: a session reads only its own repository's settings and account; only a developer-requested setup run touches other listed repositories (R-2 AC-4)
- Settled: setup refuses a worktree folder that is relative, inside the main checkout, inside another repository, or another repository's folder; creates it if missing (R-2 V-1) — reason corrected R-3: the Claude Code quote covers only a hook folder with no git data
- Settled: setup saves an account only when the host accepts it, and suggests both assignees from it (R-2 V-2)
- Settled: the repository list holds only main checkouts; a worktree path maps to its main checkout; bare clones, non-repositories and duplicates are refused with the reason (R-2 V-3)
- Settled: existing worktrees stay where they are, keep working, cleaned up as before · decided-by agent R-2 · accepted 2026-10-16 · spec: user's first message keeps existing worktrees working · reverse: add a setup step offering to move idle worktrees (R-2 W-1)
- Settled: the machine-wide worktree folder value stops being used at once; setup asks each repository and offers to delete it (R-2 W-2)
- Settled: the existing machine-wide Jira sign-in is kept as the sign-in for its site; setup asks which repositories use it (R-2 W-3)
- Settled: machine-wide assignee and reviewer values are shown per repository for confirmation; answers go to the repository personal file (R-2 W-4)
- Settled: V-1 kept on corrected evidence — a folder inside a repository confuses plugin tools there (R-3 V-1R)
- Settled: forge and tracker kinds stay private; every part that looks for the committed file accepts the repository personal file; pain: "there will be a wider consumer scope from other teams, so I do not like it to be shared" (R-3 DA-1 = A, gives S-1 its pain)
- Settled: the repository's account also covers push sign-in and commit email; setup warns when they disagree (R-3 DA-2)
- Settled: jira.credentials-env is made to work or removed; design picks (R-3 DA-11)
- Settled: one worktree root for every repository; each repository's worktrees apart by path; pain: a harness with one path setting (R-3 DA-3 write-in) — reopens T-1, S-3, S-4, V-1, W-2, US-5, US-7, DA-6, DA-12a for R-4
- Settled: the guard covers only worktrees of listed repositories (R-3 DA-4 write-in) — check restated R-4
- Settled: setup lists worktrees sitting inside another repository, offers to remove clean idle ones (R-3 DA-5)
- Settled: the suggestion obeys the folder rules, every parent checked; on failure agents refuse (R-3 DA-8)
- Settled: no repository suggestions — setup asks the developer to paste every repository path; later runs list them with remove and add (R-3 DA-7 write-in, amends S-5)
- Settled: setup saves an account only when its host accepts it; recovery: rerun setup for that repository when the host is reachable, others carry on (R-3 DA-12b = block)
- Settled: two clones of one remote are two repositories · decided-by agent R-3 · accepted 2026-10-16 · spec: R-1 S-7 · reverse: reopen S-7 and key settings by remote (R-3 DA-9)
- Settled: fix the investigation tool first, then rerun the four investigations; PRD waits (R-3 L-1 = C)
- Settled: term Worktree root replaces Worktree folder (R-4 T-1R) — GLOSSARY.md updated
- Settled: layout inside the root is repository name, then worktree name · decided-by agent R-4 · accepted 2026-10-16 · repo: `scripts/create-worktree:228` builds parent plus name · reverse: dash-prefixed flat names (R-4 WR-1; note asks whether one Codex root suffices — answered R-5 WR-3)
- Settled: a repository's subfolder is its main checkout folder name; setup asks a different short name on a clash (R-4 WR-2)
- Settled: setup asks the root once per machine, suggesting repo-worktrees in the home folder; agents use a passing suggestion until confirmed, else refuse (R-4 S-4R, replaces S-4)
- Settled: setup refuses a relative root or one inside any repository, every parent checked; creates it if missing (R-4 V-1R2, replaces V-1)
- Settled: only the machine file holds the root; a root in any repository file is ignored with a warning; checked on every read (R-4 DA-6R)
- Settled: the existing machine value becomes the root if it passes; today's fails (inside another repository), so agents refuse until setup is answered (R-4 W-2R, replaces W-2)
- Settled: the guard checks every new worktree of a listed repository by where it lands, refuses moves out; unlisted repositories unchecked (R-4 DA-4R, replaces S-3 guard clause)
- Settled: setup tells the developer to point the Codex app worktree root at the same root when Codex is installed (R-4 DA-3R, replaces US-7)
- Settled: setup trusts the root once if a harness asks; live check before build (R-4 DA-12aR)
- Ledger: the Codex app names its own folders inside its worktree root (naming undocumented); Claude Code and Codex extend folder trust to subfolders → unverified-external (user acknowledged R-4 F-2)
- Settled: setup refuses a repository short name already taken in the root by a folder it did not make for that repository (R-5 WR-3)
- Settled: ownership is decided setting by setting, team or personal (R-5 DA-10 write-in) — reopens X-2 and DA-1; table in R-6
- Settled: a team setting comes from the committed file when present and cannot be overridden there; with no committed file setup keeps it in the personal file; a personal setting lives only in the developer's files, a committed value for it ignored with a warning; when a committed file appears setup offers to delete the copies (R-6 OW-0, supersedes R-2 X-2 and the all-private part of R-3 DA-1)
- Settled: team — forge kind, tracker kind, Jira site, project, work item types and status names, GitHub issues repository and labels, and every other rule (R-6 OW-1, OW-3, OW-4, OW-5, OW-10)
- Settled: personal — worktree copy list; accounts, both assignees, reviewer, commit email, IDE, root (root machine file only) (R-6 OW-8, OW-9)
- Settled: notes are personal and per machine — notes kind, Notion parent page, Obsidian vault in the machine file; pain: "there's no Team notes taking practice. it's all personal. it's also NOT per repo" (R-6 OW-6 write-in, OW-7)
- Settled: the forge remote is personal; setup asks only when the clone has more than one remote, else it stays empty (R-7 OW-2R)
- Settled: no notes setting per repository — "keep notes out of \"per repo\" setting. it is per machine" (R-7 NT-1 write-in; agent's folder-per-repository proposal declined)
- Settled: setup accepts a root with a space and warns when a listed repository builds with Maven (R-7 WR-4)
- Settled: the notes platform is for the developer's own notes, written with agents' help; agents keep working files in the repository or on the change — "it's not meant for agents to write notes for themselves for their operations" (R-8 NT-2 write-in; overwrite question withdrawn)
- Settled: glossary term Developer notes (R-9 T-6) — written to GLOSSARY.md
- Settled: in this feature, agents write every working file into the repository spec folder whatever note-taking app is chosen; the app holds only developer notes; pain: a per-machine notes choice would move one repository's requirements out of it on that machine (`skills/afk/to-prd/SKILL.md:36`) (R-9 NT-3)
- Exhausted 2026-10-19: no open items; ledger has no pending row; devil's-advocate findings DA-1..DA-12 settled
  page: `grill.round.json` is the durable round state; a resumed session appends the next round to it and renders `grill.html` with `scripts/lavish_render.py`
  reruns 2026-10-16 on PR #113: INV-004 closed-with-frontier 13/14 (answer unchanged; unreadable .git or commondir crashes config reader and tracker server); INV-003 partial 13/14, all in-repo closed, answer unchanged; INV-001 partial 6/14 (refinement: branch-mode skills read worktreeBasePath; relative or ~ value lands inside main checkout and exits 0; nested worktree misleads six tools incl. redact.py); INV-002 partial 6/14, answer unchanged — the partial classes are held by fold defects sent back to PR #113
  2026-10-16: PR #113 follow-up landed (442cfa6, 8dafc0c: deltas supersede/withdraw, name forms kept, read+search conflict keeps the search, counter-check defects refuse); INV-001..003 re-fold running, outputs scratchpad/inv00{1,2,3}-r3
  2026-10-16 re-fold done: INV-002 closed-with-frontier (verified); INV-001 and INV-003 partial 13/14, every in-repo class closed, held only by outside facts c-3a16d3e8, c-dde2db70, c-288d7e16, c-1630239b, c-94386e72 → acknowledgement card in round 7, plus a root-with-a-space card (`worktree-provision.sh:114-118`)
  was blocked: ledger closure waits on INV-001..004 reruns on the fixed tool — fix is Draft PR #113 (closes #77, #83; adds write_report.py; validate_coverage accepts `irrelevant`); reruns use AFK_PLUGIN_ROOT at the PR #113 worktree; known leftover: validate_coverage.py ~630 and ~703 accept only traced/terminal

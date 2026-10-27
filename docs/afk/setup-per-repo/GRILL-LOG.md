# Grill log — setup-per-repo

Checkpoint of interactive grill sessions. Working state, updated as decisions lock;
superseded when the synthesized artifacts (PRD / SDD / VERIFICATION-PLAN) land.
Card ids are written with a dot here (`L9.3`); the round files use a hyphen.

## Requirements grill

- Ledger: new agent worktrees land only where developer.worktreeBasePath points → refuted (INV-001) — counterexample `scripts/create-worktree:228`: every agent and harness path uses `--name` and lands inside the main checkout — re-settled: verified as current behaviour; requirement corrected to the worktree root (R-4 S-4R, WR.1, DA-4R)
- Ledger: worktrees outside the configured folder keep working with every plugin hook and script → verified in-repo, outside facts unverified-external (user acknowledged R-7 F-3) (INV-001 partial 13/14 re-fold 2026-10-16; in-repo: commit gates are location-free `hooks/plugin-source-gates.sh:180`, a nested worktree misleads six tools, a space in the path makes Maven provisioning skip its own cache and warn (degraded, builds work) `adapters/build-gate/maven/worktree-provision.sh:113-119`, a plain `git worktree add` passes the guard `hooks/lib/shell_mutations.py:456-457`; outside facts: harness worktree creation and subagent isolation c-3a16d3e8, `codex` app worktrees c-dde2db70, where a harness tool lands when the hook fails or is absent c-288d7e16; pending seed check completed by delta K on PR #113 1df735c)
- Ledger: only the developer-values step of /afk:setup can target a repository other than the current directory → verified (INV-002 closed-with-frontier 13/14, re-fold 2026-10-16) — `developer_values.py --repo PATH`; SessionStart H5 binds to the session cwd (`hooks/install-git-hooks.sh:44`)
- Ledger: no durable list of the developer's repositories exists → verified (INV-002) — the harness `~/.claude.json` projects map is read only inside the Jira credential walk (`adapters/tracker/jira/api.py:74-87`)
- Ledger: Jira credentials are one set per machine; jira.credentials-env is never read → verified (INV-003 13/14, in-repo `adapters/tracker/jira/api.py:107-127`); harness passes the tracker env block and picks one tracker entry across scopes (c-1630239b) → unverified-external (user acknowledged R-7 F-3)
- Ledger: gh and glab sign-in is per host in the CLI's own store, with no per-repository account choice → verified (INV-003, in-repo); gh/glab pick the host for host-less --repo, plain api calls and auth status (c-94386e72) → unverified-external (user acknowledged R-7 F-3)
- Ledger: a repository with no committed .afk/config.yaml can be configured through the shared overlay alone → refuted (INV-004) — reader accepts it, but `hooks/precommit-gates.sh:59`, H0, `init`, `developer_values.py:177` and `behavior_registry.py:227` need the committed file — re-settled: verified as current behaviour; requirement corrected so every part that looks for the committed file accepts the repository personal file (R-3 DA.1, R-6 OW.0)
- Ledger: gh holds several accounts per host since v2.40.0 and selects one per command via GH_TOKEN; glab holds one account per host; a Jira API token belongs to one Atlassian account; `claude` moves worktrees only through a WorktreeCreate hook; the `codex` app keeps its worktrees under $CODEX_HOME/worktrees, movable only in its settings screen → unverified-external (user acknowledged R-1 F-1)
- Staples: none — this plugin has no STAPLES.md registry
- Settled: pain — agents put every new worktree inside the main checkout, not in the developer's worktree folder (R-1 P-1)
- Settled: pain — setup configures only the repository the session stands in, except personal values (R-1 P-2)
- Settled: pain — setup does not remember the developer's repositories and re-asks the paths each run (R-1 P-4)
- Settled: actors — developer (runs setup, owns personal values and sign-ins); agent session (reads config, makes worktrees, opens changes, files work items, never writes a sign-in); teammate (sees only committed files) (R-1 A-1)
- Settled: forge kind and tracker kind are always private, per developer, in the repository personal file (R-1 S-1 = C) — which keys move with them re-asked R-2
- Settled: personal sign-in — each repository names its account; each secret stored once per host and account (R-1 S-2 = B) — scope re-asked R-2: P-3 marked not-a-pain, S-2 note "currently JIRA I only have one acc as it is from my employment. Github I use for personal projects and might use different acc for different repos"
- Settled: worktree folder rule covers the plugin creator and the Claude worktree tool; setup tells the developer to set the `codex` app worktree root by hand; the command guard refuses an agent's worktree add whose target is outside the folder (R-1 S-3 = B)
- Settled: setup asks the worktree folder for every repository, suggesting <main checkout name>-worktrees beside it; until confirmed agents use that suggestion and setup reports it not confirmed (R-1 S-4)
- Settled: setup keeps a repository list in ~/.afk, offers it every run, allows add and remove; first run suggests folders agent tools opened before, records only picked ones (R-1 S-5)
- Settled: every per-repository setup step takes the repository as a target and works from any folder; the sign-in script still runs in the developer's own terminal (R-1 S-6)
- Settled: one repository = one clone (main checkout + its worktrees); a second clone of the same remote is separate (R-1 S-7)
- Settled: setup never writes per-worktree values; .afk/config.local.yaml stays for hand edits; setup warns when it overrides a repository value (R-1 S-8)
- Settled: glossary terms Worktree folder, Repository list, Personal sign-in, Change assignee, Repository personal file (R-1 T-1..T-5) — written to GLOSSARY.md
- Settled: accounts — forge account named per repository; Jira one account per Jira site; pain: GitHub may use a different account per repository (R-2 X-1 = A, resolves P-3)
- Settled: forge and tracker kinds and all their settings (remote, Jira project, issue types, transitions, GitHub issues repository and labels) are private; team rules (build gates, verification tiers, branch pattern and template, spec folder) stay committed (R-2 X-2 = A)
- Settled: committed forge and tracker values act as setup suggestions and keep working, reported not confirmed, until the developer confirms (R-2 X-3)
- Settled: stories — setup from any folder walks every listed repository asking only what is missing; add a new clone in the same run; stale entry → remove or new path; change one value alone; agents create every new worktree in the repository's folder; agents act as the repository's account with its assignees; setup shows the `codex` app worktree-root step when `codex` is installed (R-2 US-1..US-7)
- Settled: worktree folder rule binds agents only; the developer may create anywhere from their own terminal · decided-by agent R-2 · accepted 2026-10-16 · spec: user's first message limits the rule to future agents · reverse: add a git hook checking every user's worktree target (R-2 AC-1)
- Settled: the developer gives every value; an agent writes a non-secret value only as the developer's in-session answer and never handles a secret; a teammate sees none (R-2 AC-2)
- Settled: a guard refusal names the folder; the agent creates there or asks; only the developer creates elsewhere; no agent-settable bypass (R-2 AC-3)
- Settled: a session reads only its own repository's settings and account; only a developer-requested setup run touches other listed repositories (R-2 AC-4)
- Settled: setup refuses a worktree folder that is relative, inside the main checkout, inside another repository, or another repository's folder; creates it if missing (R-2 V-1) — reason corrected R-3: the `claude` quote covers only a hook folder with no git data
- Settled: setup saves an account only when the host accepts it, and suggests both assignees from it (R-2 V-2)
- Settled: the repository list holds only main checkouts; a worktree path maps to its main checkout; bare clones, non-repositories and duplicates are refused with the reason (R-2 V-3)
- Settled: existing worktrees stay where they are, keep working, cleaned up as before · decided-by agent R-2 · accepted 2026-10-16 · spec: user's first message keeps existing worktrees working · reverse: add a setup step offering to move idle worktrees (R-2 W-1)
- Settled: the machine-wide worktree folder value stops being used at once; setup asks each repository and offers to delete it (R-2 W-2)
- Settled: the existing machine-wide Jira sign-in is kept as the sign-in for its site; setup asks which repositories use it (R-2 W-3)
- Settled: machine-wide assignee and reviewer values are shown per repository for confirmation; answers go to the repository personal file (R-2 W-4)
- Settled: V-1 kept on corrected evidence — a folder inside a repository confuses plugin tools there (R-3 V-1R)
- Settled: forge and tracker kinds stay private; every part that looks for the committed file accepts the repository personal file; pain: "there will be a wider consumer scope from other teams, so I do not like it to be shared" (R-3 DA.1 = A, gives S-1 its pain)
- Settled: the repository's account also covers push sign-in and commit email; setup warns when they disagree (R-3 DA.2)
- Settled: jira.credentials-env is made to work or removed; design picks (R-3 DA.11)
- Settled: one worktree root for every repository; each repository's worktrees apart by path; pain: a harness with one path setting (R-3 DA.3 write-in) — reopens T-1, S-3, S-4, V-1, W-2, US-5, US-7, DA.6, DA-12a for R-4
- Settled: the guard covers only worktrees of listed repositories (R-3 DA.4 write-in) — check restated R-4
- Settled: setup lists worktrees sitting inside another repository, offers to remove clean idle ones (R-3 DA.5)
- Settled: the suggestion obeys the folder rules, every parent checked; on failure agents refuse (R-3 DA.8)
- Settled: no repository suggestions — setup asks the developer to paste every repository path; later runs list them with remove and add (R-3 DA.7 write-in, amends S-5)
- Settled: setup saves an account only when its host accepts it; recovery: rerun setup for that repository when the host is reachable, others carry on (R-3 DA-12b = block)
- Settled: two clones of one remote are two repositories · decided-by agent R-3 · accepted 2026-10-16 · spec: R-1 S-7 · reverse: reopen S-7 and key settings by remote (R-3 DA.9)
- Settled: fix the investigation tool first, then rerun the four investigations; PRD waits (R-3 L-1 = C)
- Settled: term Worktree root replaces Worktree folder (R-4 T-1R) — GLOSSARY.md updated
- Settled: layout inside the root is repository name, then worktree name · decided-by agent R-4 · accepted 2026-10-16 · repo: `scripts/create-worktree:228` builds parent plus name · reverse: dash-prefixed flat names (R-4 WR.1; note asks whether one `codex` root suffices — answered R-5 WR.3)
- Settled: a repository's subfolder is its main checkout folder name; setup asks a different short name on a clash (R-4 WR.2)
- Settled: setup asks the root once per machine, suggesting repo-worktrees in the home folder; agents use a passing suggestion until confirmed, else refuse (R-4 S-4R, replaces S-4)
- Settled: setup refuses a relative root or one inside any repository, every parent checked; creates it if missing (R-4 V-1R2, replaces V-1)
- Settled: only the machine file holds the root; a root in any repository file is ignored with a warning; checked on every read (R-4 DA-6R)
- Settled: the existing machine value becomes the root if it passes; today's fails (inside another repository), so agents refuse until setup is answered (R-4 W-2R, replaces W-2)
- Settled: the guard checks every new worktree of a listed repository by where it lands, refuses moves out; unlisted repositories unchecked (R-4 DA-4R, replaces S-3 guard clause)
- Settled: setup tells the developer to point the `codex` app worktree root at the same root when `codex` is installed (R-4 DA-3R, replaces US-7)
- Settled: setup trusts the root once if a harness asks; live check before build (R-4 DA-12aR)
- Ledger: the `codex` app names its own folders inside its worktree root (naming undocumented); `claude` and `codex` extend folder trust to subfolders → unverified-external (user acknowledged R-4 F-2)
- Settled: setup refuses a repository short name already taken in the root by a folder it did not make for that repository (R-5 WR.3)
- Settled: ownership is decided setting by setting, team or personal (R-5 DA.10 write-in) — reopens X-2 and DA.1; table in R-6
- Settled: a team setting comes from the committed file when present and cannot be overridden there; with no committed file setup keeps it in the personal file; a personal setting lives only in the developer's files, a committed value for it ignored with a warning; when a committed file appears setup offers to delete the copies (R-6 OW.0, supersedes R-2 X-2 and the all-private part of R-3 DA.1)
- Settled: team — forge kind, tracker kind, Jira site, project, work item types and status names, GitHub issues repository and labels, and every other rule (R-6 OW.1, OW.3, OW.4, OW.5, OW.10)
- Settled: personal — worktree copy list; accounts, both assignees, reviewer, commit email, IDE, root (root machine file only) (R-6 OW.8, OW.9)
- Settled: notes are personal and per machine — notes kind, Notion parent page, Obsidian vault in the machine file; pain: "there's no Team notes taking practice. it's all personal. it's also NOT per repo" (R-6 OW.6 write-in, OW.7)
- Settled: the forge remote is personal; setup asks only when the clone has more than one remote, else it stays empty (R-7 OW-2R)
- Settled: no notes setting per repository — "keep notes out of \"per repo\" setting. it is per machine" (R-7 NT.1 write-in; agent's folder-per-repository proposal declined)
- Settled: setup accepts a root with a space and warns when a listed repository builds with Maven (R-7 WR.4)
- Settled: the notes platform is for the developer's own notes, written with agents' help; agents keep working files in the repository or on the change — "it's not meant for agents to write notes for themselves for their operations" (R-8 NT.2 write-in; overwrite question withdrawn)
- Settled: glossary term Developer notes (R-9 T-6) — written to GLOSSARY.md
- Settled: in this feature, agents write every working file into the repository spec folder whatever note-taking app is chosen; the app holds only developer notes; pain: a per-machine notes choice would move one repository's requirements out of it on that machine (`skills/afk/to-prd/SKILL.md:36`) (R-9 NT.3)
- Exhausted 2026-10-19: no open items; ledger has no pending row; devil's-advocate findings DA.1..DA.12 settled
  page: `grill.round.json` is the durable round state; a resumed session appends the next round to it and renders `grill.html` with `scripts/lavish_render.py`
  reruns 2026-10-16 on PR #113: INV-004 closed-with-frontier 13/14 (answer unchanged; unreadable .git or commondir crashes config reader and tracker server); INV-003 partial 13/14, all in-repo closed, answer unchanged; INV-001 partial 6/14 (refinement: branch-mode skills read worktreeBasePath; relative or ~ value lands inside main checkout and exits 0; nested worktree misleads six tools incl. redact.py); INV-002 partial 6/14, answer unchanged — the partial classes are held by fold defects sent back to PR #113
  2026-10-16: PR #113 follow-up landed (442cfa6, 8dafc0c: deltas supersede/withdraw, name forms kept, read+search conflict keeps the search, counter-check defects refuse); INV-001..003 re-fold running, outputs scratchpad/inv00{1,2,3}-r3
  2026-10-16 re-fold done: INV-002 closed-with-frontier (verified); INV-001 and INV-003 partial 13/14, every in-repo class closed, held only by outside facts c-3a16d3e8, c-dde2db70, c-288d7e16, c-1630239b, c-94386e72 → acknowledgement card in round 7, plus a root-with-a-space card (`worktree-provision.sh:114-118`)
  was blocked: ledger closure waits on INV-001..004 reruns on the fixed tool — fix is Draft PR #113 (closes #77, #83; adds write_report.py; validate_coverage accepts `irrelevant`); reruns use AFK_PLUGIN_ROOT at the PR #113 worktree; known leftover: validate_coverage.py ~630 and ~703 accept only traced/terminal

## Solution grill

- Locked: L1 no new running program; every part reads settings and the repository list from files when needed (INV-004, INV-005) · decided-by agent R-1 · accepted 2026-10-19 · repo: `scripts/afk-config.py:388-397` reads per call, no cache · reverse: put a helper behind the same read functions
- Locked: L2 config reader applies the owner rule while merging; the 12 sites that skip `load()` move onto it where the owner rule changes their value (INV-005) · decided-by agent R-1 · accepted 2026-10-19 · spec: `CONFIG.md:7` one reader · reverse: filter in the setup writer
- Locked: L2 repository list module owns the list; setup sole writer; creator, guard, setup read through it · decided-by agent R-1 · accepted 2026-10-19 · pattern: `design-quality.md:40` one decision one owner · reverse: fold into the reader
- Locked: L2 one placement function computes `<root>/<short name>/<worktree name>`; creator, move helper, guard call it (INV-001) · decided-by agent R-1 · accepted 2026-10-19 · repo: `create-worktree:225-228`, `h2_move.py:66-100` compute it twice today · reverse: inline per caller
- Locked: L2 the reader answers "is this repository set up"; every committed-file test asks it (INV-004) · decided-by agent R-1 · accepted 2026-10-19 · repo: `precommit-gates.sh:59`, `developer_values.py:177`, `behavior_registry.py:227` · reverse: two-file test per site
- Locked: L2 setup walk runs each per-repository step with that main checkout as working folder; register rows gain a machine/repository scope mark (INV-002) · decided-by agent R-1 · accepted 2026-10-19 · repo: `MANIFEST.md:11`, `install-git-hooks.sh:44` · reverse: repository option per step
- Locked: L2 Jira adapter picks the account for the repository's Jira site at each sign-in load; server and registration unchanged (INV-003) · decided-by agent R-1 · accepted 2026-10-19 · repo: `jira/api.py:107-136`, `server.py:65-76` · reverse: one server entry per site
- Locked: L2 requirements step always takes the spec folder from the repository-files kind's resolve · decided-by agent R-1 · accepted 2026-10-19 · repo: `notion/NOTES.md:18` already does · reverse: restore the notes-kind lookup
- Locked: L2 one account helper gives every gh/glab call for a repository its host and account: both forge wrappers, branch protection, GitHub issues tracker, setup's user lookup; plugin-issue reporter keeps the default login (INV-006) · decided-by agent R-1 · accepted 2026-10-19 · repo: `forge.sh:88`, `gitlab/forge.sh:95` single wrappers · reverse: session-wide variables
- Locked: L2 harness worktree tools — `claude` via the worktree-create hook; `codex` via the guard plus the setup step for its own root (inherited gap acknowledged: harness placement unverified-external, requirements R-1/R-4/R-7) (R-1 L2.8)
- Signoff: HL-2 command surface → signed 2026-10-19 "sign" — covers /afk:setup and /afk:setup repo, create-worktree --name and --branch/--dir (root placement, exit 3), worktree-create hook, guard refusal on git worktree add/move, resolve worktreeRoot, validate warnings, ignored values absent from get/effective/export-shell/resolve
- Locked: L3 repository list in `~/.afk/repositories.json` `{schema:1, repositories:[{path, shortName}]}`, list module sole writer, temp file then rename (R-2 L3.1)
- Locked: L3 short-name marker `<root>/<shortName>/.afk-repository` holds the main checkout path; evidence for R-06 (R-2 L3.2)
- Locked: L3 root is machine `developer.worktreeRoot`; absent = not confirmed, suggestion `~/repo-worktrees`; legacy machine `worktreeBasePath` used while absent, agents refuse when it fails a rule (R-2 L3.3)
- Locked: L3 team key `jira.site`; unset = the one legacy sign-in and its address (R-2 L3.4)
- Locked: L3 `developer.forgeAccount` in the repository personal file; host derived from the forge remote (INV-004) (R-2 L3.5)
- Locked: L3 `jira.credentials-env` removed; reader ignores it, validate warns (INV-008) (R-2 L3.6)
- Locked: L4 GitHub calls get per-call GH_HOST + GH_TOKEN from `gh auth token --hostname --user`; token in memory only (INV-006; gh multi-account premise unverified-external, acknowledged) (R-2 L4.1)
- Locked: L4 GitLab: one account per host; setup checks `glab api user` equals forgeAccount, saves nothing otherwise; helper sets GITLAB_HOST only (unverified-external premise acknowledged) (R-2 L4.2)
- Locked: L4 Jira sign-ins per site as `JIRA_SITE_<KEY>_EMAIL` / `_API_TOKEN` in the existing tracker env block; legacy trio = sign-in for its own site (R-2 L4.3, debate, human chose envnames)
- Locked: L4 Jira adapter takes a whole sign-in from one source, never mixes fields (INV-008) · decided-by agent R-2 · accepted 2026-10-19 · repo: `jira/api.py:107-127` · reverse: restore per-field fill
- Locked: L4 secret step takes `jira --site` / `forge --host --account`; refuses without a terminal on input and output, or with the `claude` or `codex` session marker set (INV-008) (R-2 L4.5)
- Locked: L4 secret files owner-only on Linux/macOS; one backup copy, replaced each run (INV-008) (R-2 L4.6)
- Locked: L4 ignored values listed by validate and the setup walk only; other reads silent (R-2 L4.7)
- Locked: L4 numbers: guard adds no read except on `git worktree add`/`move`, ≤50 ms there, no network; owner rule ≤10 ms per load; account checks 1 try, 20 s each, failure reported per repository (R-2 L4.8)
- Locked: L4 listing a repository is the only switch; unlisted repositories unchanged · decided-by agent R-2 · accepted 2026-10-19 · spec: PRD AC-055 · reverse: add an on-off setting
- Locked: L4 outside setup, code reads only the session's repository; read-all only from the setup walk · decided-by agent R-2 · accepted 2026-10-19 · spec: PRD AC-080 · reverse: add read-all for other callers
- Locked: L4 setup writes another repository's files only through its scripts (INV-007) · decided-by agent R-2 · accepted 2026-10-19 · repo: `protected_branch_guard.py:374-383` · reverse: guard exception for direct edits
- Signoff: HL-1 stored state → signed 2026-10-19 "I sign" — covers repositories.json fields, marker file, machine-file keys, personal-file keys, committed-file changes (jira.site, credentials-env removed, owner-ignored keys), per-site Jira sign-in names, legacy-value migration, retention
- Signoff: HL-3 access → signed 2026-10-19 "I sign" — covers the who-may-do-what matrix (list, personal file, accounts, secrets, root, worktree placement, cross-repository reads, cleanup deletes, harness trust) with enforcement per side, four rules instruction-only, and the data-scope table
- Open: HL-3 signature voided by drift 2026-10-19 — its cleanup row said "the existing remover refuses a changed or busy worktree"; INV-009 refutes it: `remove-worktree.py` keeps such a worktree (`:334-336`, `:402-405`), `--force` skips both checks, and the guard (`protected_branch_guard.py:462-476`) and `/afk:gc` (`gc-check.sh:176-186`) are what refuse; corrected packet returns in R-3
- Locked: L5 removing a listed repository keeps its marker while the folder holds a worktree; empty folder and marker deleted (R-3 L5.1)
- Locked: L5 a missing main checkout is reported and removed only on your answer; a moved one re-points the marker only on your yes (R-3 L5.2)
- Locked: L5 a root change moves nothing; old worktrees stay; a `git worktree move` must target the current root (R-3 L5.3)
- Locked: L5 each stored-data rule has one guardian; callers ask it (INV-001) · decided-by agent R-3 · accepted 2026-10-20 · pattern: `design-quality.md:40` · reverse: copy the rule into each caller
- Locked: L6 one shared safe-write module (lock, re-read, temp, fsync, replace) extracted from `install_block.py:105-224`; list, markers, settings writer, secret step use it (INV-010) · decided-by agent R-3 · accepted 2026-10-20 · repo: `install_block.py:105-224` · reverse: per-writer copies
- Locked: L6 Windows replace retried 10× 50 ms, lock wait 2 s, then fail naming the file, temp deleted (INV-010) (R-3 L6.2)
- Locked: L6 secret step re-reads `~/.claude.json` under the lock at write time, changes only its own keys (INV-010) · decided-by agent R-3 · accepted 2026-10-20 · repo: `setup_secrets.py:185,252` · reverse: write back the start copy
- Locked: L6 every setup write sets a value; rerun is the recovery; no progress file (INV-011) · decided-by agent R-3 · accepted 2026-10-20 · repo: `setup/SKILL.md:80,130` · reverse: add a progress file
- Locked: L6 setup walk gains status `failed` with reason and rerun command; continues other steps and repositories (INV-011) (R-3 L6.5)
- Locked: L6 adding a repository: under list lock check, write marker, then list entry; a stopped run's marker is reused (R-3 L6.6)
- Locked: L6 creator's new checks run before anything is made (exit 3); pre-existing no-rollback gaps go to their own issue (INV-009) (R-3 L6.7)
- Locked: L6 worktrees inside another repository removed only when clean and idle, on your yes, via `git worktree remove` without force plus the guard; branch kept (INV-009) (R-3 L6.8)
- Overridden: L6 personal copies of team settings — human chose `auto` (delete without asking) over the recommended one answer per repository (R-3 L6.9); conflicts with PRD AC-024 "offers to delete" and the HL-3-corrected and HL-5 rows → returns as debate in R-4
- Locked: L6 legacy root migration: write `developer.worktreeRoot`, read back, then offer to delete the old value (R-3 L6.10)
- Locked: L6 out-of-feature defects from INV-009/010/011 filed as plugin issues through `/afk:report-issue`, each previewed before sending (R-3 L6.11)
- Signoff: HL-4 lifecycle and rules → signed 2026-10-20 "I sign" — covers list-entry, root, account and sign-in lifecycles, and the rule-to-guardian table
- Superseded: HL-3-corrected and HL-5 signed 2026-10-20 "I sign", voided by the L6.9 override; replaced by the amended packets below
- Locked: L6 personal copies of team settings deleted without asking once a committed settings file exists; each deleted setting, file and value listed in setup's report (R-4 L6.9-debate, human chose autoreport) — requirement change: PRD AC-024 "offers to delete" → "deletes and lists each in its report"; PRD reword through `/afk:to-prd` before `/afk:to-sdd`
- Signoff: HL-3 access (amended) → signed 2026-10-20 "I sign" — covers the round 2 matrix with the remover row corrected (git worktree remove without force + guard; plugin remover not used, INV-009) and personal-copy deletion as its own row (setup run, no asking, report)
- Signoff: HL-5 irreversible effects (amended) → signed 2026-10-20 "I sign" — covers copy deletion without asking with report, worktree removal on yes (clean and idle, branch kept), old root value deletion, secret writes, git hooks in other repositories, marker deletion, read-only account calls, harness trust shown
- Spinoffs filed 2026-10-20 (R-3 L6.11, each previewed and approved): #118 lesson-append duplicate ids, #119 create-worktree no rollback, #120 npm provision marked provisioned after failure, #121 install-git-hooks false success, #122 settle-change cleanup refused by guard + remover docs
- Locked: L7 four new shared modules (repository list, placement, safe writer, forge account helper) in `scripts/` beside `worktree_owner.py`, stdlib only, loaded by path, tests in `scripts/tests` (INV-012) · decided-by agent R-5 · accepted 2026-10-20 · repo: `occupancy.py:26`, `tests.yml:64` · reverse: move to `hooks/lib`
- Locked: L7 dependencies point hooks/skills/adapters → `scripts/` → stdlib; safe writer moves out of `install_block.py` (no Python importer) (INV-012) · decided-by agent R-5 · accepted 2026-10-20 · repo: INV-012 guard never reaches skills · reverse: load from the installer
- Locked: L7 module interfaces — list: find, all (setup only), add, remove, repoint; placement: root with state, target for a new worktree, check a chosen target; safe writer: locked update with change refusal and owner-only option; account helper: host and account, never a token; reader: owner-filtered merge, ignored list, is-set-up (R-5 L7.3)
- Locked: L7 forge wrappers fetch the token themselves per call; helper never returns it (R-5 L7.4)
- Locked: L7 placement reads only the machine file and the list, not `load()`; measured import 18 ms, parse <1 ms, `load()` 92 ms; L9 re-measures vs the 50 ms budget (R-5 L7.5)
- Locked: L8 owner rule is one table in the reader beside the key and default tables · decided-by agent R-5 · accepted 2026-10-20 · repo: `afk-config.py:53-59,108-147` · reverse: owner per caller
- Locked: L8 root and short-name rules as one check per catalog R row, first failure returned, one test per row · decided-by agent R-5 · accepted 2026-10-20 · spec: PRD catalog R · reverse: one if-chain
- Locked: L8 Jira sign-in from the first source with a complete set for the site, existing source order · decided-by agent R-5 · accepted 2026-10-20 · repo: `jira/api.py:107-136` · reverse: per-field fill
- Locked: L8 one wrapper per forge kind; shared account helper · decided-by agent R-5 · accepted 2026-10-20 · repo: `forge.sh:88`, `gitlab/forge.sh:95` · reverse: one shared wrapper
- Locked: L9 upgrade — values the owner rule ignores stop counting at once, with a warning in validate and setup; setup offers to copy each where its owner reads it; no fallback code (R-6 L9.1 strictmove, human; agent recommended a one-release fallback per `api-contract.md:29`)
- Locked: L9 release is the next major version with a changelog upgrade section (R-6 L9.2, follows L9.1; `CHANGELOG.md:22-26`)
- Locked: L9 cards L9.3..L9.14, L9.16 and seam rows L9-S1..S6 accepted as presented (R-6), subject to the R-7 corrections A-1..A-7 and fixes F-1..F-16 from the compatibility audit
- Settled: one worktree's own folder is 'the worktree's top folder'; 'worktree root' means only the folder holding every worktree (R-7 L9-15b, human; 'worktree main checkout' declined: `GLOSSARY.md:59-60` 'main checkout' = the original clone)
- Locked: L9 compatibility audit resolved 2026-10-21 — 39 findings (20 major, 0 blocker) closed by R-7 corrections A-1..A-7 (human-accepted: provider detector + guard checks the creator call and refuses inline AFK_WORKTREE_FOLDER/AFK_ALLOW_PROTECTED; idle = every recorded session dead, no record = unknown; installer error type unchanged; set-up = committed file or personal file, gates also run on a bare .afk folder; walk checks as scripts with the project folder set; legacy worktree base per repository ignored + deleted on yes; init seeds from personal team values, copy deletion narrowed) and agent-decided fixes F-1..F-16 (accepted R-7)
- Signoff: HL-6 changed behaviour → signed 2026-10-21 "I sign" — covers settings, worktrees and guard, setup/sign-ins/accounts, and release tables (next major version, changelog upgrade section, doc rewrites)
- Signoff: HL-5 irreversible effects (copy-deletion row narrowed) → signed 2026-10-21 "I sign" — deletion only once the committed file holds a real value and no worktree is on a branch without it
- Signoff: HL-1 stored state (R-7 delta) → signed 2026-10-21 "I sign" — owner table total (schema, toolkit-version team; copy switches personal; auto-publish stays ignored), init seeds from personal team values, no schema line in the personal file
- Signoff: HL-2 command surface (R-7 delta) → signed 2026-10-21 "I sign" — guard also refuses an agent's creator call with --parent/--dir outside the folder and inline AFK_WORKTREE_FOLDER/AFK_ALLOW_PROTECTED; own add parser; creator exit 3 names rule and fix; forge sign-in check 'account not available'
- Signoff: HL-3 access (R-7 delta) → signed 2026-10-21 "I sign" — the launch flag AFK_ALLOW_PROTECTED=1 lifts worktree placement (corrects 'no bypass'); idle/unknown removal on yes; review ledger trusts every login on the host plus --trust
- Signoff: HL-5 irreversible effects (R-7 delta) → signed 2026-10-21 "I sign" — removal of clean idle or unknown worktrees, each on yes; per-repository old worktree base deleted on yes
- Locked: solution grill exhausted 2026-10-21 — L1..L9 locked, HL-1..HL-6 signed against the R-8 design; next: /afk:to-sdd (PRD AC-024 reworded 2026-10-21 per R-4 L6.9-debate and R-7 A-7)
- Open: before the change opens — committed spec files fail `plugin-source-gates.sh --range main HEAD` (harness names, a personal path in COVERAGE.json `run.repository`), per INV-018
  page: `design.round.json` is the durable design-round state; a resumed session appends the next round to it and renders `design.html` with `scripts/lavish_render.py`

## Verification grill

- Settled: verification form — one black-box acceptance test file (sandbox home folder, temporary repositories, stand-in gh, glab and Jira) plus a live-run list for checks that need a real harness or account (R-1 V-1 = accept, human)
- Settled: this feature's first subtask adds `verification.tiers` to the committed AFK file — `unit` (pytest scripts/tests), `smoke` (hook smoke script), `static` (plugin-source gates over the branch), copying CI's steps (R-1 V-2 = here, human)
- Journeys settled: J-1 setup over several repositories; J-2 worktree placement by every agent route; J-3 forge account per repository; J-4 repository list; J-5 change one setting; J-6 no committed AFK file, then one arrives; J-8 Jira sign-in per site and the secret step; J-9 upgrade from the previous release; J-10 worktree root and its rules; J-11 ordinary session scope and working files · decided-by agent R-1 · accepted 2026-10-26 · spec: each journey's steps and observables are quoted from its PRD story and criteria (cites on each card in verification.round.json) · reverse: delete the journey test; contract checks still cover each criterion
- Journeys settled: J-7 `codex` app step — stand-in install shows the step naming the root, no install shows nothing; detection method recorded as a plan gap; real `codex` screen is a live check (R-1, human accept)
- Aspect: role-based access → triggered (J-2, J-3, J-8; contract rows R-2); list edits and team-setting writes on the agent's own initiative are instruction-only per signed HL-3, recorded with that reason
- Aspect: data-scoped access → triggered, scope = repository and machine, no company/vendor (J-11, J-6, J-1)
- Aspect: input validation → triggered (J-10, J-4, J-5, J-8; contract rows R-2)
- Aspect: audit history of new database records → N/A (no table or entity; files only, SDD.md:285-291)
- Aspect: deep link / address state → N/A (no web page, SDD.md:123)
- Aspect: accepted staples → N/A (no staples registry, PRD.md:192)
- Aspect: external-state recheck → triggered, 5 windows: forge token removed (J-3), session starts before removal (J-9), harness file rewritten (J-8), root becomes a repository (J-10); branch change between copy-deletion check and deletion accepted (undo from the report)
- Aspect: concurrency → applies (safe writer rows R-2)
- Aspect: idempotency → applies (J-1, J-4, J-8; marker reuse R-2)
- Aspect: pagination → N/A (no paged answer)
- Aspect: state transitions → applies (J-3, J-9, J-8)
- Aspect: error answer shape → applies (contract rows R-2)
- Env: env-limited live checks — second real GitHub account on one host; GitHub Enterprise Server host (live half unrun until a host exists); real GitLab host; real Jira site (second site env-limited); `claude` worktree tool and hook exit 3; folder trust for root subfolders in `claude` and `codex`; second Windows drive (skip with reason when absent)
- Env: every automated test runs on Windows and Linux before push (WSL locally, CI both); add correctness tests for a separate git folder and a submodule, guard timing ungated for them
- Gaps: G-1 smoke-test needs a running app and ui-e2e/api suites this repository lacks → plan gaps list, then draft a plugin issue (approval before send); G-2 CLAUDE_CONFIG_DIR target of the secret step unsettled → plan gaps, test expects follow-or-refuse, subtask settles; G-3 CI does not run the two worktree smoke scripts → creator checks go in the pytest acceptance file, CI run of the scripts is a follow-up candidate; J-7 `codex` app detection method → plan gap
- Spinoffs: candidate — run create-worktree-smoke.sh and worktree-provision-smoke.sh in CI (G-3); candidate — smoke-test skill for repositories with no running app (G-1, as a plugin issue)
- API scenarios: designed — 22 contract checks (C-1..C-22) · decided-by agent R-2 · accepted 2026-10-26 · spec: one check per SDD §3 contract row and per §14 module with no row; C-8 is pattern grade (hooks/lib/lavish_direct.py:5 assignment-or-export forms) · reverse: delete the contract test; journeys still cover the main path
- Settled: time budgets — gate on counts (no new file read off add/move, no network on add/move); report the 50/10/20 ms times only, in the informational bench (R-2 C-23, human accept)
- Gaps: G-4 bare secret-step exit status unstated → test checks the 3 commands and no write; status left to the subtask (R-2, human accept)
- Locked: verification grill settled 2026-10-26 — R-1 (36 cards) and R-2 (24 cards) all accepted; VERIFICATION-PLAN.md written 2026-10-26 (U1–U11, L1–L7, A1–A22; 48 of 48 criteria traced)
- Open: AC-060 "every plugin hook, gate and script" on an existing outside-root worktree — only the commit gate and cleanup are proven; the set was not enumerated (enumerate in one grill pass, or the human records the narrowing)
  page: `verification.round.json` is the durable round state; render `verification.html` with `scripts/lavish_render.py`

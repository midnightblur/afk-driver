# Adversary report — 0002-settings-reader

- Date: 2026-10-28 · head f432ca0 (`feat/setup-per-repo`)
- Target: no app runs in this repository. Per D-2 (`plan/DECISIONS.md`), the probes ran the shipped `scripts/afk-config.py` (command line and module), `hooks/precommit-gates.sh` (installed as a real `pre-commit` hook through `hooks/install-git-hooks.sh`, agent-marked commits in linked worktrees), the notes adapters through `hooks/lib/adapter.sh`, `skills/afk/setup/scripts/developer_values.py status` and `scripts/behavior_registry.py render`.
- Platforms: Windows (Python 3.14, Git Bash) and Linux (WSL, `git archive` of the head; `scripts/afk-config.py`, `hooks/precommit-gates.sh` and `adapters/notes/common.sh` hash-equal to the worktree).
- Scratch: `C:/t/adv2/` and `/tmp/adv2-*` only. Every process had `HOME` and `USERPROFILE` set to a scratch folder and `AFK_CONFIG` unset unless a scenario set it. "No launcher" = `AFK_PYTHON=adv-no-such-python`.
- Information diet: kept. Read the contract, cited PRD/SDD/ADR sections, `plan/DECISIONS.md`, `CONFIG.md`, `ADAPTERS.md`, the notes `CONTRACT.md`/`NOTES.md` files, hook-doc headers, and the INV-004 ledger the contract's Seams cite. No branch diff, commit, implementor test or other review file entered context.
- Probed: 330 process runs, each judged against a promise.

## Findings (worst first)

| ID | Severity | Class | Promise broken | Summary |
|---|---|---|---|---|
| F-1 | medium | robustness | `CONFIG.md` "Repository hooks" (PreCommit: a handler that cannot run blocks the commit; without the launcher, a file that cannot be read blocks); Acceptance "keeps every repository that has hooks gated" | With the launcher present, a configuration file the reader cannot read or parse turns off the repository's declared PreCommit handlers, and the commit lands |
| F-2 | low | robustness | Acceptance "An unreadable `.git` file or common directory is reported as a reader error" (PRD §Implementation Decisions); `CONFIG.md` "Discovery" | Run from the checkout, the reader answers built-in defaults and `validate` says `configuration is valid` when the `.git` file or `commondir` cannot be read |
| F-3 | low | spec | Acceptance "choosing a note-taking app moves no agent working file out of the repository" (PRD AC-070); ADR-0003 (requirements) | A `repo-files.spec-dir` that climbs out of the repository passes `validate`, and every file-backed notes kind writes outside the repository |
| F-4 | low | robustness | `adapters/notes/repo-files/CONTRACT.md` "Exit codes" ("An absolute `name` ... is refused with exit 2") | On Windows, a drive-letter `name` (`C:/...`) is accepted (exit 0) and creates a `C\uf03a\...` folder tree inside the work item folder |

### F-1 — reader failure turns off declared PreCommit handlers when the launcher is present

Setup (Linux, same result on Windows): linked worktree `wt` on branch `feat/g` of a fresh repository; `tools/hooks.json` = `[{"event":"PreCommit","matcher":"*","timeout":60,"script":"tools/h.sh"}]`; `tools/h.sh` appends to a marker file, prints `HANDLER-BLOCK-MARKER`, exits 1. Hook installed with `bash hooks/install-git-hooks.sh`. Commit: `git commit -m probe` with the harness's agent marker set, `AFK_PYTHON=/tmp/p2c-venv/bin/python`.

| Scenario | Files | Actual | Expected |
|---|---|---|---|
| w4 / g15L | committed `schema: 1` + `repo-hooks: tools/hooks.json`; personal file `<common dir>/afk/config.yaml` = `tracker: none`, `chmod 000` (Windows: read denied by ACL) | exit 0, handler not run, `[afk] configuration not loaded (... could not run .../scripts/afk-config.py): the gates it selects are off. Run /afk:setup.` | commit blocked: the committed file declares a handler that did not run |
| w5 / g13L | personal file only, = `repo-hooks: tools/hooks.json`, `chmod 000` | exit 0, handler not run, same message | blocked |
| g17L | committed as in w4; personal file `jira: {project: X}` (flow syntax, a parse error) | exit 0, handler not run, same message | blocked |
| g18L | personal file only, `repo-hooks: tools/hooks.json` + `jira: {project: X}` | exit 0, handler not run | blocked |
| control w2 / w1 | w4/w5 personal file, no launcher | exit 1, `[afk] afk-python not found ...`, commit blocked | blocked (holds) |
| control w9 / w12 | readable personal-only / committed-only declaration, launcher present | exit 1, handler ran, `repository PreCommit handler refused: tools/h.sh exited 1` | blocked (holds) |

The no-launcher branch blocks on exactly the input that the launcher branch lets through. g16L (committed file alone with a parse error and a hook declaration) also lands with the handler not run, so the launcher-branch behaviour likely predates this slice (inferred; unverified: no pre-slice build was run). The slice widens its reach: a personal file now makes a repository gated, and a broken personal file turns off a committed file's hooks.

### F-2 — unreadable `.git` file or `commondir` gives silent defaults on the normal route

Linux repro: repository with committed `.afk/config.yaml` = `schema: 1\ntracker: jira`, committed; linked worktree `wt`.

| Step (cwd `wt`, scratch `HOME`) | Actual | Expected |
|---|---|---|
| `afk-python scripts/afk-config.py get tracker` | `jira`, exit 0 | baseline |
| `chmod 000 wt/.git`; `get tracker` | `none`, exit 0, no stderr | reader error naming `wt/.git` |
| same; `validate` | `afk-config: configuration is valid`, exit 0 | reader error |
| `chmod 000 repo/.git/worktrees/wt/commondir`; `validate` / `get tracker` | `configuration is valid` / `none`, exit 0 | reader error naming `commondir` |
| Windows: `commondir` replaced by a folder; `get jira.project` from `wt` (personal file sets it) | exit 1 (absent), `validate` exit 0 `configuration is valid` | reader error |

Holds on the other routes: with `GIT_DIR`/`GIT_WORK_TREE` set, or in-process `load(project_root())` with the harness project-folder variable naming `wt`, the reader exits 2 with `afk-config: C:\...\wt\.git: cannot read it (Permission denied)` (or the `commondir` path), no traceback. An unreadable or non-UTF-8 personal file is also reported (`cannot read it (Permission denied)`, `not UTF-8 text (...)`, exit 2). In the failing state `git status` itself exits 128, so most callers fail elsewhere; `validate` still tells the developer the configuration is valid.

### F-3 — a spec folder template outside the repository is accepted

| Committed `repo-files.spec-dir` | `validate` | `note-create {"workId":"W9","name":"PRD.md"}` (`repo-files`; `obsidian` resolves the same `dir`) |
|---|---|---|
| `'../escape/{workId}'` | exit 0, `configuration is valid` | exit 0, file at `<repo>/../escape/W9/PRD.md`, outside the repository |
| `'C:/t/adv2/s/n9c/out/{workId}'` | exit 0 | exit 0, file at `<repo>/C\uf03a/t/adv2/s/n9c/out/W9/PRD.md` (folder named `C` + U+F03A) |
| `'/tmp/{workId}'` (Git Bash) | exit 0 | `dir` = `<repo>/C:/Users/.../Temp/W9` |

The note-taking app choice is not the cause; the template is. ADR-0003 puts every agent working file in the repository's spec folder, and nothing refuses a template that leaves it. `CONFIG.md` refuses `..` and absolute paths only for the investigation block. Severity low: a team must commit such a template.

### F-4 — drive-letter note name not refused on Windows

`afk_adapter notes note-create '{"workId":"W5","name":"C:/t/adv2/s/n5b/abs.md","content":"x"}'` (kind `repo-files`, Windows) → exit 0, `{"path": ".../docs/afk/W5/C:/t/adv2/s/n5b/abs.md", "created": true}`; on disk `docs/afk/W5/C\uf03a/t/adv2/s/n5b/abs.md`. Expected: exit 2, as for `/abs2.md` and `sub/../../x.md`, which are refused with `` `name` must be relative and must not climb out of the work item's directory ``. The file stays inside the work item folder. Likely predates this slice (inferred; unverified).

## Promises that held

| Promise (source) | Evidence |
|---|---|
| AC-020: committed team value wins; personal-file and local-overlay team values absent from `get`, `effective`, `export-shell`, listed by `validate` | A1: `jira.project` `TEAM`; `jira.site` absent (exit 1); `git.base-branch` `auto`; no `AFK_CFG_JIRA_SITE`; 5 warning lines naming setting, file, rule |
| AC-021: no committed file → personal file read; local overlay over personal | A4, linked worktree (A13), N4 |
| AC-022: every personal setting in the committed file ignored, warned; machine file is the personal default; personal file over machine | A5 (10 keys), A5b, `resolve` returns no committed value |
| AC-023, AC-044: every machine setting in committed, personal or local file ignored, warned; machine file read | A6 (3 files × 5 keys), A6m |
| Team value in the machine file ignored with a warning (SDD §4 Migration) | A7 |
| `validate` output and exit status; unknown keys refused | stdout `configuration is valid` + one `warning:` line per value, exit 0; unknown top or child key exit 2 in every file |
| `jira.credentials-env` removed | absent from `get`/`effective`/`export-shell` in 5 files incl. `$AFK_CONFIG` and `validate FILE`; exact warning text |
| New keys and owners | `jira.site` (D-29 scheme plus host; path, no scheme, empty, `ftp:` refused), `developer.worktreeRoot` machine, `developer.forgeAccount` personal |
| `schema` refused in the personal file and local overlay | exit 2 naming the file, also beside a committed file |
| Module answers (SDD §8) | `load()` → `dict`; `ignored_values()` → list of 3-tuples, stable over calls; `is_set_up()` true for committed (also empty) or personal file, false for none, local overlay only, machine only, `.afk` folder only; `parse_single_file` no merge, `ConfigError` with file and line on bad syntax |
| `$AFK_CONFIG` not filtered (D-10) | A12 |
| Commit gates: configuration test (SDD §14) | launcher present: personal-only (g1L), `.afk`-only (g2L), local overlay (g9L) declarations run; committed file present → personal declaration not run (g5L); machine-file declaration not run (g6L); personal-only valid repository commits (g3L, w10, AC-025) |
| No-launcher check (CONFIG.md "Repository hooks", D-26) | Linux: blocks for `.afk/hooks.json`, personal-file mention, unreadable personal file, unreadable local overlay, unreadable `$AFK_CONFIG`; passes for committed file + personal mention, machine-file mention |
| Notes kinds (AC-070, AC-071, D-11) | `obsidian` with a vault: `dir` under the checkout, vault untouched; `notion` answers its instruction file, which writes through `repo-files` first; `notes` in the committed file ignored; subfolder and linked worktree resolve at the checkout top; outside git exit 2 |
| Plugin's own `.afk/config.yaml` holds no personal or machine value | 0 non-team keys, 0 ignored values |
| Jira adapter setting list | `configKeys` names `jira.site`, no `jira.credentials-env` |
| D-24 status source | committed `developer.ideBinary`/`trackerAssignee` not reported; `forgeAccount` source `repository`, `worktreeRoot` source `machine` |
| Behavior block repository guard | rendered "Configured repositories" guard names `.afk/config.yaml` or the common directory's `afk/config.yaml` |
| `init` (D-12) | machine `tracker: jira` written as a `TODO` comment; no personal or machine value written; file passes `validate` |

## Not probed

- Owner rule cost ≤ 10 ms per load (SDD §10): unverified: the added time needs a pre-slice build to compare against, which the diet excludes.
- A relative `developer.worktreeRoot` in the machine file passes `validate` and `get`. Catalog R checks belong to 0004-placement; not judged here.

ADVERSARY: findings — probed=330 crit=0 high=0 med=1 low=3 report: docs/afk/setup-per-repo/plan/review/0002-settings-reader-adversary.md
In plain terms: the settings reader applies its new ownership rules correctly, but when one settings file is unreadable or malformed, a commit can go through without the repository's own commit checks, and three smaller edge cases let broken metadata or odd paths pass quietly; the commit-check gap should be fixed before shipping.

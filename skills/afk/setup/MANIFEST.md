# MANIFEST.md — the external-dependency register

One entry per external dependency — CLIs, MCP servers, secrets, sibling
checkouts, env toggles. The **one home** for that fact set: skills point at an
entry id (e.g. `MANIFEST.md · N2`) instead of restating install steps; the
same-commit rule keeping it true lives in `FRESHNESS.md` (plugin root).

**Entry fields.** `Needed by` — skills/scripts hitting the dep · `Probe` — exit
0 = healthy · `Fix` — `auto:` the agent runs it; `human:` the agent guides,
never runs · `Notes`. Probes are POSIX-shell commands run from the
**the repository root** (any worktree) unless prefixed `agent:` (in-session
check). Entries tagged **[deferred]** aren't needed until the named first use —
report as `deferred`, never as failures.

**Base tier.** An entry may also carry `Base probe:` / `Base fix:` — exercised
only by `/afk-toolkit:setup base` (the default branch runs `Probe:`/`Fix:` alone).
`Base probe:` tightens the health check to the monorepo's pinned toolchain
version; `Base fix:` names the concrete install the plain `human:` fix leaves to
the reader. Version pins are never restated here — probes read them from their
one home (`.sdkmanrc` for JDK/Maven; the repository's root `CLAUDE.md` states the
Node 24 / npm 11 workspace standard). Under `base`, a version miss is
`missing/broken` even when the plain probe passes. Section **W** is base-only —
its entries have no plain `Probe:` and the default branch skips them. The base
tier is elective per item — the human picks what to install at report time
(mechanics: `SKILL.md` step 3); the plain `Probe:`/`Fix:` surface never is.

**Opt-in tier.** Entries tagged **[opt-in]** are user preferences, never
load-bearing: a probe miss classifies `opt-in available`, never
`missing/broken`. Offered at report time as an election on **every** branch,
deselected by default; accept ⇒ run the fix, decline ⇒ `skipped (user choice)`
(mechanics: `SKILL.md` step 3).

**Secrets discipline.** Probes check *presence only*. Never print, log, or echo
a token value — not even partially.

## H — Harness

### H1 · plugin installed + enabled
- **Needed by:** everything (`/afk-toolkit:*` skills, the Stop-hook gates).
- **Probe:** `agent:` the active harness reports `afk-toolkit@afk-toolkit` enabled
  and lists `/afk-toolkit:setup`.
- **Fix:** `human:` use the active-harness bootstrap in `README.md` §4, then
  refresh the plugin per `PROVIDERS.md`.

### H2 · Jira MCP server *(only when the resolved `tracker` is not `none`)*
- **Needed by:** `skills/afk/to-ticket` (creds fallback reads its `env` block),
  `skills/afk/to-sdd` (pointer section), `skills/afk/fix`,
  `skills/afk/understand` (MR-subject spec discovery), the shared Jira lib
  `adapters/tracker/jira/api.py` and `skills/afk/bug/scripts/publish_bug.py` (same
  creds-fallback env block; ADR-0001).
- **Probe:** `agent:` the plugin Jira server lists `tracker_get`; a cheap call on a
  known key succeeds. Resolve the tracker first (`scripts/afk-config.py get
  tracker`): `none` — including the case of a working directory with no
  `.afk/config.yaml` — makes this row **n/a**, not a failure. `tracker_get`
  answering `unsupported` under `tracker: none` is the adapter contract working,
  and `O7`'s `tracker_get` leg is n/a for the same reason.
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` (also
  does S1/H6/C3 or C3b, whichever the forge selects), enable the plugin, then restart the session. Python deps: P3.
- **Notes:** the host is whatever `tracker` selects and its credentials name. Server source ships
  in this plugin at `mcp-servers/tracker/server.py`; `.mcp.json` is the shared
  registration. Tool prefixes vary by harness, so skills use bare tool names.

### H4 · design-push service *(optional)* **[deferred: first `/afk-toolkit:prototype` or `/afk-toolkit:design-system` push]**
- **Needed by:** `skills/afk/prototype/CLAUDE-DESIGN-PUSH.md`,
  `skills/afk/design-system/PUBLISH.md` (the opt-in share mirror only).
- **Probe:** `agent:` DesignSync tools (`list_projects`, `write_files`) listed.
- **Fix:** `human:` use the active harness's login flow when
  `CAPABILITIES.md` marks `design_push` supported; otherwise skip.
- **Notes:** local-first skills — everything works without the optional push.

### H5 · branch-name git hook *(optional)*
- **Needed by:** branch-naming discipline for `/afk-toolkit:execute`'s push — enforces
  the repository's `git.branch-pattern` on **agent** new-branch creation only;
  human-driven creation is untouched.
  Workflow `CLAUDE.md` "Conventions to keep". Not required for any skill to *run*.
- **Probe:** `grep -q afk-branch-name-gate "$(git rev-parse --path-format=absolute --git-path hooks)/reference-transaction" 2>/dev/null`
- **Fix:** `auto:` `bash "$AFK_PLUGIN_ROOT/hooks/install-git-hooks.sh"`
- **Notes:** normally auto-installs on `SessionStart` (`hooks/install-git-hooks.sh
  --quiet`, wired in `hooks.json`) whenever the plugin is enabled in a
  checkout — this entry is the fallback for non-session / CI. One
  `reference-transaction` hook in the shared (common) hooks dir covers every
  worktree. Gates branch **creation** only — checkouts of existing/remote
  branches pass untouched.
  Bypass one command: `AFK_SKIP_BRANCH_CHECK=1`. Disable: `git config
  afk.branchNameGate false`. The installer refuses to clobber a pre-existing
  non-AFK hook of the same name.

### H6 · `.claude/afk.local.json` per-dev config
- **Needed by:** `skills/afk/bug` (dispatch/publish/Ready-flip gates — key set
  and fail-closed rules owned by `skills/afk/bug/CONFIG.md`).
- **Probe:** (interpreter resolution mirrors P1 — on Windows `python3` is often
  a Store stub that exits 49 while real `python` works)
  ```
  "$(command -v python || command -v python3)" -c "
  import json, os, sys
  from contextlib import suppress
  p = '.claude/afk.local.json'
  exists = os.path.exists(p)
  d = None
  if exists:
      with suppress(Exception):
          d = json.load(open(p, encoding='utf-8'))
  if not exists:
      print('missing: file not found'); sys.exit(1)
  if not isinstance(d, dict):
      print('missing: file present but not valid JSON (or not a JSON object)'); sys.exit(1)
  m = [k for k in ('trackerAssignee', 'mrReviewer', 'worktreeBasePath') if not d.get(k)]
  print(('missing: ' + ', '.join(m)) if m else 'ok')
  sys.exit(1 if m else 0)
  "
  ```
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` (also
  does H2/S1/C3 or C3b, whichever the forge selects; pre-fills K1 from the validated token's own account). By hand:
  create `.claude/afk.local.json` per the hypothetical example in
  `skills/afk/bug/CONFIG.md` (K1 `trackerAssignee`, K2 `mrReviewer`,
  K3 `worktreeBasePath`).
- **Notes:** gitignored, one file per checkout — key set + fail-closed matrix
  owned by `skills/afk/bug/CONFIG.md`; K4 `ideBinary` optional, not probed.

### H7 · plain-language replies (ASD-STE100) **[opt-in]**
- **Needed by:** nothing — a user preference: every agent session of this user
  (all projects, both providers) answers in Simplified Technical English, not
  only the AFK-plugin sessions `LANGUAGE.md` §1 already binds.
- **Probe:** `grep -q 'afk:plain-language:start' ~/.claude/CLAUDE.md 2>/dev/null && { ! command -v codex >/dev/null || grep -q 'afk:plain-language:start' ~/.codex/AGENTS.md 2>/dev/null; }`
- **Fix:** `auto:` append the sentinel block from
  [`PLAIN-LANGUAGE.md`](PLAIN-LANGUAGE.md) (the one home) to the user-global
  steering files — `~/.codex/AGENTS.md` only when Codex (O1) is installed —
  creating a missing file, skipping one already carrying the sentinel:
  ```sh
  src=$AFK_PLUGIN_ROOT/skills/afk/setup/PLAIN-LANGUAGE.md
  for f in ~/.claude/CLAUDE.md ~/.codex/AGENTS.md; do
    [ "$f" = "$HOME/.codex/AGENTS.md" ] && ! command -v codex >/dev/null && continue
    grep -q 'afk:plain-language:start' "$f" 2>/dev/null && continue
    mkdir -p "$(dirname "$f")"
    { [ -s "$f" ] && echo; sed -n '/afk-toolkit:plain-language:start/,/afk-toolkit:plain-language:end/p' "$src"; } >> "$f"
  done
  ```
- **Notes:** user-global, per-machine — never rides git (file map:
  `PROVIDERS.md`). Opt out later by deleting the sentinel block from the
  file(s); opt in any time by re-running `/afk-toolkit:setup`.

### H8 · lavish for grilling sessions **[opt-in]**
- **Needed by:** nothing — a user preference: grilling sessions (agent
  explains or asks in rounds, human answers, picks, or gives feedback) render
  through lavish-axi even when no skill's own render point is in play.
- **Probe:** `grep -q 'afk:lavish-sessions:start' ~/.claude/CLAUDE.md 2>/dev/null && { ! command -v codex >/dev/null || grep -q 'afk:lavish-sessions:start' ~/.codex/AGENTS.md 2>/dev/null; }`
- **Fix:** `auto:` append the sentinel block from
  [`LAVISH-SESSIONS.md`](LAVISH-SESSIONS.md) (the one home) to the user-global
  steering files — same targets and skip guards as H7's loop:
  ```sh
  src=$AFK_PLUGIN_ROOT/skills/afk/setup/LAVISH-SESSIONS.md
  for f in ~/.claude/CLAUDE.md ~/.codex/AGENTS.md; do
    [ "$f" = "$HOME/.codex/AGENTS.md" ] && ! command -v codex >/dev/null && continue
    grep -q 'afk:lavish-sessions:start' "$f" 2>/dev/null && continue
    mkdir -p "$(dirname "$f")"
    { [ -s "$f" ] && echo; sed -n '/afk-toolkit:lavish-sessions:start/,/afk-toolkit:lavish-sessions:end/p' "$src"; } >> "$f"
  done
  ```
- **Notes:** user-global, per-machine — never rides git (file map:
  `PROVIDERS.md`). The installed block self-guards: outside a repo carrying
  the plugin's `LAVISH.md` it is inert. Render doctrine (RP-10, session-default
  weave, fallback) stays in `LAVISH.md`. Opt out by deleting the sentinel
  block; opt in any time by re-running `/afk-toolkit:setup`.

### H9 · Notion MCP server *(only when `notes: notion`)*
- **Needed by:** `adapters/notes/notion` — every notes verb mirrors its local
  copy to a Notion page through this server's tools.
- **Probe:** `agent:` a Notion MCP tool is listed in this session's tool set.
- **Fix:** `human:` connect a Notion MCP server in the harness, then restart the
  session — MCP tools register at launch. The local Markdown copy is written
  either way, so an unconnected server delays the mirror, never the note.
- **Notes:** the page every work item is created under is
  `notion.parent-page-id` in `.afk/config.yaml`, not a secret.

## C — Shell & core CLIs

### C1 · bash (Git Bash on Windows) + POSIX utils
- **Needed by:** the `hooks/*.sh` gate suite (the Stop gates — wiring,
  genericity, skill-registry, native-contract via `stop-gates.sh` — **fire every
  turn**; the commit gates — Maven compile, Java format, UI lint via
  `precommit-gates.sh` — fire on agent-driven commits; plus the on-demand
  `app-start-gate.sh`), the forge adapters' `forge.sh`,
  `skills/utils/diagnose/scripts/hitl-loop.template.sh`, app-start invocations
  in `skills/afk/autopilot` and `skills/afk/to-subtasks/SMOKE-GATE.md`.
- **Probe:** `bash -c 'command -v awk && command -v sed && command -v grep' >/dev/null`
- **Fix:** `human:` install Git for Windows (ships bash + the POSIX utils).
- **Notes:** the single hardest platform assumption — outside a POSIX shell the
  Stop hooks error on every turn.

### C2 · git
- **Needed by:** the whole chain (worktrees, branches, push), `hooks/wiring-gate.sh`.
- **Probe:** `git --version`
- **Fix:** `human:` install Git for Windows (also satisfies C1).
- **Base fix:** `auto:` `winget install --id Git.Git -e` — ships bash + POSIX
  utils + perl, so it also satisfies C1 and C6.

### C3 · glab (GitLab CLI), logged in — **secret** *(only when `forge: gitlab`)*
- **Needed by:** `adapters/forge/gitlab/forge.sh` — every forge verb, so
  `skills/afk/execute` (push + Draft change), `skills/afk/preflight` (the CI
  wait and the Draft→Ready flip), `skills/afk/understand` (change intake) and
  `skills/afk/gc` (the merged proof).
- **Probe:** `glab auth status` (exit 0 = logged in; prints no token).
- **Fix:** `human:` install glab, then `glab auth login --hostname <the GitLab
  host this repository pushes to>` — the token lives in glab's own store, never in
  this plugin. `skills/afk/setup/scripts/setup_secrets.py` drives that login as
  one of its steps (it shells out to `glab`; the token still never touches this
  plugin).

### C3b · gh (GitHub CLI), logged in — **secret** *(only when `forge: github` or `tracker: github-issues`)*
- **Needed by:** `adapters/forge/github/forge.sh` — every forge verb, so
  `skills/afk/execute` (push + Draft change), `skills/afk/preflight` (the CI
  wait and the Draft→Ready flip), `skills/afk/understand` (change intake) and
  `skills/afk/gc` (the merged proof); and
  `adapters/tracker/github-issues/api.py` — every `tracker_*` operation.
- **Probe:** `gh auth status` (exit 0 = logged in; prints no token).
- **Fix:** `human:` install gh, then `gh auth login` — the token lives in gh's
  own store, never in this plugin. `skills/afk/setup/scripts/setup_secrets.py`
  drives that login when `forge: github` is configured (it shells out to `gh`;
  the token still never touches this plugin).

### C4 · Maven wrapper + JDK
- **Needed by:** `skills/afk/execute` verification tiers, the smoke gate's
  compile row (`skills/afk/to-subtasks/SMOKE-GATE.md`), the liquibase pickup
  check (`skills/afk/to-subtasks`), and the commit gates
  `adapters/build-gate/maven/maven-compile-gate.sh` / `adapters/build-gate/maven/java-format-gate.sh` (dispatched by
  `precommit-gates.sh` on agent-driven commits) plus
  `adapters/build-gate/maven/app-start-gate.sh` (all three no-op unless `maven`
  is in `build-gates:` and `maven.reactor-pom` names a POM in this checkout).
- **Probe:** `./mvnw -v` (proves wrapper **and** a resolvable JDK).
- **Fix:** `human:` the wrapper ships with the repository; JDK selection
  follows that repository's own conventions (its root `CLAUDE.md`).
- **Base probe:** `want=$(sed -n 's/^java=\([0-9][0-9]*\).*/\1/p' .sdkmanrc); ./mvnw -v 2>/dev/null | grep "Java version: $want\." | grep -qi amazon`
  — the JDK the wrapper resolves must match the `.sdkmanrc` java pin **and** be
  Amazon Corretto (the `amazon` vendor grep mirrors the pin's `-amzn` suffix —
  change both together).
- **Base fix:** `human:` with sdkman (Git Bash): `sdk env install` — installs the
  pinned Corretto JDK + Maven straight from `.sdkmanrc`; without sdkman: install
  the Amazon Corretto JDK matching the pin (`winget search corretto` for the
  right package id) and point `JAVA_HOME` at it (README §Local build).
  Standalone Maven is optional — the wrapper self-provisions its own.

### C5 · pitest (mutation probe) *(optional)* **[deferred: first review-gate mutation probe]**
- **Needed by:** `adapters/build-gate/maven/mutation-probe.sh` (invoked by `skills/afk/review`'s
  test-veracity concern, sampled).
- **Probe:** `test -f $AFK_PLUGIN_ROOT/adapters/build-gate/maven/mutation-probe.sh && ./mvnw -v >/dev/null`
- **Fix:** `human:` pitest itself resolves from Maven Central at run time
  (version pinned via `PITEST_VERSION`, default in the script) — but JUnit 5
  test discovery needs `org.pitest:pitest-junit5-plugin` on the pitest maven
  **plugin** classpath, which cannot be injected from the CLI: add the
  `<pluginManagement>` snippet from `adapters/build-gate/maven/mutation-probe.sh`'s header to the
  service's parent POM once per service.
- **Notes:** fail-open by design — without the POM entry (or on a
  JDK-compatibility miss) the probe exits 3 `unavailable` and the review gate
  treats it as "no signal", never a failure. pitest-on-JDK25 compatibility is
  unverified upstream; the first real run on a machine is the empirical test.

### C6 · perl (Git-Bash)
- **Needed by:** `skills/afk/bug`'s create-worktree script (path-rewrite step —
  SDD §9b seam "perl (Git-Bash)").
- **Probe:** `command -v perl`
- **Fix:** `human:` install Git for Windows (ships perl alongside C1's bash +
  POSIX utils).
- **Notes:** missing perl fails the worktree script's path-rewrite step before
  first use (SDD §9b row "perl (Git-Bash)").

### C7 · Docker (engine + compose v2) **[deferred: first self-provisioned app env]**
- **Needed by:** the repository's environment tooling (`verification.env`),
  `skills/afk/smoke-test` / `skills/afk/autopilot` / `skills/afk/adversary`
  (live-app verification, X5), `build-scripts/build-docker-compose.py`.
- **Probe:** `docker info >/dev/null && docker compose version >/dev/null`
  (proves the daemon is *running* and compose v2 is present — a stopped Docker
  Desktop fails this even when installed; start it and re-probe).
- **Fix:** `human:` install Docker Desktop (WSL2 backend) and start it.
- **Base probe:** `wsl.exe --status >/dev/null 2>&1` — the WSL2 runtime Docker
  Desktop's backend requires. Absent WSL, Docker Desktop fails to start with a
  **misleading** "virtualization support not detected" error even when firmware
  virtualization is on (`Get-CimInstance Win32_Processor` shows
  `VirtualizationFirmwareEnabled: True`) — probe WSL before blaming BIOS/IT.
- **Base fix:** `human:` from an **elevated** prompt:
  `wsl --install --no-distribution` (installs the WSL2 runtime + Virtual
  Machine Platform; no Linux distro needed for Docker), then reboot. Then
  `winget install --id Docker.DockerDesktop -e`, then raise the WSL2 memory
  ceiling in `~/.wslconfig` — the default cap wedges the engine under a full app
  env (all API calls 500); restart WSL after editing. If Docker still won't
  start after all that: `wsl --update` (elevated) to refresh the WSL kernel.

## P — Python

### C8 · robocopy (Windows built-in) *(optional)*
- **Needed by:** `skills/afk/bug`'s create-worktree script (per-worktree Maven repo
  seeding — multi-threaded copy of the dev's local repo minus `*-SNAPSHOT` dirs).
- **Probe:** `command -v robocopy || test -x "${SYSTEMROOT:-/c/Windows}/System32/Robocopy.exe"`
- **Fix:** none needed on Windows (ships with the OS); no fix elsewhere — the script
  falls back to `cp -a`.
- **Notes on the probe:** `command -v` reads `PATH`, and a shell whose `PATH`
  omits `System32` reported this built-in as absent. The file test is the
  authority on Windows; the `PATH` lookup stays first because it is what the
  script itself will use.
- **Notes:** fail-open — robocopy absent or the seed copy failing downgrades to the
  `cp -a` fallback / an unseeded private repo with a warning; the isolation itself
  (`.mvn/maven.config` → `<worktree>/.m2/repository`) is written regardless, so
  concurrent worktree builds never share a writable local repo.

### C9 · jq *(optional)*
- **Needed by:** `hooks/lib/provider.sh` — reads a field out of the hook payload
  and builds every hook answer (`block`, `ask`, the plain success shape), so the
  whole gate suite runs through it; `hooks/tests/hook-smoke.sh` asserts on those
  answers.
- **Probe:** `command -v jq`
- **Fix:** none needed — `provider.sh` falls back to `grep` + `sed` for both
  reading and writing, and `hook-smoke.sh` prints `SKIP: jq not on PATH` and
  exits 0.
- **Base fix:** `auto:` `winget install --id jqlang.jq -e`
- **Notes:** fail-open, and the fallback is not a lesser path — it is the one
  most machines take. Registered because shipped code names the binary, not
  because a gate needs it. `--jq` in `adapters/forge/github/forge.sh` is a `gh`
  flag with its own JSON engine, not this dependency.

### C10 · timeout + curl *(optional)*
- **Needed by:** `hooks/update-notice.sh` only — `timeout` budgets each of its
  two network steps at 2 seconds, `curl` fetches a release's `CHANGELOG.md` when
  `git archive --remote` cannot.
- **Probe:** `command -v timeout && command -v curl`
- **Fix:** none needed — both ship with Git for Windows (C1). Absent, the
  session-start notice stays silent.
- **Notes:** fail-open by construction. That hook is documented to never block,
  never slow a session start, and never need a dependency the toolkit does not
  already require; every failure path exits 0 without output. A missed notice
  about a newer release is the entire cost.

### P1 · Python 3
- **Needed by:** `hooks/run-hook.py` — the launcher every registered hook command
  runs through, so without it no gate or guard fires at all — the shared
  `.mcp.json` bootstrap,
  `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`,
  `skills/afk/claude-md/scripts/*.py`, the repository's `verification.env` command,
  the shared Jira lib `adapters/tracker/jira/api.py` and
  `skills/afk/bug/scripts/publish_bug.py` (ADR-0001).
- **Probe:** `python --version || python3 --version`
- **Fix:** `human:` install Python 3 and put it on PATH.
- **Base fix:** `auto:` `winget install --id Python.Python.3.12 -e` (any Python 3
  on PATH passes the probe — the pin here is just a working default).

### P2 · markdown-it-py
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`
  (PRD / meeting body → ADF), the shared Jira lib `adapters/tracker/jira/api.py`
  (imported by both `publish_prd.py` and `skills/afk/bug/scripts/publish_bug.py`
  for the same Markdown→ADF conversion; ADR-0001).
- **Probe:** `python -c "import markdown_it"`
- **Fix:** `auto:` `pip install markdown-it-py`

### P3 · mcp + httpx (Jira MCP server runtime)
- **Needed by:** `mcp-servers/tracker/server.py` (H2) — FastMCP host + HTTP client.
- **Probe:** `python -c "import mcp, httpx"`
- **Fix:** `auto:` `pip install mcp httpx`
- **Notes:** missing deps surface as the `jira` server failing to connect at
  session start, not as a skill error.

### P4 · openpyxl
- **Needed by:** `skills/utils/review-qa-tests/scripts/annotate_sheet.py` —
  reads QA's `.xlsx` test sheet and writes the review annotations back into it
  (`skills/utils/review-qa-tests/EXCEL.md`).
- **Probe:** `python -c "import openpyxl"`
- **Fix:** `auto:` `pip install openpyxl`

## N — Node toolchain

### N1 · node + npm + npx
- **Needed by:** mermaid rendering (N2), the verification suites (N3), UI
  builds the chain may trigger, and `adapters/build-gate/npm/ui-lint-gate.sh` (resolves eslint
  via `npx --no-install`; silently allows when unresolvable).
- **Probe:** `node --version && npm --version`
- **Fix:** `human:` install the Node version the repository standardises on.
- **Base probe:** `node --version | grep -q '^v24\.' && npm --version | grep -q '^11\.'`
  — whatever workspace standard the repository's root `CLAUDE.md` states.
- **Base fix:** `human:` via nvm: `nvm install 24 && nvm use 24` (npm 11 ships
  with Node 24); nvm itself is optional — any install path that flips the base
  probe green passes.

### N2 · mermaid-cli **[deferred: first PRD with a ```mermaid block, or first render-check]**
- **Needed by:** `skills/afk/to-ticket` (diagram → PNG, rendered locally —
  never an external render service), `skills/utils/draw-charts` (render-check).
- **Probe:** `command -v mmdc || command -v npx`
- **Fix:** `auto:` `npm i -g @mermaid-js/mermaid-cli`
- **Notes:** without a global install, engines fall back to
  `npx -y @mermaid-js/mermaid-cli`; the first such run downloads a headless
  Chromium (one-time, ~hundreds of MB).

### N3 · verification-suite runtime **[deferred: first `api` / `e2e/browser` tier or smoke run]**
- **Needed by:** `skills/afk/execute` (api/e2e tiers), `skills/afk/smoke-test`,
  `skills/afk/adversary` (live-app probing).
- **Probe:** the `e2e/browser` tier in `verification.tiers` runs its own `--version` form
- **Fix:** `human:` install per the repository's own verification README
  (that file is the one home for suite setup — browsers included); the `api`
  suite is dependency-free (`node --test` on N1 alone).

### N4 · lavish-axi (render points) **[deferred: first human-present render point]**
- **Needed by:** any skill woven with a `render per LAVISH.md` point — the pin,
  invocation shapes, and forbidden operations live in `LAVISH.md` (plugin
  root), never restated here.
- **Probe:** `command -v npx` (the pinned package resolves on first use; no
  global install, no package.json — see `LAVISH.md`).
- **Fix:** `human:` install Node/npx per N1; a failing render is **never** a
  phase failure — every render point falls back to markdown (`LAVISH.md`).

## S — Secrets

### S1 · Jira REST credentials — **secret**
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`
  (attachment upload has no MCP tool, and both engines PUT the description via
  REST directly rather than inline a large ADF through an MCP tool call),
  the shared Jira lib `adapters/tracker/jira/api.py` and
  `skills/afk/bug/scripts/publish_bug.py` (same creds resolution; ADR-0001).
- **Probe:** presence-only through the shared resolver; prints no values:
  `python "$AFK_PLUGIN_ROOT/adapters/tracker/jira/api.py" --check-creds`
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` — it
  prompts for the token without echoing it, validates it against the host before
  writing, and places it in the H2 `env` block (also does H2/H6/C3 or C3b, whichever the forge selects). By hand:
  create an API token (Atlassian account → Security → API tokens), then set
  `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` through a source listed in
  `PROVIDERS.md`.

### S2 · GitLab token — **secret**
- Held entirely by glab (C3). No plugin storage, nothing further to provision.

### S3 · verification-app auth token — **secret**
- Minted at runtime by the repository's own verification core; provisioning lives in
  that tree's docs, not here. Nothing to set up until N3's first use.

## O — OpenAI Codex CLI *(optional supported harness)*

Gating rule: if O1 misses, report the whole section as
`deferred (Codex not installed)`.

### O1 · binary, login, and tested version
- **Needed by:** running the native plugin under Codex CLI.
- **Probe:** `v=$(codex --version 2>/dev/null | awk '{print $2}'); test -n "$v" && test "$(printf '%s\n' 0.152.0 "$v" | sort -V | head -1)" = 0.152.0`
- **Fix:** `human:` install or update Codex CLI, then run `codex login`.
- **Notes:** minimum live-tested version is `0.152.0`.

### O2 · native hooks feature
- **Needed by:** plugin Stop gates and PreToolUse guards.
- **Probe:** parse `~/.codex/config.toml`; require `features.hooks = true` and
  no `features.codex_hooks` key.
- **Fix:** `human:` set `features.hooks = true`. Remove the deprecated key only
  after confirmation. Preserve every unrelated setting.

### O3 · native marketplace, plugin, and fresh cache
- **Needed by:** native skills, hooks, and MCP registration.
- **Probe:** `codex plugin marketplace list` names `afk-toolkit`; `codex
  plugin list` reports `afk-toolkit@afk-toolkit` installed and enabled; the newest
  installed plugin root that Codex plugin metadata reports matches the source
  manifests, `hooks/hooks.codex.json`, and every `skills/*/*/SKILL.md` hash.
- **Fix:** `auto:` when absent, run `codex plugin marketplace add
  midnightblur/afk-driver --ref v<toolkit-version>`, then `codex plugin add
  afk-toolkit@afk-toolkit`. For a stale cache, ask first; after confirmation run
  `codex plugin remove afk-toolkit@afk-toolkit`, add it again, then restart.

### O4 · current hook definitions trusted
- **Needed by:** every handler in `hooks/hooks.json`.
- **Probe:** parse `~/.codex/config.toml`; every enabled AFK handler has a
  current native trust entry. Never print other config or secret values.
- **Fix:** `human:` review and trust every current AFK definition through the
  native hooks interface after all `hooks.json` edits land.

### O5 · Codex agent TOML stubs
- **Needed by:** `afk-reader`, `afk-runner`, `afk-runner-lite`, and `afk-implementor` roles.
- **Sources (exactly these four, no others):**
  `providers/codex/agents/afk-toolkit-afk-implementor.toml`,
  `providers/codex/agents/afk-toolkit-afk-reader.toml`,
  `providers/codex/agents/afk-toolkit-afk-runner.toml`,
  `providers/codex/agents/afk-toolkit-afk-runner-lite.toml`.
- **Probe:** each `providers/codex/agents/afk-toolkit-afk-*.toml` is present under
  `~/.codex/agents/` with the same filename, its `{{PLUGIN_ROOT}}` placeholder is
  replaced by a plugin root that **exists on disk and contains `LANGUAGE.md` and
  `agents/`**. That harness reports the root two ways — a marketplace directory and a
  versioned cache directory — and both are real, content-identical, and work. The
  probe asked for one exact string and therefore failed on a machine whose stubs were
  correct. What matters is that the baked path resolves to the toolkit, not which of
  its two names was written.
- **Upgrading the plugin breaks this row until setup runs again.** The root baked into
  each stub carries the version, so installing any new version leaves all four stubs
  naming a directory that no longer exists, and every agent spawn on that harness
  fails. Re-run `/afk-toolkit:setup` after every version change on that harness — not
  only when a changelog entry says the dependency set changed. The last clause of the
  probe is what catches it.
- **Fix:** `auto:` read the installed plugin root from Codex plugin metadata — the
  `[plugins."afk-toolkit@afk-toolkit"]` entry in `~/.codex/config.toml`, else the
  `Installed plugin root:` line of `codex plugin list`. Never list a cache directory
  and never pick a "newest" directory. Create missing destinations, copy each
  `providers/codex/agents/afk-toolkit-afk-*.toml` to `~/.codex/agents/` under the same
  filename, and replace every `{{PLUGIN_ROOT}}` occurrence with that root verbatim.
  Refuse to overwrite a different user file without confirmation. Verify each
  destination contains no `{{PLUGIN_ROOT}}`, then start a new session.

### O6 · per-directory steering fallback **[opt-in]**
- **Needed by:** nested `CLAUDE.md` files when no nearer `AGENTS.md` exists.
- **Probe:** `~/.codex/config.toml` has
  `project_doc_fallback_filenames = ["CLAUDE.md"]`.
- **Fix:** `human:` offer that exact idempotent setting. Preserve all other
  user configuration.

### O7 · native catalog and shared Jira MCP
- **Needed by:** all workflow skills and the two Jira-writing skills.
- **Probe:** `agent:` a new session lists every `afk:<name>` plugin skill named
  in `plugin.json` and no `afk-<name>` mirror, every agent role `O5` lists, and a
  callable `tracker_get` (n/a under `tracker: none`, per `H2` — the catalog and
  role legs still stand on their own). Count the manifest rather than a number written here:
  a number in prose goes stale the first time a skill is added.
- **Fix:** repair O2–O6, then restart. Never print Jira secrets.

### O8 · stale generated activation cleanup **[opt-in]**
- **Needed by:** migration from the retired generated layer only. Run it after
  uninstalling the plugin too: these paths are gitignored, so a harness removal
  leaves them behind and a repository-root session still reads them.
- **Probe:** `test ! -d .agents/skills -a ! -f .codex/hooks.json -a ! -d .codex/agents -a ! -f AGENTS.local.md`
- **Fix:** `human:` offer removal of AFK-generated `.agents/skills/afk-*`,
  project `.codex/agents/`, project `.codex/hooks.json`, and only the AFK block
  in `AGENTS.local.md`. Delete nothing without confirmation. Preserve every
  unrelated file and block.

## X — Rows the repository contributes

A repository states its own prerequisites — its checkout, its verification
tree, its environment tooling, its credentials — in the files its
`.afk/config.yaml` lists under `setup.extra`. Each is a Markdown file in this
same row format; `/afk-toolkit:setup` reads them after the rows above and
probes them the same way. The toolkit ships no row for any one repository's
state, because it cannot know it.

## W — Workstation apps & OS config (base-only)

Human tooling and machine settings, not skill dependencies — no skill invokes
these, so entries here carry **only** base-tier fields and the default branch
skips the section entirely. Probed and fixed under `/afk-toolkit:setup base` alone; a
miss is `missing/broken` there, never on a default run. Any fix marked
**elevated prompt** stays with the human — the agent never elevates.

### W1 · Visual Studio Code
- **Needed by:** the human (no skill invokes it).
- **Base probe:** `command -v code`
- **Base fix:** `auto:` `winget install --id Microsoft.VisualStudioCode -e`

### W2 · IntelliJ IDEA
- **Needed by:** the human; optionally referenced by `/afk-toolkit:bug`'s `ideBinary`
  key (K4, `skills/afk/bug/CONFIG.md`) to open fixer worktrees.
- **Base probe:** `winget list --id JetBrains.IntelliJIDEA.Ultimate -e >/dev/null 2>&1 || winget list --id JetBrains.IntelliJIDEA.Community -e >/dev/null 2>&1 || ls -d "$LOCALAPPDATA/Programs/IntelliJ IDEA"* >/dev/null 2>&1 || ls -d "$LOCALAPPDATA/JetBrains/Toolbox/apps/intellij-idea"* >/dev/null 2>&1 || ls -d "$ProgramFiles/JetBrains/IntelliJ IDEA"* >/dev/null 2>&1`
  A probe that enumerates install locations is wrong until the next one is found:
  this row has now missed a Toolbox install and a system-wide install in turn, on
  machines where the editor was open at the time. Treat a negative as "not found
  where I looked", never as "not installed", and add the location rather than
  asking the human to install what they already have. A package manager sees only
  what it installed, so a Toolbox installation read as
  absent and the row failed on a machine where the editor was running.
- **Base fix:** `human:` `winget install --id JetBrains.IntelliJIDEA.Ultimate -e`
  (or via JetBrains Toolbox), then sign in with a license.

### W5 · Windows long paths enabled
- **Needed by:** deep paths — a hoisted `node_modules` or a nested module tree
  blows past the 260-char MAX_PATH; checkouts and builds fail with
  path-too-long errors otherwise.
- **Base probe:** `MSYS_NO_PATHCONV=1 reg query 'HKLM\SYSTEM\CurrentControlSet\Control\FileSystem' /v LongPathsEnabled 2>/dev/null | grep -q 0x1 && [ "$(git config --global --get core.longpaths)" = true ]`
  (both halves required — the OS flag and git's own limit; the
  `MSYS_NO_PATHCONV=1` prefix is load-bearing — without it Git Bash mangles
  `/v` into a path and `reg query` errors, a false negative on a healthy
  machine).
- **Base fix:** `human:` from an **elevated** prompt:
  `reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f`,
  then (no elevation needed) `git config --global core.longpaths true` — the
  git half is also offered by `skills/afk/setup/scripts/setup_secrets.py`.
- **Notes:** re-probe after. New processes pick the flag up without a reboot.

## E — Env toggles (index only; no probes)

Each var is documented at its consumer — this table is just the map.

| Var | Consumer | Role |
|---|---|---|
| `CLAUDE_PLUGIN_ROOT` | `hooks/hooks.json`, `hooks/lib/providers/claude.sh` | compatibility root set by supported plugin hooks |
| `CLAUDE_PROJECT_DIR` | `hooks/run-hook.py` | optional fast project root, read with the `${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}` fallback |
| `AFK_BASH` / `GIT_BASH` | `hooks/run-hook.py` | POSIX shell the hook launcher runs handlers with, ahead of its own lookup |
| `APP_START_KEEP` / `APP_START_PORT` / `APP_START_SKIP_UI` / `APP_START_REUSE` | `skills/afk/autopilot` | app-start-gate provisioning mode |
| `APP_START_TIMEOUT` | `adapters/build-gate/maven/app-start-gate.sh` | boot timebox (seconds, default 300) |
| `APP_START_UI_BUILD` | `adapters/build-gate/maven/app-start-gate.sh` | the UI build script the gate runs when `APP_START_SKIP_UI=false`; defaults to `build_ui.sh` beside the service directory |
| `CI_PROJECT_DIR` | `adapters/build-gate/maven/app-start-gate.sh` | checkout the service's `build_ui.sh` resolves its npm workspace from; read only when `APP_START_SKIP_UI=false`, defaults to the repo root |
| `AFK_DRIVEN` | `skills/afk/gc/scripts/gc-check.sh` | exported `=1` by hands-off invokers; makes `/afk-toolkit:gc` refuse deletion — it always gets a human eye |
| `WIRING_GATE_DISABLE` / `WIRING_FINAL` | `hooks/wiring-gate.sh` | disable / final-mode the wiring gate |
| `SKILL_REGISTRY_GATE_DISABLE` | `hooks/skill-registry-gate.sh` | disable the registry gate (plugin.json membership + skill catalog + env-toggle register) |
| `GENERICITY_GATE_DISABLE` | `hooks/genericity-gate.sh` | disable the genericity gate |
| `NATIVE_CONTRACT_GATE_DISABLE` | `hooks/native-contract-gate.sh` | bypass the native plugin contract gate |
| `AFK_PROVIDER` | `hooks/lib/provider.sh` | force provider detection before adapter probes |
| `PLUGIN_ROOT` / `PLUGIN_DATA` | `hooks/lib/providers/codex.sh` | native plugin root and data paths; root detection precedes inherited compatibility markers |
| `CLAUDE_PLUGIN_DATA` | `hooks/lib/providers/claude.sh` | compatibility plugin data path |
| `GATE_CACHE_DISABLE` | `hooks/gate-cache.sh` | bypass the Stop gates' pass cache — every run does real work |
| `AFK_PLUGIN_ROOT` | `hooks/run-hook.py`, `hooks/lib/config.sh`, `hooks/lib/adapter.sh`, `hooks/install-git-hooks.sh` | absolute plugin root, exported by the hook launcher so repository-owned handlers and adapters resolve the toolkit without searching |
| `JIRA_DEFAULT_PROJECT` | `adapters/tracker/jira/api.py` | project key used when a caller names none; absent, a create is refused with a message naming this variable rather than guessing a project |
| `GH_REPO` | `adapters/tracker/github-issues/api.py` | `owner/name` fallback when the configuration names no `repo`; the configuration wins where both are set |
| `AFK_CFG_GITHUB_REMOTE` / `AFK_CFG_GITLAB_REMOTE` | `adapters/forge/github/forge.sh`, `adapters/forge/gitlab/forge.sh` | the git remote whose URL identifies the project, exported by `hooks/lib/config.sh` from `<kind>.remote`; unset lets the forge CLI derive the project from the checkout |
| `AFK_CFG_OBSIDIAN_VAULT` | `adapters/notes/obsidian/notes.sh` | vault directory exported from `obsidian.vault`; an absent directory is answered `unavailable` rather than crashing |
| `AFK_CFG_REPO_FILES_SPEC_DIR` | `adapters/notes/common.sh` | the spec-directory template exported from `repo-files.spec-dir`, with its placeholders expanded per note |
| `CLAUDECODE` | `hooks/lib/providers/claude.sh`, `hooks/branch-name-gate.sh`, `hooks/native-contract-gate.sh`, `hooks/skill-registry-gate.sh` | a compatibility marker one harness sets; read only after the native root variable, never as the first thing tried |
| `CLAUDE_JOB_DIR` | `adapters/forge/github/forge.sh`, `adapters/forge/gitlab/forge.sh` | per-job scratch directory that harness offers; where a forge verb writes a downloaded diff when the caller names no `out_dir` |
| `AFK_CFG_MAVEN_*` | `adapters/build-gate/maven/maven-lib.sh` and the Maven gates | the `maven:` block exported by `hooks/lib/config.sh` — `reactor-pom`, `formatter-config`, `formatter-plugin`, `default-module`, `skip-ui-flag` |
| `AFK_CFG_NPM_*` | `adapters/build-gate/npm/ui-lint-gate.sh` | the `npm:` block exported by `hooks/lib/config.sh` — `lint`, `workspace-root` |
| `AFK_CFG_BUILD_GATES_*` | `hooks/lib/config.sh`, `hooks/lib/adapter.sh` | the `build-gates:` list (`_COUNT` plus indexed names) selecting which build-gate adapters load |
| `AFK_CFG_GIT_BRANCH_PATTERN` | `hooks/branch-name-gate.sh` | the branch-name convention exported by `hooks/lib/config.sh` from `git.branch-pattern`; unset means the repository has no convention and the gate is off |
| `AFK_CFG_GIT_BRANCH_TEMPLATE` | `hooks/branch-name-gate.sh` | the suggestion the gate prints on a refusal, exported from `git.branch-template`; its placeholders are expanded from the rejected name |
| `AFK_CFG_GIT_BASE_BRANCH` | `hooks/gate-context.sh` | integration base exported by `hooks/lib/config.sh` from `git.base-branch`; unset or `auto` falls back to `origin/main`, `origin/master`, `@{u}`, HEAD |
| `AFK_GATE_CTX_DISABLE` | `hooks/gate-context.sh` | rebuild the shared per-Stop change-set context on every call instead of reusing it (debug) |
| `AFK_SKIP_PRECOMMIT_GATES` | `hooks/precommit-gates.sh` | skip the commit-time code gates the `build-gates:` adapters select, for one commit |
| `GATE_METRICS_DISABLE` / `GATE_METRICS_FILE` | `hooks/gate-metrics.sh` | silence / relocate gate-latency emission |
| `MAVEN_LOCK_DIR` | `adapters/build-gate/maven/maven-lock.sh` | relocate the cross-gate maven lock dir |
| `AFK_MAVEN_LOCK_WAIT` | `adapters/build-gate/maven/maven-compile-gate.sh` | seconds the compile gate waits for the maven lock before allowing (240 on the commit path, 900 standalone) |
| `PITEST_VERSION` / `MUTATION_TIMEOUT` | `adapters/build-gate/maven/mutation-probe.sh` | pitest version pin / probe timebox |
| `AFK_SKIP_BRANCH_CHECK` | `hooks/branch-name-gate.sh` | bypass the branch-name gate for one agent command |
| `LESSON_LEDGER_DISABLE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | disable lesson-ledger writes/reads (kill switch) |
| `LESSON_LEDGER_FILE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | relocate the lesson ledger (default: main-checkout `.claude/lessons/LEDGER.jsonl`) |

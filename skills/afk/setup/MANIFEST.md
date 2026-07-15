# MANIFEST.md — the external-dependency register

One entry per external dependency — CLIs, MCP servers, secrets, sibling
checkouts, env toggles. The **one home** for that fact set: skills point at an
entry id (e.g. `MANIFEST.md · N2`) instead of restating install steps; the
same-commit rule keeping it true lives in `FRESHNESS.md` (plugin root).

**Entry fields.** `Needed by` — skills/scripts hitting the dep · `Probe` — exit
0 = healthy · `Fix` — `auto:` the agent runs it; `human:` the agent guides,
never runs · `Notes`. Probes are POSIX-shell commands run from the
**core-services repo root** (any worktree) unless prefixed `agent:` (in-session
check). Entries tagged **[deferred]** aren't needed until the named first use —
report as `deferred`, never as failures.

**Base tier.** An entry may also carry `Base probe:` / `Base fix:` — exercised
only by `/afk:setup base` (the default branch runs `Probe:`/`Fix:` alone).
`Base probe:` tightens the health check to the monorepo's pinned toolchain
version; `Base fix:` names the concrete install the plain `human:` fix leaves to
the reader. Version pins are never restated here — probes read them from their
one home (`.sdkmanrc` for JDK/Maven; core-services root `CLAUDE.md` states the
Node 24 / npm 11 workspace standard). Under `base`, a version miss is
`missing/broken` even when the plain probe passes. Section **W** is base-only —
its entries have no plain `Probe:` and the default branch skips them.

**Secrets discipline.** Probes check *presence only*. Never print, log, or echo
a token value — not even partially.

## H — Harness

### H1 · plugin installed + enabled
- **Needed by:** everything (`/afk:*` skills, the Stop-hook gates).
- **Probe:** `grep -q 'afk@nak-marketplace' ~/.claude/settings.json`
- **Fix:** `human:` the bootstrap snippet in `README.md` §4 (marketplace add +
  install + `enabledPlugins`), then `/reload-plugins`.
- **Notes:** may instead be enabled at project scope (`.claude/settings.json` /
  `.claude/settings.local.json`) — a miss here + `/afk:*` skills visible
  in-session is still healthy. Directory-source installs are snapshotted: after
  any `git pull` touching the plugin, `/reload-plugins`.

### H2 · Jira MCP server
- **Needed by:** `skills/afk/to-ticket` (creds fallback reads its `env` block),
  `skills/afk/to-sdd` (pointer section), `skills/afk/fix`,
  `skills/utils/to-code-walkthrough` (spec discovery), the shared Jira lib
  `scripts/jira_core.py` and `skills/afk/bug/scripts/publish_bug.py` (same
  creds-fallback env block; ADR-0001).
- **Probe:** `agent:` a cheap `mcp__jira__jira_get` on a known key succeeds
  (or the `mcp__jira__*` tools are listed at all).
- **Fix:** `human:` add a `jira` server to `~/.claude.json` `mcpServers` with an
  `env` block carrying the S1 variables.
- **Notes:** host is Jira Cloud (`nakisa.atlassian.net`).

### H3 · lean-ctx MCP server *(optional)*
- **Needed by:** `ctx_read`/`ctx_search`/`ctx_tree` calls in
  `skills/afk/execute` (cited-mode grep checkpoints), `skills/afk/grill-solution`
  (grounding), `skills/afk/to-subtasks` (anchor validation), `skills/afk/claude-md`,
  `skills/afk/to-sdd`, `skills/afk/to-design-brief`, `skills/afk/grill-verification`.
- **Probe:** `agent:` `ctx_read` is callable.
- **Fix:** `human:` install lean-ctx per its own docs, or skip.
- **Notes:** native Read/Grep are functional equivalents — skills degrade
  gracefully; costs nothing when absent.

### H4 · Claude Design MCP *(optional)* **[deferred: first `/afk:prototype` or `/afk:design-system` push]**
- **Needed by:** `skills/afk/prototype/CLAUDE-DESIGN-PUSH.md`,
  `skills/afk/design-system/PUBLISH.md` (the opt-in share mirror only).
- **Probe:** `agent:` DesignSync tools (`list_projects`, `write_files`) listed.
- **Fix:** `human:` one-time `/design-login` in Claude Code.
- **Notes:** local-first skills — everything works without it except the push.

### H5 · branch-name git hook *(optional)*
- **Needed by:** branch-naming discipline for `/afk:execute`'s push — enforces
  `kapteyn/development/<username>/<slug>` on **agent** new-branch creation only
  (gate no-ops unless `CLAUDECODE` is set; human-driven creation is untouched).
  Workflow `CLAUDE.md` "Conventions to keep". Not required for any skill to *run*.
- **Probe:** `grep -q afk-branch-name-gate "$(git rev-parse --path-format=absolute --git-path hooks)/reference-transaction" 2>/dev/null`
- **Fix:** `auto:` `bash tools/payable/ai-agents/plugins/workflow/hooks/install-git-hooks.sh`
- **Notes:** normally auto-installs on `SessionStart` (`hooks/install-git-hooks.sh
  --quiet`, wired in `hooks.json`) whenever the plugin is enabled in a
  core-services checkout — this entry is the fallback for non-session / CI. One
  `reference-transaction` hook in the shared (common) hooks dir covers every
  worktree. Gates branch **creation** only — checkouts of existing/remote
  branches pass untouched.
  Bypass one command: `AFK_SKIP_BRANCH_CHECK=1`. Disable: `git config
  afk.branchNameGate false`. The installer refuses to clobber a pre-existing
  non-AFK hook of the same name.

### H6 · `.claude/afk.local.json` per-dev config
- **Needed by:** `skills/afk/bug` (dispatch/publish/Ready-flip gates — key set
  and fail-closed rules owned by `skills/afk/bug/CONFIG.md`).
- **Probe:**
  ```
  python3 -c "
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
  m = [k for k in ('jiraAssignee', 'mrReviewer', 'worktreeBasePath') if not d.get(k)]
  print(('missing: ' + ', '.join(m)) if m else 'ok')
  sys.exit(1 if m else 0)
  "
  ```
- **Fix:** `human:` create `.claude/afk.local.json` per the hypothetical
  example in `skills/afk/bug/CONFIG.md` (K1 `jiraAssignee`, K2 `mrReviewer`,
  K3 `worktreeBasePath`).
- **Notes:** gitignored, one file per checkout — key set + fail-closed matrix
  owned by `skills/afk/bug/CONFIG.md`; K4 `ideBinary` optional, not probed.

## C — Shell & core CLIs

### C1 · bash (Git Bash on Windows) + POSIX utils
- **Needed by:** the `hooks/*.sh` gate suite (the Stop hooks — wiring, Maven
  compile, UI lint, Java format — **fire every turn**; plus the on-demand
  `app-start-gate.sh`), `skills/utils/to-code-walkthrough/scripts/fetch-mr.sh`,
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

### C3 · glab (GitLab CLI), logged in — **secret**
- **Needed by:** `skills/afk/execute` (push + Draft MR),
  `skills/utils/to-code-walkthrough/scripts/fetch-mr.sh` (MR mode).
- **Probe:** `glab auth status` (exit 0 = logged in; prints no token).
- **Fix:** `human:` install glab, then `glab auth login --hostname <the GitLab
  host core-services pushes to>` — the token lives in glab's own store, never in
  this plugin.

### C4 · Maven wrapper + JDK
- **Needed by:** `skills/afk/execute` verification tiers, the smoke gate's
  compile row (`skills/afk/to-subtasks/SMOKE-GATE.md`), the liquibase pickup
  check (`skills/afk/to-subtasks`), and the Stop-hook gates
  `hooks/maven-compile-gate.sh` / `hooks/java-format-gate.sh` plus
  `hooks/app-start-gate.sh` (they no-op outside a core-services checkout).
- **Probe:** `./mvnw -v` (proves wrapper **and** a resolvable JDK).
- **Fix:** `human:` the wrapper ships with the core-services checkout (X1); JDK
  selection follows the core-services conventions (root `CLAUDE.md` there).
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
- **Needed by:** `hooks/mutation-probe.sh` (invoked by `skills/afk/review`'s
  test-veracity concern, sampled).
- **Probe:** `test -f tools/payable/ai-agents/plugins/workflow/hooks/mutation-probe.sh && ./mvnw -v >/dev/null`
- **Fix:** `human:` pitest itself resolves from Maven Central at run time
  (version pinned via `PITEST_VERSION`, default in the script) — but JUnit 5
  test discovery needs `org.pitest:pitest-junit5-plugin` on the pitest maven
  **plugin** classpath, which cannot be injected from the CLI: add the
  `<pluginManagement>` snippet from `hooks/mutation-probe.sh`'s header to the
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
- **Needed by:** envstack (X3 — `envctl` builds/runs the app env),
  `skills/afk/smoke-test` / `skills/afk/autopilot` / `skills/afk/adversary`
  (live-app verification, X5), `build-scripts/build-docker-compose.py`.
- **Probe:** `docker info >/dev/null && docker compose version >/dev/null`
  (proves the daemon is *running* and compose v2 is present — a stopped Docker
  Desktop fails this even when installed; start it and re-probe).
- **Fix:** `human:` install Docker Desktop (WSL2 backend) and start it.
- **Base fix:** `human:` `winget install --id Docker.DockerDesktop -e`, then
  raise the WSL2 memory ceiling in `~/.wslconfig` — the default cap wedges the
  engine under a full app env (all API calls 500); restart WSL after editing.

## P — Python

### P1 · Python 3
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`,
  `skills/afk/claude-md/scripts/*.py`, `tools/payable/envstack/envctl.py` (X3),
  the shared Jira lib `scripts/jira_core.py` and
  `skills/afk/bug/scripts/publish_bug.py` (ADR-0001).
- **Probe:** `python --version || python3 --version`
- **Fix:** `human:` install Python 3 and put it on PATH.
- **Base fix:** `auto:` `winget install --id Python.Python.3.12 -e` (any Python 3
  on PATH passes the probe — the pin here is just a working default).

### P2 · markdown-it-py (the only pip package)
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`
  (PRD / meeting body → ADF), the shared Jira lib `scripts/jira_core.py`
  (imported by both `publish_prd.py` and `skills/afk/bug/scripts/publish_bug.py`
  for the same Markdown→ADF conversion; ADR-0001).
- **Probe:** `python -c "import markdown_it"`
- **Fix:** `auto:` `pip install markdown-it-py`

## N — Node toolchain

### N1 · node + npm + npx
- **Needed by:** mermaid rendering (N2), the verification suites (N3), UI
  builds the chain may trigger, and `hooks/ui-lint-gate.sh` (resolves eslint
  via `npx --no-install`; silently allows when unresolvable).
- **Probe:** `node --version && npm --version`
- **Fix:** `human:` install Node 24 (the core-services npm-workspace standard).
- **Base probe:** `node --version | grep -q '^v24\.' && npm --version | grep -q '^11\.'`
  — the Node 24 / npm 11 workspace standard (core-services root `CLAUDE.md`).
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
- **Probe:** `test -d 11700-payable/verification/ui-e2e/node_modules || npx playwright --version`
- **Fix:** `human:` install per `11700-payable/verification/ui-e2e/README.md`
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
  the shared Jira lib `scripts/jira_core.py` and
  `skills/afk/bug/scripts/publish_bug.py` (same creds resolution; ADR-0001).
- **Probe:** presence-only, prints names not values; mirrors the engine's
  `load_creds` (OS env, else a recursive walk of `~/.claude.json` for a `jira`
  server's `env` block — top-level or project-scoped, utf-8; `load_creds`
  additionally falls back to `~/.codex/config.toml` `[mcp_servers.jira.env]`,
  not probed here — any one populated source passes S1 via the env-var leg or
  the Fix below):
  `python -c "import json,os,sys;w=lambda o:(o['jira']['env'] if isinstance(o,dict) and isinstance(o.get('jira'),dict) and isinstance(o['jira'].get('env'),dict) else next((r for r in (w(v) for v in (list(o.values()) if isinstance(o,dict) else o if isinstance(o,list) else [])) if r),None));p=os.path.expanduser('~/.claude.json');e=(w(json.load(open(p,encoding='utf-8'))) if os.path.exists(p) else None) or {};m=[k for k in ('JIRA_BASE_URL','JIRA_EMAIL','JIRA_API_TOKEN') if not (os.environ.get(k) or e.get(k))];print('missing: '+', '.join(m) if m else 'ok');sys.exit(1 if m else 0)"`
- **Fix:** `human:` create an API token (Atlassian account → Security → API
  tokens), then set `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` either as
  OS env vars or in `~/.claude.json` → `mcpServers.jira.env` (one home
  satisfies both this engine and H2). Codex-side users may instead keep them in
  `~/.codex/config.toml` `[mcp_servers.jira.env]` — `load_creds` reads all three
  (order: env → claude.json → codex toml; PROVIDERS.md).

### S2 · GitLab token — **secret**
- Held entirely by glab (C3). No plugin storage, nothing further to provision.

### S3 · verification-app auth token — **secret**
- Minted at runtime by `11700-payable/verification/core`; provisioning lives in
  that tree's docs, not here. Nothing to set up until N3's first use.

## X — Sibling state (assumed present, not shipped by this plugin)

### X1 · core-services checkout
- **Needed by:** everything — the chain's work target; the plugin ships inside it.
- **Probe:** `git rev-parse --is-inside-work-tree >/dev/null && test -f port-map.yaml`

### X2 · verification tree + authoring recipes
- **Needed by:** `skills/afk/grill-verification`, `skills/afk/to-verification-plan`,
  `skills/afk/to-subtasks` (build subtasks), `skills/afk/smoke-test`.
- **Probe:** `test -f 11700-payable/verification/ui-e2e/AUTHORING.md && test -f 11700-payable/verification/api/AUTHORING.md`
- **Fix:** `human:` pull a core-services revision that contains it.

### X3 · envstack **[deferred: first self-provisioned app env]**
- **Needed by:** `skills/afk/smoke-test` (env build/up/status + base-URL resolution).
- **Probe:** `test -f tools/payable/envstack/envctl.py`

### X4 · app-start gate hook
- **Needed by:** `skills/afk/autopilot` (self-provisioning),
  `skills/afk/execute` (app-dependent tiers), `skills/afk/to-subtasks/SMOKE-GATE.md`.
- **Probe:** `test -f tools/payable/ai-agents/plugins/workflow/hooks/app-start-gate.sh`
- **Fix:** `human:` pull a core-services revision that contains it — the gate
  suite ships in-plugin (tracked), so every checkout/worktree at such a
  revision has it.

### X5 · running app + DB/broker infra **[deferred: verification time]**
- No probe here — `/afk:autopilot` and `/afk:smoke-test` probe and self-provision
  at run time via X3/X4 (machine prerequisite: Docker, C7). Listed so the full
  runtime surface is in one register.

### X6 · JWT minter (live-app auth) **[deferred: first live-app probe]**
- **Needed by:** `skills/utils/diagnose` (mints the dev token for live-app probing).
- **Probe:** `test -f tools/nakisa-financial-suite/jwt/mint.mjs`
- **Notes:** run via `node tools/nakisa-financial-suite/jwt/mint.mjs` (or the
  sibling `mint-jwt.cmd`); ships with the core-services checkout (X1).

## W — Workstation apps & OS config (base-only)

Human tooling and machine settings, not skill dependencies — no skill invokes
these, so entries here carry **only** base-tier fields and the default branch
skips the section entirely. Probed and fixed under `/afk:setup base` alone; a
miss is `missing/broken` there, never on a default run.

### W1 · Visual Studio Code
- **Needed by:** the human (no skill invokes it).
- **Base probe:** `command -v code`
- **Base fix:** `auto:` `winget install --id Microsoft.VisualStudioCode -e`

### W2 · IntelliJ IDEA
- **Needed by:** the human; optionally referenced by `/afk:bug`'s `ideBinary`
  key (K4, `skills/afk/bug/CONFIG.md`) to open fixer worktrees.
- **Base probe:** `winget list --id JetBrains.IntelliJIDEA.Ultimate -e >/dev/null 2>&1 || winget list --id JetBrains.IntelliJIDEA.Community -e >/dev/null 2>&1`
- **Base fix:** `human:` `winget install --id JetBrains.IntelliJIDEA.Ultimate -e`
  (or via JetBrains Toolbox), then sign in with a license.

### W3 · MySQL Server (local)
- **Needed by:** the human — running services from the IDE against a local DB
  instead of the envstack containers (which ship their own MySQL, C7/X3).
- **Base probe:** `sc query type= service state= all | grep -qi "SERVICE_NAME: MySQL"`
  (a MySQL Windows service exists — running or not).
- **Base fix:** `human:` `winget install --id Oracle.MySQL -e`, then complete the
  installer's server configuration (root password stays with the human).
- **Notes:** not needed when all services run via envstack/docker-compose —
  skip freely; a skip is `ok`, not `needs-human`.

### W4 · MySQL Workbench
- **Needed by:** the human (DB inspection; no skill invokes it).
- **Base probe:** `winget list --id Oracle.MySQLWorkbench -e >/dev/null 2>&1`
- **Base fix:** `auto:` `winget install --id Oracle.MySQLWorkbench -e`

### W5 · Windows long paths enabled
- **Needed by:** deep monorepo paths — the npm-workspace `node_modules` and
  nested Maven modules blow past the 260-char MAX_PATH; checkouts and builds
  fail with path-too-long errors otherwise.
- **Base probe:** `reg query 'HKLM\SYSTEM\CurrentControlSet\Control\FileSystem' /v LongPathsEnabled 2>/dev/null | grep -q 0x1 && [ "$(git config --global --get core.longpaths)" = true ]`
  (both halves required — the OS flag and git's own limit).
- **Base fix:** `human:` from an **elevated** prompt:
  `reg add "HKLM\SYSTEM\CurrentControlSet\Control\FileSystem" /v LongPathsEnabled /t REG_DWORD /d 1 /f`,
  then (no elevation needed) `git config --global core.longpaths true`.
- **Notes:** registry half needs admin — the agent never elevates; re-probe
  after. New processes pick the flag up without a reboot.

## E — Env toggles (index only; no probes)

Each var is documented at its consumer — this table is just the map.

| Var | Consumer | Role |
|---|---|---|
| `CLAUDE_PLUGIN_ROOT` | `hooks/hooks.json` | set by the harness; locates the Stop hook |
| `CLAUDE_JOB_DIR` | `skills/utils/to-code-walkthrough` | working dir for MR fetch output |
| `APP_START_KEEP` / `APP_START_PORT` / `APP_START_SKIP_UI` | `skills/afk/autopilot` | app-start-gate provisioning mode |
| `WIRING_GATE_DISABLE` / `WIRING_FINAL` | `hooks/wiring-gate.sh` | disable / final-mode the wiring gate |
| `GATE_METRICS_DISABLE` / `GATE_METRICS_FILE` | `hooks/gate-metrics.sh` | silence / relocate gate-latency emission |
| `PITEST_VERSION` / `MUTATION_TIMEOUT` | `hooks/mutation-probe.sh` | pitest version pin / probe timebox |

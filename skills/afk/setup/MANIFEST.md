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
only by `/afk-toolkit:setup base` (the default branch runs `Probe:`/`Fix:` alone).
`Base probe:` tightens the health check to the monorepo's pinned toolchain
version; `Base fix:` names the concrete install the plain `human:` fix leaves to
the reader. Version pins are never restated here — probes read them from their
one home (`.sdkmanrc` for JDK/Maven; core-services root `CLAUDE.md` states the
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

### H2 · Jira MCP server
- **Needed by:** `skills/afk/to-ticket` (creds fallback reads its `env` block),
  `skills/afk/to-sdd` (pointer section), `skills/afk/fix`,
  `skills/afk/understand` (MR-subject spec discovery), the shared Jira lib
  `scripts/jira_core.py` and `skills/afk/bug/scripts/publish_bug.py` (same
  creds-fallback env block; ADR-0001).
- **Probe:** `agent:` the plugin Jira server lists `jira_get`; a cheap call on a
  known key succeeds.
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` (also
  does S1/H6/C3), enable the plugin, then restart the session. Python deps: P3.
- **Notes:** host is Jira Cloud (`nakisa.atlassian.net`). Server source ships
  in this plugin at `mcp-servers/jira/server.py`; `.mcp.json` is the shared
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
  `kapteyn/development/<username>/<slug>` on **agent** new-branch creation only;
  human-driven creation is untouched.
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
  m = [k for k in ('jiraAssignee', 'mrReviewer', 'worktreeBasePath') if not d.get(k)]
  print(('missing: ' + ', '.join(m)) if m else 'ok')
  sys.exit(1 if m else 0)
  "
  ```
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` (also
  does H2/S1/C3; pre-fills K1 from the validated token's own account). By hand:
  create `.claude/afk.local.json` per the hypothetical example in
  `skills/afk/bug/CONFIG.md` (K1 `jiraAssignee`, K2 `mrReviewer`,
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
  src=tools/payable/ai-agents/plugins/workflow/skills/afk/setup/PLAIN-LANGUAGE.md
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
  src=tools/payable/ai-agents/plugins/workflow/skills/afk/setup/LAVISH-SESSIONS.md
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

## C — Shell & core CLIs

### C1 · bash (Git Bash on Windows) + POSIX utils
- **Needed by:** the `hooks/*.sh` gate suite (the Stop gates — wiring,
  genericity, skill-registry, native-contract via `stop-gates.sh` — **fire every
  turn**; the commit gates — Maven compile, Java format, UI lint via
  `precommit-gates.sh` — fire on agent-driven commits; plus the on-demand
  `app-start-gate.sh`), `skills/afk/understand/scripts/fetch-mr.sh`,
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
  `skills/afk/understand/scripts/fetch-mr.sh` (MR subjects).
- **Probe:** `glab auth status` (exit 0 = logged in; prints no token).
- **Fix:** `human:` install glab, then `glab auth login --hostname <the GitLab
  host core-services pushes to>` — the token lives in glab's own store, never in
  this plugin. `skills/afk/setup/scripts/setup_secrets.py` drives that login as
  one of its steps (it shells out to `glab`; the token still never touches this
  plugin).

### C4 · Maven wrapper + JDK
- **Needed by:** `skills/afk/execute` verification tiers, the smoke gate's
  compile row (`skills/afk/to-subtasks/SMOKE-GATE.md`), the liquibase pickup
  check (`skills/afk/to-subtasks`), and the commit gates
  `hooks/maven-compile-gate.sh` / `hooks/java-format-gate.sh` (dispatched by
  `precommit-gates.sh` on agent-driven commits) plus
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
- **Probe:** `command -v robocopy`
- **Fix:** none needed on Windows (ships with the OS); no fix elsewhere — the script
  falls back to `cp -a`.
- **Notes:** fail-open — robocopy absent or the seed copy failing downgrades to the
  `cp -a` fallback / an unseeded private repo with a warning; the isolation itself
  (`.mvn/maven.config` → `<worktree>/.m2/repository`) is written regardless, so
  concurrent worktree builds never share a writable local repo.

### P1 · Python 3
- **Needed by:** `hooks/run-hook.py` — the launcher every registered hook command
  runs through, so without it no gate or guard fires at all — the shared
  `.mcp.json` bootstrap,
  `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`,
  `skills/afk/claude-md/scripts/*.py`, `tools/payable/envstack/envctl.py` (X3),
  the shared Jira lib `scripts/jira_core.py` and
  `skills/afk/bug/scripts/publish_bug.py` (ADR-0001).
- **Probe:** `python --version || python3 --version`
- **Fix:** `human:` install Python 3 and put it on PATH.
- **Base fix:** `auto:` `winget install --id Python.Python.3.12 -e` (any Python 3
  on PATH passes the probe — the pin here is just a working default).

### P2 · markdown-it-py
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`
  (PRD / meeting body → ADF), the shared Jira lib `scripts/jira_core.py`
  (imported by both `publish_prd.py` and `skills/afk/bug/scripts/publish_bug.py`
  for the same Markdown→ADF conversion; ADR-0001).
- **Probe:** `python -c "import markdown_it"`
- **Fix:** `auto:` `pip install markdown-it-py`

### P3 · mcp + httpx (Jira MCP server runtime)
- **Needed by:** `mcp-servers/jira/server.py` (H2) — FastMCP host + HTTP client.
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
- **Probe:** presence-only through the shared resolver; prints no values:
  `python -c "import sys;sys.path.insert(0,'tools/payable/ai-agents/plugins/workflow/scripts');from jira_core import load_creds;load_creds();print('ok')"`
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` — it
  prompts for the token without echoing it, validates it against the host before
  writing, and places it in the H2 `env` block (also does H2/H6/C3). By hand:
  create an API token (Atlassian account → Security → API tokens), then set
  `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` through a source listed in
  `PROVIDERS.md`.

### S2 · GitLab token — **secret**
- Held entirely by glab (C3). No plugin storage, nothing further to provision.

### S3 · verification-app auth token — **secret**
- Minted at runtime by `11700-payable/verification/core`; provisioning lives in
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
  `~/.codex/agents/` with the same filename, and its `{{PLUGIN_ROOT}}` placeholder is
  replaced by the installed plugin root that Codex plugin metadata reports.
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
- **Probe:** `agent:` a new session lists exactly 40 `afk:<name>` plugin skills,
  no `afk-<name>` mirror, all three agent roles, and a callable `jira_get`.
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
- No probe here — `/afk-toolkit:autopilot` and `/afk-toolkit:smoke-test` probe and self-provision
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
  deselect freely at the election; a skip is `skipped (user choice)`, never
  `needs-human`.

### W4 · MySQL Workbench
- **Needed by:** the human (DB inspection; no skill invokes it).
- **Base probe:** `winget list --id Oracle.MySQLWorkbench -e >/dev/null 2>&1`
- **Base fix:** `auto:` `winget install --id Oracle.MySQLWorkbench -e`

### W5 · Windows long paths enabled
- **Needed by:** deep monorepo paths — the npm-workspace `node_modules` and
  nested Maven modules blow past the 260-char MAX_PATH; checkouts and builds
  fail with path-too-long errors otherwise.
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

### W6 · hosts entry `127.0.0.1 proxy`
- **Needed by:** local builds and any URL using the `proxy` hostname — it must
  resolve to the local machine or those URLs fail DNS.
- **Base probe:** `grep -qE '^[[:space:]]*127\.0\.0\.1[[:space:]]+([^#]*[[:space:]])?proxy([[:space:]]|$)' /c/Windows/System32/drivers/etc/hosts`
- **Base fix:** `human:` from an **elevated** prompt:
  `Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "127.0.0.1 proxy"`
  (PowerShell), then re-probe.
- **Notes:** new processes pick the entry up immediately; a stale resolution
  clears with `ipconfig /flushdns`.

### W7 · IntelliJ IDEA max heap ≥ 16384 MB
- **Needed by:** the human — indexing the ~50-module monorepo plus a Maven
  reimport blows past the stock 2 GB heap; the IDE thrashes or dies mid-import.
- **Base probe:** every installed IDE config dir carries an explicit `-Xmx`
  ≥ the target (default 16384 MB; the human may pick another value at the
  election — probe against what they picked):
  ```sh
  XMX_TARGET=${XMX_TARGET:-16384}
  python - "$XMX_TARGET" <<'PY'
  import glob, os, re, sys
  target = int(sys.argv[1])
  dirs = glob.glob(os.path.join(os.environ["APPDATA"], "JetBrains", "IntelliJIdea*"))
  if not dirs:
      print("no IntelliJ config dir (W2 first)"); sys.exit(1)
  bad = []
  for d in dirs:
      f = os.path.join(d, "idea64.exe.vmoptions")
      m = re.search(r"^-Xmx(\d+)([mMgG])", open(f, encoding="utf-8-sig").read(), re.M) if os.path.exists(f) else None
      mb = (int(m.group(1)) * (1024 if m.group(2) in "gG" else 1)) if m else 0
      if mb < target: bad.append(f"{os.path.basename(d)}={mb or 'unset'}")
  print("below target: " + ", ".join(bad) if bad else "ok"); sys.exit(1 if bad else 0)
  PY
  ```
- **Base fix:** `auto:` ask the human for the value (default **16384**, offer it
  as the pick), then for each config dir the probe named, upsert a single
  `-Xmx{value}m` line in `%APPDATA%\JetBrains\IntelliJIdea*\idea64.exe.vmoptions`
  — replace an existing `-Xmx` line in place, append when absent, leave every
  other option untouched; create the file if missing.
- **Notes:** takes effect on IDE restart. Config dir is per-IDE-version — a
  version upgrade starts from stock unless the settings import carried it, so a
  re-probe after upgrading is expected to flag the new dir. This is the IDE's
  own heap (Help → Change Memory Settings), not the compiler build-process heap
  (a per-project setting the human sets in Build Tools → Compiler).

## E — Env toggles (index only; no probes)

Each var is documented at its consumer — this table is just the map.

| Var | Consumer | Role |
|---|---|---|
| `CLAUDE_PLUGIN_ROOT` | `hooks/hooks.json`, `hooks/lib/providers/claude.sh` | compatibility root set by supported plugin hooks |
| `CLAUDE_PROJECT_DIR` | `hooks/run-hook.py` | optional fast project root, read with the `${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}` fallback |
| `AFK_BASH` / `GIT_BASH` | `hooks/run-hook.py` | POSIX shell the hook launcher runs handlers with, ahead of its own lookup |
| `APP_START_KEEP` / `APP_START_PORT` / `APP_START_SKIP_UI` / `APP_START_REUSE` | `skills/afk/autopilot` | app-start-gate provisioning mode |
| `APP_START_TIMEOUT` | `hooks/app-start-gate.sh` | boot timebox (seconds, default 300) |
| `CI_PROJECT_DIR` | `hooks/app-start-gate.sh` | checkout the service's `build_ui.sh` resolves its npm workspace from; read only when `APP_START_SKIP_UI=false`, defaults to the repo root |
| `AFK_DRIVEN` | `skills/afk/gc/scripts/gc-check.sh` | exported `=1` by hands-off invokers; makes `/afk-toolkit:gc` refuse deletion — it always gets a human eye |
| `WIRING_GATE_DISABLE` / `WIRING_FINAL` | `hooks/wiring-gate.sh` | disable / final-mode the wiring gate |
| `SKILL_REGISTRY_GATE_DISABLE` | `hooks/skill-registry-gate.sh` | disable the registry gate (plugin.json membership + skill catalog + env-toggle register) |
| `GENERICITY_GATE_DISABLE` | `hooks/genericity-gate.sh` | disable the genericity gate |
| `NATIVE_CONTRACT_GATE_DISABLE` | `hooks/native-contract-gate.sh` | bypass the native plugin contract gate |
| `AFK_PROVIDER` | `hooks/lib/provider.sh` | force provider detection before adapter probes |
| `PLUGIN_ROOT` / `PLUGIN_DATA` | `hooks/lib/providers/codex.sh` | native plugin root and data paths; root detection precedes inherited compatibility markers |
| `CLAUDE_PLUGIN_DATA` | `hooks/lib/providers/claude.sh` | compatibility plugin data path |
| `GATE_CACHE_DISABLE` | `hooks/gate-cache.sh` | bypass the Stop gates' pass cache — every run does real work |
| `AFK_CFG_GIT_BASE_BRANCH` | `hooks/gate-context.sh` | integration base exported by `hooks/lib/config.sh` from `git.base-branch`; unset or `auto` falls back to `origin/main`, `origin/master`, `@{u}`, HEAD |
| `AFK_GATE_CTX_DISABLE` | `hooks/gate-context.sh` | rebuild the shared per-Stop change-set context on every call instead of reusing it (debug) |
| `AFK_SKIP_PRECOMMIT_GATES` | `hooks/precommit-gates.sh` | skip the commit-time code gates (maven-compile, java-format, ui-lint) for one commit |
| `GATE_METRICS_DISABLE` / `GATE_METRICS_FILE` | `hooks/gate-metrics.sh` | silence / relocate gate-latency emission |
| `MAVEN_LOCK_DIR` | `hooks/maven-lock.sh` | relocate the cross-gate maven lock dir |
| `AFK_MAVEN_LOCK_WAIT` | `hooks/maven-compile-gate.sh` | seconds the compile gate waits for the maven lock before allowing (240 on the commit path, 900 standalone) |
| `PITEST_VERSION` / `MUTATION_TIMEOUT` | `hooks/mutation-probe.sh` | pitest version pin / probe timebox |
| `AFK_SKIP_BRANCH_CHECK` | `hooks/branch-name-gate.sh` | bypass the branch-name gate for one agent command |
| `CROWDSTRIKE_GUARD_OFF` | `harness/hooks/crowdstrike-guard.sh` (adopted gate — wired in this plugin's `hooks.json`) | debug bypass of the system-root scan guard |
| `LESSON_LEDGER_DISABLE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | disable lesson-ledger writes/reads (kill switch) |
| `LESSON_LEDGER_FILE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | relocate the lesson ledger (default: main-checkout `.claude/lessons/LEDGER.jsonl`) |

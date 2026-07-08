# MANIFEST.md — the external-dependency register

One entry per external dependency of the workflow — CLIs, MCP servers, secrets,
sibling checkouts, env toggles. This file is the **one home** for that fact set:
skills point at an entry id (e.g. `MANIFEST.md · N2`) instead of restating
install steps; the same-commit rule that keeps it true lives in `FRESHNESS.md`
(plugin root).

**Entry fields.** `Needed by` — which skills/scripts hit the dep · `Probe` —
exit 0 = healthy · `Fix` — `auto:` the agent runs it; `human:` the agent guides,
never runs · `Notes`. Probes are POSIX-shell commands run from the
**core-services repo root** (any worktree) unless prefixed `agent:` (an
in-session check). Entries tagged **[deferred]** aren't needed until the named
first use — report them as `deferred`, never as failures.

**Secrets discipline.** Probes check *presence only*. Never print, log, or echo
a token value — not even partially.

## H — Harness

### H1 · plugin installed + enabled
- **Needed by:** everything (`/afk:*` skills, the Stop-hook gates).
- **Probe:** `grep -q 'afk@nak-marketplace' ~/.claude/settings.json`
- **Fix:** `human:` the bootstrap snippet in `README.md` §4 (marketplace add +
  install + `enabledPlugins`), then `/reload-plugins`.
- **Notes:** may instead be enabled at project scope (`.claude/settings.json` /
  `.claude/settings.local.json` in the repo) — a miss here + `/afk:*` skills
  visible in-session is still healthy. Directory-source installs are
  snapshotted: after any `git pull` that touched the plugin, `/reload-plugins`.

### H2 · Jira MCP server
- **Needed by:** `skills/afk/to-ticket` (creds fallback reads its `env` block),
  `skills/afk/to-sdd` (pointer section), `skills/afk/fix`,
  `skills/utils/to-code-walkthrough` (spec discovery).
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
  gracefully; this dep costs nothing when absent.

### H4 · Claude Design MCP *(optional)* **[deferred: first `/afk:prototype` or `/afk:design-system` push]**
- **Needed by:** `skills/afk/prototype/CLAUDE-DESIGN-PUSH.md`,
  `skills/afk/design-system/PUBLISH.md` (the opt-in share mirror only).
- **Probe:** `agent:` DesignSync tools (`list_projects`, `write_files`) listed.
- **Fix:** `human:` one-time `/design-login` in Claude Code.
- **Notes:** local-first skills — everything works without it except the push.

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
- **Needed by:** the whole chain (worktrees, branches, push), `hooks/wiring-gate.sh`,
  `skills/afk/claude-md/scripts/fanout-shell.py` (`git worktree list`).
- **Probe:** `git --version`
- **Fix:** `human:` install Git for Windows (also satisfies C1).

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

## P — Python

### P1 · Python 3
- **Needed by:** `skills/afk/to-ticket/scripts/publish_prd.py`,
  `skills/afk/claude-md/scripts/*.py`, `tools/payable/envstack/envctl.py` (X3).
- **Probe:** `python --version || python3 --version`
- **Fix:** `human:` install Python 3 and put it on PATH.

### P2 · markdown-it-py (the only pip package)
- **Needed by:** `skills/afk/to-ticket/scripts/publish_prd.py` (PRD → ADF).
- **Probe:** `python -c "import markdown_it"`
- **Fix:** `auto:` `pip install markdown-it-py`

## N — Node toolchain

### N1 · node + npm + npx
- **Needed by:** mermaid rendering (N2), the verification suites (N3), UI
  builds the chain may trigger, and `hooks/ui-lint-gate.sh` (resolves eslint
  via `npx --no-install`; silently allows when unresolvable).
- **Probe:** `node --version && npm --version`
- **Fix:** `human:` install Node 24 (the core-services npm-workspace standard).

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
- **Needed by:** `skills/afk/to-ticket/scripts/publish_prd.py` (attachment
  upload has no MCP tool, so it calls the REST API directly).
- **Probe:** presence-only, prints names not values; mirrors the engine's
  `load_creds` (OS env, else a recursive walk of `~/.claude.json` for a `jira`
  server's `env` block — top-level or project-scoped, utf-8):
  `python -c "import json,os,sys;w=lambda o:(o['jira']['env'] if isinstance(o,dict) and isinstance(o.get('jira'),dict) and isinstance(o['jira'].get('env'),dict) else next((r for r in (w(v) for v in (list(o.values()) if isinstance(o,dict) else o if isinstance(o,list) else [])) if r),None));p=os.path.expanduser('~/.claude.json');e=(w(json.load(open(p,encoding='utf-8'))) if os.path.exists(p) else None) or {};m=[k for k in ('JIRA_BASE_URL','JIRA_EMAIL','JIRA_API_TOKEN') if not (os.environ.get(k) or e.get(k))];print('missing: '+', '.join(m) if m else 'ok');sys.exit(1 if m else 0)"`
- **Fix:** `human:` create an API token (Atlassian account → Security → API
  tokens), then set `JIRA_BASE_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` either as
  OS env vars or in `~/.claude.json` → `mcpServers.jira.env` (one home
  satisfies both this engine and H2).

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
  at run time via X3/X4. Listed so the full runtime surface is in one register.

### X6 · JWT minter (live-app auth) **[deferred: first live-app probe]**
- **Needed by:** `skills/utils/diagnose` (mints the dev token for live-app probing).
- **Probe:** `test -f tools/nakisa-financial-suite/jwt/mint.mjs`
- **Notes:** run via `node tools/nakisa-financial-suite/jwt/mint.mjs` (or the
  sibling `mint-jwt.cmd`); ships with the core-services checkout (X1).

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

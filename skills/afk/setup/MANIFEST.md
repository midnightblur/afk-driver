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
only by `/afk:setup base` (the default branch runs `Probe:`/`Fix:` alone).
`Base probe:` tightens the health check to the monorepo's pinned toolchain
version; `Base fix:` names the concrete install the plain `human:` fix leaves to
the reader. Version pins are never restated here — probes read them from their
one home (`.sdkmanrc` for JDK/Maven; the repository's root `AGENTS.md` states the
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

### H0 · repository configuration (`.afk/config.yaml`)
- **Needed by:** every skill that reads the configuration, and the legs that
  read the resolved `tracker` or `forge`: `H2`, `H6` (K1, K2), `O7`'s
  `tracker_get`, `C3`, and `C3b`'s forge leg.
- **Probe:** `test -f "$(git rev-parse --show-toplevel)/.afk/config.yaml"`
- **Fix:** `human:` `/afk:setup` step 0 (`init`, walk the `TODO`s, commit).
- **Notes:** the defaults answer `none` for a repository that never chose. A
  leg above whose resolved `tracker` or `forge` is `none` is n/a only when a
  configuration file at any layer says `none`; with no such line it is
  `needs-human: see H0`. File absent: `/afk:setup` step 0 settles it. File
  present with the key left unset (a commented `TODO`, or never named): step 0
  is skipped, so set `tracker:` and `forge:` in `.afk/config.yaml` (a value, or
  `none`; values in `CONFIG.md`), then re-probe. A resolved non-`none` value is
  a choice and probes normally, whichever layer supplied it (machine file,
  local overlay, `$AFK_CONFIG`); `H0` itself still fails until the repository
  file exists. Every other leg (the `O7` catalog, `H6` K3) keeps its own probe.

### H1 · plugin installed + enabled
- **Needed by:** everything (`/afk:*` skills, the Stop-hook gates).
- **Probe:** `agent:` the active harness reports `afk@afk-toolkit` enabled
  and lists `/afk:setup`.
- **Fix:** `human:` use the active-harness bootstrap in `README.md` §4, then
  refresh the plugin per `PROVIDERS.md`.

### H2 · Jira MCP server *(only when the resolved `tracker` is not `none`)*
- **Needed by:** `skills/afk/to-ticket` (creds fallback reads its `env` block),
  `skills/afk/to-sdd` (pointer section), `skills/afk/fix`,
  `skills/afk/understand` (MR-subject spec discovery), the shared Jira lib
  `adapters/tracker/jira/api.py` and `skills/afk/bug/scripts/publish_bug.py` (same
  creds-fallback env block; ADR-0001).
- **Probe:** `agent:` the plugin Jira server lists `tracker_get`; a cheap call on a
  known key succeeds. Decide from the server's answer, not from
  `scripts/afk-config.py get tracker`: `unsupported` naming `tracker: none`
  makes this row **n/a**, not a failure, as `H0` defines; with no
  `.afk/config.yaml` at `config_root`, the row reads `needs-human: see H0`.
  That answer is the adapter contract working, and `O7`'s `tracker_get` leg
  follows the same rule. An `unsupported` or `error` answer carries
  `config_root`, the checkout whose config the server read.
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` (also
  does S1/C3 or C3b, whichever the forge selects), enable the plugin, then
  restart the session. Python deps: P2. Registering the server needs that
  restart. The plugin's own server applies added or corrected credentials on the
  next call, no restart; without them a call answers `error: true` and the
  server stays up. The user-scoped `tracker` entry holds them in its `env`, so
  it takes a change only after a restart. The registration passes this plugin
  root; after a plugin update the launcher moves to the new install once the
  harness marks the old copy orphaned. Re-run setup if the old copy is not
  marked, or after moving a checkout.
  `setup_secrets.py` leaves a `jira` server entry alone unless its args point
  under this plugin root, into an `afk` plugin cache, or at the launcher; it
  then warns that a `jira` server remains.
- **Notes:** the host is whatever `tracker` selects and its credentials name. Server source ships
  in this plugin at `mcp-servers/tracker/server.py`; `.mcp.json` is the shared
  registration. Tool prefixes vary by harness, so skills use bare tool names.
  The server reads `tracker` from the project root
  (`${CLAUDE_PROJECT_DIR:-<git root of the working directory>}`) on every call: creating or changing
  `.afk/config.yaml` needs no restart; **Fix** says when registering the server or
  changing a credential does. The server reads the checkout the session was launched in; to
  probe another worktree's config, launch the session there.

### H4 · design-push service *(optional)* **[deferred: first `/afk:prototype` or `/afk:design-system` push]**
- **Needed by:** `skills/afk/prototype/CLAUDE-DESIGN-PUSH.md`,
  `skills/afk/design-system/PUBLISH.md` (the opt-in share mirror only).
- **Probe:** `agent:` DesignSync tools (`list_projects`, `write_files`) listed.
- **Fix:** `human:` use the active harness's login flow when
  `CAPABILITIES.md` marks `design_push` supported; otherwise skip.
- **Notes:** local-first skills — everything works without the optional push.

### H5 · branch-name git hook *(optional)*
- **Needed by:** branch-naming discipline for `/afk:execute`'s push — enforces
  the repository's `git.branch-pattern` on **agent** new-branch creation only;
  human-driven creation is untouched.
  Workflow `AGENTS.md` "Conventions to keep". Not required for any skill to *run*.
- **Probe:** `grep -q afk-branch-name-gate "$(git rev-parse --path-format=absolute --git-path hooks)/reference-transaction" 2>/dev/null`
- **Fix:** `auto:` `bash "$AFK_PLUGIN_ROOT/hooks/install-git-hooks.sh"`
- **Notes:** normally auto-installs on `SessionStart` (`hooks/install-git-hooks.sh
  --quiet`, wired in `hooks.json`) whenever the plugin is enabled in a
  checkout — this entry is the fallback for non-session / CI. One
  `reference-transaction` hook and one `pre-commit` hook in the shared (common)
  hooks dir cover every worktree; the same pair runs the protected-branch
  backstop, for every repository, not only one with `git.branch-pattern`. Gates branch **creation** only — checkouts of existing/remote
  branches pass untouched.
  Bypass one command: `AFK_SKIP_BRANCH_CHECK=1`. Disable: `git config
  afk.branchNameGate false`. The installer refuses to clobber a pre-existing
  non-AFK hook of the same name.

### H6 · per-developer values (`developer:`)
- **Needed by:** `skills/afk/bug` (dispatch/publish/Ready-flip gates — key set
  and fail-closed rules owned by `skills/afk/bug/CONFIG.md`).
- **Probe:** (interpreter resolution mirrors P2 — on Windows `python3` is often
  a Store stub that exits 49 while real `python` works). Ask `afk-config.py
  resolve`, never `get` and never a file: `resolve` applies the whole chain —
  the developer's own value from any layer, then the derived worktree base — so
  the probe cannot disagree with the pipeline it gates. `trackerAssignee` and
  `mrReviewer` name a person, so nothing resolves them but the developer's own
  answer: unresolved is a FAILURE, not an n/a. Each is asked for only where its
  adapter has the concept, so the selected kind decides which keys are probed.
  ```
  git rev-parse --git-dir >/dev/null 2>&1 \
    || { echo "skipped (no repository)"; exit 0; }
  PY="$(command -v python || command -v python3)"
  AC="$AFK_PLUGIN_ROOT/scripts/afk-config.py"
  R="$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
  C="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
  says_none() { for f in "$AFK_CONFIG" "$HOME/.afk/config.yaml" \
      "$R/.afk/config.local.yaml" "${C:+$C/afk/config.yaml}" \
      "$R/.afk/config.yaml"; do
    [ -n "$f" ] || continue
    grep -qsE "^$1:[[:space:]]*[\"']?none[\"']?([[:space:]#]|$)" "$f" \
      && return 0
  done; return 1; }
  keys="worktreeBasePath"; h=""
  if [ "$("$PY" "$AC" get tracker)" != none ]; then
    keys="trackerAssignee $keys"
  elif ! says_none tracker; then
    h="$h trackerAssignee"
  fi
  if [ "$("$PY" "$AC" get forge)" != none ]; then
    keys="$keys mrReviewer"
  elif ! says_none forge; then
    h="$h mrReviewer"
  fi
  m=""
  for k in $keys; do
    "$PY" "$AC" resolve "$k" >/dev/null 2>&1 || m="$m $k"
  done
  DV="$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/developer_values.py"
  i="$("$PY" "$DV" status 2>/dev/null | "$PY" -c \
      'import json,sys; print(" ".join(json.load(sys.stdin)["inherited"]))' \
      2>/dev/null)"
  [ -z "$h$m$i" ] && { echo ok; exit 0; }
  echo "resolved: tracker=$("$PY" "$AC" get tracker)" \
       "forge=$("$PY" "$AC" get forge)"
  [ -z "$h" ] || echo "needs-human: see H0 (${h# })"
  [ -z "$m" ] || echo "unresolved:$m"
  [ -z "$i" ] || echo "inherited from the machine file, confirm: $i"
  exit 1
  ```
- **Fix:** `auto:` in session, from anywhere: a main checkout, a worktree, or
  no repository. None of these values is a secret, so ask the human in the
  conversation. `DV="$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/developer_values.py"`.
  0. Ask the human for the main checkout paths to set up, offering this
     repository's `main_checkout` (from `status`) when there is one. Zero
     paths is a valid answer: H6 reports `skipped (user choice)` and the
     human can run `/afk:setup` again later. Run steps 1-4 once per path,
     adding `--repo <path>` to `status` and `set`, and ask step 3 once for
     the whole run. A path `status` refuses, or reports `configured: false`,
     is skipped and named in the summary: run `/afk:setup` in it first.
  1. Run `python "$DV" status --repo <path>`.
     It reports each key's `need`, resolved `value`, `source` layer and
     `suggestion`, and lists `missing` and `inherited`.
  2. Ask the human for every `missing` key, offering its `suggestion` as the
     first option. Offer the optional keys too, unless they already resolve.
     The reviewer has no suggestion: nobody else picks who reviews the
     developer's work. For every `inherited` key, show the machine value and
     ask whether it holds for this repository, then record the answer for this
     repository — a confirmed value too, so the probe stops asking. A machine
     `worktreeBasePath` also shows its `derived` value; offer to drop it from
     the machine file with `worktreeBasePath= --machine`.
  3. Ask once where the answers go: this repository (the default — the file
     the main checkout and all its worktrees read) or `--machine` (the default
     for every repository).
  4. Run `python "$DV" set KEY=VALUE ... [--machine] --repo <path>`, then
     re-run `status --repo <path>` to confirm each answer resolves.
  `set` changes only the keys it names, so another repository's values
  survive. `KEY=` removes a key. `--machine` refuses a `worktreeBasePath`
  value and accepts only its removal.
- **Notes:** a developer with no reviewer answers the literal `none`, which
  resolves and so satisfies this row; every consumer reads it as an absent key
  and fails closed. A recorded `mrAssignee=none` resolves to no assignee and
  overrides a broader layer's assignee. The repository's committed config answers none of these — a
  committed file never names a person. Under tracker `none` nothing is assigned
  and K1 is not probed; under forge `none` nothing is reviewed and K2 is not
  probed; each is then **n/a**, as `H0` defines. `worktreeBasePath` normally
  resolves without anyone setting it (it derives beside the main checkout), so an unresolved K3
  means git could not answer — a bare clone. K4 `ideBinary` and K5 `mrAssignee`
  are optional and not probed — an unset `mrAssignee` means no assignee, never a
  failure.

### H7 · managed agent behavior **[opt-in]**
- **Needed by:** users who want the managed behavior in `BEHAVIORS.md` available
  in every supported harness.
- **Probe:** run the managed behavior audit from `AUDIT.md` check 7. With no
  unified or legacy sentinel in either target, classify this row as
  `opt-in available`. Any sentinel proves prior consent; a failed audit then
  classifies as `missing/broken`, so refresh or migration runs automatically.
- **Fix:** `auto:` generate one block per target, each rendered against *that
  target's own verified* provider root — never this session's own root reused
  for the other harness's target. Root resolution is the provider adapter's
  job — `hooks/lib/provider.sh`'s `afk_all_provider_targets` (backed by each
  provider's own `hooks/lib/providers/<name>.sh` adapter and the per-provider
  resolver beside it, the one home for each provider's algorithm) — this
  recipe never re-implements it, and target/root pass as separate arguments,
  never colon-joined (a Windows root starts with a drive letter's own colon).
  The installer removes every duplicate unified block and
  every H7, H8, and H10 legacy block while preserving all other bytes:
  ```sh
  py=python
  command -v python >/dev/null 2>&1 || py=python3
  rendered=$(mktemp "${TMPDIR:-/tmp}/afk-behaviors.XXXXXX") || exit 1
  trap 'rm -f "$rendered"' EXIT INT TERM

  . "$AFK_PLUGIN_ROOT/hooks/lib/provider.sh"

  active=$(afk_provider)
  active_resolved=0
  while IFS= read -r -d '' name && IFS= read -r -d '' target \
    && IFS= read -r -d '' root && IFS= read -r -d '' enablement; do
    [ "$name" = "$active" ] && [ -n "$root" ] && active_resolved=1
    [ -n "$root" ] || continue
    [ "$enablement" = "enabled" ] || continue
    "$py" "$AFK_PLUGIN_ROOT/scripts/behavior_registry.py" render \
      --registry "$AFK_PLUGIN_ROOT/BEHAVIORS.md" \
      --plugin-root "$root" --output "$rendered" || exit 1
    "$py" "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/install_block.py" \
      install "$rendered" "$target" || exit 1
  done < <(afk_all_provider_targets)

  if [ "$active" != unknown ] && [ "$active_resolved" -ne 1 ]; then
    echo "afk: this session's own provider ($active) could not resolve its installed root; managed behavior was not installed for it. See AUDIT.md check 7's unresolved-target note for likely causes." >&2
    exit 1
  fi
  ```
- **Notes:** ask before a first install. Do not ask again when either target
  carries `afk:behaviors`, `plain-language`, `lavish-sessions`, or
  `investigation`. When the OTHER harness's own root cannot be independently
  verified (its CLI is absent or not yet configured), `afk_all_provider_targets`
  reports an empty root for it and this recipe skips writing it — never a
  guessed root; that target self-heals the next time the other harness runs
  its own `/afk:setup`. A provider whose plugin is disabled is skipped the
  same way even when its root DOES resolve — `afk_all_provider_targets`
  reports its enablement alongside the root, and installing for a disabled
  provider would create a block nobody can see or act on until it is
  re-enabled. When it is instead THIS session's own active provider whose
  root cannot resolve, that is a failure to report, not a silent skip — the
  recipe above exits 1 rather than completing as if nothing were wrong. A
  frequent cause on a not-yet-released plugin build: the resolved root exists
  but has no `BEHAVIORS.md` (the installed plugin predates this feature) —
  `unresolved: installed plugin has no BEHAVIORS.md (update the plugin)`.
  Re-run setup to refresh a stale revision or hash. Run `/afk:setup teardown`
  before plugin disable; it calls `install_block.py teardown` for both
  targets. Setup reports likely duplicate behavior outside managed sentinels
  and leaves that text unchanged. The SessionStart drift notice
  (`hooks/behavior-drift.sh`) checks only the current session's own target
  and root through the same adapter — never the other harness's file.

### H9 · Notion MCP server *(only when `notes: notion`)*
- **Needed by:** `adapters/notes/notion` — every notes verb mirrors its local
  copy to a Notion page through this server's tools.
- **Probe:** `agent:` a Notion MCP tool is listed in this session's tool set.
- **Fix:** `human:` connect a Notion MCP server in the harness, then restart the
  session — MCP tools register at launch. The local Markdown copy is written
  either way, so an unconnected server delays the mirror, never the note.
- **Notes:** the page every work item is created under is
  `notion.parent-page-id` in `.afk/config.yaml`, not a secret.

### H12 · hook trust for the protected-branch guard *(harnesses that gate new hooks behind trust)*
- **Needed by:** the guard, the change meter, the session-end cleanup, the session-start prune and the session-start occupancy registration.
  Such a harness runs a plugin hook only after the user trusts it
  (`PROVIDERS.md` "Protected-branch guard", which names the harness and the
  exact screens).
- **Probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/check_hook_trust.py"`
  reads the harness config (`$CODEX_HOME/config.toml`, else `~/.codex/config.toml`)
  for a `hooks.state` key at the guard's position (the last `PreToolUse`
  group), at the `PostToolUse` meter, at the `SessionEnd` cleanup and at the two `SessionStart` entries (prune, occupancy). Exit 1
  prints `missing: <event>:<group>:<handler>` per absent key and the step; exit 2
  means no harness config (not applicable). A key that is present but stale
  (the hash no longer matches) is invisible to the probe: `human:` type `/hooks`
  and look for a "need review" line.
- **Fix:** `human:` for a `missing` key, start the harness once in its terminal UI without the
  full-bypass flag and choose "Trust all and continue", or type `/hooks` and
  press `t`. Setup never writes a trust entry.
- **Notes:** with the full-bypass flag or a non-interactive run, untrusted
  hooks stay silent.

### H11 · native nested `AGENTS.md` reading (`instructionFiles`)
- **Needed by:** every afk developer whose harness gates nested `AGENTS.md` on
  this settings key — this plugin's own `skills/afk/AGENTS.md` and the
  `nested_steering` capability (`CAPABILITIES.md`) reach that session only when
  the key is set with the root `CLAUDE.md` bridge present. Which harness, and
  the key's values: `providers/HARNESS-MATRIX.md`; standard:
  `skills/afk/agents-md/SKILL.md`.
- **Probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/set_instruction_files.py" --check`
  — reads `$CLAUDE_CONFIG_DIR/settings.json`, else `~/.claude/settings.json`;
  exit 0 when `pluginConfigs."agents-md@builtin".options.instructionFiles` is
  `claude-md-and-agents-md`.
- **Fix:** `auto:` `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/set_instruction_files.py"`
  — merges exactly that one key, preserves every other key and the file's
  indentation, writes a timestamped backup first, and creates the file and its
  parents when absent.
- **Notes:** the key may also arrive from managed settings or `--settings`,
  which the probe cannot see — a miss it reports is advisory, and the
  idempotent fix writes the same value into the user-global settings file
  either way. It lives only in the user-global file, per machine, never on git;
  the reasons and the harness this serves are in `providers/HARNESS-MATRIX.md`.

### H12 · no instruction-file strays above the repository
- **Needed by:** every afk developer — an instruction file left in the git
  root's parent, or any directory above it up to the filesystem root, is read by
  a harness that walks the working directory upward past the git root
  (`providers/HARNESS-MATRIX.md`), so it is prepended to **every** repository
  below it, silently. Standard: `skills/afk/agents-md/SKILL.md`.
- **Probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/ancestor_instruction_files.py" --check`
  — tests the fixed names `AGENTS.md`, `AGENTS.override.md`, `CLAUDE.md`,
  `CLAUDE.local.md`, `.claude/CLAUDE.md`, `.claude/AGENTS.md` at each ancestor by
  direct path test (never a recursive scan, which would trip the endpoint
  sensor); exit 0 when none is found, 1 when one is. A file inside `~/.claude` or
  `~/.codex` is the harness user-global steering file, not a stray, and is
  excluded; one directly in the home directory (`~/AGENTS.md`, `~/CLAUDE.md`) is
  a stray.
- **Fix:** `human:` run the probe without `--check` to list each stray with its
  size and the reason it leaks into every repository below it, then per stray
  offer the developer **delete** or **add its path to `claudeMdExcludes`** in
  their settings. Never delete without the developer's answer — a stray may be
  theirs on purpose.
- **Notes:** report-only; the toolkit changes no file above the repository on
  its own. The two remediations and the harness that walks above the repository
  are in `providers/HARNESS-MATRIX.md` and the standard.

### H13 · no git hook that starts background work
- **Needed by:** every afk developer — git runs one hooks directory for every
  worktree of a checkout and does not wait for a process a hook detaches. A
  hook that detaches work on each commit stacks runs behind agent commits; the
  load stalls the machine and the tool-call gates time out.
- **Probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/background_git_hooks.py" --check`
  — reads `git rev-parse --git-path hooks` (follows `core.hooksPath`), skips
  `*.sample` files and the H5 stubs, and flags a non-comment line with a
  trailing `&`, `nohup`, `setsid`, `disown`, `start /b`, or `Start-Process`;
  exit 0 when none is found, 1 when one is.
- **Fix:** `human:` run the probe without `--check` to list each hook with the
  line that detaches, then per hook offer the developer **remove the hook** or
  **remove that line**. Never delete without the developer's answer — a hook
  may be theirs on purpose.
- **Notes:** report-only; the toolkit edits no hook it did not install.

## C — Shell & core CLIs

### C1 · bash (Git Bash on Windows) + POSIX utils
- **Needed by:** the `hooks/*.sh` gate suite (the Stop gates — wiring,
  genericity, skill-registry, native-contract via `stop-gates.sh` — **fire every
  turn**; the commit gates — Maven compile, Java format, UI lint via
  `precommit-gates.sh` (with `comment-gate.sh`) — fire on agent-driven commits; plus the on-demand
  `app-start-gate.sh`), the forge adapters' `forge.sh`,
  `skills/afk/review/scripts/forge_ledger.py`,
  `skills/utils/diagnose/scripts/hitl-loop.template.sh`, app-start invocations
  in `skills/afk/autopilot` and `skills/afk/to-subtasks/SMOKE-GATE.md`.
- **Probe:** `bash -c 'command -v awk && command -v sed && command -v grep' >/dev/null`
- **Fix:** `human:` install Git for Windows (ships bash + the POSIX utils).
- **Notes:** the single hardest platform assumption — outside a POSIX shell the
  Stop hooks error on every turn.

### C2 · git
- **Needed by:** the whole chain (worktrees, branches, push), `hooks/wiring-gate.sh`,
  `skills/utils/investigate/scripts/seed_map.py` (its only search and inventory tool).
- **Probe:** `git --version`
- **Fix:** `human:` install Git for Windows (also satisfies C1).
- **Base fix:** `auto:` `winget install --id Git.Git -e` — ships bash + POSIX
  utils + perl, so it also satisfies C1 and C6.

### C2b · git 2.46 or newer *(optional)*
- **Needed by:** the protected-branch backstop (`hooks/git-backstop.py`, through
  the `reference-transaction` hook of H5) refusing an agent's `git switch` or
  `git checkout` in the main checkout.
- **Probe:** `v=$(git --version | awk '{print $3}'); test "$(printf '%s\n' 2.46.0 "$v" | sort -V | head -1)" = 2.46.0`
- **Fix:** `human:` upgrade git (Git for Windows, or the distribution's newer
  git package).
- **Notes:** git 2.46.0 release notes: "Updates to symbolic refs can now be made
  as a part of ref transaction." Older git never passes a HEAD switch to the
  hook, so the backstop misses that one move; it still refuses commits, resets
  and branch-ref updates. The PreToolUse guard stays the primary gate.
  `scripts/tests/git_floor.py` skips the tests that need this floor.

### C3 · glab (GitLab CLI), logged in — **secret** *(only when `forge: gitlab`)*
- **Needed by:** `adapters/forge/gitlab/forge.sh` — every forge verb, so
  `skills/afk/execute` (push + Draft change), `skills/afk/preflight` (the CI
  wait and the Draft→Ready flip), `skills/afk/understand` (change intake) and
  `skills/afk/gc` (the merged proof).
- **Probe:** `glab auth status` (exit 0 = logged in; prints no token). Another
  forge selected: n/a. `forge` resolving to `none`: as `H0` defines.
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
  `adapters/tracker/github-issues/api.py` — every `tracker_*` operation; and,
  whatever the repository selects, `skills/utils/report-issue/scripts/publish.sh`
  (issue search, label create, issue create or comment; absent or logged out →
  the draft queues on disk, so it is optional there).
- **Probe:** `gh auth status` (exit 0 = logged in; prints no token). Neither
  `forge: github` nor `tracker: github-issues` selected: the forge and tracker
  leg is n/a, or as `H0` defines when they resolve to `none`; the report-issue
  leg keeps this probe.
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
  follows that repository's own conventions (its root `AGENTS.md`).
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
- **Needed by:** `scripts/create-worktree` (path-rewrite step — SDD §9b seam
  "perl (Git-Bash)").
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
- **Needed by:** `adapters/build-gate/maven/worktree-provision.sh` (per-worktree
  local-repository seeding — multi-threaded copy of the dev's local repository
  minus `*-SNAPSHOT` dirs).
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
  reading and writing. `hook-smoke.sh` is a test suite, not a hook: without jq
  it prints `FAIL: jq not on PATH` and exits 1, so a run with zero coverage never
  reads as green.
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

### C11 · Chrome, Edge, or Chromium *(optional)*
- **Needed by:** `scripts/tests/test_lavish_render.py` — serves a rendered input
  page, stubs the lavish bridge, and checks the form submit and clipboard paths
  in a browser.
- **Probe:** `python "$AFK_PLUGIN_ROOT/scripts/lavish/browser.py"` (the same
  resolver the test imports)
- **Fix:** `human:` install one Chromium browser. Standard Windows Chrome and
  Edge installation paths also pass the test when the commands are not on
  `PATH`.
- **Notes:** optional and fail-open. Without a browser, this one regression test
  skips. The renderer's structural send-control gate and all non-browser tests
  still run.

### C12 · Wave Terminal *(Windows only)* **[opt-in]**
- **Needed by:** optional Wave-hosted lavish pages. AFK and every lavish render
  remain usable without it.
- **Probe:** `agent:` on native Windows, run
  `winget list --id CommandLine.Wave --exact --source winget`; on other
  platforms classify this row `n/a`.
- **Fix:** `auto:` run
  `winget install --id CommandLine.Wave --exact --source winget`, then verify
  with `winget list --id CommandLine.Wave --exact --source winget`.
- **Notes:** setup installs and verifies only. It does not start the app, call
  its command-line tool, change the active terminal, or move a session.

### C13 · pandoc **[deferred: first `/afk:sred` DOCX export]**
- **Needed by:** `skills/utils/sred/SKILL.md` "Write" — converts each accepted
  Markdown document to DOCX.
- **Probe:** `pandoc --version`
- **Fix:** `human:` install pandoc from <https://pandoc.org/installing.html>
  (Windows: `winget install --id JohnMacFarlane.Pandoc --exact`).

### C14 · LibreOffice (`soffice`) **[deferred: first `/afk:sred` DOCX export]**
- **Needed by:** `skills/utils/sred/SKILL.md` "Write" — renders each DOCX to PDF
  so every page is inspected before delivery.
- **Probe:** `soffice --version`
- **Fix:** `human:` install LibreOffice from <https://www.libreoffice.org>
  (Windows: `winget install --id TheDocumentFoundation.LibreOffice --exact`),
  then put its `program` directory on `PATH`.
- **Notes:** the Windows installer does not add `soffice` to `PATH`.

### C15 · herdr **[opt-in]**
- **Needed by:** developers who run several agent sessions side by side —
  herdr is a terminal workspace manager for AI coding agents (workspaces, tabs,
  panes, per-agent status). No skill invokes it; every skill runs without it.
  Also needed by the H-2 worktree move (`scripts/afk-move.py`, which types the
  `/cd` line into the agent's pane through `herdr agent get|read|prompt|send-keys`);
  without herdr the refusal prints the line for the human to type. Minimum
  version: unverified, built against 0.9.1.
- **Probe:** `herdr --version`
- **Fix:** `auto:` the vendor installer (<https://herdr.dev/docs/install/>):
  - native Windows: `powershell -ExecutionPolicy Bypass -c "irm https://herdr.dev/install.ps1 | iex"`
  - macOS / Linux: `curl -fsSL https://herdr.dev/install.sh | sh`
  Then re-probe. The installer puts the binary on the user `PATH`, so a running
  session reaches it only after a relaunch (`SKILL.md` step 2's stale-environment
  rule).
- **Notes:** setup installs and verifies only. It does not start herdr, create
  a workspace, or move a session. `herdr update` self-updates later.

### C16 · herdr session reporting for the H-2 harness **[opt-in]**
- **Needed by:** the H-2 worktree move (`scripts/afk-move.py`): it types the `/cd`
  line only into a pane whose session id herdr reports, and herdr learns that id from
  its own integration hook. Without it the refusal's printed line is the human's to type.
- **Probe:** `herdr integration status | grep -q '^codex: current'`
- **Fix:** `auto:` `herdr integration install codex`, then re-probe. Restart `codex`
  so the new hook runs.
- **Notes:** needs C15. Opt-in: a miss never blocks the guard.

### P1 · afk-python runtime
- **Needed by:** the `afk-python` command, which every hook, MCP registration
  and skill command adopts at the Python release 2 cutover
  (`.claude/wiring-ious.md`). Until then: this probe and the SessionStart notice
  in `hooks/update-notice.sh`.
- **Pins:** `runtime/pyproject.toml` — CPython in `requires-python`, uv in
  `[tool.uv] required-version`, the dependency set and its import names.
  `runtime/uv.lock` holds every transitive version with its hashes.
- **Probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/python_runtime.py" check`
  — compares the installed packages with `runtime/uv.lock` (`uv sync --check
  --offline`, read-only), then resolves `afk-python` through the PATH a new
  terminal gets, never the probing process's own, from PowerShell, cmd and Git
  Bash on Windows, and from `sh` and the login shell elsewhere. Each
  shell must report the pinned Python running in the private environment
  (`sys.prefix`), import every runtime package, and set `AFK_PYTHON` to the
  entry itself. The bash every hook runs in (`hooks/run-hook.py` `find_bash`,
  with its `shell_env`) must resolve `afk-python` to the installed entry, pass
  the same interpreter checks, and find the file the stamp names. The
  environment's stamp must name the pinned Python and the current lock hash.
- **Fix:** `auto:` per-user install — ask the human first.
  `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/python_runtime.py" install`
  installs the pinned uv with Astral's versioned installer, then the pinned
  CPython, then syncs the private environment frozen from the lock, wheels only,
  with bytecode compiled. It then places the `afk-python` entry and the
  `AFK_PYTHON` line in the environment, and adds the entry's directory to the
  user PATH unless the startup files already add it. The installer and uv run
  without the user's `UV_*` settings and installer download overrides; proxy,
  TLS and uv's HTTP timeout, retry and concurrency variables pass through. It
  deletes the stamp first and publishes it only after the probe passes, with
  the `afk-python` spelling and file the hooks' bash resolved. An intent
  file that exists but cannot be read stops it before any change.
  It prints one `ok`/`fail` line per step.
  `plan` prints the same steps and changes nothing. The running harness keeps
  its old PATH: report `needs-human: restart the harness` (step 2's
  stale-environment rule). A `fail environment` line saying the platform has no
  prebuilt wheel is final: the lock has none for that platform (Windows on ARM
  and Intel macOS lack `cryptography` wheels for CPython 3.14), and setup never
  builds from source — report `needs-human: afk-python unsupported on this
  platform`.
- **Base probe:** `python "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/python_runtime.py" check --test`
- **Base fix:** `auto:` the Fix command with `--test`: adds the `test` extra
  (pytest). The suites under `scripts/tests/` then run as `afk-python -m pytest`.
  A later run without `--test` keeps the extra, even after a failed run:
  `AFK-RUNTIME.extras` records it before anything changes.
- **Notes:** the user's own `python` and `python3` stay untouched. `afk-python`
  is the interpreter itself, so every CPython option works. `-S` skips the
  `AFK_PYTHON` line. Layout: the `python_runtime.py` docstring. Network: the uv
  release host and PyPI. To remove: delete `%LOCALAPPDATA%\afk` (Windows) or
  `${XDG_DATA_HOME:-~/.local/share}/afk`, then drop its `python/afk-bin`
  directory from the user PATH.

### P2 · system Python + packages for current callers *(until the afk-python cutover)*
- **Needed by:** every Python entry point that still runs `python`:
  `hooks/run-hook.py` — the launcher every registered hook command runs
  through, so without it no gate or guard fires at all — the shared
  `.mcp.json` bootstrap and `mcp-servers/tracker/server.py` (H2),
  `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`,
  `skills/afk/agents-md/scripts/*.py`, the repository's `verification.env` command,
  the shared Jira lib `adapters/tracker/jira/api.py` (Markdown → ADF for
  `publish_prd.py` and `skills/afk/bug/scripts/publish_bug.py`; ADR-0001),
  `skills/afk/review/scripts/forge_ledger.py`,
  `skills/utils/investigate/scripts/{seed_map,validate_coverage}.py`, and
  `skills/utils/review-qa-tests/scripts/annotate_sheet.py`
  (`skills/utils/review-qa-tests/EXCEL.md`).
- **Probe:** `(python --version || python3 --version) && python -c "import markdown_it, mcp.server.fastmcp, httpx, openpyxl"`
- **Fix:** `human:` install Python 3 and put it on PATH; then `auto:`
  `pip install markdown-it-py "mcp<2" httpx openpyxl`.
- **Base fix:** `auto:` `winget install --id Python.Python.3.12 -e` (any Python 3
  on PATH passes the probe — the pin here is just a working default).
- **Notes:** `mcp` 2 removed `mcp.server.fastmcp`, which the tracker server
  imports. A missing `mcp` or `httpx` surfaces as the tracker server failing to
  connect at session start, not as a skill error. On Windows `python3` is often
  a Store stub that exits 49 while real `python` works. Removed at the cutover,
  when these callers run `afk-python` (P1).

## N — Node toolchain

### N1 · node + npm + npx
- **Needed by:** mermaid rendering (N2), the verification suites (N3), UI
  builds the chain may trigger, and `adapters/build-gate/npm/ui-lint-gate.sh` (resolves eslint
  via `npx --no-install`; silently allows when unresolvable).
- **Probe:** `node --version && npm --version`
- **Fix:** `human:` install the Node version the repository standardises on.
- **Base probe:** `node --version | grep -q '^v24\.' && npm --version | grep -q '^11\.'`
  — whatever workspace standard the repository's root `AGENTS.md` states.
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

### N4 · lavish-axi (render points), global install at the pin
- **Needed by:** any skill woven with a `render per LAVISH.md` point, and every
  session-default render — the pin, invocation shapes, and forbidden operations
  live in `LAVISH.md` (plugin root), never restated here.
- **Probe:** the `lavish-axi` on `PATH` reports exactly the pin `LAVISH.md` states:
  ```
  want=$(sed -n 's/^\*\*Pin: `lavish-axi@\([0-9][0-9.]*\)`\*\*.*/\1/p' "$AFK_PLUGIN_ROOT/LAVISH.md")
  test -n "$want" && [ "$(lavish-axi --version 2>/dev/null)" = "$want" ]
  ```
- **Fix:** `auto:` install Node/npm per N1 first, then
  `npm i -g "lavish-axi@$want"` (`want` from the probe) — the same command
  replaces a global install at another version. After a version change, run
  `lavish-axi stop` with no session open so the background server restarts on
  the pin.
- **Notes:** a pin bump in `LAVISH.md` flips this probe red until setup re-runs.
  A failing render at run time is still **never** a phase failure — every render
  point falls back to markdown (`LAVISH.md`).

## S — Secrets

### S1 · Jira REST credentials — **secret**
- **Needed by:** `skills/afk/to-ticket/scripts/{publish_prd,publish_meeting}.py`
  (attachment upload has no MCP tool, and both engines PUT the description via
  REST directly rather than inline a large ADF through an MCP tool call),
  the shared Jira lib `adapters/tracker/jira/api.py` and
  `skills/afk/bug/scripts/publish_bug.py` (same creds resolution; ADR-0001),
  and `scripts/afk-config.py init` (presence-only: the `JIRA_BASE_URL` hint).
- **Probe:** presence-only through the shared resolver; prints no values:
  `python "$AFK_PLUGIN_ROOT/adapters/tracker/jira/api.py" --check-creds`
- **Fix:** `human:` run `python skills/afk/setup/scripts/setup_secrets.py` — it
  prompts for the token without echoing it, validates it against the host before
  writing, and places it in the H2 `env` block (also does H2/C3 or C3b, whichever the forge selects). By hand:
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
- **Probe:** `codex plugin marketplace list` names `afk-toolkit`; `python
  "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/codex_marketplace_ref.py" --check`
  passes; `codex plugin list` reports `afk@afk-toolkit` installed and enabled;
  the newest installed plugin root that Codex plugin metadata reports matches
  the source manifests, `hooks/hooks.codex.json`, and every
  `skills/*/*/SKILL.md` hash.
- **Fix:** `auto:` run `python
  "$AFK_PLUGIN_ROOT/skills/afk/setup/scripts/codex_marketplace_ref.py"` to remove
  a legacy pin. When the marketplace is absent, run `codex plugin marketplace
  add midnightblur/afk-driver` with no `--ref`. Then run `codex plugin
  marketplace upgrade afk-toolkit` and `codex plugin add afk@afk-toolkit`.
  For a stale cache, ask first; after confirmation run `codex plugin remove
  afk@afk-toolkit`, add it again, then restart.

### O4 · current hook definitions trusted
- **Needed by:** every handler in `hooks/hooks.json` and its native twin
  `hooks/hooks.codex.json`.
- **Probe:** parse `~/.codex/config.toml`; every enabled AFK handler has a
  native trust entry matching the currently installed `hooks.codex.json`
  definition. Never print other config or secret values.
- **A plugin upgrade changes `hooks/hooks.codex.json`, so the harness re-prompts
  for hook trust and a dismissed prompt leaves those hooks silently off.** Re-run
  `/afk:setup` after every version change on that harness — not only when a
  changelog entry says the dependency set changed. The probe re-checks trust
  against the current definitions, which is what catches a stale or dismissed
  trust after an upgrade.
- **Fix:** `human:` review and trust every current AFK definition through the
  native hooks interface after all `hooks.json` / `hooks.codex.json` edits land,
  including after a plugin upgrade.

### O5 · Codex agent TOML stubs
- **Needed by:** `afk-reader`, `afk-runner`, `afk-runner-lite`, `afk-implementor`,
  and `afk-tracer` roles.
- **Sources (exactly these five, no others):**
  `providers/codex/agents/afk-afk-implementor.toml`,
  `providers/codex/agents/afk-afk-reader.toml`,
  `providers/codex/agents/afk-afk-runner.toml`,
  `providers/codex/agents/afk-afk-runner-lite.toml`,
  `providers/codex/agents/afk-afk-tracer.toml`.
- **Probe:** each `providers/codex/agents/afk-afk-*.toml` is present under
  `~/.codex/agents/` with the same filename, its `{{PLUGIN_ROOT}}` placeholder is
  replaced by a plugin root that **exists on disk and contains `LANGUAGE.md` and
  `agents/`**. That harness reports the root two ways — a marketplace directory and a
  versioned cache directory — and both are real, content-identical, and work. The
  probe asked for one exact string and therefore failed on a machine whose stubs were
  correct. What matters is that the baked path resolves to the toolkit, not which of
  its two names was written.
- **Upgrading the plugin breaks this row until setup runs again.** The root baked into
  each stub carries the version, so installing any new version leaves all five stubs
  naming a directory that no longer exists, and every agent spawn on that harness
  fails. Re-run `/afk:setup` after every version change on that harness — not
  only when a changelog entry says the dependency set changed. The last clause of the
  probe is what catches it.
- **Fix:** `auto:` resolve Codex's installed plugin root via
  `hooks/lib/providers/codex.sh`'s `afk_codex_installed_root()` (one home for
  the resolution algorithm; point there, do not restate it — its own
  provider-owned Python helper is that adapter's implementation detail, never
  called directly from here), then verify the result by this row's own
  criterion — distinct from that adapter's own `BEHAVIORS.md` check, which
  serves a different consumer: it exists on disk and contains `LANGUAGE.md`
  and `agents/`. Never list a cache directory
  and never pick a "newest" directory. Create missing destinations, copy each
  `providers/codex/agents/afk-afk-*.toml` to `~/.codex/agents/` under the same
  filename, and replace every `{{PLUGIN_ROOT}}` occurrence with that root verbatim.
  Refuse to overwrite a different user file without confirmation. Verify each
  destination contains no `{{PLUGIN_ROOT}}`, then start a new session.

### O6 · per-directory steering fallback **[opt-in]**
- **Needed by:** nested `CLAUDE.md` files when no nearer `AGENTS.md` exists.
- **Probe:** `~/.codex/config.toml` has
  `project_doc_fallback_filenames = ["CLAUDE.md"]`.
- **Fix:** `human:` offer that exact idempotent setting. Preserve all other
  user configuration.
- **Notes:** serves a repo that still keeps per-directory `CLAUDE.md`; inert in
  a repo migrated to the `AGENTS.md` standard, which leaves only the root bridge.

### O7 · native catalog and shared Jira MCP
- **Needed by:** all workflow skills and the two Jira-writing skills.
- **Probe:** `agent:` a new session lists every `afk:<name>` plugin skill named
  in `plugin.json` and no `afk-<name>` mirror, every agent role `O5` lists, and a
  callable `tracker_get` (n/a under `tracker: none`, per `H0` — the catalog and
  role legs still stand on their own). Count the manifest rather than a number
  written here: a number in prose goes stale the first time a skill is added.
- **Fix:** repair O2–O6, then restart. Never print Jira secrets.

### O8 · stale generated activation cleanup **[opt-in]**
- **Needed by:** migration from the retired generated layer only. Run it after
  uninstalling the plugin too: these paths are gitignored, so a harness removal
  leaves them behind and a repository-root session still reads them.
- **Probe:** `! git worktree list --porcelain | sed -n 's/^worktree //p' | while IFS= read -r w; do ls -d "$w/.agents/skills" "$w/.codex/agents" "$w/.codex/hooks.json" "$w/AGENTS.local.md" 2>/dev/null; done | grep -q .`
- **Fix:** `human:` offer removal of AFK-generated `.agents/skills/afk-*`,
  project `.codex/agents/`, project `.codex/hooks.json`, and only the AFK block
  in `AGENTS.local.md`. Delete nothing without confirmation. Preserve every
  unrelated file and block. Run `git ls-files` on those paths in each worktree
  first: zero hits ⇒ remove them there; any hit ⇒ that branch predates the
  commit that untracked the tree, so report it and leave it — merging the branch
  forward drops them, and a cleanup delete would stage a content change the
  human never asked for.
- **Notes:** each worktree holds its own copy, so a check at one root passes
  while its siblings stay stale. A stale copy is a live fault, and its two
  halves resolve differently. Skills resolve per worktree: the retired generator
  wrote a folded-scalar `description:` header that reads as invalid YAML, so a
  session opened there loses those skills, and the copies that still load shadow
  the plugin's own catalog and squeeze every description into a smaller budget.
  The hook file resolves once, from the main worktree: its `_generated` key
  fails that schema for every worktree at once, so removing the main copy clears
  it everywhere and a sibling copy sits inert.

## X — Rows the repository contributes

A repository states its own prerequisites — its checkout, its verification
tree, its environment tooling, its credentials — in the files its
`.afk/config.yaml` lists under `setup.extra`. Each is a Markdown file in this
same row format; `/afk:setup` reads them after the rows above and
probes them the same way. The toolkit ships no row for any one repository's
state, because it cannot know it.

## W — Workstation apps & OS config (base-only)

Human tooling and machine settings, not skill dependencies — no skill invokes
these, so entries here carry **only** base-tier fields and the default branch
skips the section entirely. Probed and fixed under `/afk:setup base` alone; a
miss is `missing/broken` there, never on a default run. Any fix marked
**elevated prompt** stays with the human — the agent never elevates.

### W1 · Visual Studio Code
- **Needed by:** the human (no skill invokes it).
- **Base probe:** `command -v code`
- **Base fix:** `auto:` `winget install --id Microsoft.VisualStudioCode -e`

### W2 · IntelliJ IDEA
- **Needed by:** the human; optionally referenced by `/afk:bug`'s `ideBinary`
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
| `CLAUDE_PROJECT_DIR` | `scripts/afk-config.py` `project_root` (tracker server and adapter) | optional project root for the tracker config: `project_root` reads `${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}` |
| `AFK_BASH` / `GIT_BASH` | `hooks/run-hook.py` | POSIX shell the hook launcher runs handlers with, ahead of its own lookup |
| `APP_START_KEEP` / `APP_START_PORT` / `APP_START_SKIP_UI` / `APP_START_REUSE` | `skills/afk/autopilot` | app-start-gate provisioning mode |
| `APP_START_TIMEOUT` | `adapters/build-gate/maven/app-start-gate.sh` | boot timebox (seconds, default 300) |
| `APP_START_UI_BUILD` | `adapters/build-gate/maven/app-start-gate.sh` | the UI build script the gate runs when `APP_START_SKIP_UI=false`; defaults to `build_ui.sh` beside the service directory |
| `CI_PROJECT_DIR` | `adapters/build-gate/maven/app-start-gate.sh` | checkout the service's `build_ui.sh` resolves its npm workspace from; read only when `APP_START_SKIP_UI=false`, defaults to the repo root |
| `AFK_DRIVEN` | `skills/afk/gc/scripts/gc-check.sh` | exported `=1` by hands-off invokers; makes `/afk:gc` refuse deletion — it always gets a human eye |
| `WIRING_GATE_DISABLE` / `WIRING_FINAL` | `hooks/wiring-gate.sh` | disable / final-mode the wiring gate |
| `SKILL_REGISTRY_GATE_DISABLE` | `hooks/skill-registry-gate.sh` | disable the registry gate (plugin.json membership + skill catalog + env-toggle register) |
| `GENERICITY_GATE_DISABLE` | `hooks/genericity-gate.sh` | disable the genericity gate |
| `BEHAVIOR_REGISTRY_GATE_DISABLE` | `hooks/behavior-registry-gate.sh` | disable the managed behavior registry gate |
| `COMMENT_GATE_DISABLE` | `hooks/comment-gate.sh` | disable the commit-time comment gate |
| `AFK_RATIONALE_CACHE` | `skills/afk/review/scripts/forge_ledger.py` | relocate the rationale lookup cache (default: `$XDG_CACHE_HOME/afk/rationale`, else `~/.cache/afk/rationale`); refused when the base, from any source, is inside the repository or its Git directory |
| `NATIVE_CONTRACT_GATE_DISABLE` | `hooks/native-contract-gate.sh` | bypass the native plugin contract gate |
| `NESTED_STEERING_DISABLE` | `hooks/nested-steering.sh` | disable the nested-steering injector (`nested_steering` capability) for one session |
| `AFK_PROVIDER` | `hooks/lib/provider.sh` | force provider detection before adapter probes |
| `AFK_PATH_CASE_FOLD` | `hooks/lib/provider.sh` | force path comparison to fold case (`1`) or to match exactly (`0`); unset follows the filesystem — folded on Windows and macOS, exact elsewhere |
| `PLUGIN_ROOT` / `PLUGIN_DATA` | `hooks/lib/providers/codex.sh` | native plugin root and data paths; root detection precedes inherited compatibility markers |
| `CLAUDE_PLUGIN_DATA` | `hooks/lib/providers/claude.sh` | compatibility plugin data path |
| `GATE_CACHE_DISABLE` | `hooks/gate-cache.sh` | bypass the Stop gates' pass cache — every run does real work |
| `AFK_PLUGIN_ROOT` | `hooks/run-hook.py`, `hooks/lib/config.sh`, `hooks/lib/adapter.sh`, `hooks/install-git-hooks.sh`, `skills/afk/review/scripts/forge_ledger.py` | absolute plugin root, exported by the hook launcher so repository-owned handlers and adapters resolve the toolkit without searching |
| `AFK_LEDGER_ADAPTER_CMD` | `skills/afk/review/scripts/forge_ledger.py` | test seam that replaces forge adapter dispatch with a named command |
| `AFK_LEDGER_ADAPTER_TIMEOUT` | `skills/afk/review/scripts/forge_ledger.py` | seconds one adapter call may run before the ledger reports a timeout (default 120) |
| `AFK_FORGE_TIMEOUT` | `adapters/forge/github/forge.sh`, `adapters/forge/gitlab/forge.sh` | seconds one `gh` or `glab` call may run where GNU `timeout` exists (default 60) |
| `JIRA_DEFAULT_PROJECT` | `adapters/tracker/jira/api.py` | project key used when a caller names none; absent, a create is refused with a message naming this variable rather than guessing a project |
| `GH_REPO` | `adapters/tracker/github-issues/api.py` | `owner/name` fallback when the configuration names no `repo`; the configuration wins where both are set |
| `AFK_CFG_GITHUB_REMOTE` / `AFK_CFG_GITLAB_REMOTE` | `adapters/forge/github/forge.sh`, `adapters/forge/gitlab/forge.sh` | the git remote whose URL identifies the project, exported by `hooks/lib/config.sh` from `<kind>.remote`; unset lets the forge CLI derive the project from the checkout |
| `AFK_CFG_OBSIDIAN_VAULT` | `adapters/notes/obsidian/notes.sh` | vault directory exported from `obsidian.vault`; an absent directory is answered `unavailable` rather than crashing |
| `AFK_CFG_REPO_FILES_SPEC_DIR` | `adapters/notes/common.sh` | the spec-directory template exported from `repo-files.spec-dir`, with its placeholders expanded per note |
| `CLAUDECODE` | `hooks/lib/providers/claude.sh`, `hooks/branch-name-gate.sh`, `hooks/native-contract-gate.sh`, `hooks/skill-registry-gate.sh` | a compatibility marker one harness sets; read only after the native root variable, never as the first thing tried |
| `CLAUDE_JOB_DIR` | `adapters/forge/github/forge.sh`, `adapters/forge/gitlab/forge.sh` | per-job scratch directory that harness offers; where a forge verb writes a downloaded diff when the caller names no `out_dir` |
| `AFK_CFG_MAVEN_*` | `adapters/build-gate/maven/maven-lib.sh` and the Maven gates | the `maven:` block exported by `hooks/lib/config.sh` — `reactor-pom`, `formatter-config`, `formatter-plugin`, `default-module`, `skip-ui-flag` |
| `AFK_CFG_NPM_*` | `adapters/build-gate/npm/ui-lint-gate.sh`, `adapters/build-gate/npm/worktree-provision.sh` | the `npm:` block exported by `hooks/lib/config.sh` — `lint` (the lint gate); `workspace-root`, `worktree-install`, `worktree-command` (worktree provisioning) |
| `WAVETERM` / `WAVETERM_CONN` / `WAVETERM_TABID` / `WAVETERM_BLOCKID` | `scripts/lavish/wave_host.py` | local Wave eligibility and the current tab/block scope; values are never printed |
| `LOCALAPPDATA` | `scripts/lavish/wave_host.py` | native Windows application-data root used only to resolve the generic Wave `wsh.exe` fallback |
| `AFK_CFG_BUILD_GATES_*` | `hooks/lib/config.sh`, `hooks/lib/adapter.sh` | the `build-gates:` list (`_COUNT` plus indexed names) selecting which build-gate adapters load |
| `AFK_CFG_TRACKER` / `AFK_CFG_JIRA_PROJECT` | `hooks/comment-gate.sh` | the selected tracker kind exported by `hooks/lib/config.sh` from `tracker`, and the Jira project key from `jira.project`; the comment gate reads that kind's `referencePatterns` from its `adapter.json`, matches only the configured key when one is set, and falls back to the shared ticket shape when neither exists |
| `AFK_CFG_GIT_BRANCH_PATTERN` | `hooks/branch-name-gate.sh` | the branch-name convention exported by `hooks/lib/config.sh` from `git.branch-pattern`; unset means the repository has no convention and the gate is off |
| `AFK_CFG_GIT_BRANCH_TEMPLATE` | `hooks/branch-name-gate.sh` | the suggestion the gate prints on a refusal, exported from `git.branch-template`; its placeholders are expanded from the rejected name |
| `AFK_CFG_GIT_BASE_BRANCH` | `hooks/gate-context.sh` | integration base exported by `hooks/lib/config.sh` from `git.base-branch`; unset or `auto` falls back to `origin/main`, `origin/master`, `@{u}`, HEAD |
| `AFK_GATE_CTX_DISABLE` | `hooks/gate-context.sh` | rebuild the shared per-Stop change-set context on every call instead of reusing it (debug) |
| `AFK_SKIP_PRECOMMIT_GATES` | `hooks/precommit-gates.sh` | skip the commit-time code gates the `build-gates:` adapters select, for one commit |
| `GATE_METRICS_DISABLE` / `GATE_METRICS_FILE` | `hooks/gate-metrics.sh` | silence / relocate gate-latency emission (default `<git common dir>/afk/metrics/gate-latency.jsonl`) |
| `MAVEN_LOCK_DIR` | `adapters/build-gate/maven/maven-lock.sh` | relocate the cross-gate maven lock dir |
| `AFK_MAVEN_LOCK_WAIT` | `adapters/build-gate/maven/maven-compile-gate.sh` | seconds the compile gate waits for the maven lock before allowing (240 on the commit path, 900 standalone) |
| `PITEST_VERSION` / `MUTATION_TIMEOUT` | `adapters/build-gate/maven/mutation-probe.sh` | pitest version pin / probe timebox |
| `AFK_SKIP_BRANCH_CHECK` | `hooks/branch-name-gate.sh` | bypass the branch-name gate for one agent command |
| `AFK_ALLOW_PROTECTED` | `hooks/protected-branch-guard.py`, `hooks/protected-branch-meter.py`, `hooks/protected-branch-occupancy.py` | allow an agent session on the main checkout or a protected branch; set by the human at launch |
| `AFK_PROTECTED_TIMEOUT` | `scripts/protected-lookup.py` | seconds the forge protected-branch read may take before the guard falls back to the default-branch, `main`, `master` rule (default 5) |
| `AFK_PROTECTION_CACHE_TTL` | `scripts/protected-lookup.py` | seconds a definite forge protected-branch answer is reused, in `<git common dir>/afk/protection-cache.json` (default and maximum 300; `0` asks the forge every time); the default branch, `main` and `master` are always asked |
| `AFK_GITHUB_API_URL`, `AFK_GITLAB_API_URL` | `scripts/protected-lookup.py` | per-forge API root the protected-branch read uses instead of the public forge API, used only with a `GH_TOKEN`/`GITHUB_TOKEN`/`GITLAB_TOKEN` you set yourself; without one the CLI is used, and the CLI login token is never sent to an override (tests, proxies) |
| `AFK_WORKTREE_FOLDER` | `scripts/create-worktree` | folder inside the main checkout that `--name` worktrees go in, overriding the harness's own (default `.claude/worktrees` or `.codex/worktrees`) |
| `AFK_OWNER_PROCESS` | `scripts/worktree_owner.py` | comma-separated process names that count as a worktree's owner, instead of the nearest non-shell ancestor |
| `AFK_SCAN_DEADLINE` | `hooks/lib/bounded_scan.py` | seconds one repository scan may run before the verdict is unknown (default 120; keep below the Stop hook's `--deadline`) |
| `AFK_MOVE_SPAWN` | `hooks/lib/h2_move.py` | `0` names the H-2 worktree path in a refusal without cutting it (tests only) |
| `CODEX_HOME` | `skills/afk/setup/scripts/check_hook_trust.py`, `skills/afk/setup/scripts/codex_marketplace_ref.py` | the H-2 harness's config folder; setup's trust and marketplace-pin probes read `config.toml` there, else `~/.codex` |
| `AFK_WORKTREE_OWNER` | `scripts/worktree_owner.py` | `<pid>:<creation time>` of the harness that owns a worktree; set by `hooks/run-hook.py` for the creation handler, read by the owner record |
| `CLAUDE_PID` | `scripts/worktree_owner.py` (named by `owner_pid_env` in `hooks/lib/providers/claude.json`) | the H-1 harness process id, used as the owner of a worktree it creates |
| `HERDR_ENV`, `HERDR_PANE_ID` | `hooks/lib/h2_move.py`, `hooks/lib/occupancy.py`, `scripts/afk-move.py` | set by herdr inside its panes; the H-2 move types `/cd` into that pane |
| `AFK_HOOK_DEADLINE` | `hooks/run-hook.py` (sets), `scripts/remove-worktree.py` (reads) | Unix time in seconds at which the launcher kills a handler that runs under `--deadline`; worktree cleanup fits each git call inside it and keeps the worktree when time runs out; not for humans to set |
| `HERDR_TAB_ID` | `hooks/lib/occupancy.py` | with `HERDR_ENV=1`, sessions in one herdr tab share a worktree group |
| `AFK_WORKTREE_GROUP` | `hooks/lib/occupancy.py` | names a team whose sessions may share one linked worktree; set by the human or launcher |
| `AFK_WAIT_POLL` | `scripts/remove-worktree.py` | seconds between the session-end waiter's checks of the harness process (default 2; tests lower it) |
| `AFK_WORKTREE_PATH`, `AFK_WORKTREE_BRANCH` | `scripts/create-worktree` (sets), the repository's `WorktreeCreated` scripts (read) | the new worktree's path and branch, passed to each repository setup script (`CONFIG.md`) |
| `HERDR_BIN_PATH` | `scripts/afk-move.py` | the herdr binary to call instead of the one on `PATH` |
| `GIT_DIR` | `hooks/branch-name-gate.sh` | exported by git to its hooks; the gate reads the shared git folder from it to find a sync authorization with no subprocess |
| `AFK_WORKTREE_OP` | `hooks/git-backstop.py` callers (`hooks/branch-name-gate.sh`, `hooks/precommit-gates.sh`) | set to `1` by the plugin's own worktree scripts so their git calls pass the backstop; not for humans to set |
| `LESSON_LEDGER_DISABLE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | disable lesson-ledger writes/reads (kill switch) |
| `LESSON_LEDGER_FILE` | `hooks/lesson-append.sh`, `hooks/lesson-digest.sh` | relocate the lesson ledger (default: main-checkout `.claude/lessons/LEDGER.jsonl`) |

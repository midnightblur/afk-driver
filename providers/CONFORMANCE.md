# Native harness conformance

This ledger records live probes for the committed plugin tree. `CAPABILITIES.md` owns degradation. `PROVIDERS.md` owns provider mappings.

## Run metadata

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-02 | 2026-09-02 (probe rounds 1-4) |
| Version | 2.1.257 | 0.152.0 (confirmed live, meets the minimum tested version) |
| Install | Enabled plugin, this session | Installed and enabled from a cache refreshed at round 4; every probe re-run against that cache |

## Probe ledger

| Probe | Claude Code | Codex CLI | Evidence |
|---|---|---|---|
| Native manifest loads | pass 2026-09-01 | pass 2026-09-01 | Second harness: remove + add refreshed the cache, which then carried `.codex-plugin/plugin.json` with no unknown-field warning |
| 40 `/afk:<x>` skills load | pass 2026-09-01 (38 listed) | pass 2026-09-01 (40 listed) | Counts differ by harness listing rules, not by catalog: 40 manifest entries = 38 model-visible + `harvest` (`disable-model-invocation: true`) + `diagnose` (absent from the first harness's model-visible listing before this change too — its own open item). The second harness lists all 40, no duplicates, no hyphenated mirrors, and the `$`-prefixed form invokes one |
| No generated mirror skills | n/a | pass 2026-09-01 | Zero hyphenated mirror names in the catalog |
| Shared hooks load and are trusted | pass 2026-09-01 | pass 2026-09-02 (round 3) | Round 1 failed on CRLF in the cached handlers, round 2 on the shell a bare `bash` resolved to. With LF pinning and the launcher, the handlers run natively on both harnesses |
| SessionStart envelope and environment names | pass 2026-09-01 | pass 2026-09-02 (round 2) | Second harness, instrumented capture: `CLAUDECODE` unset, `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA`/`PLUGIN_ROOT`/`PLUGIN_DATA` set, `CLAUDE_PROJECT_DIR` unset — the adapter order (native root before compatibility markers) is the correct one. Round 2 re-ran it against the refreshed cache and the three provider functions returned `provider=codex`, the native cache root, the native data path, exit 0. Envelope keys carry the shared set plus `model`, `permission_mode`, `turn_id` |
| CrowdStrike guard denies a system-root recursive scan | pass 2026-09-01 | pass 2026-09-02 (round 3) | Second harness, native session: the exact denial text surfaced and the command never executed |
| Stop gates block after a plugin edit | pass 2026-09-01 | pass 2026-09-02 (round 4) | Second harness, native session, no trust bypass: an unregistered scratch skill produced `Stop Blocked` carrying the full native-contract reason, and it kept blocking while the tree stayed invalid. Rounds 1-3 failed in turn on CRLF handlers, the shell a bare `bash` resolved to, and a verdict that travelled only as stderr plus exit 2 |
| Shared Jira MCP tool is callable | pass 2026-09-01 | pass 2026-09-02 (round 3) | Second harness: server up with all nine tools once the bootstrap stopped relying on an inherited environment. Tool spelling there is `mcp__jira__jira_search` — the bare server-name prefix, the same spelling a non-plugin registration produces, which is why skills call the bare tool names |
| `afk-reader` returns a cited digest | pass 2026-09-01 | pass 2026-09-01 | Second harness: all four stubs copied byte-identical, each resolved its role Markdown through the plugin cache, and the read-only role refused the write |
| `afk-tracer` closes a partition and writes only its fragment | pass 2026-09-05 | **unproven** | First harness: the role ran read-only against the plugin tree, wrote its fragment to the named scratch path, and touched no tracked file. Not yet run on the second harness; its stub declares the same write-scoped sandbox the runner role uses |
| Agent sandbox and write boundaries | pass 2026-09-01 | pass 2026-09-01 | Read-only role refused on both harnesses; the target file did not exist afterwards |
| Same-child continuation | pass 2026-09-01 | pass 2026-09-01 | Both harnesses reached the same child with its nonce intact — `DELEGATION.md` may claim continuation on both |
| Cache refresh after source-only change | n/a | pass 2026-09-01 | Minimum sequence: re-run the plugin add, then start a new session. Removal first is not required |
| Script-only hook change trust behavior | n/a | pass 2026-09-01 | Editing a referenced script body left the trust hash unchanged and raised no new prompt — trust covers the handler definition, not the script it runs. Security consequence: an approved handler keeps running whatever its script later says, so the shell handlers are gated content, and the pre-commit and Stop gates are the control | Round 4 recording nuance: a trust prompt (8 hooks) did appear on the second harness, and it is consistent with this row rather than against it — round 3 had run with the trust bypass, so the command-definition change that introduced the launcher had never been persisted on that machine. The prompt was the delayed approval for those handler definitions; the later script-body-only change raised none.
| Disable or uninstall leaves repository inert | pass (static) 2026-09-01 | pass 2026-09-01 | Second harness: after removal, zero skills, agents, MCP tools or plugin hooks, and no tracked repository file was touched. Caveat: pre-native ignored mirrors survive on a machine that once had them — the setup register's stale-activation entry offers the cleanup |
| Managed behavior install, refresh, and teardown | deterministic tests 2026-09-28; model receipt unverified | deterministic tests 2026-09-28; model receipt unverified | Native user files are the v1 transport. The `.afk/config.yaml` guard is model-evaluated. Setup tests prove hash, revision, migration, duplicate cleanup, and teardown. Live receipt after compaction remains unclaimed. |
| Native contract negative probe blocks | pass 2026-09-01 | n/a | Scratch skill with a `harness:` frontmatter key, a harness-tool reference, a fallback-free project-dir read, and a harness name: gate exit 2 naming all six findings; exit 0 after removal |
| Hook launcher runs handlers whatever the PATH | pass 2026-09-02 | pass 2026-09-02 (round 3) | First harness: the launcher ran the repository guard and carried its deny envelope, stayed silent on an absent handler, and still produced the denial when PATH held only the system directory (the WSL-stub case the second harness hit). Covered by `hooks/tests/hook-smoke.sh`; gate rule J rejected a hand-written bare-`bash` command with the expected diagnostic and exit 2, then passed once restored |
| Stop block decision object is honoured | pass 2026-09-02 | pass 2026-09-02 (round 4) | First harness, live rig: with the adapter exit code set to 0 so only the decision object could carry the verdict, an unregistered scratch skill produced a real Stop block carrying the gate findings. Second harness: same emission, `Stop Blocked` with the same reason. One emission serves both |
| Nested `AGENTS.md` reaches the model (main + subagent) | main **pass** + subagent **pass** 2026-09-23 (native) | **pending** (account usage limit) | See "Nested steering probe (2026-09-23)" below. Claude, real config: both the main session and a spawned subagent quoted a token that exists only in `sub/deep/AGENTS.md`, delivered natively as an attachment on the Read result (no hook). So Claude's injector mode stays `never`. Codex: plugin + hook config install and load with no parse error, but a model turn is blocked by the account usage limit, so injection could not be observed live |

## Unresolved items

- The `afk-tracer` row is green on the first harness and unproven on the second: the role
  shipped after round 4 and has not been run there. Its stub carries the same write-scoped
  sandbox as the runner role, whose row is green on both.
- Every other probe in this ledger is green on both harnesses as of round 4 (2026-09-02). The four failures it took to get there are kept as history in the evidence column: CRLF handlers, a bare `bash` that named the WSL stub, an MCP child started without the credential environment, and a Stop verdict that travelled only as stderr plus exit 2.
- `diagnose` is missing from the model-visible skill listing on the first harness although its frontmatter carries no hiding flag. Pre-dates the native migration; open as its own follow-up.


## Adapter proofs (round 5, 2026-09-03)

Round 5 is the first round run against a **release candidate installed from a
marketplace**, not against a working tree, and the first that exercises every
adapter kind against its real service. Both harnesses used isolated homes
(`CLAUDE_CONFIG_DIR` and `CODEX_HOME` under a scratch directory), so the
owner's own installs were untouched throughout.

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-03 | 2026-09-03 |
| Source | local directory marketplace on the candidate tree (`claude plugin marketplace add` has no `--ref`) | `codex plugin marketplace add midnightblur/afk-driver --ref rc/1.0.0` |
| Install | `claude plugin install afk@afk-toolkit --scope user -y` | `codex plugin add afk@afk-toolkit` |
| Inventory | 41 skills, 3 hook events, 1 MCP server (`tracker`) | installed, enabled, 1.0.0 |

The Codex install confirms the S1.5 question live: the marketplace at
`.agents/plugins/marketplace.json` in the **repository root** resolved, so no
`plugins/<name>/` prefix was needed anywhere in this plan.

`claude plugin details` prints `Agents (0)` for this plugin. It prints the same
for the old `afk@nak-marketplace` install whose four agents demonstrably work,
so it is a counting rule in that listing, not a regression. Agent parity is
proved by spawning, not by the inventory line.

Two operational facts this round established, both of which change how the
install is done rather than what is installed:

- `codex plugin marketplace add` on an **already-added** marketplace does not
  refetch: it says "already added" and keeps the old snapshot. Refreshing a
  Git marketplace to a newer commit of the same ref needs
  `codex plugin marketplace upgrade`, then a re-add of the plugin.
- An isolated harness home (`CLAUDE_CONFIG_DIR` under a scratch directory) has
  no credentials, so the session-level probes — the setup audit, spawning an
  agent, calling a tracker tool from inside a session — cannot run there. They
  are proved on the real install instead, which is where a user meets them; the
  isolated homes prove installation, inventory and every adapter that runs as a
  process.

### Every adapter kind, against its real service

Every live object is named `afk-toolkit-proof-2026-09-03`.

| Family / kind | Verbs proven | Object | Cleanup |
|---|---|---|---|
| defaults (no config at all) | `effective --json` = tracker `none`, forge `none`, notes `repo-files`, no build gates; `forge change-view` → `unsupported` exit 3; `tracker_create` → `unsupported` exit 3; `notes resolve` → `docs/afk/PROJ-1` | temporary Git repository | directory removed |
| notes / repo-files | `resolve`, `note-create`, `note-read`, `note-update` (replace and append), `note-link`, `note-delete`; a `../..` name refused, exit 2 | temporary Git repository | file deleted, tree empty |
| notes / obsidian | the same six against a scoped temporary vault; `note-link` answered a wikilink; the vault directory removed → `{"unavailable": true}` exit 4 | temporary vault | vault removed |
| notes / notion | dispatch answered the instruction object for each declared verb and `unsupported` exit 3 for an undeclared one; live page created under the configured parent, fetched, local copy deleted | two Notion pages | **not archived — see unresolved** |
| tracker / jira | all nine: `tracker_create`, `tracker_get`, `tracker_search`, `tracker_edit`, `tracker_comment`, `tracker_transitions`, `tracker_transition`, `tracker_attachments`, `tracker_changelog` | one issue in the live project | closed |
| tracker / github-issues | `tracker_create`, `tracker_get`, `tracker_search`, `tracker_edit`, `tracker_comment`, `tracker_transitions`, `tracker_transition`, `tracker_attachments`, `tracker_changelog` | issue #6 on `midnightblur/afk-driver` | closed |
| forge / github | `change-create-draft`, `change-view`, `change-diff`, `change-update-body`, `change-comment` (plain and inline), `thread-list`, `thread-reply`, `thread-resolve` (documented `unsupported`), `change-reviewers`, `change-ready`, `change-state`, `change-fetch`, `ci-status`, `ci-wait`, `change-close`, `auth-status` (`commit-changes`: stub-tested only — see Unresolved) | pull requests 7 and 8 | both closed, both branches deleted |
| forge / gitlab | the same set, with `thread-resolve` supported | one draft merge request on the monorepo | closed, branch deleted, pipeline canceled |
| build-gate / maven | `gate-discover` → `java-format`, `maven-compile`; `java-format` blocked an unformatted file exit 2 and passed exit 0 once formatted; `maven-compile` exit 0 in 148 s with its metrics line | one tracked Java file staged in a disposable worktree | worktree restored |
| build-gate / npm | `gate-discover` → `ui-lint`; exit 0 clean, exit 2 on a lint error, both with metrics lines | minimal workspace fixture | directory removed |

`ci-wait` on the GitHub side returned `{"status":"success","elapsed":45}` — the
release gate added in this release ran green on a real pull request, so
`.github/workflows/release-gate.yml` is proven live and not only by its author.

The npm row could not be proved against the monorepo's own UI workspace: that
checkout carries a stale per-project `node_modules` beside the hoisted one, and
the two ESLint copies crash each other before the gate is reached. That is a
condition of the developer checkout, not of the adapter, so the row was proved
against a minimal workspace fixture instead and the monorepo observation is
recorded here rather than hidden.

### What the live proofs found

Every one of these was invisible to the gates, the fixtures and the unit tests,
and every one is fixed in this release. They are listed because a proof round
that finds nothing has usually proved nothing.

1. `forge/none` and `tracker/none` still declared the `runner.type` of an early
   skeleton, `instruction`. `forge: none` therefore answered the agent with a
   file to read instead of refusing — the exact silent-degradation the `none`
   kinds exist to prevent.
2. The registry check could not see 1, because it only checked that the runner
   entry existed. It now also requires `runner.type` to be `cli` or
   `instruction` **and** to match the entry: an `instruction` entry must be a
   Markdown procedure, a `cli` entry must not be.
3. `instruction` dispatch answered any word at all, so a typo read back as a
   supported verb. It now checks the kind's own operations list.
4. Neither forge kind read `github.remote` / `gitlab.remote` — a key both
   declared and both documented, and neither consumed. Both now resolve the
   project from that remote's URL, through one shared
   `adapters/forge/project_from_remote.py`. They also now load the
   configuration at all: a forge script runs in its own process, so the
   `AFK_CFG_*` view its caller had loaded was never inherited.
5. An inline `change-comment` sent `commit_id` with a trailing carriage return
   on Windows — `read` keeps the CR of a CRLF line — and every inline comment
   failed with HTTP 422.
6. The same path printed a raw Python traceback when `gh pr view` was asked for
   a field it does not have.
7. `reviewers: ["someone"]` reached both CLIs as the literal string
   `['someone']`.
8. `tracker_search` rejected the comma-separated `fields` string that
   `tracker_get` requires, with a 400.
9. `tracker/github-issues` could not close an issue at all unless the
   repository had configured `state-labels`. `open` and `closed` are GitHub's
   own states and are now always available.
10. The same kind passed `gh`'s bare `'label' not found` through to the caller;
    it now names the label and says GitHub labels must exist first.
11. `glab mr close` refuses on a project that requires a passing pipeline
    before merging — it reports the *merge* precondition for a *close*.
    `change-close` now closes through the API, which has no such precondition.
12. The UI lint gate's workspace walk stopped one directory short of the
    repository root, and its `workspace-root` fallback could never match `.`.
    A repository whose only ESLint configuration sits at its root gated
    nothing and reported a pass.

### Unresolved

- The forge `commit-changes` verb and the `rationale-*` ledger commands are proven with stub `gh` / `glab` tools, a bare-repository remote, and a fake forge (`scripts/tests/test_forge_adapters.py`, `scripts/tests/test_rationale_ledger.py`). No live pull request or merge request has carried a rationale comment or a batch receipt yet. Run the live proof before the next release.
- The connected Notion MCP server exposes no archive or trash tool, so
  `notes/notion`'s `note-delete` cannot archive its mirror. This is now
  documented in that kind's `CONTRACT.md` and `NOTES.md` as a local delete plus
  `notion.error`, rather than promised and silently skipped. The two proof
  pages from this round are still in the workspace, retitled to say they are
  safe to archive. Archive requested through the release owner, who has the
  workspace tools this server does not expose.

### Decisions the extraction plan did not name

The plan required that a choice it was silent on be made consistently with its
own boundary and recorded here.

- The originating monorepo carried a second copy of the Jira MCP server, at
  `tools/payable/ai-agents/harness/mcp-servers/jira/`, beside the copy inside
  the plugin. Its only referrer was the harness README that the extraction
  branch rewrites, and the setup register's own row already pointed at the
  plugin copy. The boundary gives this toolkit the tracker MCP server together
  with its Jira adapter, so the harness copy is residue of the era before that
  line existed and the extraction branch deletes it. Nothing in the monorepo
  reads it, and nothing here depends on the monorepo.

### What installing on a real second harness found

Round 5 installed on both harnesses but proved the tracker MCP server on only
one, because the isolated Codex home could not authenticate far enough to reach
a tool call. Installing v1.0.0 on the owner's real Codex CLI closed that gap and
immediately failed: a session had no `tracker_*` tool at all.

The evidence was the harness's own start-up log, not a deduction. It listed the
server among the six it had registered, and one line later:

```
MCP server stderr (python): afk tracker MCP: mcp-servers\tracker\server.py
not found. Pass the plugin root as the first argument, or export
CLAUDE_PLUGIN_ROOT (Claude) or PLUGIN_ROOT (Codex).
```

Codex CLI expands no placeholder inside an `args` entry and exports no
equivalent variable, so the launcher was handed `${PLUGIN_ROOT}` as a literal
string. Claude Code does expand it, which is why every gate, all eighty tests
and four earlier proof rounds passed: the failure needed the other harness to
exist at all. Two bugs were stacked — the launcher could not locate itself, and
the server resolved the unexpanded placeholder into a relative path rather than
rejecting it. Both are fixed in v1.0.1.

**Deviation from the plan, recorded because it is one.** The plan forbade a
cache search at MCP start-up: a search can find a stale copy as readily as the
live one, so the registration passes the root and the server never looks. One
harness makes that impossible. The launcher therefore searches, and the search
is bounded to the narrowest thing that still works:

- an explicit first argument wins whenever it is present and is not an
  unexpanded placeholder;
- then `AFK_PLUGIN_ROOT`, `CLAUDE_PLUGIN_ROOT`, `PLUGIN_ROOT`, in that order;
- only when all of those are absent does it look, and then only at four fixed
  plugin-directory shapes one level under the user's home directory, each tried
  with a dotted and an undotted harness segment because glob never matches a
  leading dot.

It never recurses, never starts from a filesystem root, and never leaves the
user's home directory. The newest match of each shape wins, so a stale older
version loses to the current one.

`v1.0.2` states in the changelog that v1.0.0 does not work on Codex CLI and that
a user on that harness needs v1.0.1 or later.

### Marketplace pins, corrected by running the commands

`claude plugin marketplace add --help` documents no ref option, and the round-5
table recorded that it has none. It does: `<owner>/<repo>@<tag>` pins it, and the
marketplace checkout then sits detached at that tag. Both harnesses pin.

Neither `claude plugin marketplace update` nor `codex plugin marketplace upgrade`
moves a marketplace off the tag it was pinned to — both refresh within the pin.
Moving to a later release means removing the marketplace, adding it again at the
new tag, and reinstalling the plugin. Round 5's note that `codex plugin
marketplace add` does not refresh an already-added marketplace stands, and this
is the fuller rule it was one case of.

### The cutover, on the owner's own harnesses

| | Claude Code | Codex CLI |
|---|---|---|
| `afk-toolkit` | 1.0.1, user scope, enabled | 1.0.1, installed and enabled |
| Old `afk@nak-marketplace` | uninstalled, marketplace removed | uninstalled, marketplace removed |
| Residue | none: no `nak-marketplace` string in settings, `known_marketplaces.json` or `installed_plugins.json` | none: eight `hooks.state` trust tables dropped by parsing the file and re-parsing the result, four agent stubs deleted only after each was confirmed to carry the old install's marker, and the plugin cache directory removed after its path was resolved and confirmed to sit under the harness's own cache |
| Agent stubs | — | `afk-afk-{implementor,reader,runner,runner-lite}.toml`, plugin root substituted; the unrelated `mr-reviewer.toml` carries no marker and was left alone |
| Live tracker proof | round 5 | `tracker_get` on a real ticket in the configured project returns its summary and status; zero start failures in the session log, where there had been three |
| Live agent proof | round 5 | `afk-afk-reader` spawned and returned `LANGUAGE.md`'s first heading verbatim |

### H2, and why `unsupported` is not a failure

`tracker_get` was proven against the real service on the second harness in the
1.0.1 round: a call on a real ticket key returned its summary and status, with
zero start failures in the session log where there had been three. That is the
positive proof for `H2`, and it is not re-run per audit.

A later audit ran from a working directory with no `.afk/config.yaml`, where the
tracker resolves to `none` and `tracker_get` answers `unsupported`. It recorded
that as a failed row. It is the opposite: a `none` adapter answering
`unsupported` is the adapter contract doing its job, and the row had simply
assumed a tracker exists. `H2` and `O7`'s tracker leg are conditional from 1.0.7,
the way `C3` and `C3b` already were. The lesson generalizes past this row — an
adapter family with a `none` member needs every probe that touches it to say
what `none` means for that probe.

### What an upgrade does and does not invalidate

Established by upgrading 1.0.5 → 1.0.6 on the second harness: marketplace
removed, re-added at the new tag, plugin reinstalled.

| | Survived the upgrade | Why |
|---|---|---|
| Hook trust (8 `hooks.state` entries) | yes, all 8, hashes unchanged | the key is `<marketplace>:hooks/hooks.codex.json:<event>:<i>:<j>` and the value is a hash of the definition. Neither names the installed path, so a version bump that changes no hook definition changes no key and no hash. |
| Agent TOML stubs (4) | no | each holds the installed plugin root, which carries the version, so every upgrade leaves them naming a directory that is gone (the 1.0.3 defect). `/afk:setup` rewrites them. |

So the two look alike at install time and behave oppositely afterwards. A
release that touches `hooks/hooks.codex.json` will ask the human to trust the
hooks again; one that does not, will not. Both facts are in the README beside
the install block, because the cost of guessing wrong is a harness whose gates
silently do not run.

## Design-silent choices — worktree provisioning (1.0.11)

Where the agreed design did not say, these are the choices taken and the reason,
so a later reader does not re-open them as accidents.

| Choice | Taken | Why |
|---|---|---|
| How a kind is invoked | `gates.sh worktree-provision '<json>'`, not the script file | `adapter.json`'s `runner` is the declared entry for every other verb; a second, undeclared entry path would make the descriptor untrue. A kind without the verb answers exit 3, which the driver already treats as a skip. |
| Where the copy defaults live | `afk-config.py` `DEFAULTS` | the list is then in the configuration view every reader shares, so `afk-config.py get` and the shell view agree with the script. Per-kind defaults stay in their adapter, which is the only thing that knows them. |
| How an adapter sees configuration | the driver exports every `AFK_CFG_*` before dispatch | adapters run as subprocesses here, and the shell view exports plain variables that a subprocess would not inherit. |
| The flag name on `create-worktree` | `--force-provision` | its own `--force` would read as forcing the worktree itself, which it does not do. |
| When a marker is written | only when the adapter returned a fingerprint | a marker with nothing to compare against would suppress a later run without being able to say whether anything changed. |
| Per-worktree state in a copied directory | still excluded by name (`TODO.md`) | it is the toolkit's own per-worktree state, not build state, so it does not belong to any adapter. |

## Nested steering probe (2026-09-23)

Live probes for the `nested_steering` capability (P3 of the AGENTS.md-standard
plan). The authoritative Claude run used the **real** `~/.claude` config (config
read only, never written; installed `afk@afk-toolkit` 1.5.0 has no injector). The
Codex run used a sandbox `CODEX_HOME` with `auth.json` copied in and deleted
after. An earlier Claude sandbox run is recorded below as superseded.

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-23 | 2026-09-23 |
| Version | 2.1.280 (installed `afk@afk-toolkit` 1.5.0) | codex-cli 0.155.1 |
| Home | real `~/.claude` (read only); superseded earlier run in a scratch `CLAUDE_CONFIG_DIR` | scratch `CODEX_HOME`, `auth.json` copied in, deleted after |

Fixture: a throwaway Git repo with a root `AGENTS.md` (token `ROOT-OK`), a root
`CLAUDE.md` bridging `@AGENTS.md`, and a nested `sub/deep/AGENTS.md` carrying a
unique nonsense token that appears nowhere else, plus a `sub/deep/x.txt`.

### Claude Code

Authoritative result is the **real-config** run: the main session, real
`~/.claude/settings.json` holding `instructionFiles=claude-md-and-agents-md`,
the installed `afk@afk-toolkit` 1.5.0 (which has **no** nested injector), the
same fixture `scratchpad/nsfix`.

- **Control — root load / setting dependence.** `instructionFiles=claude-md-and-agents-md`
  answers `ROOT-OK` through the `@AGENTS.md` bridge. Forcing `--settings`
  `instructionFiles=claude-md` returns `NONE` for the nested token while
  `ROOT-OK` still appears. The nested read depends only on the setting, so it is
  the harness's built-in `AGENTS.md` support, not any hook of ours.
- **Probe (a) — native nested load, main session: PASS.** The main session read
  `sub/deep/x.txt`, then reported the nested token `ZORBLEQ-...` attributed to
  an attachment on the Read result. The nested `AGENTS.md` is delivered
  natively once a Read touches its directory.
- **Probe (b) — subagent native lazy load: PASS.** The main session spawned one
  general-purpose subagent that read `sub/deep/x.txt`; the subagent quoted the
  same nested token from the attachment on its Read result. A Claude subagent
  **does** lazy-load a nested `AGENTS.md` natively.
- **Envelope shape.** A scratch capture hook confirmed a subagent's own
  `PostToolUse` envelope carries `agent_id` (and `agent_type`); the main-session
  `PostToolUse` for the `Agent`/`Task` tool call carries **no** `agent_id`. This
  is the correct discriminator for `agent-only`, kept as machinery — see below.

**Amendment (P3.7) — NOT taken.** Because (a) and (b) both pass natively,
`claude.sh` `afk_claude_nested_inject_mode` stays `never`: selecting `agent-only`
would inject a nested `AGENTS.md` a subagent already has natively, once from the
hook and once from the native attachment. `afk_claude_nested_inject_rules` stays
`0` (Claude reads `.claude/rules` `paths:` natively). The `agent-only` mode is
still implemented and tested — see "agent-only machinery" — for a future harness
whose subagents do not lazy-load; no shipped provider selects it.

**agent-only machinery (not selected for any shipped provider).** The
`nested_steering.py` `agent-only` branch (inject only when the envelope carries
`agent_id`) is exercised directly — `--mode agent-only` with and without an
`agent_id` — by `scripts/tests/test_nested_steering.py::test_agent_only_gate` and
by a synthetic-mode row in `hooks/tests/hook-smoke.sh`. It is correct machinery,
kept for a harness that needs it; it is not Claude's policy.

**Superseded sandbox runs.** An earlier pass of these probes ran in a **fresh**
sandbox `CLAUDE_CONFIG_DIR` (credential copied in, deleted after) and reported
(a) and (b) as FAIL, which drove a wrong `agent-only` amendment. Those runs are
**superseded** by the real-config runs above. Hypothesis for the false FAIL
(inferred, not verified): the sandbox home was a **first session after install**,
which the docs list as a session where Claude reads `CLAUDE.md` files only, so
native nested `AGENTS.md` support was off while the `@AGENTS.md` bridge still
loaded the root — which matches the sandbox control still returning `ROOT-OK`.

**Probe-method rule.** Never run instruction-file probes in a fresh harness home:
the first session after an install or upgrade disables native `AGENTS.md`
support. Run a warm-up session first, or probe the real config with the plugin's
installed version stated.

**(c) — compaction survival: not run.** Not exercised live; moot for Claude
while its mode is `never`. Covered deterministically for the `codex` path by
`hooks/tests/hook-smoke.sh` and `scripts/tests/test_nested_steering.py`
(reset-then-re-arm). Open.

### Codex CLI — pending (account usage limit)

The temporary `CODEX_HOME` authenticated with the copied `auth.json`, the local
worktree was added as marketplace `afk-toolkit`, and `afk@afk-toolkit` installed
`enabled` at 1.6.1 with its source resolved to the worktree. `codex exec`
rendered its session banner (hooks loaded) with **no** parse or matcher warning
against `hooks/hooks.codex.json`, including the new `SessionStart`
`startup|clear` group and the `PostToolUse` / `PostCompact` nested-steering
groups. Every model turn then returned `You've hit your usage limit ... try
again at Sep 28th, 2026`, exit 1.

So the wiring is accepted locally, but the behavioral probe — injection reaching
a Codex main session and subagent, and observing which `SessionStart` matcher
fires — could **not** run. **Blocker:** the Codex ChatGPT account is over its
usage limit until 2026-09-28; no model turn is possible. Re-run after the reset:
the fixture and command sequence above reproduce it. The provider-agnostic
mechanics for `provider=codex` are meanwhile proven deterministically by
`hooks/tests/hook-smoke.sh` (codex injection, dedup, reset, rules leg) and
`scripts/tests/test_nested_steering.py`.

Note on the `SessionStart` `startup|clear` matcher on Codex: even if that
harness does not recognize the matcher vocabulary, correctness is preserved —
the dedup marker tree is keyed by `session_id`, so a fresh Codex session gets
fresh markers regardless, and `PostCompact` still resets within a session. The
`SessionStart` reset is a belt-and-suspenders reset, not the only one. This is
recorded as the reason the pending Codex verdict does not gate the release.

## Add harness #N

1. Add the harness row to the supported-harness registry in `PROVIDERS.md`.
2. Add `hooks/lib/providers/<name>.json` (the guard's provider facts: tool classes, move hint, worktree folder) and
   `hooks/lib/providers/<name>.sh` with the adapter functions
   `hooks/lib/provider.sh` dispatches by name: detect, priority, plugin root,
   plugin data, stop block code, and the plugin directory the harness manages.
   A missing one makes the managed-path answer undecidable, and every caller
   reads undecidable the safe way: `plugin-clone.sh` then says `installed`.
3. Add one envelope fixture per shared event under `hooks/tests/envelopes/<name>/`.
4. Add a native manifest twin only when the harness cannot consume an existing manifest.
5. Add unchanged agent-definition stubs when the harness cannot consume `agents/*.md`.
6. Add one `CAPABILITIES.md` provider column and one `PROVIDERS.md` mapping column.
7. Add one `/afk:setup` probe section.
8. Run `hooks/tests/hook-smoke.sh` and `hooks/native-contract-gate.sh`.
9. Install through the harness enable flag. Run every probe in this ledger.
10. Record version, date, commands, verdicts, and unresolved capabilities here.
11. Confirm no skill prose changed for the harness.

## Pane-agent probes (2026-09-30)

A pane agent is an agent session that herdr starts in its own terminal pane with `herdr agent start`. Host: Windows 11, Claude Code 2.1.285, Codex CLI 0.159.0, herdr 0.9.1. Both harnesses ran the installed plugin 1.9.0 from their plugin caches, not this worktree. Every probe pane started in this worktree.

Launch lines (`<probe>` is a probe folder in the operator's scratchpad):

- Claude Code: `herdr agent start <name> --kind claude --pane <pane> -- --model claude-opus-4-8 --effort high --permission-mode auto --add-dir <scratchpad> --debug-file <probe>/debug.log --session-id <uuid> --settings <probe>/settings.json "<brief>"`. The settings file adds probe hooks for SessionStart, Stop, SubagentStop and PreCompact. Each probe hook appends one line (event, source, session id, nonce) to a marks file; a SessionStart probe hook also prints its nonce.
- Codex CLI: `herdr agent start <name> --kind codex --pane <pane> -- --no-daemon -c check_for_update_on_startup=false --approve-for-me --add-dir <scratchpad> -m gpt-5.6-terra "<brief>"`. On this host every shell call of this launch failed with `Failed to create unified exec process: helper_unknown_error: setup refresh had errors` (Windows sandbox setup). A relaunch with `--dangerously-bypass-approvals-and-sandbox` was refused by the permission classifier of the launching session and was not retried. Codex probes therefore use tool-free tasks, the session rollout (`~/.codex/sessions/`), the log database (`~/.codex/logs_2.sqlite`) and the terminal screen. Re-probe 2026-10-06, Codex CLI 0.160.0, plugin 1.12.0, same launch line without `-m` (model GPT-5.6-Sol): the shell worked, so the rows marked 2026-10-06 replace the no-shell cells. The sandbox shell's Git `usr/bin/bash.exe` started with no `/usr/bin` on `PATH` (`env: command not found`, `dirname: command not found`); the probe scripts then exported `PATH=/usr/bin:/bin:$PATH`.
- Each pane was split with `herdr pane split --env GATE_METRICS_FILE=<probe>/gate-metrics.jsonl`, so the plugin Stop gates write one metrics line per gate.

| Probe | Claude Code | Codex CLI | Evidence |
|---|---|---|---|
| SessionStart in a pane agent: fires, output reaches the agent, re-fires on resume, clear and compaction, hooks file found | pass 2026-09-30 | fires at startup, resume and clear: pass 2026-09-30; output reaches the agent: **unproven**; compaction: no SessionStart seen | Claude: probe marks `SessionStart|startup|<session>`; the agent quoted `PROBE-SessionStart-B nonce=0b581de0` and `PROBE-SessionStart-A nonce=b76e19e1` from its start context, matching the marks. Outputs arrive in finish order (B, BIG, A), not in configuration order (A, B, BIG). A 23.9 KB output arrived as `Output too large (23.9KB)` with a saved file and a preview of lines 001-032; its last line was not in context. Re-fire: marks with source `resume` after `claude --resume <id>`, `compact` after `/compact` (after a `PreCompact` mark), `clear` after `/clear` (new session id). Subagents: the marks hold 11 `SubagentStop` marks and no `SessionStart` mark at any subagent start. Hooks file: debug log `Read hooks.json for plugin afk (enabled=true): <home>\.claude\plugins\cache\afk-toolkit\afk\1.9.0\hooks\hooks.json`. The plugin's own SessionStart handlers logged `timed out after 15000ms` in these panes. Codex: screen `Hook failed └ hook timed out after 15s` at startup, after `codex resume <id>`, and at the first prompt after `/clear`. After `/clear` the new thread's rollout starts at 17:48:22 and records the prompt at 17:48:38, 16 s later; herdr then reported the new thread id for the pane. After `/compact` the screen showed `Context compacted · 26s`, then `Running hooks`, and no SessionStart line. Codex keys plugin hook trust as `afk@afk-toolkit:hooks/hooks.codex.json:session_start:<group>:<index>` under `[hooks.state]` in `~/.codex/config.toml`, so it reads the installed plugin's `hooks/hooks.codex.json`. The agent reported `No session-start lines began with PROBE-. No other hook text was received at session start.` A nonce-printing Codex hook needs a new trust entry, which these probes do not grant. |
| Plugin MCP tracker server in a pane agent, and the server's start directory | pass 2026-09-30 | registered: pass 2026-09-30; tools in the model's turn: fail 2026-09-30 | Claude: the agent held 9 `mcp__plugin_afk_tracker__*` tools; `tracker_transitions` with key `"1"` returned `open`, `closed`, `dev-pending` (`status:dev-pending`), `in-review` (`status:in-review`), `done` (`status:done`). Codex: `/mcp` printed `tracker: connected (9 tools)`; asked to call the tool, the agent replied `NO-TRACKER; MCP servers: cua_repl`; asked to search for it, `Tools seen: none. NO-TRACKER`; log `using cached MCP catalog without waiting for startup server_name=tracker`. Start directory: a read-only process query (`psutil` `Process.cwd()`) showed the tracker `python.exe` child of a pane's `claude.exe` and of a pane's `codex.exe resume <id>` with `cwd= <this worktree>`, the pane's launch directory. Tracker servers of sessions launched in a scratch directory had that scratch directory as `cwd`. `mcp-servers/tracker/server.py:63` loads configuration from `Path.cwd()`. |
| Provider marker variables in a pane agent's processes | pass 2026-09-30 | pass 2026-10-06; the plugin's provider check answers `unknown` in the agent's shell | Claude: the agent's shell printed `CLAUDECODE=1`, `CLAUDE_CODE_ENTRYPOINT=cli`, `CLAUDE_CODE_CHILD_SESSION=1` and `CLAUDE_CODE_SESSION_ID=<id>`, and no `CLAUDE_PLUGIN_ROOT`, `AFK_PLUGIN_ROOT` or `PLUGIN_ROOT`. Sourcing the plugin's `hooks/lib/provider.sh` in that shell gave `provider=claude` and `agent_session=yes`. A probe hook process also carried `CLAUDE_PROJECT_DIR` and `CLAUDE_ENV_FILE`. On both harnesses a variable set with `herdr pane split --env` reached the Stop hook processes (`GATE_METRICS_FILE`, metrics lines below). Codex 2026-09-30: every shell call failed with the sandbox error above. Codex 2026-10-06: the agent's shell carried `CODEX_CI=1`, `CODEX_SANDBOX_NETWORK_DISABLED=1`, `CODEX_SESSION_ID=<id>`, `CODEX_THREAD_ID=<id>` (same value), `CODEX_VERSION=0.160.0`, and `HERDR_ENV=1`, `HERDR_PANE_ID`, `HERDR_TAB_ID`, `HERDR_WORKSPACE_ID`, `HERDR_SOCKET_PATH`, `HERDR_BIN_PATH`; no `PLUGIN_ROOT`, `AFK_*` or `CLAUDE*` name. Sourcing the plugin's `hooks/lib/provider.sh` gave `provider=unknown` and `agent_session=no`: `hooks/lib/providers/codex.sh` detects on `PLUGIN_ROOT`, which only hook processes carry. |
| Stop fires in a pane session and runs the plugin Stop gates | pass 2026-09-30 | pass 2026-09-30 | Claude: metrics `{"ts":"2026-09-30T15:43:15Z","gate":"context","result":"pass","duration_ms":12173,"changed":92}`, one line per turn; debug log `Hook Stop [python "<home>\.claude\plugins\cache\afk-toolkit\afk\1.9.0/hooks/run-hook.py" plugin stop-gates.sh] (plugin afk@afk-toolkit) timed out after 300000ms`. At a subagent's end only the `SubagentStop` probe mark appeared, with no metrics line. Codex: metrics `{"ts":"2026-09-30T15:34:12Z","gate":"context","result":"pass","duration_ms":8938,"changed":92}`, one line per turn, and the screen line `Hook failed └ hook timed out after 300s` after each turn. On both harnesses the gate run passed the 300 s hook limit in this worktree (92 changed files); only the `context` gate wrote a line. |
| A pane agent resolves the plugin's named agent definitions | pass 2026-09-30 | pass 2026-09-30 | Claude: the Agent tool accepted `afk:afk-reader` and `afk:afk-implementor`; subagent metadata `"agentType":"afk:afk-reader"` and `"agentType":"afk:afk-implementor"`. Codex: `spawn_agent` accepted `agent_type` `afk-afk-reader` and `afk-afk-implementor`; each sub-agent rollout `session_meta` carries `agent_role` with that name. |
| A pinned model name runs exactly that model | pass 2026-09-30 | pass 2026-09-30 | Claude: `--model claude-opus-4-8` gave `"model":"claude-opus-4-8"` on 54 of 54 assistant messages. Agent pins are aliases: `afk-implementor` (`model: opus`) ran `claude-opus-4-8`, the session's model; `afk-reader` (`model: sonnet`) ran `claude-sonnet-5-5`. Codex: `-m gpt-5.6-terra` gave `turn_context` `model: gpt-5.6-terra`. The installed `afk-afk-implementor.toml` pin `model = "gpt-6-sol"` gave a sub-agent `turn_context` `gpt-6-sol`; the `afk-afk-reader.toml` pin `gpt-5.6-terra` gave `gpt-5.6-terra`. The reader stub's `sandbox_mode = "read-only"` did not apply: that sub-agent ran `workspace-write`. |
| A pane agent reads scratchpad and plugin cache files | pass 2026-09-30 | pass 2026-10-06 (shell) | Claude, launched with `--add-dir <scratchpad>`: the Read tool and the shell each read a file in the added scratchpad (`p7-7147ebaa1c`), a file in another session's scratchpad that was not added (`# Brief: run one seam investigation to a validated staging ledger`), and the installed plugin's `skills/afk/review/checklists/PRECEDENCE.md` (`# Baseline precedence — pasted with every checklist`). Codex 2026-09-30: `I can't open that local file without using the shell, and no other available tool provides filesystem access.` Codex 2026-10-06, launched with `--add-dir <scratchpad>`: the shell read the added scratchpad's nonce file (`nonce-cxc-1790828431`), the other session's `ORCH-BRIEF.md` (`# Brief: run one seam investigation to a validated staging ledger`) and the installed plugin 1.12.0's `PRECEDENCE.md` (`# Baseline precedence — pasted with every checklist`). |
| A busy pane agent receives several sent messages in order | pass 2026-09-30 | pass 2026-09-30 | Claude: 3 `herdr agent prompt` messages at 15:50:30, :34 and :37 during a Stop hook (screen `Press up to edit queued messages`) arrived at 15:55:21 as 3 user messages in send order; the agent wrote `MSG-1`, `MSG-2`, `MSG-3`. Codex: 3 messages at 16:44:09, :12 and :14 during a turn (screen `Messages to be submitted after next tool call`) arrived at 16:49:05.054, .094 and .101 in send order, after the 300 s Stop hook; reply `MSG-1 MSG-2 MSG-3`. |
| A blocked pane agent stays live and takes a relayed answer; a resumed session keeps its context | pass 2026-09-30 | pass 2026-09-30 | Claude: the agent asked a question at 16:21Z and ended its turn; a relayed answer at 16:24:56, after about 4 min idle, gave `answer=green`. After `herdr pane close`, `claude --resume <id>` in a new pane answered `resume-word=word-9924a0`, a word it had read from a file that was then moved away. Codex: question `P9-Q: which colour?` at 17:15:56Z, turn complete at 17:20:57; answer `green` at 17:24:57 gave `answer=green` at 17:25:08. After `herdr pane close`, `codex resume <id> --no-daemon -c check_for_update_on_startup=false --approve-for-me --add-dir <scratchpad> -m gpt-5.6-terra "<prompt>"` in a new pane answered `resume-word=word-47c79b`, a word given only in the conversation. The same command through `herdr agent start <name> --kind codex -- resume <id> …` left no pane; typed with `herdr pane run`, it worked. |
| A subagent's file write is refused, and which paths the refusal covers | pass 2026-09-30: Write tool refuses report-like names | pass 2026-09-30: no refusal | Claude: a subagent's Write calls for `REPORT.md`, `SUMMARY.md` and `findings.md` failed with `Subagents should return findings as text, not write report files. Include this content in your final response instead.` The same subagent wrote `0001-x-adversary.md`, `notes.md`, `fragment.json`, `COVERAGE.json` and `evidence.txt` with Write, and `bash-REPORT.md` with the shell; the main agent wrote `main-REPORT.md` with Write. Codex: a default sub-agent wrote `REPORT.md`, `SUMMARY.md`, `0001-x-adversary.md` and `fragment.json` with `apply_patch`, and the main agent wrote `main-REPORT.md`, with no refusal. |
| A capture command's run-time limit; a pane close and shell traps | pass 2026-09-30 | run-time limit: the call returns after 10 s, 2026-10-06; pane close: bash killed without a trapped signal, its child left running, 2026-10-06 | Claude: `bash <probe>/trap.sh cla bash-timeout 200` without a timeout parameter returned `Command did not complete within its 120s timeout and was moved to the background (ID: …)`; the trap file shows `start`, `finished-normally` 201.6 s later, then `EXIT`, so the command was not killed. A bare foreground `sleep 75` was refused: `Blocked: sleep 75 followed by: echo slept.` Pane close, agent pane: the agent ran `bash <probe>/trap.sh cla agent-close 600` (timeout 600000 ms); after `herdr pane close` the trap file got no `EXIT`, `TERM`, `INT` or `HUP` line, and the bash process and its `sleep 600` stayed alive; 600 s after start the trap file got `finished-normally`, then `EXIT`. Pane close, plain PowerShell pane running Git `bin/bash.exe <probe>/trap.sh plain pane-close 600`: after `herdr pane close` the process was gone within 10 s and the trap file got no line, so it was killed without a signal a trap catches. Codex 2026-10-06: `bash <probe>/trap.sh cxd shell-timeout 200` without a timeout argument returned after `wall_time_seconds=10.0114479`; the trap file holds only `start`. Asked for a 900000 ms timeout, the agent set 30000 ms, and after the call the screen read `1 background terminal running`. Pane close 26 s into `trap.sh cxe pane-close 900`: within 30 s the bash process was gone with no `EXIT`, `TERM`, `INT` or `HUP` line, and its `sleep.exe` stayed alive with no live parent process. That child belongs to the sandbox user: the operator's `Stop-Process` got `Access is denied`. `mkdir -p` on the probe folder printed `mkdir: cannot create directory 'C:/Users/mvu': Permission denied` though the folder existed. |

## Managed behavior receipt matrix

Native user files are the v1 transport. A generated block and a hook envelope
do not prove model receipt. Do not claim compaction survival until each harness
passes this matrix with the earliest decision turn showing the behavior.

| Session shape | Claude Code | Codex CLI |
|---|---|---|
| Default agent | pending | pending |
| Custom agent | pending | pending |
| Subagent | pending | pending |
| Fresh session | pending | pending |
| Resume | pending | pending |
| Clear | pending | pending |
| First turn after compaction | pending | pending |

Probe from a disposable plugin copy and disposable harness home. Add a temporary
behavior whose decision-turn response contains a nonce. Install its generated
block, start each session shape, and ask the matching nonce prompt. Record the
launch command, first decision-turn response, plugin root, revision, and body
hash. Remove the disposable home and run teardown after the probe.

## Protected-branch guard (2026-09-30)

Proof lives in the probe rows below and in `scripts/tests/`. Every row was run live
on 2026-09-29/30 (Windows 11, Git Bash, git 2.53, claude 2.1.285, codex-cli 0.159.0,
herdr 0.9.1) unless it says *source* or *inferred*. Live-only, not automated: the H-1
native move in every permission mode, and herdr's agent-kind detection through a wrapper.

| Probe | Result |
|---|---|
| P0-a H-2 `/cd` in herdr | The path must not be quoted: quotes become part of the path. An unquoted path with a space works. The conversation is kept: the session forks and history carries over. A worktree of a trusted repository needs no trust answer. Sent during a turn, `/cd` is refused (`'/cd' is disabled while a task is in progress`) and stays in the composer; the next typed text appends to it. A bash caller of `herdr agent prompt` must disable MSYS path conversion or call from python. The session id changes on `/cd`. |
| P0-c H-2 PreToolUse envelope | Fields `session_id, turn_id, cwd, hook_event_name, model, permission_mode, tool_name, tool_input, tool_use_id`; no `workdir`. Shell is `Bash` (`tool_input.command`); a patch is `apply_patch` with absolute Windows paths that may hold spaces. `HERDR_*` reaches the hook. SessionStart fires lazily at the first turn. |
| P0-d H-1 worktree events | `WorktreeCreate` and `WorktreeRemove` (input carries `worktree_path`) replace the native pair; no approval prompt in default mode, inside or outside `.claude/worktrees/`. Removal is delegated to the hook: the folder stays if the hook removes nothing. `-p` session end and the Keep choice fire no removal. `CLAUDE_PID` is the harness process. |
| P0-e git `reference-transaction` | A `prepared` veto aborts `commit`, `reset`, `merge`, `rebase` and the ref update of `checkout`/`switch`, but leaves the index and work tree switched on `checkout` and a rebase in progress. `git worktree add -b` emits the new branch and `ref:refs/heads/<b> HEAD` in the main checkout's context, so the backstop must let a fresh `worktrees/*/HEAD.lock` through. |
| P0-h detached helper from a hook | A helper spawned detached from an H-2 hook survives the hook's exit, waits for `idle`/`done` through `herdr agent get`, and types `/cd <path>` into its own pane. |
| P0-i untrusted plugin hook | Trust keys are positional: `[hooks.state."<plugin>@<marketplace>:hooks/hooks.codex.json:<event>:<group>:<handler>"] trusted_hash`; the hash covers event, matcher and handler, so inserting a group shifts every later key (inferred, not run on an upgraded install). The TUI shows "Hooks need review" at startup without the full-bypass flag. Under the full-bypass flag and under `exec` the hooks silently do not run. `/hooks` then `t` trusts them; `--dangerously-bypass-hook-trust` skips trust for one run. |
| P-2 H-2 deny shape | The H-2 harness treats PreToolUse exit 2 as a failed hook and runs the command. Exit 0 plus the `permissionDecision: deny` JSON blocks. The H-1 harness honours both. The guard and every plugin refusal therefore use exit 0 plus the JSON. |
| H-2 `SessionEnd` on `/cd` and exit | Fires on `/cd` with the old session id and the old `cwd`, on the next turn, and on exit with the current `cwd`; `reason` is `other` in both. A session that moves between two plugin worktrees has the one it left judged for removal. Codex 0.159.3 cuts a `SessionEnd` timeout to 3 s whatever the manifest says ("`SessionEnd` and `Interrupt` use `1` second by default and support up to `3` seconds", https://learn.chatgpt.com/docs/hooks), so it declares 3. A handler standing in the worktree returns in about 0.7 s and hands removal to a detached waiter; one judging a worktree it left removes it inline, which a large tree can push past 3 s (unverified: whether Codex then kills the handler; if it does, the leftover holds no work, since removal starts only after the clean and pushed check, and the human removes it by hand). |
| P-3 H-2 composer placeholder | An empty composer shows a rotating placeholder after the prompt glyph (`Ask Codex to do anything`). `herdr agent read --format ansi` paints the glyph bold (SGR 1) and the placeholder dim (SGR 2); typed text follows a reset and has no dim. The helper reads the ANSI pane and treats a dim composer line as empty. Captures: `scripts/tests/fixtures/codex-composer-empty.ansi` and `codex-composer-typed.ansi`. Herdr output is UTF-8: decoding it with the Windows code page corrupts the glyph. Live 2026-09-30, codex-cli 0.159.0 in an isolated `CODEX_HOME`. |
| Latency: login token | `gh auth token` costs about 0.15 s and avoids the second `gh api` process. Real `cli/cli` branch read on a quiet machine, 5 runs: CLI path median 0.92 s (min 0.65), token path median 0.71 s (min 0.66). `glab` has no token command, so GitLab keeps its single paginated CLI call. The CLI host flag: reading the CLI's hosts file costs 0.1 ms (no process); `ssh -G <alias>` costs about 66 ms and runs only for a non-public host the CLI does not list. |
| P-7 H-2 helper never typed `/cd` | The detached helper waited 3 x 40 s for an idle agent, then returned without typing; a slow turn answering the refusal outlasted it (inferred: the helper had no log, so the failing run cannot be replayed). The wait is now up to 10 minutes per attempt. Every move logs to `<git dir>/afk-worktrees/<name>.log`. Live, codex in a herdr pane, main checkout: the log shows `wait: agent status 'working'`, then `'idle'` 2 s later, `composer: ''`, `done: typed, no refusal after it`, and the pane reads `Working directory changed`. |
| P-6 H-1 `SessionEnd` and `/exit` | Claude 2.1.286 fires `SessionEnd` at `/exit` with `reason: prompt_input_exit` and `cwd` = the original checkout, even after a worktree move. A clean plugin worktree is removed at `/exit` in the TUI (3 of 3 live runs; `WorktreeRemove` fires before `SessionEnd`) and, after a headless `claude -p` run, about 20 s after exit. A dirty one gets Claude's own `Keeping worktree...` line and its `Resume this session with` hint; afk's kept report is not shown at exit, because the event names no worktree. It appears at the next `SessionStart`. Accepted AC-028 deviation on H-1. A `SessionEnd` whose `cwd` is inside a plugin worktree starts a detached waiter that removes it after the harness exits. |
| P-9 `SessionStart` user-visible message | The kept-worktree report goes out as `systemMessage` (the human) and `additionalContext` (the model) when the provider file sets `session_start_user_message`; `shown` is set after the report is printed. H-1 live (Claude 2.1.286 TUI, a kept record in a fresh checkout): the report text, including the remove command, is painted on screen at session start. H-2: the flag is set from the harness docs, not verified live; if its TUI paints nothing, the model still gets the report |
| P-10 move helper and an inherited pane id | Live (2026-09-30): a refusal run by a child process from the shell of a Claude TUI pane inherits `HERDR_PANE_ID` of that pane. The helper logged `pane <id> belongs to another agent (claude/<session>/<cwd>): nothing typed` and the pane received no input. `herdr agent get` reports `agent`, `agent_session.value` and `cwd` for the pane; the helper types only when kind = provider name, session matches when reported, and cwd = the refused session's cwd |
| H-2 `/cd` typing needs herdr session reporting | 2026-09-30, AC-013 at aef0a54: herdr learns an H-2 pane's session id only from its own `SessionStart` hook in the harness hooks config (`herdr integration install codex`; `herdr integration status` shows `codex: current`). Without it `owns_pane` sees no session and types nothing: accepted, fail-closed. The helper log says `herdr reports no session for pane <id>; install herdr's integration for codex to get the line typed`; the human types the printed `/cd` line. `/afk:setup` row C16 probes it |

| Choice | Taken | Why |
|---|---|---|
| `WorktreeCreate` and `WorktreeRemove` | shipped together | a harness that replaces its own creation must also replace its removal, or plugin-made worktrees are never cleaned |
| Hook order in the Codex manifest | guard last in `PreToolUse` | trust is positional, so earlier trusted entries keep their keys |
| H-2 creation | detached from the guard | the hook timeout is 30 s and a checkout plus provisioning can pass it |
| `/cd` retry | only after a refusal shown in the pane | typing twice into a session that already moved would break it |

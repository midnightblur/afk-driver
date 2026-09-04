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
| 40 `/afk-toolkit:<x>` skills load | pass 2026-09-01 (38 listed) | pass 2026-09-01 (40 listed) | Counts differ by harness listing rules, not by catalog: 40 manifest entries = 38 model-visible + `harvest` (`disable-model-invocation: true`) + `diagnose` (absent from the first harness's model-visible listing before this change too — its own open item). The second harness lists all 40, no duplicates, no hyphenated mirrors, and the `$`-prefixed form invokes one |
| No generated mirror skills | n/a | pass 2026-09-01 | Zero hyphenated mirror names in the catalog |
| Shared hooks load and are trusted | pass 2026-09-01 | pass 2026-09-02 (round 3) | Round 1 failed on CRLF in the cached handlers, round 2 on the shell a bare `bash` resolved to. With LF pinning and the launcher, the handlers run natively on both harnesses |
| SessionStart envelope and environment names | pass 2026-09-01 | pass 2026-09-02 (round 2) | Second harness, instrumented capture: `CLAUDECODE` unset, `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA`/`PLUGIN_ROOT`/`PLUGIN_DATA` set, `CLAUDE_PROJECT_DIR` unset — the adapter order (native root before compatibility markers) is the correct one. Round 2 re-ran it against the refreshed cache and the three provider functions returned `provider=codex`, the native cache root, the native data path, exit 0. Envelope keys carry the shared set plus `model`, `permission_mode`, `turn_id` |
| CrowdStrike guard denies a system-root recursive scan | pass 2026-09-01 | pass 2026-09-02 (round 3) | Second harness, native session: the exact denial text surfaced and the command never executed |
| Stop gates block after a plugin edit | pass 2026-09-01 | pass 2026-09-02 (round 4) | Second harness, native session, no trust bypass: an unregistered scratch skill produced `Stop Blocked` carrying the full native-contract reason, and it kept blocking while the tree stayed invalid. Rounds 1-3 failed in turn on CRLF handlers, the shell a bare `bash` resolved to, and a verdict that travelled only as stderr plus exit 2 |
| Shared Jira MCP tool is callable | pass 2026-09-01 | pass 2026-09-02 (round 3) | Second harness: server up with all nine tools once the bootstrap stopped relying on an inherited environment. Tool spelling there is `mcp__jira__jira_search` — the bare server-name prefix, the same spelling a non-plugin registration produces, which is why skills call the bare tool names |
| `afk-reader` returns a cited digest | pass 2026-09-01 | pass 2026-09-01 | Second harness: all four stubs copied byte-identical, each resolved its role Markdown through the plugin cache, and the read-only role refused the write |
| Agent sandbox and write boundaries | pass 2026-09-01 | pass 2026-09-01 | Read-only role refused on both harnesses; the target file did not exist afterwards |
| Same-child continuation | pass 2026-09-01 | pass 2026-09-01 | Both harnesses reached the same child with its nonce intact — `DELEGATION.md` may claim continuation on both |
| Cache refresh after source-only change | n/a | pass 2026-09-01 | Minimum sequence: re-run the plugin add, then start a new session. Removal first is not required |
| Script-only hook change trust behavior | n/a | pass 2026-09-01 | Editing a referenced script body left the trust hash unchanged and raised no new prompt — trust covers the handler definition, not the script it runs. Security consequence: an approved handler keeps running whatever its script later says, so the shell handlers are gated content, and the pre-commit and Stop gates are the control | Round 4 recording nuance: a trust prompt (8 hooks) did appear on the second harness, and it is consistent with this row rather than against it — round 3 had run with the trust bypass, so the command-definition change that introduced the launcher had never been persisted on that machine. The prompt was the delayed approval for those handler definitions; the later script-body-only change raised none.
| Disable or uninstall leaves repository inert | pass (static) 2026-09-01 | pass 2026-09-01 | Second harness: after removal, zero skills, agents, MCP tools or plugin hooks, and no tracked repository file was touched. Caveat: pre-native ignored mirrors survive on a machine that once had them — the setup register's stale-activation entry offers the cleanup |
| Native contract negative probe blocks | pass 2026-09-01 | n/a | Scratch skill with a `harness:` frontmatter key, a harness-tool reference, a fallback-free project-dir read, and a harness name: gate exit 2 naming all six findings; exit 0 after removal |
| Hook launcher runs handlers whatever the PATH | pass 2026-09-02 | pass 2026-09-02 (round 3) | First harness: the launcher ran the repository guard and carried its deny envelope, stayed silent on an absent handler, and still produced the denial when PATH held only the system directory (the WSL-stub case the second harness hit). Covered by `hooks/tests/hook-smoke.sh`; gate rule J rejected a hand-written bare-`bash` command with the expected diagnostic and exit 2, then passed once restored |
| Stop block decision object is honoured | pass 2026-09-02 | pass 2026-09-02 (round 4) | First harness, live rig: with the adapter exit code set to 0 so only the decision object could carry the verdict, an unregistered scratch skill produced a real Stop block carrying the gate findings. Second harness: same emission, `Stop Blocked` with the same reason. One emission serves both |

## Unresolved items

- Every probe in this ledger is green on both harnesses as of round 4 (2026-09-02). The four failures it took to get there are kept as history in the evidence column: CRLF handlers, a bare `bash` that named the WSL stub, an MCP child started without the credential environment, and a Stop verdict that travelled only as stderr plus exit 2.
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
| Install | `claude plugin install afk-toolkit@afk-toolkit --scope user -y` | `codex plugin add afk-toolkit@afk-toolkit` |
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
| forge / github | `change-create-draft`, `change-view`, `change-diff`, `change-update-body`, `change-comment` (plain and inline), `thread-list`, `thread-reply`, `thread-resolve` (documented `unsupported`), `change-reviewers`, `change-ready`, `change-state`, `change-fetch`, `ci-status`, `ci-wait`, `change-close`, `auth-status` | pull requests 7 and 8 | both closed, both branches deleted |
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
| Agent stubs | — | `afk-toolkit-afk-{implementor,reader,runner,runner-lite}.toml`, plugin root substituted; the unrelated `mr-reviewer.toml` carries no marker and was left alone |
| Live tracker proof | round 5 | `tracker_get` on a real ticket in the configured project returns its summary and status; zero start failures in the session log, where there had been three |
| Live agent proof | round 5 | `afk-toolkit-afk-reader` spawned and returned `LANGUAGE.md`'s first heading verbatim |

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
| Agent TOML stubs (4) | no | each holds the installed plugin root, which carries the version, so every upgrade leaves them naming a directory that is gone (the 1.0.3 defect). `/afk-toolkit:setup` rewrites them. |

So the two look alike at install time and behave oppositely afterwards. A
release that touches `hooks/hooks.codex.json` will ask the human to trust the
hooks again; one that does not, will not. Both facts are in the README beside
the install block, because the cost of guessing wrong is a harness whose gates
silently do not run.

## Add harness #N

1. Add the harness row to the supported-harness registry in `PROVIDERS.md`.
2. Add `hooks/lib/providers/<name>.sh` with detect, root, and data functions.
3. Add one envelope fixture per shared event under `hooks/tests/envelopes/<name>/`.
4. Add a native manifest twin only when the harness cannot consume an existing manifest.
5. Add unchanged agent-definition stubs when the harness cannot consume `agents/*.md`.
6. Add one `CAPABILITIES.md` provider column and one `PROVIDERS.md` mapping column.
7. Add one `/afk-toolkit:setup` probe section.
8. Run `hooks/tests/hook-smoke.sh` and `hooks/native-contract-gate.sh`.
9. Install through the harness enable flag. Run every probe in this ledger.
10. Record version, date, commands, verdicts, and unresolved capabilities here.
11. Confirm no skill prose changed for the harness.

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

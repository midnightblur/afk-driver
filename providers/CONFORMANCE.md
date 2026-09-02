# Native harness conformance

This ledger records live probes for the committed plugin tree. `CAPABILITIES.md` owns degradation. `PROVIDERS.md` owns provider mappings.

## Run metadata

| Field | Claude Code | Codex CLI |
|---|---|---|
| Date | 2026-09-02 | 2026-09-02 (probe rounds 1-2) |
| Version | 2.1.257 | 0.152.0 (confirmed live, meets the minimum tested version) |
| Install | Enabled plugin, this session; reload owed after this change | Installed and enabled from a cache refreshed at round 2; re-probe round 3 owed for the three failures fixed since |

## Probe ledger

| Probe | Claude Code | Codex CLI | Evidence |
|---|---|---|---|
| Native manifest loads | pass 2026-09-01 | pass 2026-09-01 | Second harness: remove + add refreshed the cache, which then carried `.codex-plugin/plugin.json` with no unknown-field warning |
| 40 `/afk:<x>` skills load | pass 2026-09-01 (38 listed) | pass 2026-09-01 (40 listed) | Counts differ by harness listing rules, not by catalog: 40 manifest entries = 38 model-visible + `harvest` (`disable-model-invocation: true`) + `diagnose` (absent from the first harness's model-visible listing before this change too — its own open item). The second harness lists all 40, no duplicates, no hyphenated mirrors, and the `$`-prefixed form invokes one |
| No generated mirror skills | n/a | pass 2026-09-01 | Zero hyphenated mirror names in the catalog |
| Shared hooks load and are trusted | pass 2026-09-01 | FAIL 2026-09-02 (round 2) | Round 1: every cached shell handler carried CRLF — `syntax error near unexpected token $'do'`. LF pinning fixed that (round 2 verified `CRLF=0 LF=129` in the cache). Round 2 exposed the next layer: the commands said bare `bash`, which resolves to the system directory's WSL stub on that machine, so the handlers still never started (`hook: … Failed`). Fixed here by routing every command through `hooks/run-hook.py`; awaiting re-probe round 3 |
| SessionStart envelope and environment names | pass 2026-09-01 | pass 2026-09-02 (round 2) | Second harness, instrumented capture: `CLAUDECODE` unset, `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA`/`PLUGIN_ROOT`/`PLUGIN_DATA` set, `CLAUDE_PROJECT_DIR` unset — the adapter order (native root before compatibility markers) is the correct one. Round 2 re-ran it against the refreshed cache and the three provider functions returned `provider=codex`, the native cache root, the native data path, exit 0. Envelope keys carry the shared set plus `model`, `permission_mode`, `turn_id` |
| CrowdStrike guard denies a system-root recursive scan | pass 2026-09-01 | FAIL 2026-09-02 (round 2) | Second harness: still no native denial, but the guard itself is proven — run under an explicit Git Bash against the captured envelope it emitted the exact denial text, and a control hook carrying the same deny envelope was honoured, so the decision-JSON contract is valid. The gap was the shell the command string resolved to; awaiting re-probe round 3 |
| Stop gates block after a plugin edit | pass 2026-09-01 | FAIL 2026-09-02 (round 2) | Second harness: handlers reported failure and the turn exited 0. Under an explicit Git Bash the same tree produced the real verdict — the native-contract diagnostic naming the unregistered skill, exit 2. Same shell-resolution cause; awaiting re-probe round 3 |
| Shared Jira MCP tool is callable | pass 2026-09-01 | FAIL 2026-09-02 (round 2) | The bootstrap now finds `server.py` through the cache glob (locator fixed), but the second harness starts the MCP child with a filtered environment: parent had all three `JIRA_*` names set, child had none, and the server exits on absent credentials. Fixed here — the bootstrap fills them from the exported variables, then a `jira` server `env` block in the user's harness config files (names only, no secret ever printed or committed); awaiting re-probe round 3 |
| `afk-reader` returns a cited digest | pass 2026-09-01 | pass 2026-09-01 | Second harness: all four stubs copied byte-identical, each resolved its role Markdown through the plugin cache, and the read-only role refused the write |
| Agent sandbox and write boundaries | pass 2026-09-01 | pass 2026-09-01 | Read-only role refused on both harnesses; the target file did not exist afterwards |
| Same-child continuation | pass 2026-09-01 | pass 2026-09-01 | Both harnesses reached the same child with its nonce intact — `DELEGATION.md` may claim continuation on both |
| Cache refresh after source-only change | n/a | pass 2026-09-01 | Minimum sequence: re-run the plugin add, then start a new session. Removal first is not required |
| Script-only hook change trust behavior | n/a | pass 2026-09-01 | Editing a referenced script body left the trust hash unchanged and raised no new prompt — trust covers the handler definition, not the script it runs. Security consequence: an approved handler keeps running whatever its script later says, so the shell handlers are gated content, and the pre-commit and Stop gates are the control |
| Disable or uninstall leaves repository inert | pass (static) 2026-09-01 | pass 2026-09-01 | Second harness: after removal, zero skills, agents, MCP tools or plugin hooks, and no tracked repository file was touched. Caveat: pre-native ignored mirrors survive on a machine that once had them — the setup register's stale-activation entry offers the cleanup |
| Native contract negative probe blocks | pass 2026-09-01 | n/a | Scratch skill with a `harness:` frontmatter key, a harness-tool reference, a fallback-free project-dir read, and a harness name: gate exit 2 naming all six findings; exit 0 after removal |
| Hook launcher runs handlers whatever the PATH | pass 2026-09-02 | awaiting round 3 | First harness: the launcher ran the repository guard and carried its deny envelope, stayed silent on an absent handler, and still produced the denial when PATH held only the system directory (the WSL-stub case the second harness hit). Covered by `hooks/tests/hook-smoke.sh`; gate rule J rejected a hand-written bare-`bash` command with the expected diagnostic and exit 2, then passed once restored |

## Unresolved items

- Round 2 (2026-09-02) cleared the line-ending and locator causes and isolated two integration ones, both fixed here and awaiting re-probe round 3: hook commands named a shell (`bash`) that resolves to the WSL stub on that machine, so no handler ran natively; and the second harness starts the MCP child with a filtered environment, so the Jira credentials never reached the server. Both fixes are proven on the first harness and by explicit-shell control runs on the second, not yet by a native run there.
- `diagnose` is missing from the model-visible skill listing on the first harness although its frontmatter carries no hiding flag. Pre-dates the native migration; open as its own follow-up.


## Add harness #N

1. Add the harness row to the supported-harness registry in `PROVIDERS.md`.
2. Add `hooks/lib/providers/<name>.sh` with detect, root, and data functions.
3. Add one envelope fixture per shared event under `hooks/tests/envelopes/<name>/`.
4. Add a native manifest twin only when the harness cannot consume an existing manifest.
5. Add unchanged agent-definition stubs when the harness cannot consume `agents/*.md`.
6. Add one `CAPABILITIES.md` provider column and one `PROVIDERS.md` mapping column.
7. Add one `/afk:setup` probe section.
8. Run `hooks/tests/hook-smoke.sh` and `hooks/native-contract-gate.sh`.
9. Install through the harness enable flag. Run every probe in this ledger.
10. Record version, date, commands, verdicts, and unresolved capabilities here.
11. Confirm no skill prose changed for the harness.

# Facts — quota detection, reset, and resumption

Observed: 2026-09-15. Owner: debater-astra. Research only; no design decision is settled here.
Read `LANGUAGE.md` before extending this ledger.
CLI means command-line interface. SDK means software development kit. JSON means JavaScript Object Notation.
`verified` means the stated source, documentation, or command result was checked; it does not imply a live exhaustion test.
`inferred` marks a conclusion from those observations. `unverified` marks an unresolved interface or runtime claim.

Scope: Claude Code, the installed claude-hud, Codex, Windows scheduling, herdr, and 1DevTool.
No quota was deliberately exhausted. No generation probe, quota request, credential read, scheduler registration, or session restart ran.
Research readers inspected independent source partitions. This file is the only artifact written for this side task.

## Source keys

Paths below are source references, not instructions to read credentials or execute the plugin.

| key | location |
|---|---|
| HUD | `C:/Users/mvu/.claude/plugins/cache/claude-hud/claude-hud/0.3.0` |
| CODEX | `C:/Users/mvu/AppData/Local/Programs/OpenAI/Codex/bin/codex.exe` |
| DT | `C:/Program Files/1DevTool/resources/app.asar.unpacked/dist/cli/1devtool-agent.cjs` |
| CS | [Claude status line](https://code.claude.com/docs/en/statusline), field table and Rate limit usage |
| CE | [Claude errors](https://code.claude.com/docs/en/errors), Usage limits |
| CI | [Claude interactive mode](https://code.claude.com/docs/en/interactive-mode), Wait for a usage limit to reset |
| CH | [Claude headless](https://code.claude.com/docs/en/headless), Exit codes, Handle API retries, and interruption |
| CT | [Claude scheduling](https://code.claude.com/docs/en/scheduled-tasks), scheduling options, jitter, expiry, and limitations |
| CA | [Claude Agent SDK types](https://code.claude.com/docs/en/agent-sdk/typescript), SDKRateLimitEvent |
| OA | [Codex application server](https://learn.chatgpt.com/docs/app-server), Initialization, Errors, and Rate limits (ChatGPT) |
| ON | [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), machine-readable output and resumption |

## Claude: usage data and claude-hud

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| QH01 | The inspected installed HUD version is 0.3.0 under the HUD path above. | Read-only cache enumeration; `HUD/src/types.ts`, `HUD/src/stdin.ts`. | verified | Installation changes |
| QH02 | HUD reads `rate_limits.five_hour` and `rate_limits.seven_day` from Claude Code's standard input. Each contains `used_percentage` and `resets_at`. | `HUD/src/types.ts:38-47`; `HUD/src/stdin.ts:307-324`. Parent spot-check confirms the parser. | verified | HUD or input schema changes |
| QH03 | HUD rounds and clamps percentages to 0–100. It converts reset timestamps from Unix seconds to dates. Missing or invalid windows do not produce a usage value. | `HUD/src/stdin.ts:291-324`; `HUD/src/render/lines/usage.ts:22-32`. | verified | Parser changes |
| QH04 | HUD prefers standard input over a configured external snapshot. The external snapshot can supply usage when input lacks it, including a missing weekly window. | `HUD/src/index.ts:113-143`. | verified | HUD changes |
| QH05 | The inspected HUD source has no quota HTTP client. Its usage path reads input or a local snapshot. | Reader enumerated all `HUD/src/` files for `oauth`, `fetch(`, `http://`, `https://`; matches concern Git URLs/comments. `src/index.ts:113-143`, `src/external-usage.ts:1-316`. This excludes other plugins and Claude's own implementation. | verified | HUD source changes |
| QH06 | External snapshots use ISO 8601 observation/reset dates. Default maximum age is 300,000 milliseconds. Invalid, stale, relative-path, and failed reads return no usage. | `HUD/src/external-usage.ts:13-23,263-315`; `HUD/src/config.ts:241-243`. | verified | HUD configuration or source changes |
| QH07 | Optional snapshot writing copies supplied input, using atomic replacement and requested mode `0600`; identical data is throttled for 30,000 milliseconds. This does not fetch quota. | `HUD/src/external-usage.ts:10-11,216-260`; `HUD/src/index.ts:115-122`. Windows permission enforcement was not tested. | verified | HUD or filesystem behavior changes |
| QH08 | HUD formats reset dates as relative, absolute, or both. Relative is the default; unknown/past reset dates produce no countdown text. | `HUD/src/render/format-reset-time.ts:15-70`; `HUD/README.md:186-195,260-267`. This explains the user's countdown without requiring a separate quota endpoint. | verified | HUD or configuration changes |
| QH09 | Claude documents percentages for five-hour and seven-day windows and Unix-second reset timestamps. Windows can disappear independently after their reset passes. | [CS](https://code.claude.com/docs/en/statusline), field table and absent fields. | verified | Claude schema changes |
| QH10 | Documented status-line quota requires version 2.1.251 or later and a supported subscription/gateway. It appears after the first provider response, not necessarily at startup. | [CS](https://code.claude.com/docs/en/statusline), Rate limit usage. Pro/Max subscription windows and gateway spend limits are distinct. | verified | Claude version, account, or schema changes |
| QH11 | Missing HUD data cannot establish available quota. A local snapshot can remain a historical observation after the actual allowance changes. | Inference from QH03, QH06, QH09–QH10; no live quota measurement. | inferred | Fresh scoped service evidence resolves the observation |

## Claude: exhaustion and built-in continuation

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| QH12 | Claude displays `You've hit your session limit` or `You've hit your weekly limit`, followed by reset time. Session/weekly limits span models; Opus/Sonnet limits apply to their named family. | [CE](https://code.claude.com/docs/en/errors), Usage limits. No exhaustion was induced. | verified | Claude service or error behavior changes |
| QH13 | Claude distinguishes account quota from server throttling, model entitlement, and unanswered spending consent. A generic failure is not sufficient quota classification. | [CE](https://code.claude.com/docs/en/errors), Usage limits introduction. | verified | Error classification changes |
| QH14 | Since 2.1.234, eligible interactive subscription sessions enable automatic continuation by default; at reset they submit a fixed continuation prompt. | [CI](https://code.claude.com/docs/en/interactive-mode), Wait for a usage limit to reset. | verified | Claude continuation behavior changes |
| QH15 | Automatic waits do not start for resets beyond 24 hours, Remote Control, or team teammates. Background sessions and `-p` runs do not offer this wait. | [CI](https://code.claude.com/docs/en/interactive-mode), Start a wait yourself. | verified | Claude continuation behavior changes |
| QH16 | Exiting or transferring the session cancels its wait; session resume does not restore that wait. | [CI](https://code.claude.com/docs/en/interactive-mode), Cancel the wait. | verified | Claude continuation behavior changes |
| QH17 | Sleep exceeding about 30 minutes can require Enter after reset. Repeated quota hits re-arm at most twice; ordinary permission prompts still apply. | [CI](https://code.claude.com/docs/en/interactive-mode), Wait for a usage limit to reset. | verified | Claude continuation behavior changes |
| QH18 | `autoContinueAtUsageLimit` controls the interactive setting. The desktop session-limit checkbox is separate; its weekly-limit card lacks that checkbox. | [CI](https://code.claude.com/docs/en/interactive-mode), Turn automatic continue off; [CE](https://code.claude.com/docs/en/errors), Usage limits. | verified | Claude settings or desktop behavior changes |
| QH19 | Headless failure returns a nonzero exit and failure output. Stream JSON can report `system/api_retry`, including retry count and HTTP status. This is not a weekly-reset scheduler. | [CH](https://code.claude.com/docs/en/headless), Exit codes and Handle API retries. Documentation only. | verified | Headless result behavior changes |
| QH20 | The reader reports an SDK `rate_limit_event` carrying `rate_limit_info.status`, optional `resetsAt`/`utilization`, and session identity; statuses include allowed, allowed_warning, rejected. | Reader extraction of [CA](https://code.claude.com/docs/en/agent-sdk/typescript), SDKRateLimitEvent. Parent fetch failed on page size; exact installed stream contract was not reproduced. | unverified | Installed SDK schema or a captured event establishes the contract |
| QH21 | The reset unit and window identity in QH20 remain unresolved. The verified status-line seconds contract does not establish this separate SDK field's unit. | QH03/QH09 versus reader's CA excerpt, which gives only numeric `resetsAt`. No live event captured. | unverified | SDK source or event evidence establishes units and scope |
| QH22 | Native continuation does not cover every requested unattended case, including long weekly waits and exited/headless agents. | Inference from QH15–QH17. This is a capability boundary, not a proposed implementation. | inferred | Claude adds broader continuation guarantees |

## Codex: limits, exhaustion, and saved sessions

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| QC01 | Codex documents five-hour usage estimates; weekly limits may also apply. Current limits/reset times come from the usage dashboard. | [Codex pricing](https://learn.chatgpt.com/docs/pricing), What are the usage limits for my plan? | verified | Plan/service changes |
| QC02 | After initialization, `account/rateLimits/read` queries ChatGPT quota; `account/rateLimits/updated` reports changes. | [OA](https://learn.chatgpt.com/docs/app-server), Initialization and Auth endpoints. | verified | Application-server protocol changes |
| QC03 | Quota windows expose `usedPercent`, `windowDurationMins`, and Unix-second `resetsAt`; `primary` and `secondary` describe windows. | [OA](https://learn.chatgpt.com/docs/app-server), Rate limits (ChatGPT). | verified | Application-server protocol changes |
| QC04 | `rateLimitsByLimitId` groups buckets; `rateLimits` preserves a single-bucket view. `rateLimitReachedType` records the service's limit classification. | [OA](https://learn.chatgpt.com/docs/app-server), Rate limits (ChatGPT). | verified | Application-server protocol changes |
| QC05 | Failed application-server turns emit an error and finish failed. Documentation names `UsageLimitExceeded` among `codexErrorInfo` variants. | [OA](https://learn.chatgpt.com/docs/app-server), Errors. Exact serialized spelling was not exercised. | verified | Error protocol changes |
| QC06 | The documented quota request is separate from generation; no `turn/start` is needed in its documented sequence. Live success remains untested here. | Inference from [OA](https://learn.chatgpt.com/docs/app-server), Initialization and Rate limits (ChatGPT); earlier `FACTS-codex.md` C071–C077. | inferred | Protocol changes or a live metadata response establishes operation |
| QC07 | Window lengths are returned data; assigning primary=five-hour and secondary=weekly universally is not established. | Inference from QC03–QC04; OA examples include other durations and nullable windows. | inferred | Provider publishes a fixed window mapping |
| QC08 | `codex exec --json` emits thread/turn/item events, including `turn.failed` and `error`. The thread-start event supplies the identifier for later resumption. | [ON](https://learn.chatgpt.com/docs/non-interactive-mode), Make output machine-readable. | verified | CLI event schema changes |
| QC09 | Installed Codex is 0.154.0. `exec resume` accepts a session identifier and new prompt, plus model, JSON output, and last-message file options. | Read-only `CODEX --version` and `CODEX exec resume --help`, exit 0. | verified | Executable changes |
| QC10 | `--ephemeral` suppresses persisted sessions. Explicit identifiers avoid the ambiguity of concurrent workers using `--last`. | `CODEX exec resume --help`, exit 0; first sentence verified from help, identifier choice inferred. | inferred | Session persistence/selection changes |
| QC11 | This round does not establish Codex's exact exhaustion text, quota-specific process exit code, reset-bearing error payload, or automatic wait after exhaustion. | Only help/version and official documentation were checked; no failing generation, live quota query, or resume ran. QC05 establishes the documented application-server category only. | unverified | Captured natural exhaustion or version-matched source establishes each behavior |
| QC12 | Reset time is a timestamp for a quota window, not proof that authentication, another bucket, or model entitlement will permit the next request. | Inference from QC03–QC07 and `FACTS-codex.md` C070/C076/C078. | inferred | Service provides a stronger acceptance guarantee |

## Mechanisms that can run work later

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| QW01 | Claude `CronCreate` accepts one-shot or recurring prompts using five-field cron expressions; scheduling uses local time. | [CT](https://code.claude.com/docs/en/scheduled-tasks), Manage scheduled tasks and How scheduled tasks run. | verified | Claude scheduler changes |
| QW02 | Cron prompts run only while Claude is running and idle. Closing the session stops firing; backgrounding carries scheduled loops forward. | [CT](https://code.claude.com/docs/en/scheduled-tasks), Limitations. This differs from the quota wait in QH16. | verified | Claude scheduler changes |
| QW03 | Session resume restores unexpired `CronCreate` tasks. Passed one-shots, self-paced loops, background Bash, and monitor tasks are not restored. | [CT](https://code.claude.com/docs/en/scheduled-tasks), Limitations. | verified | Claude scheduler changes |
| QW04 | Recurring tasks expire after seven days. They can fire up to 30 minutes late; one-shots at :00/:30 can fire 90 seconds early. | [CT](https://code.claude.com/docs/en/scheduled-tasks), Seven-day expiry and Jitter. | verified | Claude scheduler changes |
| QW05 | Claude Desktop scheduling persists without an open session but needs the machine on. Cloud scheduling is independent and uses a fresh clone. | [CT](https://code.claude.com/docs/en/scheduled-tasks), Compare scheduling options. Neither establishes recovery of this local working tree. | verified | Scheduling products change |
| QW06 | Claude Routines run durable cloud schedules. Runs submitted at quota exhaustion can be rejected until reset when credits are unavailable. | [Claude Routines](https://code.claude.com/docs/en/routines), Usage and limits; reader documentation check. | verified | Routine limits or billing changes |
| QW07 | Windows Task Scheduler supports a one-time action through `/SC ONCE`; an action can invoke an executable. | Reader ran `schtasks /Create /?`; help only, no task created. | verified | Windows task interface changes |
| QW08 | `StartWhenAvailable` permits a timed task to start after its scheduled time was missed. | [Microsoft StartWhenAvailable](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-startwhenavailable-settingstype-element). Documentation, not a wake test. | verified | Windows scheduler behavior changes |
| QW09 | `WakeToRun` permits waking a sleeping computer. PowerShell exposes it and `StartWhenAvailable` through scheduled-task settings. | [Microsoft WakeToRun](https://learn.microsoft.com/en-us/windows/win32/taskschd/taskschedulerschema-waketorun-settingstype-element); reader ran `Get-Help New-ScheduledTaskSettingsSet -Full`. | verified | Windows module or power behavior changes |
| QW10 | This machine's unattended task identity, power restrictions, wake support, and available credentials after restart were not tested. | No scheduled task was registered or run, and no power-state test occurred. QW07–QW09 establish interface capability only. | unverified | A bounded scheduler conformance test checks the machine |
| QW11 | Herdr provides a blocking lifecycle wait and timeout. It is not evidence of a timer that survives the manager's exit. | Reader ran `herdr agent wait --help`; earlier `FACTS-claude.md` HR-08. | verified | herdr changes |
| QW12 | No scheduler command appears in the enumerated herdr top-level, agent, session, and pane help lists. Other APIs were not exhaustively checked. | Reader ran `herdr --help`, `herdr agent --help`, `herdr session --help`, `herdr pane --help`. Scoped absence only. | verified | herdr command surface changes |
| QW13 | 1DevTool recovery identifies team, member, expected run, and client request. Swarm pause/resume are immediate controls with no scheduling argument in the inspected handlers. | `DT:6539-6563,6607-6620`; reader source extraction. | verified | 1DevTool handlers change |
| QW14 | The inspected 1DevTool CLI contains no literal `schedule`, `cron`, `delayed`, `wakeup`, or `wake`. Its help lists recovery/resume, not timed execution. | Reader searched complete DT with `Select-String -SimpleMatch`; each count 0. Help string `DT:7649-7669`. App backend and other APIs excluded. | verified | CLI source changes |
| QW15 | Direct 1DevTool help execution failed before help because sandbox access to a license file was denied. Source inspection remains the evidence for QW13–QW14. | Reader command `1DevTool.exe <DT> --help` fails with EPERM; license contents were not read. | verified | Sandbox or launcher changes |
| QW16 | Timed wake, normal scheduler availability, and accepted provider generation are separate conditions. A session-local timer cannot itself restart an exited process. | Inference from QW02–QW03, QW07–QW12, QC12. | inferred | A transport supplies a tested combined guarantee |
| QW17 | 1DevTool defines separate `rate-limit` and `quota-exhausted` fallback triggers. Its account-pool `all-over-rotate` case maps to quota exhaustion before spawn. An ambiguous headless exit maps to launch error. | Parent re-read `DT:3800-3806,3937-3977`. Source classification only; no reset timer or provider switching exercised. | verified | 1DevTool failure classification changes |

## Resumption and state that survives exhaustion

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| QR01 | Claude documents explicit identifier resumption for `-p` sessions even though they do not appear in the picker or `--continue`. | [Claude sessions](https://code.claude.com/docs/en/sessions), Resume a session; reader documentation check. | verified | Claude session behavior changes |
| QR02 | A headless Claude turn interrupted by SIGTERM can continue after session resume. That guarantee does not cover missing or disabled transcript storage. | [CH](https://code.claude.com/docs/en/headless), interruption/resumption; `FACTS-claude.md` CN-03 lists persistence controls. | verified | Claude persistence or signal handling changes |
| QR03 | `claude --bg --resume <id>` continues a background session; when it already runs, documented help says it starts a copy. | Reader ran `claude --help`, `--bg` option. No background session started. | verified | Claude CLI changes |
| QR04 | Herdr exposes underlying session identifiers. Combining these with provider resume is plausible, but no delayed herdr restart was tested. | `FACTS-claude.md` HR-13–HR-14; QC09 and QR01. | inferred | Session persistence or transport changes |
| QR05 | The previously inspected 1DevTool direct Codex launcher forces ephemeral execution; its retained run output is not a resumable Codex session. | `FACTS-codex.md` C024/C079/C080; QC10. These earlier source findings were not fully rechecked this round. | inferred | Launcher or persistence changes |
| QR06 | Existing disk handoff requires goal, current state, next steps, and artifact pointers sufficient for a fresh agent. | Read-only `rg -n` over `skills/utils/handoff/SKILL.md:9-15`; format/source verified. | verified | Handoff contract changes |
| QR07 | Saving a final model-written summary only after exhaustion is not established as possible: the exhausted provider can reject further requests. Previously saved artifacts remain usable independently. | Inference from QH12, QC05, QR06; no post-limit compaction trial. | inferred | A supported post-limit compaction mechanism is established |
| QR08 | The requested complete sequence—detect, save, learn reset, wake, resume—is not live-verified for either provider in this research. | No intentional exhaustion, scheduler registration, forced sleep, provider restart, or natural-limit capture occurred. The preceding rows establish component interfaces and limits. | unverified | A bounded test or natural exhaustion validates the complete sequence |

## Probe record

| boundary | read-only checks | result |
|---|---|---|
| Installed Codex | `Get-Command codex`; explicit `CODEX --version`, `app-server --help`, `exec resume --help` | PATH lookup yields no executable here; explicit help/version succeed with a home-directory warning. Version 0.154.0. |
| HUD | Cache enumeration, bounded reads of cited source, scoped `src/` search; parent re-read `stdin.ts:291-324` | Input fields and Unix-second conversion confirmed; no plugin execution. |
| Schedulers | Cited help commands, DT source reads/searches, official documentation | No scheduler, task, timer, or service installed or registered. |
| Provider documentation | Opened official OpenAI/Claude pages and cited sections; reader extracted additional Claude documentation | Provider behavior remains documentation/source evidence. SDK page failed parent retrieval because of response size; QH20–QH21 remain unverified. |

New requirement supplied by the human: agents detect exhausted quota, preserve state, learn reset time, and resume automatically.
This ledger supplies facts for later design. It does not revise `RESPONSE-codex.md` or perform Step 2.

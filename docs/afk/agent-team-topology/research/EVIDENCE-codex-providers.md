# Codex transport and provider evidence

Observed: 2026-09-15. Owner: `codex` provider-research child. Advisory extraction; no inference request ran.
Language: read `LANGUAGE.md` before extending this artifact.

## Local commands

`$codexBin` denotes `C:\Users\mvu\AppData\Local\Programs\OpenAI\Codex\bin\codex.exe` below.
Commands run in PowerShell from this worktree. Help checks run inside the sandbox.

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| CP01 | Codex is installed, but this child shell cannot resolve `codex` through PATH. | `Get-Command codex` reports command not recognized; `Get-Process -Name '*codex*'` supplies `$codexBin`. | verified | Process environment changes |
| CP02 | The discovered executable is Codex command-line interface (CLI) 0.154.0. | `& $codexBin --version` → `codex-cli 0.154.0`. | verified | Executable changes |
| CP03 | `exec` supports a prompt argument, standard input, or both. | `& $codexBin exec --help`: omitted prompt or `-` reads stdin; piped stdin with a prompt becomes a `<stdin>` block. | verified | CLI changes |
| CP04 | `-m/--model` selects a model; `-c/--config` overrides configuration. | `exec --help`: `Model the agent should use`; dotted keys supported; values parse as TOML, else literal strings. | verified | CLI changes |
| CP05 | `--oss` selects an open-source provider; `--local-provider` accepts `lmstudio` or `ollama`. | `exec --help`, corresponding flag descriptions. | verified | CLI changes |
| CP06 | `--sandbox` accepts `read-only`, `workspace-write`, and `danger-full-access`. | `exec --help`, sandbox options. | verified | CLI changes |
| CP07 | Automatic approval review has a separate flag. | `exec --help`: `--approve-for-me` routes requests through automatic review with workspace-write sandbox. | verified | CLI changes |
| CP08 | Full bypass disables both approvals and sandboxing. | `exec --help`: `--dangerously-bypass-approvals-and-sandbox`; documented for externally sandboxed environments. | verified | CLI changes |
| CP09 | Approval policy accepts `on-request` and `never` at the top level. | `& $codexBin --help`; `& $codexBin -a never exec --help` parses successfully, exit 0. | verified | CLI changes |
| CP10 | New automation should use explicit sandbox settings. | [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), “Permissions and safety”: default read-only; `--full-auto` is deprecated compatibility. | verified | Documentation or CLI changes |
| CP11 | Working directory and additional writable roots are configurable. | `exec --help`: `-C/--cd`, `--add-dir`; `--worktree` creates a managed Git worktree. | verified | CLI changes |
| CP12 | Events can be captured as JSON Lines, one JSON object per line. | `exec --help`: `--json` prints events to stdout. [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), “Make output machine-readable”, names thread, turn, item, and error events. | verified | CLI or event schema changes |
| CP13 | Final text and progress use separate streams by default. | [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode), “Basic usage”: final message on stdout, progress on stderr. | verified | CLI changes |
| CP14 | The final answer can have a schema and a dedicated output file. | `exec --help`: `--output-schema <FILE>`, `-o/--output-last-message <FILE>`. | verified | CLI changes |
| CP15 | `--ephemeral` suppresses persisted session files. | `exec --help`, corresponding flag description. | verified | CLI changes |
| CP16 | Resume accepts an explicit session identifier, thread name, or `--last`. | `exec resume --help`: UUID takes precedence; `--all` disables working-directory filtering; `-` reads the next prompt from stdin. | verified | CLI changes |
| CP17 | Resume can change the model and preserve machine-readable output. | `exec resume --help` lists `--model`, `--json`, `--output-schema`, and `--output-last-message`. | verified | CLI changes |
| CP18 | A new session can fork an existing session. | `exec --help` lists `fork`: “Fork a previous session by id into a new session”. | verified | CLI changes |
| CP19 | The sandbox can make auth probing fail before auth is evaluated. | `& $codexBin login status` inside sandbox: `Error loading configuration: Could not find home directory`, exit 1. | verified | Sandbox or environment changes |
| CP20 | The installed Codex reports a ChatGPT login outside this sandbox. | Approved `& $codexBin login status` → `Logged in using ChatGPT`, exit 0. | verified | Login or account changes |
| CP21 | Claude CLI is version 2.1.272 and reports a Max login. | `claude --version` → `2.1.272 (Claude Code)`; selected fields from `claude auth status --json`: `loggedIn=true`, `authMethod=claude.ai`, `apiProvider=firstParty`, `subscriptionType=max`; exit 0. | verified | Login, account, or executable changes |
| CP22 | Claude auth status has documented success and failure exit codes. | [CLI reference](https://code.claude.com/docs/en/cli-usage), `claude auth status`: 0 logged in; 1 not logged in. | verified | CLI changes |
| CP23 | Neither local login result proves remaining quota or acceptance of the next model request. | CP20–CP22 contain auth data only. No model request or remote quota probe ran. | inferred | Successful request or fresh quota evidence |

## Probes that avoid a model request

| id | claim | evidence | status | expires-when |
|---|---|---|---|---|
| CP24 | Codex exposes account information through its application server. | [App Server](https://learn.chatgpt.com/docs/app-server), “Check auth state”: `account/read` with `refreshToken:false`; response can include account type and `planType`. | verified | Protocol changes |
| CP25 | Codex exposes a separate request for ChatGPT limits. | [App Server](https://learn.chatgpt.com/docs/app-server), “Rate limits (ChatGPT)”: `account/rateLimits/read`; response reports windows, used percentage, reset time, and limits by identifier. | verified | Protocol or account changes |
| CP26 | Codex can discover models and supported effort options. | [App Server](https://learn.chatgpt.com/docs/app-server), “List models”: `model/list`, pagination, `supportedReasoningEfforts`. | verified | Protocol or model catalog changes |
| CP27 | These three Codex requests need no generation turn. | CP24–CP26 document independent methods. Inference: issue them after protocol initialization, without `thread/start` or `turn/start`. | inferred | Protocol changes |
| CP28 | Codex has a machine-readable diagnostic command. | `& $codexBin doctor --help`: `--json` emits a redacted report; scope includes installation, configuration, auth, and runtime health. The command itself was not run. | verified | CLI changes |
| CP29 | Claude `/usage` displays plan limits and reset times. | [Error reference](https://code.claude.com/docs/en/errors), “Usage limits”. This is an interactive command; headless support was not established. | verified | CLI changes |
| CP30 | An existing Claude status line can expose quota data without a new inference request. | [Status line](https://code.claude.com/docs/en/statusline), “Display rate limit usage”: `rate_limits` appears after the first API response for supported accounts. | verified | CLI or account changes |
| CP31 | A status line is not a cold-start quota probe. | Same section: quota fields require a preceding API response; missing fields must be handled. | verified | CLI changes |
| CP32 | Claude status commands must not be promised strictly free. | [Costs](https://code.claude.com/docs/en/costs), “Background token usage”: `/usage` can generate status requests; background work can consume tokens. | verified | Billing or CLI changes |
| CP33 | Credentials can select a different billing source than the stored subscription. | [Authentication](https://code.claude.com/docs/en/team), “Authentication precedence”: provider selection and approved API credentials can outrank subscription credentials. `/status` shows the active source. | verified | Auth configuration changes |
| CP34 | Positive quota does not prove every model is permitted. | [Error reference](https://code.claude.com/docs/en/errors), “Usage credits required for 1M context”: entitlement can reject a model despite remaining allowance. | verified | Model entitlement changes |
| CP35 | Actual remaining quotas were not measured in this research. | Executed commands: help/version, Codex login status, Claude auth status. No application-server limit request or Claude `/usage` ran. | unverified | Fresh quota probe |
| CP36 | A universal zero-cost headless readiness guarantee is not established. | Enumerated local CLI help and cited auth, application-server, limits, and status-line documentation. Inference: remaining uncertainty includes quota, model entitlement, server capacity, and network access. | unverified | Provider supplies such a contract |

## Proposed consumer behavior

Inference: retain independent fields for installation, auth, billing source, model entitlement, quota, and last successful request.
Do not collapse an unavailable quota check into `usable=true` or `usable=false`.
Record the executable path, provider configuration identity, observation time, expiry, and error category.
Use explicit session identifiers for resume; `--last` can select another concurrent worker's session.
Use `--ephemeral` only when future session resume is unnecessary.
Keep stdout events, stderr diagnostics, final answer, process exit, and session identifier as separate evidence.
Treat auth failures, quota failures, network failures, configuration failures, and denied permissions as separate causes.

### Research caveat

A search snippet claimed separate Claude headless credits from June 2026.
The fetched current authentication page does not contain that statement.
This artifact does not use that unsupported claim.

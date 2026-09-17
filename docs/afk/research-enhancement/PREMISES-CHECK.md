# Premises check

Evidence date: 2026-09-15.

No model request, paid call, or application programming interface call ran.

The product requirements document (PRD) supplies each premise. Acceptance criterion (AC) identifiers refer to that document.

| # | Premise | Verdict | Effect |
|---|---|---|---|
| 1 | `claude auth status` schema and subscription tier | HYPOTHESIS | AC-025 must use captured fixtures and fail closed. |
| 2 | `codex login status` and environment-key precedence | REFUTED | Status cannot prove the effective authentication for `codex exec`. |
| 3 | `claude -p` silently draws usage credits | HYPOTHESIS | The current zero-balance probe is insufficient. |
| 4 | Antigravity key names and defaults | HYPOTHESIS — DEFERRED | Keep Antigravity disabled until step 5. |
| 5 | `claude -p` is ordinary individual use | HYPOTHESIS | Keep ADR-0006's explicit policy risk. |

## 1. Claude authentication status

PRD premise: `PRD.md:208`.

Release note: “Added `configDirectory` to the output of `claude auth status --json`.”
[Anthropic Claude Code v2.1.268 release](https://github.com/anthropics/claude-code/releases/tag/v2.1.268)

Local checks:

```text
$ claude --version
2.1.273 (Claude Code)

$ claude auth status --help
Usage: claude auth status [options]

Show authentication status

Options:
  -h, --help  Display help for command
  --json      Output as JSON (default)
  --text      Output as human-readable text
```

Both commands exited with code 0.

The evidence confirms JSON output and schema changes. It does not define the complete schema or guarantee `subscriptionType`.

Verdict: **HYPOTHESIS**.

Step 2 probe:

1. Capture `claude auth status --json` for subscription, API-key, and logged-out states.
2. Record the Claude Code version with each fixture.
3. Treat an absent or null `subscriptionType` as unknown.
4. Fail closed for unknown fields or values.

## 2. Codex authentication status

PRD premise: `PRD.md:209`.

The status source contains “Logged in using an API key - {}” and “Logged in using ChatGPT.”
Runtime output replaces `{}` with a masked key.
It also calls `.load_auth(/*enable_codex_api_key_env*/ false)`.
[OpenAI Codex status source](https://github.com/openai/codex/blob/c51cb968e43fd52255aacf568220aed4654c3f97/codex-rs/cli/src/login.rs#L461-L476)

The authentication manager states: “API key via env var takes precedence over any other auth method.”
The condition requires `enable_codex_api_key_env` and an allowed API-key method.
[OpenAI Codex authentication manager](https://github.com/openai/codex/blob/c51cb968e43fd52255aacf568220aed4654c3f97/codex-rs/login/src/auth/manager.rs#L1460-L1478)

`codex exec` sets `enable_codex_api_key_env: true`.
[OpenAI Codex execution source](https://github.com/openai/codex/blob/c51cb968e43fd52255aacf568220aed4654c3f97/codex-rs/exec/src/lib.rs#L705-L714)

The switch means: “Whether auth loading should honor the `CODEX_API_KEY` environment variable.”
[OpenAI Codex application server client](https://github.com/openai/codex/blob/c51cb968e43fd52255aacf568220aed4654c3f97/codex-rs/app-server-client/src/lib.rs#L197-L198)

Current source reads `CODEX_API_KEY` for the execution override.
[OpenAI Codex environment-key source](https://github.com/openai/codex/blob/c51cb968e43fd52255aacf568220aed4654c3f97/codex-rs/login/src/auth/manager.rs#L926-L938)

Local checks:

```text
$ codex --version
codex-cli 0.154.0

$ codex login status --help
Show login status

Usage: codex login status [OPTIONS]
```

Both commands exited with code 0.

Verdict: **REFUTED**.

The combined premise claims generic exported-key precedence. Current source proves conditional `CODEX_API_KEY` precedence only.
It does not prove `OPENAI_API_KEY` precedence.

Correct fact:

- `codex login status` reports stored authentication.
- It does not report the effective environment override for `codex exec`.
- `codex exec` can honor `CODEX_API_KEY` when API authentication is allowed.
- `forced_login_method=chatgpt` and environment removal are separate controls.
- Current source does not use `OPENAI_API_KEY` for this override.
- Denying both key variables remains conservative.

## 3. Claude usage-credit behavior

PRD premise: `PRD.md:210`.

The page says: “For now, nothing has changed: Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits.”
[Anthropic Agent SDK plan guidance](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)

The same page also says: “Starting June 15, 2026, Claude Agent SDK and `claude -p` usage no longer counts toward your Claude plan’s usage limits.”

It later says: “When your monthly credit runs out, additional Agent SDK usage flows to usage credits at standard API rates—but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes.”

Credit guidance says “you can choose to continue working” and “you’ll see a clear notification.”
[Anthropic usage-credit guidance](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans)

The page contains conflicting current-state statements. This check cannot establish which billing behavior is current.

Verdict: **HYPOTHESIS**.

The plan's zero-balance probe cannot prove a debit. It tests only whether hidden funding occurs.

Proposed live probe:

1. Disable automatic reload.
2. Enable usage credits with a small known balance.
3. Record included usage, the credit balance, and current credit spending.
4. With available subscription capacity, run one fixed one-turn `claude -p` request after explicit user approval.
5. Re-read all 3 values after usage reporting updates.
6. Exhaust included capacity. Repeat the same request with fresh explicit approval.
7. Record whether Claude requires a notification or confirmation before credit use.
8. Repeat with credits disabled or a zero balance as the control.
9. Confirm that `usage_credits: disabled` makes overflow stop instead of billing.

The first run tests initial routing. The exhausted-capacity run tests credit fallback.
A reduced balance verifies a credit debit. A required confirmation refutes silent fallback.

## 4. Antigravity settings

PRD premise: `PRD.md:211`.

Google states: “Set `modelProvider` to `gemini`.”
[Antigravity CLI installation](https://antigravity.google/docs/cli/install)

The credit guide shows `"useG1Credits": true`.
[Antigravity CLI credits](https://www.antigravity.google/docs/cli/credits/)

The settings guide says it writes “only values to disk that differ from their system defaults.”
[Antigravity CLI settings](https://www.antigravity.google/docs/cli/settings)

The official documents verify both key names. They do not state either absent-key default.

Verdict: **HYPOTHESIS — DEFERRED TO STEP 5**.

Step 5 probe:

1. Start Antigravity with a clean isolated profile.
2. Open `/config`.
3. Record each effective value that `/config` shows before any change.
4. Toggle each value and confirm the effective route.
5. Keep Antigravity disabled until the probe completes.

The sparse settings file omits system defaults. It cannot prove an absent-key default.

## 5. Anthropic policy for `claude -p`

PRD premise: `PRD.md:212`.

Anthropic says included usage is designed to support “ordinary use of native Anthropic applications,” including Claude Code.
The same page says: “If you’re building a product, application, or tool for others, use API key authentication.”
[Anthropic account authentication guidance](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account)

The page also says: “The preferred way to access Anthropic services using third-party software, tools, or services (“third-party tools”), including open-source projects, is through API key authentication through Claude Console or a supported cloud provider.”

It prohibits third-party tools that “misrepresent their identity to Anthropic’s servers” or “attempt to route third-party traffic against subscription limits.”

The Agent SDK page says: “For now, nothing has changed: Claude Agent SDK, `claude -p`, and third-party app usage still draw from your subscription's usage limits.”
[Anthropic Agent SDK plan guidance](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan)

The same page also says: “Starting June 15, 2026, Claude Agent SDK and `claude -p` usage no longer counts toward your Claude plan’s usage limits.”

It later says: “When your monthly credit runs out, additional Agent SDK usage flows to usage credits at standard API rates—but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes.”

The cited authentication page is Help Center guidance. It is not Anthropic's legal terms.
The Agent SDK page contains conflicting current-state statements. This check cannot establish which billing behavior is current.
The documents do not classify an external orchestrator that launches the unmodified binary.

Verdict: **HYPOTHESIS**.

A live billing probe cannot establish policy permission. Written Anthropic support or legal guidance is required for verification.

ADR-0006 can retain this premise only as an explicit accepted risk.

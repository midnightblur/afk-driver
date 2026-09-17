# 0002-provider-verbs — six member verbs per provider file

## Goal
Append the six member verbs `probe`, `auth_mode`, `invocation`, `parse_result`, `classify_failure`, `quota_headroom` to `hooks/lib/providers/claude.sh` and `codex.sh`, leaving the 5 existing members untouched. `auth_mode` parses recorded status output (`claude auth status --json`, `codex login status`) into `subscription | api | none | unknown` from fixtures for every state; `quota_headroom` reports an exhausted monthly credit or plan window as `quota` (FC-6), never as an error; `invocation` returns the argument vector for the headless CLI (`claude -p` on stdin, never `--bare`; `codex exec -` with `-c forced_login_method=chatgpt --sandbox read-only`); `parse_result` and `classify_failure` map a stream + exit code to a `result.json` candidate and one FC-1..FC-12 class. `PROVIDERS.md` gains the member role, the billing env-deny list and the config-file refusal rule; `providers/CONFORMANCE.md` names the six verbs; `skills/afk/setup/MANIFEST.md` gains opt-in rows for the two participant binaries; `hooks/tests/hook-smoke.sh` pins the verbs and the fixtures.

## Complexity
standard

## Design refs
- SDD: SDD.md#§3 row "provider member verbs" — the six verbs, output contract, missing verb → dispatcher exit 3; 5 existing members untouched
- SDD: SDD.md#§5 "AuthN" — `auth_mode` reads a status, never a token; unknown fails closed
- SDD: SDD.md#§5 "Rate limit" — exhausted monthly Agent SDK credit or plan window is `quota`, never an error (AC-044)
- SDD: SDD.md#§8 row "provider shell library" — public interface `probe, auth_mode, invocation, parse_result, classify_failure, quota_headroom`
- SDD: SDD.md#§9b row "Provider status strings" — seam-test `test_auth_mode_parse` per fixture state
- SDD: SDD.md#§14 row "provider shell library function set" — glob-sourced files, built-name resolution, hook-smoke pins, `CONFORMANCE.md:297` member list
- ADR: adr/design/0001-provider-strategy-member-verbs.md — Strategy through a shell-function verb contract; new verbs appended; every provider file defines every verb
- ADR: adr/requirements/0004-pilot-read-only-claude-codex.md — Claude + Codex only in the pilot
- ADR: adr/requirements/0006-same-provider-participant-is-native-subagent.md — `claude -p` conditions (a) unmodified binary, (b) no `--bare`

## Scope
- hooks/lib/providers/claude.sh
- hooks/lib/providers/codex.sh
- hooks/tests/hook-smoke.sh
- hooks/tests/fixtures/providers/**   # recorded status/stream fixtures per provider and state
- PROVIDERS.md
- providers/CONFORMANCE.md
- skills/afk/setup/MANIFEST.md
- skills/afk/setup/SKILL.md            # only the probe section for the two participant binaries

## Seams
- implement: §9b "Provider status strings" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — this subtask owns `auth_mode` parsing + seam-test `test_auth_mode_parse` per fixture state (INV-003)

## Acceptance
- [ ] Each of `claude.sh` and `codex.sh` defines all six functions `afk_<provider>_{probe,auth_mode,invocation,parse_result,classify_failure,quota_headroom}`; the 5 existing members (`priority`, `detect`, `plugin_root`, `stop_block_code`, `plugin_data`) are byte-identical (SDD §3 row "provider member verbs")
- [ ] `afk_claude_auth_mode` returns `subscription`, `api`, `none` or `unknown` from a recorded `claude auth status --json` fixture for each state; an absent or unrecognised `subscriptionType` returns `unknown` (SDD §5 "AuthN"; PRD Further Notes #1)
- [ ] `afk_codex_auth_mode` returns `subscription` for a ChatGPT-login fixture, `api` for an API-key fixture, `none` for a logged-out fixture, `unknown` otherwise (SDD §9b row "Provider status strings")
- [ ] `afk_claude_invocation` emits `claude -p` reading the prompt from stdin and never `--bare`; `afk_codex_invocation` emits `codex exec -` with `-c forced_login_method=chatgpt` and `--sandbox read-only` (PRD C3 rows P-claude, P-codex)
- [ ] `afk_<provider>_quota_headroom` reports an exhausted monthly Agent SDK credit, or an exhausted plan window, as `quota` in both live states of the Claude plan article; no fixture state maps to an error class (PRD AC-044)
- [ ] `afk_<provider>_classify_failure` maps every fixture (exit code + stream) to exactly one of FC-1..FC-12; an unrecognised fixture maps to `unknown` with the original text retained (PRD AC-023)
- [ ] `afk_<provider>_parse_result` turns a recorded stdout fixture into a `result.json` candidate; a stream that fails the schema yields `invalid_output` (PRD AC-021)
- [ ] A verb reads a status output only; no function reads a token, key file or credential value (SDD §5 "AuthN")
- [ ] `hooks/tests/hook-smoke.sh` loops over every provider file and fails when any of the six verbs is missing; existing cases stay green (SDD §14 row "provider shell library function set")
- [ ] `PROVIDERS.md` documents the `host`/`member` role, the billing env-deny list (`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY`) and the config-file refusal rule (`apiKeyHelper`, gateway credential, `codex login status` API key) (PRD "Implementation Decisions" row "hooks/lib/providers/<name>.sh")
- [ ] `providers/CONFORMANCE.md` names the six member verbs beside the existing member list; probe counts are not refreshed (SDD §14 "Accepted compatibility-audit findings" (3))
- [ ] `skills/afk/setup/MANIFEST.md` carries one **[opt-in]** entry per participant binary (`claude`, `codex`) with presence-only probes and the Codex instruction to keep the balance at 0 with auto-reload off (ADR-0005)
- [ ] Implements the public interface in SDD §8 row "provider shell library" unmodified (SDD §8)
- [ ] Conforms to ADR-0001 (design) — no `case`-per-provider block anywhere; a provider is selected by name only (ADR-0001)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Fixtures use the real provider names `claude` and `codex` and the real command names, never placeholders (PRD "Testing Decisions")

## Produces
- hooks/lib/providers/claude.sh#afk_claude_probe — prints JSON `{auth_mode, quota_headroom, binary}`; exit 4 when the binary is missing
- hooks/lib/providers/claude.sh#afk_claude_auth_mode — prints `subscription|api|none|unknown` from `claude auth status --json`
- hooks/lib/providers/claude.sh#afk_claude_invocation — prints the argv for `claude -p` (stdin prompt, never `--bare`)
- hooks/lib/providers/claude.sh#afk_claude_parse_result — stdout stream → `result.json` candidate or `invalid_output`
- hooks/lib/providers/claude.sh#afk_claude_classify_failure — exit code + stream → one FC-1..FC-12 value
- hooks/lib/providers/claude.sh#afk_claude_quota_headroom — window headroom; exhausted credit or window → `quota`
- hooks/lib/providers/codex.sh#afk_codex_probe — as the Claude verb, for `codex`
- hooks/lib/providers/codex.sh#afk_codex_auth_mode — prints `subscription|api|none|unknown` from `codex login status`
- hooks/lib/providers/codex.sh#afk_codex_invocation — prints the argv for `codex exec -` with `-c forced_login_method=chatgpt --sandbox read-only`
- hooks/lib/providers/codex.sh#afk_codex_parse_result — stdout stream → `result.json` candidate or `invalid_output`
- hooks/lib/providers/codex.sh#afk_codex_classify_failure — exit code + stream → one FC-1..FC-12 value
- hooks/lib/providers/codex.sh#afk_codex_quota_headroom — window headroom; exhausted window → `quota`
- PROVIDERS.md#Member verbs — the member role, the six-verb contract, the billing env-deny list, the config-file refusal rule
- skills/afk/setup/MANIFEST.md#participant binaries — opt-in register entries for `claude` and `codex` as consultation participants

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash -n hooks/lib/providers/claude.sh hooks/lib/providers/codex.sh` + `bash hooks/native-contract-gate.sh` + grep every ## Produces anchor | files parse; provider registry rules hold; all 12 verbs present |
| unit | `bash hooks/tests/hook-smoke.sh` — new cases: six verbs present per file; `test_auth_mode_parse` per fixture state (subscription / api / none / unknown, both providers); `quota_headroom` exhausted-credit and exhausted-window fixtures → `quota` (AC-044); `classify_failure` one class per fixture; `parse_result` invalid stream → `invalid_output` | the verb contract; seam-test for the provider-status seam on the recorded real output |

## Context excerpts
> (SDD §3 row "provider member verbs") shell functions in the provider library, one file per provider | the dispatcher and hooks | per verb: `probe`, `auth_mode`, `invocation`, `parse_result`, `classify_failure`, `quota_headroom` (optional) | the verb's documented output | a missing verb makes the dispatcher exit 3 (adapter-family shape, `ADAPTERS.md`); the library's own convention for its 5 existing members is silent fallback, which the dispatcher does not adopt | pure functions | 1 | **compatible**: the 5 existing members (`priority`, `detect`, `plugin_root`, `stop_block_code`, `plugin_data`) untouched; no pin enumerates a member list (INV-003)
> (SDD §5 "AuthN") No plugin-issued credential. A participant CLI authenticates with its own subscription login; the dispatcher only observes the mode. … Caption: the gate reads a status, never a secret; an unknown mode fails closed (PRD Further Notes #1).
> (SDD §5 "Rate limit") An exhausted monthly Agent SDK credit or plan window is `quota`, never an error *(amendment, AC-044)*.
> (SDD §8 row "provider shell library") per-provider member verbs | `probe, auth_mode, invocation, parse_result, classify_failure, quota_headroom` | — | —
> (SDD §9b row "Provider status strings") `codex login status`, `claude auth status` | free-text or JSON we parse | step-2 fixtures | `unknown` → fail closed | `test_auth_mode_parse` per fixture state
> (SDD §14 row "provider shell library function set") glob-sourced provider files (`hooks/lib/provider.sh:7-14`), members resolved by built name `afk_<provider>_<member>` with silent fallback when absent (`:31,:62,:75,:145`); 5 members per file pinned by `hooks/tests/hook-smoke.sh:43-123`; … | +6 member verbs appended per file; … | hook smoke test loops over provider files; `providers/CONFORMANCE.md:297` names the member list; a new provider *file* trips native-contract gate rules G/H … | no pin enumerates members, so appending breaks nothing; … conformance table gains a row | extends
> (ADR-0001 design) Each provider file implements the same six member verbs: `probe`, `auth_mode`, `invocation`, `parse_result`, `classify_failure`, and optional `quota_headroom`. The dispatcher selects a provider by its configured name and calls only the verb contract. … Existing members stay untouched; the new verbs are appended (SDD §3, §9, §14).
> (PRD C3 row P-claude) native subagent when the host is Claude (ADR-0006); else `claude -p` on stdin, never `--bare` | `/login` OAuth or `CLAUDE_CODE_OAUTH_TOKEN` | any of `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `apiKeyHelper`, `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY`, gateway credential is active | on
> (PRD C3 row P-codex) `codex exec -` with `-c forced_login_method=chatgpt`, `--sandbox read-only` | ChatGPT login | `codex login status` reports API key; `OPENAI_API_KEY`/`CODEX_API_KEY` present | on
> (PRD AC-044) The headroom probe reports an exhausted monthly Agent SDK credit, or an exhausted plan window, as the end of the usage window (`quota`, FC-6), never as an error class, in both live states of the Claude plan article (separate monthly credit, or plan-limit draw).
> (PRD AC-023) Every failure maps to exactly one FC-1..FC-12 class; an unrecognized error is `unknown` with the original text retained in protected scratch.
> (PRD Further Notes #1) HYPOTHESIS: `claude auth status --json` field names and whether the subscription tier is reported (unverified premise: field names). Step 2 captures fixtures for the subscription, API-key and logged-out states; an absent or unknown `subscriptionType` fails closed (AC-025).
> (PRD "Implementation Decisions" row "hooks/lib/providers/<name>.sh") member verbs `probe`, `invocation`, `parse_result`, `classify_failure`, `auth_mode`, optional `quota_headroom`; billing env-deny list; config-file refusal rule; `host`/`member` role | Claude + Codex in the pilot; agy and Grok after live conformance — ADR-0004
> (PRD "Testing Decisions") Conformance: one recorded live probe per participant provider in `providers/CONFORMANCE.md`; unverified fields (`claude auth status` output fields, `codex login status` strings) become fixtures at step 2.
> (ADR-0005 requirements) the setup docs tell the user to keep the Codex balance at 0 with auto-reload off (AC-027)

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

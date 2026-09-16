# PRD — world research, organization priorities, prepared asks, multi-provider consultation

Work item: `research-enhancement`. Source of record for D-1..D-6: `MERGED-PLAN.md` §6 (:113-126). ADR-0007 derives from A4, A7, and D2 (:26, :29, :49). ADR-0008 derives from A12, A14, and dispute 6 (:34, :36, :62). Their human acceptance is recorded in `GRILL-LOG.md` (:26-27). Vocabulary: `GLOSSARY.md` (plugin root); new terms below are registered there by the sync-harness subtask.

## Problem Statement

The plugin answers design questions from local truth only. Four gaps:

- No skill researches the world (standards, vendor behaviour, what other teams do) before a grill; version and flag claims reach the human unverified.
- No skill infers what the organization prefers from its own decision records, so recommendations ignore the team's settled priorities.
- Items reach the human before the agent has exhausted its tools; the human does the fact-finding.
- Every judgment comes from one model. No second provider can investigate independently or challenge a conclusion, and a host whose quota ends leaves unfinished read-only work with no successor.

## Solution

Four capabilities, all opt-in through `.afk/config.yaml`, absent config = today's behaviour:

1. **Research** (`/afk:research`): a single-writer research skill that answers a world question (W1–W4, catalog C1) with cited primary sources, records inferred organization priorities as advisory findings, and closes on a type-specific rule or reports `incomplete`.
2. **Prepared ask**: one bar in `DECISIONS.md` for anything that reaches a human. The round renderer already enforces the core fields; two optional fields are added.
3. **Consultation** (`/afk:consult`): independent reports from ≥2 participants (a participant is one provider's headless CLI run, or a native subagent when the provider is the host), one challenge round, evidence-weighted disposition, dissent preserved. Advisory only.
4. **Dispatch** (`scripts/dispatch_harness.py`): one deterministic subprocess runner for cross-provider participants, subscription-billed only by default, with resumable read-only job state.

## Catalog

### C1 — Research question types

| ID | Type | Closes when | Output on budget exhaustion |
|---|---|---|---|
| W1 | Landscape: what other teams or products do | Every declared question, material counterclaim and option-eliminating assumption has a disposition; source count is metadata | `incomplete` + named gaps |
| W2 | Standard or specification | One authoritative primary source with quoted text | `incomplete` + named gaps |
| W3 | Common-sense baseline or default number | Same as W1 | `incomplete` + named gaps |
| W4 | Behaviour of a version or flag | Same as W2 | `incomplete` + named gaps |

Source classes carried per claim: `primary` (standard owner, official product doc, original study), `secondary` (reputable write-up), `tertiary` (forum). Search snippets and agreement between providers are never evidence.

### C2 — Consultation dispositions and dispatcher failure classes

| ID | Kind | Value | Meaning |
|---|---|---|---|
| DS-1 | disposition | `supported` | Decisive claims pass their evidence check; no material dispute remains |
| DS-2 | disposition | `qualified` | Agreement with recorded reservations or unchecked premises |
| DS-3 | disposition | `unresolved` | Dispute remains after the round cap; both positions reach the human |
| FC-1 | failure | `ok` | Result validated against schema |
| FC-2 | failure | `unsupported` | Capability the participant lacks |
| FC-3 | failure | `missing_binary` | CLI not on PATH |
| FC-4 | failure | `auth` | No credentials |
| FC-5 | failure | `billing` | Auth mode is not subscription, or a required declaration is missing, or the CLI config carries an API key |
| FC-6 | failure | `quota` | Usage window ended; never a reason to switch auth |
| FC-7 | failure | `transient` | Retry within bounded attempts |
| FC-8 | failure | `timeout` | Deadline reached; process tree cleaned |
| FC-9 | failure | `cancelled` | Parent cancelled the job |
| FC-10 | failure | `invalid_output` | Output fails the schema |
| FC-11 | failure | `task_failure` | Participant reported failure |
| FC-12 | failure | `unknown` | Not classified; original error retained |

Run-level exit codes reuse the adapter answer shape (`ADAPTERS.md` answer-shape table): `0` verdict, `3` single participant, `4` unavailable.

### C3 — Participant providers and billing

| ID | Provider | Invocation | Subscription path | Refused when | Default |
|---|---|---|---|---|---|
| P-claude | Claude Code | native subagent when the host is Claude (ADR-0006); else `claude -p` on stdin, never `--bare` | `/login` OAuth or `CLAUDE_CODE_OAUTH_TOKEN` | any of `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `apiKeyHelper`, `CLAUDE_CODE_USE_BEDROCK/VERTEX/FOUNDRY`, gateway credential is active | on |
| P-codex | Codex CLI | `codex exec -` with `-c forced_login_method=chatgpt`, `--sandbox read-only` | ChatGPT login | `codex login status` reports API key; `OPENAI_API_KEY`/`CODEX_API_KEY` present | on |
| P-agy | Antigravity CLI | `agy -p` | Google account login | `modelProvider: gemini`, `GEMINI_API_KEY`, or `useG1Credits: true` in its settings | off until live conformance (step 5) |
| P-grok | Grok Build | `grok -p` | `grok login` session | per-model `api_key`/`env_key` in `~/.grok/config.toml`; `XAI_API_KEY` without session | off until live conformance (step 5) |
| P-gemini | Gemini CLI | `gemini -p` | none (API key only since 2026-06-18) | always while `subscription_only` holds | excluded |

### C4 — Artifacts and their consumers

| ID | Artifact | Sole writer | Consumers |
|---|---|---|---|
| AR-1 | `{spec}/research/<id>/REPORT.md` | `/afk:research` | grill pre-brief digests; ADR Context and Alternatives sections written by `/afk:to-prd` and `/afk:to-sdd`; `/afk:consult` briefs; cited on cards as grade `spec` |
| AR-2 | `{spec}/research/<id>/evidence.json` | `/afk:research` | `/afk:consult` (claim sources, dates, contradictions); report renderer |
| AR-3 | `{spec}/consult/<id>/request.json` | `/afk:consult` | dispatcher validation (identity, scope, permission, route, deadline, billing) |
| AR-4 | `{spec}/consult/<id>/jobs/<participant>/result.json` | dispatcher | consultation judge; challenge round |
| AR-5 | `{spec}/consult/<id>/REPORT.md` | `/afk:consult` | the calling grill or gate; `/afk:retro` (`changed_answer` metadata) |
| AR-6 | `{spec}/consult/<id>/state.json` | dispatcher | dispatcher resume on another host (read-only jobs) |
| AR-7 | raw provider streams (scratch, outside the spec folder) | dispatcher | diagnostics; expired by the next dispatcher run |
| AR-8 | `RESEARCH.md` (plugin root) | plugin author | `/afk:research`, `afk-researcher`, caller pointers |
| AR-9 | `DECISIONS.md` "Prepared ask" section | plugin author | `ROUND.md` debate/confirm items; execute, preflight and autopilot park reports; `scripts/lavish/schema.py` |
| AR-10 | `DELEGATION.md` dispatch and handoff section | plugin author | `/afk:consult`, dispatcher, fallback resume |

### C5 — Plug-in points (callers of research and consultation)

| ID | Caller | Research purpose | Consultation boundary |
|---|---|---|---|
| PP-1 | `/afk:grill-requirements` | user problem, external practice, scope alternatives, organization priorities | prepares a round; the human accepts decisions |
| PP-2 | `/afk:grill-solution` | official compatibility, constraints, implementation alternatives | code claims link to closed or explicitly partial investigations |
| PP-3 | `/afk:grill-verification` | failure scenarios, standards-based obligations | obligations become proposed scenarios through existing writers |
| PP-4 | `/afk:review` | — | participants are ordinary concern reviewers under existing concern ids; no new concern; provenance stays in AR-3..AR-5 |
| PP-5 | `/afk:adversary` | — | second independent adversary; blindness to the diff kept |
| PP-6 | `/afk:fix` (diagnosis) | — | competing hypotheses ranked; opt-in route |
| PP-7 | standalone | any W1–W4 question before a feature exists | caller supplies scope and output directory |

Trigger for any row: an external claim, a consequential unknown, or a configured route. Elapsed time never triggers. Not a plug-in point: any human conversation, any synthesis skill, single-writer stamps, and investigation counter-search (ADR-0008).

## User Stories

1. As a designer grilling a feature, I want vendor and standard claims verified against primary sources before they reach me, so that no version or flag premise is decided on memory.
2. As a team lead, I want each item that reaches me to carry a recommendation, graded evidence, what was tried, and the cost of postponing, so that I decide in one pick.
3. As a designer, I want the team's settled priorities surfaced from its own ADRs and decision ledgers as cited, advisory findings, so that a recommendation matches how the team already decides.
4. As a reviewer, I want a second provider to investigate the same question independently and challenge my model's conclusion, with dissent preserved, so that one model's blind spot is not the plan's blind spot.
5. As a subscriber, I want every cross-provider call to draw on the subscription I already pay for, and to stop at its usage window, so that no run ever bills an API key or a credit balance.

## Acceptance Criteria

Research (`/afk:research`)
- [ ] AC-001 A W2 or W4 question returns `closed` only when the report cites one authoritative primary source with quoted text, URL and fetch date; without one it returns `incomplete` with the unanswered question named.
- [ ] AC-002 A W1 or W3 question returns `closed` only when every declared question, material counterclaim and option-eliminating assumption carries a disposition; any missing disposition returns `incomplete`.
- [ ] AC-003 A claim supported only by a search snippet, or only by two providers agreeing, is recorded as `unverified`, never as fact.
- [ ] AC-004 Each material claim in AR-2 carries source locator, retrieval date, source class (C1), applicability, and `fact` or `inference`; a claim missing any field fails the research fixture.
- [ ] AC-005 An inferred organization priority is recorded with scope, authority, supersession, provenance and counterevidence, marked advisory; a report that states a priority as binding fails the fixture.
- [ ] AC-006 Research exhausting `research.max_minutes` returns `incomplete` with named gaps; it never claims the web was exhaustively searched.
- [ ] AC-007 With `research.public: off`, no web tool call occurs; with `when_relevant`, a web call occurs only for a question an authorized local tool cannot settle; with `required`, a run with no web call fails.
- [ ] AC-008 A public query that contains a glossary-listed internal term, a ticket id, code, or a customer identifier is rejected before it leaves the machine.

Prepared ask
- [ ] AC-009 A `debate_card` with fewer than 2 options, or without `recommended`, `why`, `undecided_because`, fails to render (existing check); `exhausted` and `postpone_cost` are accepted when present and absent without error.
- [ ] AC-010 A value judgment reaches the human as a `debate` item with `undecided_because` naming the value; the renderer accepts it.

Consultation (`/afk:consult`)
- [ ] AC-011 With `consultation.enabled: false` or the block absent, no participant runs and every caller behaves as before.
- [ ] AC-012 Round-0 reports are written before any participant sees another's output; a fixture that injects peer text into round 0 fails.
- [ ] AC-013 Exactly 1 challenge round runs; a configuration requesting more is rejected at validation.
- [ ] AC-014 In the challenge round, a participant's `none found` is accepted only with the evidence check cited; without it the report is `invalid_output` (FC-10).
- [ ] AC-015 A changed position without cited evidence is recorded as `unjustified` and excluded from the disposition.
- [ ] AC-016 The disposition is one of DS-1..DS-3; vote counts appear only as metadata; a factual dispute is checked against an official source or local probe before any human escalation.
- [ ] AC-017 With 2 participants, a judge that authored no position adjudicates; when none can be reserved, the disposition is `unresolved` and both positions reach the human.
- [ ] AC-018 A consultation report never changes a review finding class, review verdict, or adversary verdict; the gate's own routing applies unchanged (ADR-0007).
- [ ] AC-019 With `unavailable: single` and exactly 1 healthy participant, the run exits `3` and the report is marked single-provider; with `unavailable: block`, it exits `4`; with 0 participants, it exits `4` in both modes.

Dispatch (`scripts/dispatch_harness.py`)
- [ ] AC-020 The prompt reaches the child on stdin; no shell text from a provider is evaluated; a fixture with spaces and Unicode in paths and prompt passes.
- [ ] AC-021 A child that exits `0` with output failing the schema is `invalid_output`, never `ok`.
- [ ] AC-022 A job exceeding its deadline is `timeout` and its process tree is gone within 5 seconds on Windows.
- [ ] AC-023 Every failure maps to exactly one FC-1..FC-12 class; an unrecognized error is `unknown` with the original text retained in protected scratch.
- [ ] AC-024 The child environment contains only allowlisted variables; a fixture exporting `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY` sees none of them in the child.
- [ ] AC-025 With `billing: subscription_only` (default), a participant whose auth gate reports `api` or `none` is `billing` (FC-5) and skipped; no run falls back to an API key.
- [ ] AC-026 A `quota` result on a subscription participant ends that participant for the window; it is never retried with different auth.
- [ ] AC-027 A participant marked with `credits: disabled` absent, on a route requiring it, is `billing` (FC-5).
- [ ] AC-028 Unfinished read-only jobs listed in AR-6 resume on a second host without re-running completed jobs; a job with a write policy is never resumed.
- [ ] AC-029 Raw provider streams older than `retain_raw_days` are deleted by the next dispatcher run; AR-1..AR-6 survive.

Egress
- [ ] AC-030 By default a participant's working directory contains only staged, approved files; a fixture with a denied path or a secret file sees it absent from the staging directory.
- [ ] AC-031 Whole-repository access runs only when the participant's `allowed_paths` grants it explicitly.
- [ ] AC-032 A destination without a `no_training` declaration is refused on a route that requires one (ADR-0002).

Configuration
- [ ] AC-033 An unknown key under `research:` or `consultation:` is rejected by the config reader with the key named.
- [ ] AC-034 `billing: false` with a participant lacking `billing: api` is rejected at validation; when accepted, the value appears in AR-3 and one journal line.
- [ ] AC-037 A route that requires a hard spend cap on a destination whose CLI cannot enforce one blocks that route at validation with the destination named; no job runs.
- [ ] AC-038 The enforced budget units are turns (`max_turns` per job) and window headroom from the provider probe; a dollar figure is recorded as `requested`, never as `enforced`, on every destination.
- [ ] AC-039 A job ended by its deadline is reported as `timeout` (FC-8) in every report and journal line; no report or page presents a timeout or a turn cap as a dollar cap.
- [ ] AC-040 The billing gate removes `CODEX_API_KEY` and `OPENAI_API_KEY` from the Codex child environment as a control separate from `-c forced_login_method=chatgpt`; a fixture exporting either key sees neither in the child and the job still runs under the ChatGPT login (PREMISES-CHECK.md #2: `codex login status` reports stored auth only, `codex exec` honors `CODEX_API_KEY` when API auth is allowed).
- [ ] AC-041 A `subscription_only` route requires the participant declaration `usage_credits: disabled` (the config spelling of the `credits: disabled` declaration in ADR-0005); a Claude participant without it is `billing` (FC-5) and the route blocks, deterministically and before any live probe. A dollar balance is never shown as a cap (AC-038, AC-039).
- [ ] AC-042 The cross-provider `claude -p` route is off by default; with no explicit `enabled: true` on that route, no `claude` subprocess is spawned and the participant is reported `unsupported` (FC-2).
- [ ] AC-043 The Codex billing gate has three separately tested controls: `CODEX_API_KEY` absent from the child environment, `OPENAI_API_KEY` absent from the child environment, and `-c forced_login_method=chatgpt` present on the command line; each fixture fails when its one control is removed.
- [ ] AC-044 The headroom probe reports an exhausted monthly Agent SDK credit, or an exhausted plan window, as the end of the usage window (`quota`, FC-6), never as an error class, in both live states of the Claude plan article (separate monthly credit, or plan-limit draw).

Plug-in points and evaluation
- [ ] AC-035 Each PP-1..PP-7 caller runs research or consultation only on its documented trigger; a run with no trigger produces no research or consult artifact.
- [ ] AC-036 The evaluation fixture set (single provider, independent reports, reports + challenge) reports citation support, factual error, unjustified consensus, useful dissent, human decisions required, time and provider usage; `changed_answer` is present as metadata only.

## Access & validation policy

| Capability | Permitted actor | Denied actor | Data scope | Key validation rules |
|---|---|---|---|---|
| Run research (PP-1..PP-3, PP-7) | host agent in an interactive or autopilot session | any child agent below nesting cap 3; a participant | spec folder of the work item; web with sanitized queries | `research:` block present; query hygiene (AC-008) |
| Write AR-1, AR-2 | `/afk:research` only | every other skill | spec folder | single writer |
| Run consultation | host agent through a configured route | human conversation; synthesis skills; participants themselves | staged evidence only unless `allowed_paths` grants more | `consultation.enabled`, route resolves, ≥1 participant passes auth gate |
| Participant execution | dispatcher | any skill directly | staging directory; read-only | subscription auth gate; allowlisted env; deadline |
| Accept a decision or priority | human | `/afk:consult`, `/afk:research`, dispatcher | — | ADR-0001, ADR-0007 |
| Set `billing: false`, `no_training`, `credits` | repository administrator in `.afk/config.yaml` | any agent | repository | value echoed to AR-3 and journal (AC-034) |

## Implementation Decisions

| Module | Responsibility | Decision |
|---|---|---|
| `RESEARCH.md` (root doctrine) | question types C1, source classes, citation shape, sufficiency, query hygiene, organization-priority inference rules | new file; `INVESTIGATION.md` gains one pointer, keeps code closure |
| `skills/utils/research/` + `agents/afk-researcher.md` | executable procedure; frontier-tier child with web tools | new skill and agent; `web_access` capability row with per-harness mapping and `unavailable` degradation |
| `DECISIONS.md` "Prepared ask" + `ROUND.md` + `scripts/lavish/schema.py` | the bar for anything reaching a human; 2 optional card fields | 4-file round-dossier lockstep, same commit |
| `skills/utils/consult/` + protocol sibling | sealed reports, 1 challenge round, dispositions, judge rule | advisory only — ADR-0007 |
| `scripts/dispatch_harness.py` | subprocess lifecycle, allowlisted env, auth gate, failure classes, `state.json`, raw-stream expiry | one script; rules for dispatch and handoff live once in `DELEGATION.md` |
| `hooks/lib/providers/<name>.sh` + `PROVIDERS.md` + `providers/CONFORMANCE.md` | member verbs `probe`, `invocation`, `parse_result`, `classify_failure`, `auth_mode`, optional `quota_headroom`; billing env-deny list; config-file refusal rule; `host`/`member` role | Claude + Codex in the pilot; agy and Grok after live conformance — ADR-0004 |
| `.afk/config.yaml` schema (`CONFIG.md`, `scripts/afk-config.py`) | `research:` and `consultation:` blocks; `billing` hard default | ADR-0002, ADR-0003, ADR-0005 |
| Caller pointers (PP-1..PP-7) | one line per chosen branch | callers name the utility; the utility never names a caller |
| Organization priorities | advisory in AR-1; accepted ones go to CLAUDE.md through `/afk:claude-md` | no registry now — ADR-0001 |
| Same-provider participant | native subagent, no subprocess, no billing gate | ADR-0006 |
| Registry surfaces | `GLOSSARY.md` terms (research, world question, consultation, participant, prepared ask, disposition), `CAPABILITIES.md` rows, `skills/afk/setup/MANIFEST.md` opt-in rows, `FRESHNESS.md` rows, both plugin manifests, CLAUDE.md and README catalogs | same-commit rule per `FRESHNESS.md` |

Candidate new staple: none.

## Testing Decisions

- Fixture-driven, no live paid runs: research fixtures (authoritative fact, contradicted claim, stale source, organization inference, `incomplete`); consult fixtures (sealed reports, preserved dissent, 1-round cap, `single`, `block`); dispatcher fake-process tests (timeout, quota, malformed output, cancel, spaces and Unicode, atomic resume, env allowlist, auth gate).
- Prior art: `scripts/tests/test_afk_config.py` for config keys; `hooks/tests/envelopes/` for provider envelopes; `scripts/lavish/schema.py` contract errors for card fields.
- Conformance: one recorded live probe per participant provider in `providers/CONFORMANCE.md`; unverified fields (`claude auth status` output fields, `codex login status` strings) become fixtures at step 2.
- Gates before ship: hook tests, `skill-registry-gate`, `genericity-gate`, `/afk:setup audit`, `/afk:verify-seams final`.

## Out of Scope

- Executor or write-role hop to another provider; automatic host replacement (ADR-0004; IOU on `state.json`).
- A priorities registry file (ADR-0001; IOU on a retro-observed trigger).
- Gemini CLI as a participant; agy and Grok before live conformance (C3).
- MCP bridges, OpenRouter, LiteLLM, 1devtool in the runtime path.
- New review concern, new evidence grades, investigation counter-search route (ADR-0008).
- Publishing any artifact to a tracker.

## Further Notes

Assumptions this PRD rests on (unverified premises, all outside this repository):
- #1 HYPOTHESIS: `claude auth status --json` field names and whether the subscription tier is reported (unverified premise: field names). Step 2 captures fixtures for the subscription, API-key and logged-out states; an absent or unknown `subscriptionType` fails closed (AC-025).
- #2 REFUTED (PREMISES-CHECK.md #2): `codex login status` reports stored auth only, not the environment override, and `codex exec` honors `CODEX_API_KEY` when API auth is allowed. Consequence: the billing gate strips `CODEX_API_KEY` and, conservatively, `OPENAI_API_KEY` from the child environment as a control separate from `forced_login_method=chatgpt` (AC-024, AC-040).
- #3 HYPOTHESIS: whether `claude -p` draws an enabled usage-credit balance without a confirmation. Source statements, both from support.claude.com article 15036540 (recorded 2026-09-15, orchestrator page extraction): "When your monthly credit runs out, additional Agent SDK usage flows to usage credits at standard API rates—but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes." and "Starting June 15, 2026, Claude Agent SDK and `claude -p` usage no longer counts toward your Claude plan's usage limits." against "For now, nothing has changed: ... `claude -p` ... still draw from your subscription's usage limits." Which statement is current is unresolved. Deterministic control: the `subscription_only` route requires `usage_credits: disabled` and blocks without it (AC-027, AC-041). Confirmation: live probe per PREMISES-CHECK.md:120-132 (small known balance, one fixed one-turn run, re-read balance, repeat at exhausted capacity, control with credits disabled). USER-GATED: the probe spends a small known credit balance and runs only with explicit user approval at execution time.
- #4 HYPOTHESIS, DEFERRED to step 5: Antigravity settings keys `modelProvider` and `useG1Credits` are verified names; their absent-key defaults are not documented. Step 5 probe per PREMISES-CHECK.md:151-157 (clean isolated profile, `/config` effective values, toggle each). C3 P-agy stays disabled until the probe completes.
- #5 HYPOTHESIS, recorded as an accepted policy risk (user decision A with 4 conditions, 2026-09-15; ADR-0006). Verified texts only: support.claude.com article 13189465 says "The preferred way ... is through API key authentication", says "If you're building a product, application, or tool for others, use API key authentication through Claude Console or a supported cloud provider.", and that to "... misrepresent their identity ... route third-party traffic against subscription limits ... is prohibited"; article 15036540 says "Starting June 15, 2026, Claude Agent SDK and `claude -p` usage no longer counts toward your Claude plan's usage limits", "For now, nothing has changed: ... `claude -p` ... still draw from your subscription's usage limits", and the overflow rule "additional Agent SDK usage flows to usage credits at standard API rates—but only if you've enabled usage credits. If usage credits aren't enabled, Agent SDK requests stop until your credit refreshes." The accepted risk names that sentence: the plugin is a tool, and the route runs it under the user's own subscription login rather than an API key. Rationale: first-party use of the unmodified binary under the user's own login is not third-party traffic and misrepresents no identity; extra paid use happens only with usage credits enabled, which condition (c) forbids. Conditions: (a) unmodified binary, own login, no token extraction; (b) `ANTHROPIC_API_KEY` stripped, no `--bare`; (c) `usage_credits: disabled` declared or the route blocks (AC-041); (d) the cross-provider `claude -p` route is opt-in, off by default (AC-042); the enable rule lives behind one config switch so a later decision B ("written Anthropic guidance required before enabling") changes one key, not the design.

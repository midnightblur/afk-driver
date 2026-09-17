# 0003-dispatch-harness — the participant dispatcher

## Goal
Create `scripts/dispatch_harness.py`, the one site that spawns a provider CLI: `run --request <request.json> --out <dir>` (prompt on stdin), `resume --state <state.json>`, `probe --provider <name>`. It validates the request record, reserves the judge, runs the gate before anything a participant could see (auth mode `subscription`, `usage_credits: disabled` present, `no_training` where the route requires it, unknown mode fails closed, cross-provider Claude route off unless its one switch is `true`), builds the staging directory from the approved evidence list, constructs the child environment from an allowlist, spawns each participant through the provider verbs with a deadline, kills the process tree on timeout, classifies every ending into one FC-1..FC-12 class, writes `result.json` per job and `state.json` by temp-file-plus-rename, resumes read-only jobs on another host, and expires raw streams older than `retain_raw_days`. Exit codes follow the adapter answer shape: 0 verdict, 3 single or missing verb, 4 unavailable, 2 unresolved config. The rules for dispatch and handoff land once, as a `## Dispatch and handoff` section in `DELEGATION.md`.

## Complexity
complex

## Review
policy: full — the dispatcher is the one spawn site and the largest slice; the full roster runs here, the plan stays lean elsewhere
opt-in: resilience, logic-correctness — every later slice imitates this subprocess and file-write pattern; a defect here multiplies into every participant run

## Design refs
- SDD: SDD.md#§3 rows "dispatcher `run`", "dispatcher `resume`", "dispatcher `probe`" — the CLI surface, envelopes, exit codes, idempotency
- SDD: SDD.md#§3 sequence "consult skill → dispatcher → provider verbs → participant CLI" — gate before staging and spawn
- SDD: SDD.md#§4 "State table", "Entity design" — `result.json`, `state.json`, raw streams in scratch; shapes verbatim in `SIGNED-PACKETS.md` §HL-1
- SDD: SDD.md#§5 "AuthN", "AuthZ", "Data scoping", "Idempotency", "Retry + timeout", "Observability" — gate rules, staging, allowlist, deadlines, journal line
- SDD: SDD.md#§6 invariants I-1, I-3, I-6, I-7 and the participant-job state machine
- SDD: SDD.md#§7 "Failure & recovery matrix" F-1..F-5, F-8; "Outward and irreversible effects" E-1, E-3, E-4, E-5
- SDD: SDD.md#§8 row "dispatcher script" — public interface `run`, `resume`, `probe`
- SDD: SDD.md#§9b rows "Claude CLI headless invocation", "Codex CLI headless invocation", "Windows process tree" — seam-tests
- SDD: SDD.md#§13 row "Windows process-tree kill" — no mechanism exists in the repo today; the deadline table in §5 is the contract
- ADR: adr/design/0002-classified-result-and-state-file.md — tagged-union `class`; exit 0 is never success by itself; one `state.json`, atomic replace
- ADR: adr/design/0004-gate-before-spawn-and-staging.md — gate order; staging from an allowlist; child env from an allowlist
- ADR: adr/design/0001-provider-strategy-member-verbs.md — the dispatcher calls only the verb contract; exit 3 on a missing verb
- ADR: adr/requirements/0004-pilot-read-only-claude-codex.md — read-only jobs only; resume from `state.json`
- ADR: adr/requirements/0005-subscription-only-billing-with-credit-declarations.md — refuse, never fall back; quota ends the window
- ADR: adr/requirements/0006-same-provider-participant-is-native-subagent.md — conditions (a)–(d) on the `claude -p` route

## Scope
- scripts/dispatch_harness.py
- scripts/tests/test_dispatch_harness.py
- scripts/tests/test_dispatch_seams.py
- scripts/tests/samples/dispatch/**        # fake provider CLIs + recorded streams the tests put on PATH
- DELEGATION.md                            # the new `## Dispatch and handoff` section only
- FRESHNESS.md                             # one registry row for the dispatcher + its tests

## Seams
- implement: §9b "Claude CLI headless invocation" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — this subtask owns the spawn + seam-test `test_dispatch_claude_envelope` (INV-003)
- implement: §9b "Codex CLI headless invocation" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — this subtask owns the spawn + the three AC-043 tests (INV-003)
- implement: §9b "Windows process tree" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — no spawn site exists today; this subtask owns the kill + seam-test `test_timeout_kills_tree_5s` (INV-003)
- use: §9b "Provider status strings" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — calls `auth_mode` / `quota_headroom`; relies on their output contract (INV-003)
- use: §14 row "config reader `TOP_LEVEL` and `export-shell` flattening (`scripts/afk-config.py:541,978-990`)" — reads the validated `consultation:` block through `afk-config.py get` (INV-002)
- implement: §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — this subtask adds the `## Dispatch and handoff` section to `DELEGATION.md` (INV-004)

## Acceptance
- [ ] The prompt reaches the child on stdin; no text from a provider is passed to a shell; a fixture with spaces and Unicode in paths and prompt passes (PRD AC-020)
- [ ] A child that exits `0` with output failing the schema is classified `invalid_output`; `ok` is written only after schema validation (PRD AC-021)
- [ ] A job exceeding `deadline_minutes` is `timeout`, and its process tree (child + grandchild) is gone within 5 seconds on Windows (PRD AC-022)
- [ ] Every job ending maps to exactly one FC-1..FC-12 value in `result.json.class`; an unrecognised error is `unknown` with the original text retained in scratch (PRD AC-023)
- [ ] The child environment is constructed from an allowlist (PATH, HOME, locale, provider login files); a fixture exporting `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CODEX_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY` sees none of them in the child (PRD AC-024)
- [ ] Under `billing: subscription_only`, a participant whose `auth_mode` is `api`, `none` or `unknown` is `billing` (FC-5) and skipped; no code path retries with another auth (PRD AC-025; SDD §5 "AuthN")
- [ ] A `quota` result ends that participant for the run; it is never re-queued (PRD AC-026)
- [ ] A participant without `usage_credits: disabled` on a `subscription_only` route is `billing` (FC-5) and the route blocks before any probe or spawn (PRD AC-027, AC-041)
- [ ] `resume --state` runs only jobs not `done`, refuses any job whose `write_policy` is not `read-only`, and treats a `running` job past `deadline_at` as `timeout` with one re-queue when `transient` budget remains (PRD AC-028; SDD §7 use case "resume")
- [ ] Raw streams under the scratch directory older than `retain_raw_days` (default 7) are deleted by the next run; `request.json`, `result.json`, `state.json`, `REPORT.md`, `evidence.json` are never touched (PRD AC-029)
- [ ] The staging directory holds only files on the approved evidence list; a denied path or a file matching a secret pattern is absent; `denied_paths` wins over `allowed_paths` (PRD AC-030)
- [ ] Whole-repository access is granted only when the participant's `allowed_paths` names it explicitly (PRD AC-031)
- [ ] On a route that requires `no_training`, a destination without the declaration is refused (FC-5) with the destination named (PRD AC-032)
- [ ] `billing` and `no_training` values from config are echoed into `request.json` and one `plan/JOURNAL.md` line per run (PRD AC-034)
- [ ] Budget units are `max_turns` per job and window headroom from the probe; a dollar figure in config is recorded as `requested`, never `enforced` (PRD AC-038)
- [ ] A deadline ending is reported as `timeout` (FC-8) in `result.json`, `state.json` and the journal line; no output presents a timeout or turn cap as a dollar cap (PRD AC-039)
- [ ] `CODEX_API_KEY` and `OPENAI_API_KEY` are removed from the Codex child environment as a control separate from `-c forced_login_method=chatgpt`; the job still runs under the ChatGPT-login fixture (PRD AC-040)
- [ ] Three separate tests exist for the Codex controls — `CODEX_API_KEY` absent, `OPENAI_API_KEY` absent, `-c forced_login_method=chatgpt` present — and each fails when its one control is removed (PRD AC-043)
- [ ] With the cross-provider Claude route switch absent or `false`, no `claude` subprocess is spawned and the participant is `unsupported` (FC-2); with `true`, `ANTHROPIC_API_KEY` is absent from the child and `--bare` never appears in the argv (PRD AC-042; ADR-0006)
- [ ] A missing member verb on the selected provider file makes the dispatcher exit 3; the library's silent fallback is not used (SDD §3 row "provider member verbs"; ADR-0001)
- [ ] Round-0 prompts carry no other participant's output; a fixture that injects peer text into a round-0 prompt fails; a round-1 `none found` counterclaim without `evidence_check` is `invalid_output` (SDD §6 I-1, I-7; PRD AC-012, AC-014)
- [ ] `state.json` is written by temp-file-plus-rename after every job transition; a `done` job never re-runs; the judge is reserved before dispatch or recorded `null` (ADR-0002; SDD §5 "Idempotency")
- [ ] `probe --provider <name>` prints JSON `{auth_mode, quota_headroom, binary}` and exits 4 on a missing binary or no auth (SDD §3 row "dispatcher `probe`")
- [ ] Raw streams live under the scratch directory, never under the spec folder; a request naming a raw path inside the spec folder is refused (SDD §6 I-6)
- [ ] Every record written matches the field tables in `SIGNED-PACKETS.md` §HL-1 (`result.json`, `state.json`) with `schema: 1`; a reader rejects any other schema value (SDD §4 "Entity design")
- [ ] `DELEGATION.md` gains one `## Dispatch and handoff` section stating the dispatch rules and the resume handoff once; no skill restates them (PRD "Implementation Decisions" row "scripts/dispatch_harness.py")
- [ ] Implements the public interface in SDD §8 row "dispatcher script" unmodified: `run`, `resume`, `probe` (SDD §8)
- [ ] Conforms to ADR-0004 (design) — every gate runs before staging and before any spawn; no spawn-then-classify path exists (ADR-0004)
- [ ] Conforms to ADR-0002 (design) — `class` is a tagged union; exit 0 never means `ok`; one `state.json` per run (ADR-0002)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Seam-tests assert on the real subprocess behaviour — the fake CLI's real stdout parsed into `result.json`, the real child environment observed by the fake, the real process tree ended — not on intermediate objects (SDD §9b rows "Claude CLI headless invocation", "Codex CLI headless invocation", "Windows process tree")
- [ ] Fixtures use the real provider names `claude` and `codex`, the real env var names, and the real file names `request.json`, `result.json`, `state.json` (PRD "Testing Decisions")
- [ ] No live provider call runs in any test; every participant in tests is a fake process on PATH (PRD "Testing Decisions")

## Produces
- scripts/dispatch_harness.py#FAILURE_CLASSES — the tagged union FC-1..FC-12 values (`ok`, `unsupported`, `missing_binary`, `auth`, `billing`, `quota`, `transient`, `timeout`, `cancelled`, `invalid_output`, `task_failure`, `unknown`)
- scripts/dispatch_harness.py#ENV_ALLOWLIST — the only variable names a child environment may carry
- scripts/dispatch_harness.py#run_consultation — `run --request --out` entry: validate, reserve judge, gate, stage, spawn, classify, write; returns the exit code 0/2/3/4
- scripts/dispatch_harness.py#resume_consultation — `resume --state` entry: read-only jobs not `done` run again; other write policies refused
- scripts/dispatch_harness.py#probe_provider — `probe --provider` entry: JSON `{auth_mode, quota_headroom, binary}`; exit 4 when missing binary or no auth
- scripts/dispatch_harness.py#billing_auth_gate — the pre-spawn gate: auth mode, `usage_credits: disabled`, `no_training`, Claude-route switch; returns the FC class or passes
- scripts/dispatch_harness.py#build_staging_dir — staging directory from the approved evidence list; denied and secret-pattern paths omitted
- scripts/dispatch_harness.py#kill_process_tree — ends the child and its descendants within 5 s on Windows and POSIX
- scripts/dispatch_harness.py#write_state_atomic — temp-file-plus-rename write of `state.json`
- DELEGATION.md#Dispatch and handoff — the once-stated rules for dispatching a participant and resuming on another host

## Consumes
- 0001-config-blocks scripts/afk-config.py#CONSULTATION_KEYS — the validated `consultation:` block the dispatcher reads (participants, routes, billing, `retain_raw_days`, `deadline_minutes`, `max_turns`, `max_attempts`)
- 0001-config-blocks scripts/afk-config.py#validate_consultation_block — a config that reaches the dispatcher already passed the challenge cap, billing guard, collision and spend-cap rules
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_auth_mode — `subscription|api|none|unknown`
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_invocation — the argv for `claude -p`
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_parse_result — stdout → `result.json` candidate
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_classify_failure — exit + stream → FC class
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_quota_headroom — headroom or `quota`
- 0002-provider-verbs hooks/lib/providers/claude.sh#afk_claude_probe — probe JSON
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_auth_mode — `subscription|api|none|unknown`
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_invocation — the argv for `codex exec -`
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_parse_result — stdout → `result.json` candidate
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_classify_failure — exit + stream → FC class
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_quota_headroom — headroom or `quota`
- 0002-provider-verbs hooks/lib/providers/codex.sh#afk_codex_probe — probe JSON

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile scripts/dispatch_harness.py` + grep every ## Produces anchor + grep `DELEGATION.md` for `## Dispatch and handoff` | script loads; declared symbols present; doctrine section present |
| unit | `python -m pytest scripts/tests/test_dispatch_harness.py -q` — fake-process cases: stdin prompt with spaces + Unicode (AC-020); exit-0-bad-schema → `invalid_output` (AC-021); one class per fixture + `unknown` retention (AC-023); env allowlist with the five keys exported (AC-024); auth gate `api`/`none`/`unknown` → `billing` (AC-025); `quota` never re-queued (AC-026); missing `usage_credits: disabled` → `billing` before probe (AC-027, AC-041); atomic resume, non-read-only refused, past-deadline `running` → `timeout` (AC-028); raw-stream expiry keeps AR-1..AR-6 (AC-029); staging omits denied + secret paths, `denied_paths` wins (AC-030); whole-repo only with explicit grant (AC-031); `no_training` refusal names the destination (AC-032); config echo to `request.json` + journal line (AC-034); `requested` vs `enforced` (AC-038); `timeout` wording (AC-039); Claude route switch absent → `unsupported`, no spawn (AC-042); missing verb → exit 3; round-0 peer-text injection fails; `none found` without `evidence_check` → `invalid_output` (AC-012, AC-014) | every dispatcher rule in isolation with a fake CLI on PATH |
| integration | `python -m pytest scripts/tests/test_dispatch_seams.py -q` — `test_dispatch_claude_envelope` (recorded `claude -p` stdout fixture → valid `result.json`; unknown `subscriptionType` → FC-5); `test_codex_key_absent_codex_api_key`, `test_codex_key_absent_openai_api_key`, `test_codex_forced_login_flag_present` (AC-040, AC-043 — each fails when its one control is removed); `test_timeout_kills_tree_5s` (fake child spawns a grandchild; both gone ≤ 5 s after the deadline, on Windows) | the three §9b seams on the real subprocess boundary |

## Context excerpts
> (SDD §3 row "dispatcher `run`") `run --request <request.json> --out <dir>`; prompt on stdin | the consult skill only (§5) | request record: identity, scope, permission, route, deadline, billing; schema 1 | `result.json` per job, `state.json`, exit 0 | exit 3 / 4 per the adapter answer shape; exit 2 unresolved config; per-job class FC-1..FC-12 in `result.json` | job_id = CON-NNN/participant; a `done` job never re-runs | 1 | new
> (SDD §3 row "dispatcher `resume`") `resume --state <state.json>` | the consult skill, on any host | `state.json` schema 1 | remaining read-only jobs run; exit 0 | as `run`; a job whose `write_policy` is not `read-only` is refused | same job ids | 1 | new
> (SDD §3 row "dispatcher `probe`") `probe --provider <name>` | the consult skill or setup | provider name in config | JSON `{auth_mode, quota_headroom, binary}` | exit 4 missing binary or no auth | read-only, repeatable | 1 | new
> (SDD §3 sequence caption) the auth gate runs before any staging or spawn; a refused participant never receives content.
> (SDD §4 "State table" row "Raw provider streams") scratch, outside the spec folder | per run and participant | none | `retain_raw_days` (default 7), deleted by the next dispatcher run | never committed | possible (provider chatter) | no
> (SDD §4 "Entity design") the file set and the four record shapes (claim record, `evidence.json`, `result.json`, `state.json`) stand verbatim in `SIGNED-PACKETS.md` §HL-1 and are binding here without restatement. Identity: `RES-NNN` and `CON-NNN` sequential per spec folder; job identity `CON-NNN/<participant>`; the reader tolerates a `-b` suffix on collision across worktrees.
> (SDD §5 "AuthN" sequence notes) subscription and usage_credits: disabled and no_training (when required) → proceed · anything else → FC-5 billing, skipped, no retry with other auth
> (SDD §5 "AuthZ" row "Enable the cross-provider Claude route *(amendment)*") repository administrator, one config switch, default off | any agent | route resolution | dispatcher reports `unsupported` (FC-2) when the switch is absent (AC-042)
> (SDD §5 "Data scoping" row "Working directory") staging directory, approved files only | `allowed_paths` per participant; `denied_paths` always wins | staging built from the evidence list; denied or secret-pattern files never copied (AC-030, AC-031)
> (SDD §5 "Data scoping" row "Environment") allowlist only (PATH, HOME, locale, provider login files) | none | child env constructed, not inherited (AC-024); `ANTHROPIC_API_KEY`, `CODEX_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`, `GEMINI_API_KEY` absent *(amendment: each Codex key its own test, AC-043)*
> (SDD §5 "Idempotency" row "dispatcher job") `CON-NNN/<participant>` | life of the run | `state.json.jobs[]` status; a `done` job never re-runs
> (SDD §5 "Retry + timeout" row "participant job") 1 + `max_attempts` re-queues, `transient` only (default 1) | fixed 30 s | `deadline_minutes` (default 45); process tree killed within 5 s on Windows (AC-022)
> (SDD §5 "Retry + timeout" row "provider probe") 1 | — | 30 s
> (SDD §5 "Rate limit") None imposed by the plugin; budgets are turns per job (`max_turns`) and window headroom from the probe (AC-038).
> (SDD §5 "Observability") one journal line per consultation run (route, participants, classes, disposition, billing value) | a refused participant, a single-provider run, a `billing: false` route (§7 F-1..F-3)
> (SDD §6 I-1) Round-0 reports written before any participant sees another's output | consultation run | dispatcher prompt builder | fixture fails; runtime `invalid_output`
> (SDD §6 I-3) Subscription-only unless `billing: false` declared | consultation run | dispatcher auth gate | `billing` (FC-5), skipped, never retried with other auth
> (SDD §6 I-6) Raw streams never under the spec folder | consultation run | dispatcher path rule | path validation refuses; expiry (AC-029)
> (SDD §6 I-7) `none found` counterclaim only with an evidence check | participant job | result schema | `invalid_output` (AC-014)
> (SDD §6 participant-job state machine caption) participant job; `done` and `failed` are terminal, and only `transient` re-queues.
> (SDD §7 use case "resume") host quota ended or session lost | read-only jobs only (ADR-0004) | as above | past `deadline_at` on a `running` job is `timeout`, one re-queue if `transient` budget remains
> (SDD §7 F-3) child hung | deadline reached | `timeout` (FC-8), process tree killed, one re-queue if `transient` budget | none | dispatcher
> (SDD §7 F-8) staged file matches a secret pattern | staging refuses | file omitted | administrator approves explicitly | dispatcher
> (SDD §7 "Outward and irreversible effects") Amendments: E-3 counts an exhausted monthly Agent SDK credit as the end of the window (AC-044); the cross-provider Claude route is off by default and, when enabled, strips `ANTHROPIC_API_KEY` and never passes `--bare` (ADR-0006 conditions).
> (SDD §8 row "dispatcher script") subprocess lifecycle, auth gate, staging, env allowlist, failure classes, resume, raw-stream expiry | `run`, `resume`, `probe` (§3) | provider library, config reader | consultation run, participant job
> (SDD §9b row "Claude CLI headless invocation") `claude -p` on the user's installed version (no version pin in this repo; probed live) | reads the prompt from stdin; prints the result; draws on the subscription window (both live states of the plan article, PRD #5) | support article 15036540 text quoted in PRD Further Notes; `claude auth status --json` fixtures captured at step 2 | `billing` / `quota` / `invalid_output` | `test_dispatch_claude_envelope`: fixture stdout parsed to a valid `result.json`; unknown `subscriptionType` → FC-5
> (SDD §9b row "Codex CLI headless invocation") `codex exec -` with `-c forced_login_method=chatgpt --sandbox read-only` | reads stdin; stored ChatGPT login; honors `CODEX_API_KEY` if present in env | PREMISES-CHECK.md #2 | `billing` / `quota` / `invalid_output` | three tests: key absent ×2, flag present (AC-043)
> (SDD §9b row "Windows process tree") OS job objects / `taskkill /T` | ends the child and grandchildren | fixture AC-022 | orphan process | `test_timeout_kills_tree_5s`
> (SDD §13 row "Windows process-tree kill") no mechanism exists in the repo today; the seam-test `test_timeout_kills_tree_5s` and fixture AC-022 are step-2 deliverables | L4 | no (implementer builds it under AC-022; the deadline table in §5 is the contract)
> (SDD §14 row "provider shell library function set" — conventions) the child-environment precedent `hooks/run-hook.py:142-150` copies `os.environ` and strips nothing, so the allowlist is new code
> (ADR-0002 design) Every job ends in a `result.json` whose `class` field is one value of the tagged union FC-1..FC-12; `ok` is written only after schema validation, so exit 0 is never success by itself (SDD §4 entity design, AC-021). One `state.json` per run is the single source of truth for resume: the dispatcher writes it by temp-file-plus-rename after every job transition, a `done` job never re-runs, and a `running` job past `deadline_at` reads as `timeout` on resume
> (ADR-0004 design) The dispatcher runs every check before it builds anything a participant could see: `auth_mode` must be `subscription`; the `usage_credits: disabled` declaration must be present; a route that requires `no_training` blocks without it; an unknown mode fails closed. Only then it builds a staging directory from the approved evidence list (denied and secret-pattern paths never copied; `denied_paths` wins) and a child environment constructed from an allowlist, with every provider API key absent. A refused participant is classified `billing` (FC-5), skipped, and never retried under another auth
> (ADR-0001 design) The dispatcher adopts the adapter-family answer shape (`ADAPTERS.md`) and exits 3 when a provider file lacks a verb; this is a deliberate second convention beside the library's silent fallback, because a missing `auth_mode` must never read as "no gate".
> (ADR-0006 requirements) (a) only the unmodified `claude` binary under the user's own login, never an extracted token; (b) `ANTHROPIC_API_KEY` stripped from the child environment, never `--bare`; (c) the `subscription_only` route requires a declared `usage_credits: disabled` or it blocks; (d) the cross-provider `claude -p` route is opt-in and off by default, behind one config switch
> (PRD AC-040) The billing gate removes `CODEX_API_KEY` and `OPENAI_API_KEY` from the Codex child environment as a control separate from `-c forced_login_method=chatgpt`; a fixture exporting either key sees neither in the child and the job still runs under the ChatGPT login (PREMISES-CHECK.md #2: `codex login status` reports stored auth only, `codex exec` honors `CODEX_API_KEY` when API auth is allowed).
> (PRD AC-043) The Codex billing gate has three separately tested controls: `CODEX_API_KEY` absent from the child environment, `OPENAI_API_KEY` absent from the child environment, and `-c forced_login_method=chatgpt` present on the command line; each fixture fails when its one control is removed.
> (PRD C2) Run-level exit codes reuse the adapter answer shape (`ADAPTERS.md` answer-shape table): `0` verdict, `3` single participant, `4` unavailable.
> (PRD C4 AR-7) raw provider streams (scratch, outside the spec folder) | dispatcher | diagnostics; expired by the next dispatcher run
> (PRD "Implementation Decisions" row "scripts/dispatch_harness.py") subprocess lifecycle, allowlisted env, auth gate, failure classes, `state.json`, raw-stream expiry | one script; rules for dispatch and handoff live once in `DELEGATION.md`
> (PRD "Testing Decisions") dispatcher fake-process tests (timeout, quota, malformed output, cancel, spaces and Unicode, atomic resume, env allowlist, auth gate).
> (SIGNED-PACKETS.md §HL-1 result.json) class | enum FC-1..FC-12 values | — | PRD catalog C2; `ok` only after schema validation (AC-021) · counterclaim | {statement, evidence_check} or {none_found: true, evidence_check} | — | `none_found` legal only with `evidence_check` (AC-014) · changed_from | {round: 0, cited: claim id} or null | null | change without a cite is `unjustified` (AC-015)
> (SIGNED-PACKETS.md §HL-1 state.json) judge | {participant, reserved_at} or null | null | reserved before dispatch; null means `unresolved` on dispute (AC-017) · jobs[] | {participant, role, status: queued \| running \| done \| failed, class, result_path, attempts:int, deadline_at, write_policy: read-only} | — | any other write_policy is never resumed (AC-028)
> (SIGNED-PACKETS.md §HL-1 file set) <scratch>/afk-dispatch/<CON-NNN>/<participant>.raw | dispatcher | raw provider stream | same id | diagnostics only; deleted after `retain_raw_days`; never under the spec folder

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
0001-config-blocks, 0002-provider-verbs

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

# Signed sign-off packets — research-enhancement

The contract-grade tables the human signed in round R-1 (2026-09-15, answers verbatim in `GRILL-LOG.md`). `/afk:to-sdd` transcribes these into SDD §3–§7 and §14 without change; any later edit voids the signature (HUMAN-SIGNOFF.md "Void on drift"). Rendered form at signing time: `GRILL-SOLUTION-ROUND.html` round 1 (now settled cards).

## HL-1 Persistence → SDD §4

Files added under `{spec}/`. Retention: all live as long as the spec folder; nothing migrates.

| Path | Writer | Format | Identity | Consumers |
|---|---|---|---|---|
| research/<RES-NNN>/REPORT.md | /afk:research | markdown, LANGUAGE.md §3 | RES-NNN sequential per spec folder | grill pre-briefs, ADR Context sections, /afk:consult briefs, cards as grade `spec` |
| research/<RES-NNN>/evidence.json | /afk:research | JSON, schema 1 | same id | /afk:consult, report renderer |
| consult/<CON-NNN>/request.json | /afk:consult | JSON, schema 1 | CON-NNN sequential per spec folder | dispatcher validation |
| consult/<CON-NNN>/jobs/<participant>/result.json | dispatcher | JSON, schema 1 | CON-NNN + participant name | judge, challenge round, REPORT.md |
| consult/<CON-NNN>/REPORT.md | /afk:consult | markdown | same id | calling grill or gate, /afk:retro |
| consult/<CON-NNN>/state.json | dispatcher | JSON, schema 1, atomic write (temp + rename) | same id | dispatcher resume on another host |
| <scratch>/afk-dispatch/<CON-NNN>/<participant>.raw | dispatcher | raw provider stream | same id | diagnostics only; deleted after `retain_raw_days`; never under the spec folder |

evidence.json claim record (`claims[]`); every field required unless a default is shown.

| Field | Type | Default | Rule |
|---|---|---|---|
| id | string `claim-N` | — | unique inside the report |
| statement | string | — | one sentence |
| kind | enum fact \| inference | — | PRD AC-004 |
| status | enum verified \| unverified \| contradicted | — | snippet-only or agreement-only claim is `unverified` (AC-003) |
| source_locator | URL or repo path | — | required when status is not `unverified` |
| source_class | enum primary \| secondary \| tertiary | — | PRD catalog C1 |
| retrieved_at | ISO date | — | date the source was read |
| quote | string, 500 chars max | — | required when status is `verified`; literal source text |
| applicability | string | — | why the source applies (version, product, date) |
| counterevidence | array of claim ids | [] | claims that dispute this one |

evidence.json document fields.

| Field | Type | Default | Rule |
|---|---|---|---|
| schema | int | 1 | reader rejects any other value |
| research_id | string RES-NNN | — | matches the folder |
| question | string | — | the world question as asked |
| type | enum W1 \| W2 \| W3 \| W4 | — | PRD catalog C1 |
| status | enum closed \| incomplete | — | closure rule per type (AC-001, AC-002) |
| gaps | array of strings | [] | required non-empty when `incomplete` (AC-006) |
| claims | array of claim records | — | table above |
| priorities | array of {statement, scope, authority, supersession, provenance[], counterevidence[]} | [] | advisory; never binding (AC-005) |
| budget | {max_minutes:int, used_minutes:int} | — | from research.max_minutes |
| public | {mode: off \| when_relevant \| required, queries: string[]} | — | each query passed hygiene (AC-008) |

result.json (one per participant job).

| Field | Type | Default | Rule |
|---|---|---|---|
| schema | int | 1 | — |
| job_id | string CON-NNN/<participant> | — | idempotency key |
| participant | string | — | provider name from config |
| role | enum researcher \| consultant \| reviewer \| adversary \| diagnosis | — | read-only roles only (ADR-0004) |
| class | enum FC-1..FC-12 values | — | PRD catalog C2; `ok` only after schema validation (AC-021) |
| round | int 0 \| 1 | — | 0 independent, 1 challenge |
| position | string | — | the participant's answer, one paragraph |
| claims | array of claim records | [] | same shape as evidence.json |
| counterclaim | {statement, evidence_check} or {none_found: true, evidence_check} | — | `none_found` legal only with `evidence_check` (AC-014) |
| changed_from | {round: 0, cited: claim id} or null | null | change without a cite is `unjustified` (AC-015) |
| started_at / ended_at | ISO datetime | — | — |
| usage | {turns:int, provider_reported: object or null} | — | budget in turns; provider figures kept raw |

state.json (dispatcher resume record).

| Field | Type | Default | Rule |
|---|---|---|---|
| schema | int | 1 | — |
| consult_id | string CON-NNN | — | — |
| route | string | — | configured route name |
| created_at | ISO datetime | — | — |
| host | {provider, session} | — | who created the run |
| round | int 0 \| 1 | 0 | current round |
| judge | {participant, reserved_at} or null | null | reserved before dispatch; null means `unresolved` on dispute (AC-017) |
| jobs[] | {participant, role, status: queued \| running \| done \| failed, class, result_path, attempts:int, deadline_at, write_policy: read-only} | — | any other write_policy is never resumed (AC-028) |

Alternatives rejected: one JSONL event log per consultation; SQLite state; raw streams under the spec folder. Blast radius: no existing file changes shape; `/afk:gc` unaffected. Risks: 10-field claim records fail the fixture when a field is skipped (intended); sequential ids can collide across worktrees, reader tolerates suffix `RES-NNN-b`.

## HL-2 Callable surfaces → SDD §3

| Surface | Invocation | Inputs | Success | Errors | Idempotency |
|---|---|---|---|---|---|
| /afk:research | skill; args: question, type W1..W4, spec dir | question text; optional prior RES ids | REPORT.md + evidence.json, status closed or incomplete | refuses: no `research:` block; hygiene reject (AC-008); required-web with no web tool (AC-007) | new id per run; a re-run cites the prior report |
| /afk:consult | skill; args: route, brief path, spec dir | route name; staged evidence list | REPORT.md with disposition; exit 0 | exit 3 single, exit 4 unavailable (AC-019); validation errors name the key | CON id per run; resume reuses it |
| dispatch_harness.py run | `run --request <request.json> --out <dir>`; prompt on stdin | request.json (identity, scope, permission, route, deadline, billing) | result.json per job, state.json, exit 0 | exit 3 / 4 per ADAPTERS.md answer shape; exit 2 unresolved config | job_id; a `done` job never re-runs |
| dispatch_harness.py resume | `resume --state <state.json>` | state.json | remaining read-only jobs run; exit 0 | as above; non-read-only write_policy refused | same job ids |
| dispatch_harness.py probe | `probe --provider <name>` | provider name | JSON {auth_mode, quota_headroom, binary} | exit 4 missing binary / no auth | read-only, repeatable |
| provider member verbs | shell functions in hooks/lib/providers/<name>.sh | probe, auth_mode, invocation, parse_result, classify_failure, quota_headroom (optional) | the verb's documented output | unsupported verb exits 3 | pure functions |

| Existing surface | Change | Verdict |
|---|---|---|
| hooks/lib/providers/claude.sh, codex.sh (:3-:25) | new verbs appended; existing untouched | compatible |
| hooks/lib/adapter.sh answer shape (ADAPTERS.md:29-34) | reused; not changed | compatible |
| scripts/afk-config.py TOP_LEVEL (24 keys) | +2 keys; unknown-key rejection unchanged | compatible |

Alternatives rejected: MCP server for dispatch; one combined skill; bash dispatcher. Blast radius: no existing command changes; two skill entries in both manifests, one agent entry in `.claude-plugin/plugin.json`. Risks: `claude auth status` fields unverified (fixture at step 2); Codex env-key precedence known from bug reports only, gate refuses any key present.

## HL-3 Authorization and data scoping → SDD §5

| Capability | Permitted | Denied | Enforced in the skill | Enforced below the skill |
|---|---|---|---|---|
| Run research | host agent in an interactive or autopilot session | child agents below nesting cap 3; any participant | precheck: `research:` block present | afk-config.py validation; hygiene script rejects before egress |
| Write research artifacts | /afk:research | every other skill | single-writer law | fixture: no other write site |
| Run consultation | host agent through a configured route | human conversation; synthesis skills; participants | precheck: `consultation.enabled` and route resolves | dispatcher validates request.json; refuses a nested consult |
| Participant execution | dispatcher | any skill calling a provider CLI directly | skills carry only the pointer | dispatcher is the only spawn site |
| Accept a decision or a priority | human | /afk:consult, /afk:research, dispatcher | ADR-0001, ADR-0007 | /afk:claude-md propose-approve-write |
| Set billing, no_training, credits | repository administrator in .afk/config.yaml | any agent | values echoed to request.json and one journal line (AC-034) | afk-config.py rejects `billing: false` without `billing: api` |

| Scope | Default | Widening | Mechanism |
|---|---|---|---|
| Working directory | staging directory, approved files only | `allowed_paths` per participant; `denied_paths` always wins | staging built from the evidence list; denied or secret-pattern files never copied (AC-030, AC-031) |
| Environment | allowlist only (PATH, HOME, locale, provider login files) | none | child env constructed, not inherited (AC-024) |
| Network | provider endpoint; web tools only if role and config allow | `research.public` mode | provider flags (Codex `--sandbox read-only`); query hygiene |
| Training treatment | route requires `no_training` declaration | administrator declaration per destination | ADR-0002; missing blocks (AC-032) |

Alternatives rejected: plugin-internal roles; whole-repo default with denylist; trusting the provider sandbox alone. Risks: staged-only participants cannot investigate code; secret detection reuses redact.py patterns (:323-328), unusual shapes can pass if the human approves the file.

## HL-4 Lifecycle and invariants → SDD §6

| Object | States | Transitions | Trigger |
|---|---|---|---|
| Research report | closed (terminal), incomplete (terminal) | none after write; follow-up is a new RES id | /afk:research |
| Participant job | queued → running → done (terminal) \| failed (terminal, carries class) | queued→running on spawn; running→done on validated result; running→failed on FC-2..FC-12; failed→queued only for `transient` within `max_attempts` | dispatcher only |
| Consultation run | pending → round0 → challenge → adjudicated \| unresolved \| single (exit 3) \| unavailable (exit 4); all four terminal | round0→challenge only when ≥2 jobs done; challenge→adjudicated only with a reserved judge, else unresolved | dispatcher advances; /afk:consult reads |
| Judge reservation | none → reserved → used \| released | reserved before dispatch; released when no dispute | dispatcher |

| Id | Invariant | Guardian | Response |
|---|---|---|---|
| I-1 | Round-0 reports written before any participant sees another's output | dispatcher prompt builder | fixture with injected peer text fails; runtime `invalid_output` |
| I-2 | At most 1 challenge round | afk-config.py validation | config rejected, key named (AC-013) |
| I-3 | Subscription-only unless `billing: false` declared | dispatcher auth gate | `billing` (FC-5), skipped, never retried with other auth (AC-025, AC-026) |
| I-4 | Consultation never changes a gate verdict or a human decision | the calling gate | ADR-0007; a caller reading the disposition into its verdict fails review |
| I-5 | One writer per artifact | the owning skill | fixture greps for a second write site |
| I-6 | Raw streams never under the spec folder | dispatcher path rule | path validation refuses; expiry (AC-029) |
| I-7 | `none found` counterclaim only with an evidence check | result.json schema | `invalid_output` (AC-014) |
| I-8 | A snippet or provider agreement is never evidence | claim record `status` | `unverified`; excluded from closure (AC-003) |

Alternatives rejected: retry `quota` with other auth; host adjudicates without a judge; an `abandoned` job state. Risk: a `running` job on a dead host looks live until the deadline; resume treats a past `deadline_at` as `timeout` and re-queues once if `transient` budget remains.

## HL-5 Irreversible and outward side effects → SDD §7

| Id | Effect | Trigger | Ordering | Idempotency key | Partial failure leaves | Recovery |
|---|---|---|---|---|---|---|
| E-1 | Staged evidence sent to an external provider | job start | after auth gate, no_training check and staging | job_id | content disclosed; nothing local changed | none; prevention only. Irreversible. |
| E-2 | Sanitized web query leaves the machine | `when_relevant` or `required` mode | after hygiene check | query hash in `public.queries` | query text disclosed | none; prevention only (AC-008). Irreversible. |
| E-3 | Subscription usage consumed | each participant turn | bounded by turns budget and `deadline_minutes` | job_id | usage spent, result may be absent | `quota` ends the participant for the window |
| E-4 | Raw stream files deleted | next dispatcher run, age > `retain_raw_days` | after the run's own jobs | path + mtime | diagnostics lost | none; spec-folder artifacts untouched (AC-029) |
| E-5 | Process tree killed on timeout or cancel | deadline or parent cancel | before marking `timeout` / `cancelled` | job_id | orphan if kill fails within 5 s on Windows | resume re-checks; fixture AC-022 |
| E-6 | CLAUDE.md gains an accepted priority | human accepts a finding | /afk:claude-md propose-approve-write only | the finding's RES id | none (git-tracked) | git revert |

Alternatives rejected: per-query human approval; raw streams kept forever; currency spend cap. Risks: silent credit draw by `claude -p` is a HYPOTHESIS (ADR-0005 declaration + live probe); provider telemetry may retain prompts beyond the declaration (ADR-0002).

Defaults settled in R-1: `retain_raw_days` 7 (accepted); `deadline_minutes` 45 (human picked `m45`).

## HL-6 Change to existing behaviour → SDD §14

All verdicts `extends`; none `reworked`. Anchors verified by afk-reader against origin/main d8ca9b4; ledger gap acknowledged by the human (no objection, R-1). `/afk:investigate` runs on these rows before `/afk:to-subtasks`.

| File | Anchor | Change | Existing readers see | Compatibility | Rollback |
|---|---|---|---|---|---|
| scripts/lavish/schema.py | :46-48 | +2 optional debate_card fields `exhausted`, `postpone_cost` | nothing | compatible | revert |
| ROUND.md, LAVISH-KIT.md, GRILL-LOG-FORMAT.md | ROUND.md:308-313 | prepared-ask pointer + 2 fields (four-file lockstep, same commit) | 2 optional lines on a debate card | compatible | revert |
| DECISIONS.md | :9-15 | +section `Prepared ask` | ledger grammar unchanged | compatible | revert |
| INVESTIGATION.md | :94-108, :110-114 | +1 pointer to RESEARCH.md | nothing | compatible | revert |
| DELEGATION.md | :5,15,29,41,63 | +section `Dispatch and handoff` | spawn rules unchanged | compatible | revert |
| hooks/lib/providers/claude.sh, codex.sh | :3-:25 | +member verbs | nothing | compatible | revert |
| PROVIDERS.md, providers/CONFORMANCE.md | PROVIDERS.md:5,23-24 | +member role, billing env-deny list, probe rows | pin at :58,:65 untouched | compatible | revert |
| scripts/afk-config.py, CONFIG.md | afk-config.py:105-125; CONFIG.md:83-107 | TOP_LEVEL 24 → 26; +2 blocks | repo without the blocks behaves as today | compatible | revert |
| CAPABILITIES.md | :7-22 | 16 → 17 rows (+`web_access`) | degradation rules unchanged | compatible | revert |
| ADAPTERS.md | :29-34 | none; exit shape reused | nothing | compatible | — |
| skills/afk/{grill-requirements,grill-solution,grill-verification,review,adversary,fix}/SKILL.md | review SKILL.md:41,108-115,144-146 | +1 pointer line per chosen branch (PP-1..PP-6) | no step order changes | compatible | revert |
| .claude-plugin/plugin.json, .codex-plugin/plugin.json | .claude-plugin:9-15,16-62 | agents 5 → 6, skills 44 → 46; Codex skills only | nothing | compatible | revert |
| GLOSSARY.md, FRESHNESS.md, skills/afk/setup/MANIFEST.md, CLAUDE.md, README.md | GLOSSARY.md:228-242; FRESHNESS.md:31-70 | +6 terms, registry rows, opt-in dependency rows, catalog rows | nothing | compatible | revert |
| skills/afk/claude-md/SKILL.md | :10,29,35 | +1 sentence: accepted priority enters via the inclusion bar citing its RES id | protocol unchanged | compatible | revert |

Alternatives rejected: separate plugin; provider provenance in the findings JSON. Blast radius: every change additive (PRD AC-011); version 1.3.0 → 1.4.0 across manifests, marketplace, CHANGELOG, tag.

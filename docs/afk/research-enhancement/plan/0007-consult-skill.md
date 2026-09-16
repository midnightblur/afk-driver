# 0007-consult-skill — `/afk:consult` and its protocol sibling

## Goal
Create the consultation skill `skills/utils/consult/` (SKILL.md + `PROTOCOL.md` sibling + scripts): `route, brief path, spec dir → {spec}/consult/<CON-NNN>/REPORT.md, exit 0/3/4`. The skill prechecks `consultation.enabled` and route resolution, writes `request.json` (identity, scope, permission, route, deadline, billing, `no_training`), runs the dispatcher (`run`, or `resume` on another host), then applies the protocol: sealed round-0 reports, a deterministic citation-and-field check, exactly one challenge round with neutral shuffled labels, `none found` only with an evidence check, a changed position without a cite recorded `unjustified` and excluded, a factual dispute checked against an official source or local probe, a value dispute to the pre-reserved fresh judge or `unresolved`, disposition `supported | qualified | unresolved` with vote counts as metadata only, dissent preserved in `REPORT.md`, one journal line per run, `changed_answer` as metadata. It also ships the evaluation fixture set (single provider, independent reports, reports + challenge) reporting the seven metrics. The report is advisory: it changes no gate verdict. Register the skill in both manifests, `FRESHNESS.md`, `CLAUDE.md` and `README.md` catalogs.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 row "`/afk:consult`" — args, precheck, envelopes, exit 3/4, CON id per run, resume reuses it
- SDD: SDD.md#§4 "State table" row "Consultation request, results, report"; "Entity design" — shapes in `SIGNED-PACKETS.md` §HL-1 (`request.json` fields; `result.json` reader)
- SDD: SDD.md#§5 "AuthZ" row "Run consultation"; "Observability" row "one journal line per consultation run"
- SDD: SDD.md#§6 invariants I-2, I-4, I-5, I-7, I-8; consultation-run state machine (pending → round0 → challenge → adjudicated | unresolved | single | unavailable)
- SDD: SDD.md#§7 sequence + use case "consultation run"; F-5 host dies mid-run; F-6 no judge reservable
- SDD: SDD.md#§8 row "consult skill + protocol sibling" — public interface `route, brief, spec dir → REPORT.md, exit 0/3/4`; depends on dispatcher, config reader, delegation doctrine
- SDD: SDD.md#§10 row "Evaluation fixtures" — 3 modes × 7 metrics
- ADR: adr/design/0003-sealed-rounds-and-fresh-judge.md — sealed round 0; one challenge; reserved fresh judge; `unresolved` when none
- ADR: adr/design/0002-classified-result-and-state-file.md — the reader side of `result.json` / `state.json`
- ADR: adr/requirements/0007-consultation-is-advisory-only.md — no verdict change; dispositions; votes are metadata
- ADR: adr/requirements/0003-web-research-when-relevant-staged-egress.md — `unavailable: single` advisory, `block` refuses
- ADR: adr/requirements/0006-same-provider-participant-is-native-subagent.md — a same-provider participant is a native subagent, no subprocess, no billing gate

## Scope
- skills/utils/consult/**
- scripts/tests/test_consult_skill.py
- scripts/tests/samples/consult/**        # fixtures: sealed reports, preserved dissent, 1-round cap, `single`, `block`, evaluation set
- .claude-plugin/plugin.json
- .codex-plugin/plugin.json
- FRESHNESS.md
- CLAUDE.md                                # the skills catalog row only
- README.md                                # the skill catalog entry only

## Seams
- implement: §14 row "`plugin.json` manifests, `skill-registry-gate.sh`, `native-contract-gate.sh`, `genericity-gate.sh`, `wiring-gate.sh` and the `README.md` / `CLAUDE.md` catalogs that must list `research`, `consult` and `afk-researcher`" — this subtask owns the `consult` skill directory and its registrations (INV-004)
- use: §9b "Claude CLI headless invocation" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — reaches a Claude participant only through the dispatcher's `run`; relies on the FC class and `result.json` contract (INV-003)
- use: §9b "Codex CLI headless invocation" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — same, for a Codex participant (INV-003)
- use: §9b "Windows process tree" — §14 row "provider shell library function set (`hooks/lib/providers/claude.sh`, `codex.sh`) and adapter answer shape" — reads a `timeout` class; never kills a process itself (INV-003)
- use: §14 row "config reader `TOP_LEVEL` and `export-shell` flattening (`scripts/afk-config.py:541,978-990`)" — reads `consultation.enabled`, routes, `unavailable`, `billing` through `afk-config.py get` (INV-002)
- use: §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — points at `DELEGATION.md` "Dispatch and handoff" for spawn and resume rules (INV-004)

## Acceptance
- [ ] With `consultation.enabled: false` or the block absent, the skill exits before writing any file and no participant runs (PRD AC-011)
- [ ] Round-0 prompts are built from the neutral brief only; the fixture that injects peer text into a round-0 prompt fails; round-0 `result.json` files exist before any challenge prompt is built (PRD AC-012; SDD §6 I-1)
- [ ] Exactly one challenge round runs; a `state.json` with `round: 1` complete transitions to adjudication, never to another challenge (PRD AC-013; ADR-0003)
- [ ] In the challenge round a `none found` counterclaim without `evidence_check` makes that report `invalid_output` (FC-10) and it is excluded (PRD AC-014)
- [ ] A round-1 position that differs from round 0 without `changed_from.cited` is recorded `unjustified` in `REPORT.md` and excluded from the disposition (PRD AC-015)
- [ ] The disposition is exactly one of `supported`, `qualified`, `unresolved`; vote counts appear only under a metadata heading; a factual dispute is checked against an official source or a local probe before any human escalation, and the check is cited in `REPORT.md` (PRD AC-016)
- [ ] With 2 participants, the judge reserved in `state.json` before dispatch adjudicates a value dispute with identities blind; with `judge: null` the disposition is `unresolved` and both positions appear in `REPORT.md` (PRD AC-017; SDD §7 F-6)
- [ ] `REPORT.md` carries no review finding class, review verdict or adversary verdict, and `PROTOCOL.md` states the advisory rule; a fixture caller that copies a disposition into a verdict field is flagged by the test (PRD AC-018; SDD §6 I-4)
- [ ] With `unavailable: single` and exactly 1 healthy participant the run exits 3 and `REPORT.md` is marked single-provider; with `unavailable: block` it exits 4; with 0 healthy participants it exits 4 in both modes (PRD AC-019)
- [ ] `request.json` echoes `billing` and `no_training` from config; one `plan/JOURNAL.md` line per run names route, participants, classes, disposition and billing value (PRD AC-034; SDD §5 "Observability")
- [ ] A participant whose provider is the host harness runs as a native subagent with no subprocess and no billing gate, still restricted to staged evidence and `allowed_paths` (ADR-0006)
- [ ] On a lost host, `resume` on another host reuses the CON id and runs only jobs not `done` (SDD §7 F-5)
- [ ] The evaluation fixture set covers single provider, independent reports, and reports + challenge, and reports citation support, factual error, unjustified consensus, useful dissent, human decisions required, time, provider usage; `changed_answer` appears only as metadata (PRD AC-036)
- [ ] `/afk:consult` is the only writer of `request.json` and `consult/<CON-NNN>/REPORT.md`; a test greps the plugin for a second write site and finds none (SDD §6 I-5)
- [ ] `SKILL.md` opens with the `LANGUAGE.md` pointer line, names no caller skill or stage, and points at `PROTOCOL.md` and `DELEGATION.md` "Dispatch and handoff" instead of restating them (plugin `CLAUDE.md` "Downstream is blind to upstream", "DRY")
- [ ] Both plugin manifests list `./skills/utils/consult`; `CLAUDE.md` and `README.md` catalogs carry the skill; `FRESHNESS.md` carries a row for the skill and its protocol sibling (SDD §14 row "`plugin.json` manifests …"; FRESHNESS.md "The same-commit rule")
- [ ] Implements the public interface in SDD §8 row "consult skill + protocol sibling" unmodified: `route, brief, spec dir → REPORT.md, exit 0/3/4` (SDD §8)
- [ ] Conforms to ADR-0003 (design) — sealed round 0, one challenge, reserved fresh judge, `unresolved` without one; no open multi-round debate, no host adjudication, no majority vote on facts (ADR-0003)
- [ ] Conforms to ADR-0007 — advisory only; no gate verdict or human decision replaced (ADR-0007)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Fixtures use the real directory name `consult/`, the real file names `request.json`, `result.json`, `state.json`, `REPORT.md`, and the real id shape `CON-NNN` (PRD "Testing Decisions")
- [ ] No test runs a live participant; every dispatcher call in tests targets fake processes on PATH (PRD "Testing Decisions")

## Produces
- skills/utils/consult/SKILL.md#name: consult — the skill: args route, brief path, spec dir; precheck; writes request.json + REPORT.md; exit 0/3/4
- skills/utils/consult/PROTOCOL.md#Dispositions — `supported | qualified | unresolved` rules; votes as metadata; factual-dispute check; judge rule; advisory-only rule
- skills/utils/consult/scripts/consult_run.py#build_request — `request.json` from route + brief + config (billing, no_training echoed)
- skills/utils/consult/scripts/consult_run.py#check_round_results — deterministic citation-and-field check; `none found` without `evidence_check` → invalid; uncited change → `unjustified`
- skills/utils/consult/scripts/consult_run.py#write_consult_report — `REPORT.md` with disposition, dissent, single-provider mark, metadata block
- skills/utils/consult/scripts/evaluate_fixtures.py#evaluation_metrics — the 7 metrics over the 3 fixture modes; `changed_answer` metadata
- .claude-plugin/plugin.json#./skills/utils/consult — skill registration
- .codex-plugin/plugin.json#./skills/utils/consult — skill registration

## Consumes
- 0003-dispatch-harness scripts/dispatch_harness.py#run_consultation — `run --request --out` with the prompt on stdin; exit 0/2/3/4
- 0003-dispatch-harness scripts/dispatch_harness.py#resume_consultation — `resume --state` on another host
- 0003-dispatch-harness scripts/dispatch_harness.py#probe_provider — `{auth_mode, quota_headroom, binary}` for the route precheck
- 0003-dispatch-harness scripts/dispatch_harness.py#FAILURE_CLASSES — the `result.json.class` values the skill reads
- 0003-dispatch-harness DELEGATION.md#Dispatch and handoff — the dispatch and resume rules the skill points at
- 0001-config-blocks scripts/afk-config.py#CONSULTATION_KEYS — `enabled`, routes, `unavailable`, `billing`, participants
- 0001-config-blocks scripts/afk-config.py#validate_consultation_block — a config reaching the skill already passed the challenge cap and billing rules

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile skills/utils/consult/scripts/*.py` + grep every ## Produces anchor + `python hooks/run-hook.py plugin stop-gates.sh` + `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | scripts load; registrations present; the new skill passes the plugin's own gates |
| unit | `python -m pytest scripts/tests/test_consult_skill.py -q` — disabled/absent block → no run (AC-011); sealed round 0 (AC-012); one challenge (AC-013); `none found` gate (AC-014); uncited change → `unjustified` (AC-015); disposition set + votes metadata + factual check (AC-016); judge / `unresolved` (AC-017); advisory report (AC-018); `single` / `block` / zero → exit 3/4 (AC-019); config echo + journal line (AC-034); single-writer grep (I-5) | every protocol rule in isolation on fixture `result.json` files |
| integration | `python -m pytest scripts/tests/test_consult_skill.py -q -k end_to_end` — the skill's script drives the real `dispatch_harness.py run` and `resume` with fake participant CLIs on PATH through round 0, the challenge round and adjudication; asserts on the real `REPORT.md`, `state.json` and exit code; the evaluation fixture set reports the 7 metrics (AC-036) | the skill ↔ dispatcher contract end-to-end without a live provider |

## Context excerpts
> (PRD §Solution 3) **Consultation** (`/afk:consult`): independent reports from ≥2 participants (a participant is one provider's headless CLI run, or a native subagent when the provider is the host), one challenge round, evidence-weighted disposition, dissent preserved. Advisory only.
> (PRD C2) | DS-1 | disposition | `supported` | Decisive claims pass their evidence check; no material dispute remains | · | DS-2 | disposition | `qualified` | Agreement with recorded reservations or unchecked premises | · | DS-3 | disposition | `unresolved` | Dispute remains after the round cap; both positions reach the human |
> (PRD C4 AR-3) `{spec}/consult/<id>/request.json` | `/afk:consult` | dispatcher validation (identity, scope, permission, route, deadline, billing)
> (PRD C4 AR-5) `{spec}/consult/<id>/REPORT.md` | `/afk:consult` | the calling grill or gate; `/afk:retro` (`changed_answer` metadata)
> (PRD AC-011) With `consultation.enabled: false` or the block absent, no participant runs and every caller behaves as before.
> (PRD AC-012) Round-0 reports are written before any participant sees another's output; a fixture that injects peer text into round 0 fails.
> (PRD AC-013) Exactly 1 challenge round runs; a configuration requesting more is rejected at validation.
> (PRD AC-014) In the challenge round, a participant's `none found` is accepted only with the evidence check cited; without it the report is `invalid_output` (FC-10).
> (PRD AC-015) A changed position without cited evidence is recorded as `unjustified` and excluded from the disposition.
> (PRD AC-016) The disposition is one of DS-1..DS-3; vote counts appear only as metadata; a factual dispute is checked against an official source or local probe before any human escalation.
> (PRD AC-017) With 2 participants, a judge that authored no position adjudicates; when none can be reserved, the disposition is `unresolved` and both positions reach the human.
> (PRD AC-018) A consultation report never changes a review finding class, review verdict, or adversary verdict; the gate's own routing applies unchanged (ADR-0007).
> (PRD AC-019) With `unavailable: single` and exactly 1 healthy participant, the run exits `3` and the report is marked single-provider; with `unavailable: block`, it exits `4`; with 0 participants, it exits `4` in both modes.
> (PRD AC-036) The evaluation fixture set (single provider, independent reports, reports + challenge) reports citation support, factual error, unjustified consensus, useful dissent, human decisions required, time and provider usage; `changed_answer` is present as metadata only.
> (PRD "Testing Decisions") consult fixtures (sealed reports, preserved dissent, 1-round cap, `single`, `block`)
> (SDD §3 row "`/afk:consult`") skill; args: route, brief path, spec dir | host agent through a configured route; `consultation.enabled` | route resolves; staged evidence list; every path allowed | `REPORT.md` with disposition; exit 0 | exit 3 `single` (one healthy participant, `unavailable: single`); exit 4 `unavailable` (0 participants, or 1 under `block`) (AC-019); validation error names the key | none / CON id per run; resume reuses it | 1 | new
> (SDD §5 "AuthZ" row "Run consultation") host agent through a configured route | human conversation; synthesis skills; participants | precheck: `consultation.enabled` and route resolves | dispatcher validates the request; refuses a nested consult
> (SDD §6 I-4) Consultation never changes a gate verdict or a human decision | consultation run | the calling gate | ADR-0007; a caller reading the disposition into its verdict fails review
> (SDD §6 consultation-run state machine caption) consultation run; four terminal states map to exit 0 (adjudicated, unresolved), 3 (single), 4 (unavailable).
> (SDD §7 sequence caption) one independent round, one challenge round, then a check before any human sees a dispute.
> (SDD §7 F-5) host dies mid-run | `state.json` shows `running` past deadline | `resume` on another host | run `resume` | consult skill
> (SDD §7 F-6) no judge reservable | dispute at challenge | disposition `unresolved`; both positions reach the human | none | consult skill
> (SDD §8 row "consult skill + protocol sibling") sealed reports, one challenge, dispositions, judge rule | `route, brief, spec dir → REPORT.md, exit 0/3/4` | dispatcher, config reader, delegation doctrine | consultation run
> (SDD §10 row "Evaluation fixtures") 3 modes × 7 metrics reported | AC-036 | retro
> (ADR-0003 design) Round 0 reports are sealed: every participant gets the same neutral brief and never sees another report. A deterministic check of citations and fields runs next. Exactly one challenge round follows with neutral labels, shuffled per recipient; `none found` is accepted only with the evidence check cited. A factual dispute gets an official-source or local-probe check. A remaining value dispute goes to a judge that was reserved before dispatch and authored no position, identities blind; when no judge can be reserved the disposition is `unresolved` and both positions reach the human
> (ADR-0007 requirements) A consultation report informs a grill, review, adversary or diagnosis; it never changes a review finding class, a review or adversary verdict, or a human decision (PRD AC-018). Dispositions are `supported`, `qualified`, `unresolved`; votes are metadata
> (ADR-0006 requirements) When the participant's provider is the host harness, the participant is a native subagent: no subprocess and no billing gate. The participant remains subject to staged evidence and explicit `allowed_paths` grants.
> (SIGNED-PACKETS.md §HL-1 request.json row) consult/<CON-NNN>/request.json | /afk:consult | JSON, schema 1 | CON-NNN sequential per spec folder | dispatcher validation

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
0001-config-blocks, 0003-dispatch-harness

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

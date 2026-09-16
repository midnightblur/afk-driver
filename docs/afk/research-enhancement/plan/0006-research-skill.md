# 0006-research-skill — `/afk:research` and the `afk-researcher` agent

## Goal
Create the research skill `skills/utils/research/` (SKILL.md + siblings) and the frontier-tier agent `agents/afk-researcher.md` (+ the Codex stub `providers/codex/agents/afk-afk-researcher.toml`): `question, type W1–W4, spec dir → {spec}/research/<RES-NNN>/REPORT.md + evidence.json`, `status: closed | incomplete`, following `RESEARCH.md`. The skill refuses without a `research:` block, runs query hygiene on every public query before egress, honours `research.public` (`off | when_relevant | required`), stops at `research.max_minutes` with named gaps, records organization priorities as advisory, and is the single writer of AR-1 and AR-2. Two deterministic scripts back it: `query_hygiene.py` (reject set) and `validate_evidence.py` (`evidence.json` schema 1, claim field completeness, advisory-only priorities). Register the skill and agent everywhere the same-commit rule names: both plugin manifests, `CAPABILITIES.md` (`web_access` row with per-harness mapping and `unavailable` degradation), `FRESHNESS.md`, `CLAUDE.md` and `README.md` catalogs.

## Complexity
complex

## Design refs
- SDD: SDD.md#§3 row "`/afk:research`" — args, actor, validation, envelopes, refusals, RES id per run
- SDD: SDD.md#§4 "State table" row "Research report + evidence" and "Entity design" — file set + shapes in `SIGNED-PACKETS.md` §HL-1 (claim record, `evidence.json`)
- SDD: SDD.md#§5 "AuthZ" rows "Run research", "Write research artifacts"; "Retry + timeout" row "web fetch in research"; "Idempotency" row "research run"
- SDD: SDD.md#§7 use case "research run"; F-7 web query fails hygiene; E-2 sanitized query leaves the machine
- SDD: SDD.md#§8 row "research skill + researcher agent" — public interface `question, type, spec dir → REPORT.md + evidence.json`; depends on doctrine, config reader, web tools (capability `web_access`)
- SDD: SDD.md#§9b row "Web fetch in research" — seam-test `test_research_fixture_closed_incomplete`
- SDD: SDD.md#§14 row "`plugin.json` manifests, `skill-registry-gate.sh` … must list `research`, `consult` and `afk-researcher`" — same-commit set gate-enforced; `web_access` row is documentation duty
- ADR: adr/requirements/0003-web-research-when-relevant-staged-egress.md — `when_relevant` default; hygiene
- ADR: adr/requirements/0001-no-priorities-registry-now.md — advisory priorities
- ADR: adr/requirements/0008-rejected-extensions.md — claim cites as `spec`

## Scope
- skills/utils/research/**
- agents/afk-researcher.md
- providers/codex/agents/afk-afk-researcher.toml
- scripts/tests/test_research_skill.py
- scripts/tests/samples/research/**       # fixtures: authoritative fact, contradicted claim, stale source, organization inference, `incomplete`
- .claude-plugin/plugin.json
- .codex-plugin/plugin.json
- CAPABILITIES.md
- FRESHNESS.md
- CLAUDE.md                                # the skills catalog row only
- README.md                                # the skill catalog entry only

## Seams
- implement: §9b "Web fetch in research" — §14 row "`plugin.json` manifests, `skill-registry-gate.sh`, `native-contract-gate.sh`, `genericity-gate.sh`, `wiring-gate.sh` and the `README.md` / `CLAUDE.md` catalogs that must list `research`, `consult` and `afk-researcher`" — this subtask owns the skill + agent that fetch the web and the seam-test `test_research_fixture_closed_incomplete` (INV-004)
- use: §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — the skill and agent read `RESEARCH.md`; they restate none of it (INV-004)
- use: §14 row "config reader `TOP_LEVEL` and `export-shell` flattening (`scripts/afk-config.py:541,978-990`)" — reads `research:` through `afk-config.py get` (INV-002)

## Acceptance
- [ ] A W2 or W4 fixture run returns `closed` only with one primary source carrying quoted text, URL and retrieval date in `evidence.json`; the fixture without one returns `incomplete` with the unanswered question in `gaps` (PRD AC-001)
- [ ] A W1 or W3 fixture run returns `closed` only when every declared question, material counterclaim and option-eliminating assumption carries a disposition; one missing disposition returns `incomplete` (PRD AC-002)
- [ ] A claim whose only support is a search snippet, or agreement between providers, has `status: unverified` and is excluded from closure (PRD AC-003)
- [ ] `validate_evidence.py` rejects a claim missing any of locator, retrieval date, source class, applicability, `kind`; rejects a `priorities[]` entry stated as binding or missing scope, authority, supersession, provenance, counterevidence; rejects `schema` other than 1 (PRD AC-004, AC-005)
- [ ] A run that exhausts `research.max_minutes` returns `incomplete` with non-empty `gaps` and `budget.used_minutes`; no report text claims exhaustive search (PRD AC-006)
- [ ] With `research.public: off` the fixture records zero web calls; with `when_relevant` a web call is recorded only for a question the local tools could not settle; with `required` a run with zero web calls fails (PRD AC-007)
- [ ] `query_hygiene.py` rejects a query containing a term from the repository's glossary, a ticket id, a code fragment, or a customer identifier before egress; `evidence.json.public.queries` lists only accepted queries (PRD AC-008; SDD §7 E-2)
- [ ] The skill refuses to run without a `research:` block, and refuses `required` mode when the harness reports no web tool (SDD §3 row "`/afk:research`")
- [ ] `/afk:research` is the only writer of `{spec}/research/<RES-NNN>/REPORT.md` and `evidence.json`; a test greps the plugin for a second write site and finds none (SDD §5 "AuthZ" row "Write research artifacts"; §6 I-5)
- [ ] RES ids are sequential per spec folder; a re-run cites the prior report; the reader tolerates a `-b` suffix (SDD §4 "Entity design")
- [ ] `agents/afk-researcher.md` opens with the `LANGUAGE.md` pointer line, names the frontier tier, and lists web tools; the Codex stub is pointer-only with `{{PLUGIN_ROOT}}` (FRESHNESS.md rows "agents/*.md", "providers/codex/agents/*.toml")
- [ ] `SKILL.md` opens with the `LANGUAGE.md` pointer line, names no caller skill or stage, and points at `RESEARCH.md` for every rule instead of restating it (plugin `CLAUDE.md` "Downstream is blind to upstream", "DRY")
- [ ] Both plugin manifests list `./skills/utils/research`; `.claude-plugin/plugin.json` lists `./agents/afk-researcher.md`; `CLAUDE.md` and `README.md` catalogs carry the skill; `CAPABILITIES.md` carries the `web_access` row with a Claude Code column, a Codex CLI column and the degradation `unavailable`; `FRESHNESS.md` carries a row for the skill (SDD §14 row "`plugin.json` manifests …"; FRESHNESS.md "The same-commit rule")
- [ ] A research-report claim cited on a round card carries grade `spec`; no grade is added (ADR-0008)
- [ ] Implements the public interface in SDD §8 row "research skill + researcher agent" unmodified: `question, type, spec dir → REPORT.md + evidence.json` (SDD §8)
- [ ] Conforms to ADR-0003 — `when_relevant` is the default; hygiene rejects before egress; no per-query human approval (ADR-0003)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Seam-test `test_research_fixture_closed_incomplete` drives the skill's scripts against recorded page fixtures and asserts on the real `evidence.json` written to disk (status, gaps, claims, queries), not on intermediate objects (SDD §9b row "Web fetch in research")
- [ ] Fixtures use the real directory name `research/`, the real file names `REPORT.md` and `evidence.json`, and the real id shape `RES-NNN` (PRD "Testing Decisions")
- [ ] No test performs a live web fetch; page content comes from recorded fixtures (PRD "Testing Decisions")

## Produces
- skills/utils/research/SKILL.md#name: research — the skill: args question, type W1..W4, spec dir; writes REPORT.md + evidence.json; refuses without `research:`
- skills/utils/research/scripts/query_hygiene.py#hygiene_verdict — accept/reject a public query with the offending fragment named
- skills/utils/research/scripts/validate_evidence.py#validate_evidence — `evidence.json` schema 1, claim completeness, advisory-only priorities; exit 1 with the field named
- agents/afk-researcher.md#name: afk-researcher — frontier-tier child with web tools, bound to `RESEARCH.md`
- providers/codex/agents/afk-afk-researcher.toml#afk-afk-researcher — pointer-only Codex stub
- CAPABILITIES.md#`web_access` — the capability row: per-harness mapping + `unavailable` degradation
- .claude-plugin/plugin.json#./skills/utils/research — skill registration
- .codex-plugin/plugin.json#./skills/utils/research — skill registration
- .claude-plugin/plugin.json#./agents/afk-researcher.md — agent registration

## Consumes
- 0005-research-doctrine RESEARCH.md#Question types — W1–W4 closure rules the skill applies
- 0005-research-doctrine RESEARCH.md#Claim record shape — the claim field set `validate_evidence.py` enforces
- 0005-research-doctrine RESEARCH.md#Query hygiene — the reject set `query_hygiene.py` enforces
- 0005-research-doctrine RESEARCH.md#Organization priorities — the advisory fields the skill records
- 0001-config-blocks scripts/afk-config.py#RESEARCH_KEYS — `research.public`, `research.max_minutes` read through `afk-config.py get`

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile skills/utils/research/scripts/*.py` + grep every ## Produces anchor + `python hooks/run-hook.py plugin stop-gates.sh` (skill-registry, native-contract, genericity, wiring gates) + `python -m pytest scripts/tests/test_skill_frontmatter.py -q` | scripts load; registrations present; the new skill and agent pass the plugin's own gates |
| unit | `python -m pytest scripts/tests/test_research_skill.py -q` — hygiene reject set (AC-008); evidence validator field completeness + advisory priorities + schema (AC-004, AC-005); `public` modes off / when_relevant / required (AC-007); budget exhaustion → `incomplete` + gaps (AC-006); snippet-only → `unverified` (AC-003); single-writer grep (I-5); RES id sequence + `-b` suffix | every research rule in isolation on recorded fixtures |
| integration | `python -m pytest scripts/tests/test_research_skill.py -q -k closed_incomplete` — `test_research_fixture_closed_incomplete`: authoritative-fact fixture → `closed` with quote + URL + date; contradicted-claim and stale-source fixtures → `incomplete` with named gaps; organization-inference fixture → advisory `priorities[]` (AC-001, AC-002) | the web-fetch seam on the real `evidence.json` written to disk |

## Context excerpts
> (PRD §Solution 1) **Research** (`/afk:research`): a single-writer research skill that answers a world question (W1–W4, catalog C1) with cited primary sources, records inferred organization priorities as advisory findings, and closes on a type-specific rule or reports `incomplete`.
> (PRD C4 AR-1) `{spec}/research/<id>/REPORT.md` | `/afk:research` | grill pre-brief digests; ADR Context and Alternatives sections written by `/afk:to-prd` and `/afk:to-sdd`; `/afk:consult` briefs; cited on cards as grade `spec`
> (PRD C4 AR-2) `{spec}/research/<id>/evidence.json` | `/afk:research` | `/afk:consult` (claim sources, dates, contradictions); report renderer
> (PRD "Access & validation policy" row "Run research") host agent in an interactive or autopilot session | any child agent below nesting cap 3; a participant | spec folder of the work item; web with sanitized queries | `research:` block present; query hygiene (AC-008)
> (PRD "Implementation Decisions" row "`skills/utils/research/` + `agents/afk-researcher.md`") executable procedure; frontier-tier child with web tools | new skill and agent; `web_access` capability row with per-harness mapping and `unavailable` degradation
> (PRD "Testing Decisions") research fixtures (authoritative fact, contradicted claim, stale source, organization inference, `incomplete`)
> (PRD AC-001) A W2 or W4 question returns `closed` only when the report cites one authoritative primary source with quoted text, URL and fetch date; without one it returns `incomplete` with the unanswered question named.
> (PRD AC-002) A W1 or W3 question returns `closed` only when every declared question, material counterclaim and option-eliminating assumption carries a disposition; any missing disposition returns `incomplete`.
> (PRD AC-003) A claim supported only by a search snippet, or only by two providers agreeing, is recorded as `unverified`, never as fact.
> (PRD AC-004) Each material claim in AR-2 carries source locator, retrieval date, source class (C1), applicability, and `fact` or `inference`; a claim missing any field fails the research fixture.
> (PRD AC-005) An inferred organization priority is recorded with scope, authority, supersession, provenance and counterevidence, marked advisory; a report that states a priority as binding fails the fixture.
> (PRD AC-006) Research exhausting `research.max_minutes` returns `incomplete` with named gaps; it never claims the web was exhaustively searched.
> (PRD AC-007) With `research.public: off`, no web tool call occurs; with `when_relevant`, a web call occurs only for a question an authorized local tool cannot settle; with `required`, a run with no web call fails.
> (PRD AC-008) A public query that contains a glossary-listed internal term, a ticket id, code, or a customer identifier is rejected before it leaves the machine.
> (SDD §3 row "`/afk:research`") skill; args: question, type W1..W4, spec dir | host agent in an interactive or autopilot session; `research:` block present | question text; type in enum; optional prior RES ids; query hygiene on every public query | `REPORT.md` + `evidence.json`, `status: closed \| incomplete` | refuse: no `research:` block; hygiene reject (AC-008); `required` web mode with no web tool (AC-007) | none / new RES id per run; a re-run cites the prior report | 1 | new
> (SDD §4 "State table" row "Research report + evidence") files under `{spec}/research/<RES-NNN>/` | one folder per report | git, with the spec folder | life of the spec folder | `schema: 1` field; reader rejects other values | no by construction (hygiene) | no
> (SDD §5 "AuthZ" row "Write research artifacts") research skill | every other skill | single-writer law | fixture: no other write site
> (SDD §5 "Retry + timeout" row "web fetch in research") 2 | 5 s | 60 s per fetch; `research.max_minutes` overall
> (SDD §5 "Idempotency" row "research run") `RES-NNN` | none (each run is new) | `evidence.json.public.queries` records every query sent
> (SDD §7 F-7) web query fails hygiene | hygiene reject before egress | query dropped; research may end `incomplete` | rephrase | research skill
> (SDD §8 row "research skill + researcher agent") run one W1–W4 question to closure or `incomplete` | `question, type, spec dir → REPORT.md + evidence.json` | doctrine, config reader, web tools (capability `web_access`) | research report
> (SDD §9b row "Web fetch in research") the public web | returns pages we quote | primary sources only, quoted with date | `incomplete` | `test_research_fixture_closed_incomplete`
> (SDD §14 row "`plugin.json` manifests, `skill-registry-gate.sh` …") skill-registry gate check A/B/D, native-contract gate rules C/D, genericity and wiring gates (INV-008, INV-004) | +2 skills, +1 agent (+ Codex agent stub), +1 doctrine file, +6 glossary terms, +1 capability row, catalog mentions in CLAUDE.md and README.md | Stop gates on every session in this repo (INV-004) | same-commit set is gate-enforced; `web_access` row has no mechanical consumer (doc duty only); CONFORMANCE counts refresh on the next probe round | extends
> (SIGNED-PACKETS.md §HL-1 evidence.json) schema | int | 1 | reader rejects any other value · research_id | string RES-NNN · question · type | enum W1 \| W2 \| W3 \| W4 · status | enum closed \| incomplete · gaps | array of strings | [] | required non-empty when `incomplete` (AC-006) · claims | array of claim records · priorities | array of {statement, scope, authority, supersession, provenance[], counterevidence[]} | [] | advisory; never binding (AC-005) · budget | {max_minutes:int, used_minutes:int} · public | {mode: off \| when_relevant \| required, queries: string[]} | — | each query passed hygiene (AC-008)
> (ADR-0003 requirements) Public web research runs at `research.public: when_relevant` by default: only for a question an authorized local tool cannot settle, with queries rejected when they carry internal terms, ticket ids, code or customer identifiers (PRD AC-007, AC-008).
> (ADR-0008 requirements) a research-report claim cites as `spec`

## Parent PRD
docs/afk/research-enhancement/PRD.md

## Parent SDD
docs/afk/research-enhancement/SDD.md

## Blocked by
0001-config-blocks, 0005-research-doctrine

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.

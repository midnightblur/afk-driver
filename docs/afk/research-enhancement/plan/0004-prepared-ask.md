# 0004-prepared-ask — the prepared-ask bar and two optional debate-card fields

## Goal
Add the `## Prepared ask` section to `DECISIONS.md` (plugin root): the one bar for anything that reaches a human — recommendation, graded evidence, what was tried (`exhausted`), the cost of postponing (`postpone_cost`), and the value named in `undecided_because`. Add the two optional fields `exhausted` and `postpone_cost` to `debate_card` in the round-dossier lockstep set, all in one commit: `scripts/lavish/schema.py` (OPTIONAL tuple), `scripts/lavish/components.py` (rendered beside `third_paradigm`), `LAVISH-KIT.md` (component table), `skills/afk/grill-requirements/ROUND.md` (debate item contract points at the bar), `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md` (checkpoint tail). The existing required-field check and the grade enum stay unchanged.

## Complexity
standard

## Design refs
- SDD: SDD.md#§4 "Surface reachability" — two optional debate-card fields; renderer changes with the schema in the same commit; response grammar unchanged
- SDD: SDD.md#§8 rows "prepared ask (decision protocol section)", "round renderer + schema" — public interfaces: 2 optional debate-card fields; unchanged CLI
- SDD: SDD.md#§9b row "Round renderer" — seam-test `test_lavish_render` addition for the two fields
- SDD: SDD.md#§14 row "round schema `debate_card` optional field set" — four-file lockstep same commit; no test pins the optional tuple today
- ADR: adr/requirements/0008-rejected-extensions.md — no new evidence grades; the grade enum in `scripts/lavish/schema.py` is unchanged
- ADR: adr/requirements/0007-consultation-is-advisory-only.md — a value judgment reaches the human; the human decides

## Scope
- DECISIONS.md
- scripts/lavish/schema.py
- scripts/lavish/components.py
- LAVISH-KIT.md
- skills/afk/grill-requirements/ROUND.md
- skills/afk/grill-requirements/GRILL-LOG-FORMAT.md
- scripts/tests/test_lavish_render.py

## Seams
- implement: §9b "Round renderer" — §14 row "round schema `debate_card` optional field set (`scripts/lavish/schema.py:69`; required set at :46-48)" — this subtask owns the two fields in schema + renderer and the seam-test `test_lavish_render` addition (INV-001)
- implement: §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — this subtask adds the `## Prepared ask` section to `DECISIONS.md` (INV-004)

## Acceptance
- [ ] A `debate_card` with fewer than 2 options, or without `recommended`, `why` or `undecided_because`, still fails to render with the existing contract error; `exhausted` and `postpone_cost` render when present and are absent without error (PRD AC-009)
- [ ] A round JSON carrying a `debate_card` with `undecided_because` naming a value renders; no field of the required set changes (PRD AC-010)
- [ ] `OPTIONAL["debate_card"]` gains exactly `exhausted` and `postpone_cost`; `REQUIRED["debate_card"]` and the evidence-grade enum are byte-identical (SDD §14 row "round schema `debate_card` optional field set"; ADR-0008)
- [ ] `components.py` renders `exhausted` and `postpone_cost` beside `third_paradigm`, in the detail block before the option grid; an existing round JSON without them renders as before (SDD §4 "Surface reachability")
- [ ] `DECISIONS.md` carries one `## Prepared ask` section naming the bar: recommendation, evidence + grade, `exhausted` (what was tried), `postpone_cost`, and the value in `undecided_because`; `ROUND.md`'s debate and confirm items point at it, never restate it (PRD C4 AR-9)
- [ ] `LAVISH-KIT.md`'s `debate_card` row lists the two optional fields; `GRILL-LOG-FORMAT.md`'s checkpoint tail carries them where a debate item is logged (SDD §14 row "round schema `debate_card` optional field set")
- [ ] All five lockstep files change in this one subtask's commit (PRD "Implementation Decisions" row "`DECISIONS.md` \"Prepared ask\" + `ROUND.md` + `scripts/lavish/schema.py`")
- [ ] Implements the public interfaces in SDD §8 rows "prepared ask (decision protocol section)" and "round renderer + schema" unmodified: 2 optional fields; unchanged CLI (SDD §8)
- [ ] Conforms to ADR-0008 — no `world` or `org` grade added; a research-report claim cites as `spec` (ADR-0008)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] Seam-test asserts on the renderer's real HTML output (the two fields present when given, absent otherwise, required-field refusal unchanged), not on the parsed dict (SDD §9b row "Round renderer")

## Produces
- scripts/lavish/schema.py#postpone_cost — `OPTIONAL["debate_card"]` carries `exhausted` and `postpone_cost`
- scripts/lavish/components.py#postpone_cost — the debate card renders both fields beside `third_paradigm`
- DECISIONS.md#Prepared ask — the bar for anything that reaches a human: recommendation, graded evidence, `exhausted`, `postpone_cost`, value named
- LAVISH-KIT.md#postpone_cost — the `debate_card` component row lists both optional fields
- skills/afk/grill-requirements/ROUND.md#Prepared ask — debate and confirm items point at the `DECISIONS.md` bar
- skills/afk/grill-requirements/GRILL-LOG-FORMAT.md#postpone_cost — checkpoint tail carries the two fields on a logged debate item

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `python -m py_compile scripts/lavish/schema.py scripts/lavish/components.py` + grep every ## Produces anchor | modules load; all five lockstep files carry the change |
| unit | `python -m pytest scripts/tests/test_lavish_render.py -q` — new cases: `test_a_debate_card_renders_exhausted_and_postpone_cost`, `test_a_debate_card_without_the_optional_fields_renders_as_before`, `test_a_debate_card_missing_a_required_field_is_still_refused` (AC-009, AC-010) | the round renderer seam on its real HTML output; existing refusal unchanged |

## Context excerpts
> (PRD AC-009) A `debate_card` with fewer than 2 options, or without `recommended`, `why`, `undecided_because`, fails to render (existing check); `exhausted` and `postpone_cost` are accepted when present and absent without error.
> (PRD AC-010) A value judgment reaches the human as a `debate` item with `undecided_because` naming the value; the renderer accepts it.
> (PRD §Solution 2) **Prepared ask**: one bar in `DECISIONS.md` for anything that reaches a human. The round renderer already enforces the core fields; two optional fields are added.
> (PRD C4 AR-9) `DECISIONS.md` "Prepared ask" section | plugin author | `ROUND.md` debate/confirm items; execute, preflight and autopilot park reports; `scripts/lavish/schema.py`
> (PRD "Implementation Decisions") `DECISIONS.md` "Prepared ask" + `ROUND.md` + `scripts/lavish/schema.py` | the bar for anything reaching a human; 2 optional card fields | 4-file round-dossier lockstep, same commit
> (PRD User Story 2) As a team lead, I want each item that reaches me to carry a recommendation, graded evidence, what was tried, and the cost of postponing, so that I decide in one pick.
> (SDD §4 "Surface reachability") No existing entity gains a field. The round document gains two optional debate-card fields (`exhausted`, `postpone_cost`): the renderer changes with the schema in the same commit; the response grammar and the answer form are unchanged (INV-001).
> (SDD §8 row "prepared ask (decision protocol section)") the bar for anything reaching a human | 2 optional debate-card fields | round schema | —
> (SDD §8 row "round renderer + schema") render the two new optional fields | unchanged CLI | — | —
> (SDD §9b row "Round renderer") plugin's own schema (`schema: 1`) | renders two optional fields | INV-001 | contract error exit 1 | `test_lavish_render` addition for the two fields
> (SDD §14 row "round schema `debate_card` optional field set") unknown key is a hard render exit; fields render only where the components emit them (INV-005, INV-001) | +2 optional fields `exhausted`, `postpone_cost`; renderer emits them beside `third_paradigm` | render script, kit fixture, round-page tests (INV-001) | four-file lockstep same commit; renderer first or same commit; no test pins the optional tuple today | extends (ADR-0007 req.)
> (LAVISH-KIT.md:129) | `debate_card` | `question`, `options[]` `{id, label, criteria{}}` (≥2), `criteria_order[]`, `recommended`, `why`, `undecided_because` | `context`, `depends_on[]`, `third_paradigm` | side-by-side options, identical criteria rows, recommendation flagged |
> (scripts/lavish/schema.py:69) "debate_card": ("context", "third_paradigm"),
> (ADR-0008 requirements) No `world` or `org` evidence grades: a research-report claim cites as `spec`, an accepted priority in CLAUDE.md as `pattern`; the grade enum in `scripts/lavish/schema.py` is unchanged.
> (PRD "Testing Decisions") Prior art: … `scripts/lavish/schema.py` contract errors for card fields.

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

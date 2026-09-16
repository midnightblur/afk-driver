# 0005-research-doctrine — `RESEARCH.md` root doctrine

## Goal
Create `RESEARCH.md` (plugin root): the one home for world-research doctrine — the question types W1–W4 with their closure rules and budget-exhaustion output, the source classes `primary | secondary | tertiary`, the claim citation shape (locator, retrieval date, class, applicability, `fact | inference`, quote), what is never evidence (search snippets, provider agreement), the sufficiency rule per type, query hygiene (what a public query may not carry), and organization-priority inference (scope, authority, supersession, provenance, counterevidence; advisory only; accepted priorities reach CLAUDE.md through `/afk:claude-md`). Add one pointer line in `INVESTIGATION.md` from code closure to world research; code closure and counter-search rules stay unchanged. Register the file in `FRESHNESS.md`. Prose only — the executable procedure is a later slice.

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 row "research doctrine file" — question types, source classes, citation shape, closure, hygiene, priority inference; prose contract read by the research skill and the researcher agent
- SDD: SDD.md#§6 invariant I-8 — a snippet or provider agreement is never evidence
- SDD: SDD.md#§14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — pointer-only lockstep; closure and counter-search unchanged
- ADR: adr/requirements/0001-no-priorities-registry-now.md — priorities are advisory findings; no registry file
- ADR: adr/requirements/0003-web-research-when-relevant-staged-egress.md — `when_relevant` default; hygiene rejects internal terms, ticket ids, code, customer identifiers
- ADR: adr/requirements/0008-rejected-extensions.md — no counter-search route; a research claim cites as `spec`

## Scope
- RESEARCH.md
- INVESTIGATION.md          # one pointer line only
- FRESHNESS.md              # one registry row for RESEARCH.md
- CLAUDE.md                 # the Reference list entry for RESEARCH.md only

## Seams
- implement: §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc" — this subtask owns `RESEARCH.md` and the `INVESTIGATION.md` pointer line (INV-004)

## Acceptance
- [ ] `RESEARCH.md` carries the catalog C1 table (W1–W4: closes-when rule and `incomplete` + named gaps on budget exhaustion) as its closure rule, with the W2/W4 rule "one authoritative primary source with quoted text, URL and fetch date" and the W1/W3 rule "every declared question, material counterclaim and option-eliminating assumption has a disposition" (PRD C1; AC-001, AC-002)
- [ ] `RESEARCH.md` defines the source classes `primary`, `secondary`, `tertiary` and states that a search snippet or agreement between providers is never evidence and yields `unverified` (PRD C1; SDD §6 I-8; AC-003)
- [ ] `RESEARCH.md` fixes the claim shape: source locator, retrieval date, source class, applicability, `fact` or `inference`, quote when verified, counterevidence ids — the field set of `SIGNED-PACKETS.md` §HL-1 claim record (PRD AC-004)
- [ ] `RESEARCH.md` states the budget rule: exhausting `research.max_minutes` returns `incomplete` with named gaps and never claims the web was exhaustively searched (PRD AC-006)
- [ ] `RESEARCH.md` states query hygiene: a public query carrying a glossary-listed internal term, a ticket id, code, or a customer identifier is rejected before egress; the three `research.public` modes `off | when_relevant | required` and their rule (PRD AC-007, AC-008; ADR-0003)
- [ ] `RESEARCH.md` states organization-priority inference: recorded with scope, authority, supersession, provenance and counterevidence, marked advisory, never binding; an accepted priority enters CLAUDE.md only through `/afk:claude-md`; no registry file (PRD AC-005; ADR-0001)
- [ ] `RESEARCH.md` states the evidence grade a research claim carries on a card: `spec`; no new grade (ADR-0008)
- [ ] `INVESTIGATION.md` gains exactly one pointer line to `RESEARCH.md` for world questions; its question types, boundary catalog, closure and counter-search sections are unchanged (SDD §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc")
- [ ] `RESEARCH.md` names no caller skill and no calling stage (plugin `CLAUDE.md` "Downstream is blind to upstream")
- [ ] `FRESHNESS.md` registry gains one row for `RESEARCH.md` (steward: plugin author; triggers: a question type, source class, citation field, closure or hygiene rule changes); `CLAUDE.md` Reference list gains one line (FRESHNESS.md "Artifact registry")
- [ ] Implements the public interface in SDD §8 row "research doctrine file" unmodified: a prose contract read by the research skill and the researcher agent (SDD §8)
- [ ] Every artifact in ## Produces exists with its declared section heading (SDD §8)
- [ ] Written per `LANGUAGE.md` §3 and `skills/utils/writing-for-agents`; every sentence carries a rule the reader acts on (plugin `CLAUDE.md` "How to write these skill files")

## Produces
- RESEARCH.md#Question types — W1–W4 with closes-when and budget-exhaustion output
- RESEARCH.md#Source classes — `primary | secondary | tertiary`; snippets and provider agreement are never evidence
- RESEARCH.md#Claim record shape — the per-claim field set and `fact | inference`
- RESEARCH.md#Closure and budget — type-specific closure; `incomplete` + named gaps on `research.max_minutes`
- RESEARCH.md#Query hygiene — the reject set and the three `research.public` modes
- RESEARCH.md#Organization priorities — inference fields, advisory status, the `/afk:claude-md` path
- INVESTIGATION.md#world question — the one pointer line from code closure to world research

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | grep every ## Produces anchor; `python hooks/run-hook.py plugin stop-gates.sh` (genericity + wiring gates on the added prose); `git diff --stat INVESTIGATION.md` shows one added line | sections present; prose passes the plugin's Stop gates; the pointer is one line |

## Context excerpts
> (PRD C1) | W1 | Landscape: what other teams or products do | Every declared question, material counterclaim and option-eliminating assumption has a disposition; source count is metadata | `incomplete` + named gaps | · | W2 | Standard or specification | One authoritative primary source with quoted text | `incomplete` + named gaps | · | W3 | Common-sense baseline or default number | Same as W1 | `incomplete` + named gaps | · | W4 | Behaviour of a version or flag | Same as W2 | `incomplete` + named gaps |
> (PRD C1) Source classes carried per claim: `primary` (standard owner, official product doc, original study), `secondary` (reputable write-up), `tertiary` (forum). Search snippets and agreement between providers are never evidence.
> (PRD AC-001) A W2 or W4 question returns `closed` only when the report cites one authoritative primary source with quoted text, URL and fetch date; without one it returns `incomplete` with the unanswered question named.
> (PRD AC-002) A W1 or W3 question returns `closed` only when every declared question, material counterclaim and option-eliminating assumption carries a disposition; any missing disposition returns `incomplete`.
> (PRD AC-003) A claim supported only by a search snippet, or only by two providers agreeing, is recorded as `unverified`, never as fact.
> (PRD AC-004) Each material claim in AR-2 carries source locator, retrieval date, source class (C1), applicability, and `fact` or `inference`; a claim missing any field fails the research fixture.
> (PRD AC-005) An inferred organization priority is recorded with scope, authority, supersession, provenance and counterevidence, marked advisory; a report that states a priority as binding fails the fixture.
> (PRD AC-006) Research exhausting `research.max_minutes` returns `incomplete` with named gaps; it never claims the web was exhaustively searched.
> (PRD AC-007) With `research.public: off`, no web tool call occurs; with `when_relevant`, a web call occurs only for a question an authorized local tool cannot settle; with `required`, a run with no web call fails.
> (PRD AC-008) A public query that contains a glossary-listed internal term, a ticket id, code, or a customer identifier is rejected before it leaves the machine.
> (PRD "Implementation Decisions" row "`RESEARCH.md` (root doctrine)") question types C1, source classes, citation shape, sufficiency, query hygiene, organization-priority inference rules | new file; `INVESTIGATION.md` gains one pointer, keeps code closure
> (PRD C4 AR-8) `RESEARCH.md` (plugin root) | plugin author | `/afk:research`, `afk-researcher`, caller pointers
> (SDD §6 I-8) A snippet or provider agreement is never evidence | research report, participant job | claim record `status` | `unverified`; excluded from closure (AC-003)
> (SDD §8 row "research doctrine file") question types, source classes, citation shape, closure, hygiene, priority inference | prose contract read by the research skill and the researcher agent | — | research report
> (SDD §14 row "`DECISIONS.md`, `DELEGATION.md`, `INVESTIGATION.md` and `LANGUAGE.md` pointer lines, plus the new `RESEARCH.md` root doc") pointer-only lockstep partners per the freshness registry (INV-008, INV-004) | +`Prepared ask` section; +`Dispatch and handoff` section; +1 pointer line | none at runtime (INV-004) | closure and counter-search rules unchanged | extends
> (ADR-0001 requirements) Inferred organization priorities appear as advisory findings inside the research report (PRD catalog C4, AR-1). A human-accepted priority is written into CLAUDE.md only by `/afk:claude-md` through its existing inclusion bar. No `PRIORITIES.md` registry file is created in this release
> (ADR-0003 requirements) Public web research runs at `research.public: when_relevant` by default: only for a question an authorized local tool cannot settle, with queries rejected when they carry internal terms, ticket ids, code or customer identifiers (PRD AC-007, AC-008).
> (ADR-0008 requirements) No `world` or `org` evidence grades: a research-report claim cites as `spec`, an accepted priority in CLAUDE.md as `pattern` … No consultation route into investigation counter-search: a second provider running the same enumeration is not a different method per `INVESTIGATION.md`.
> (SIGNED-PACKETS.md §HL-1 claim record) id · statement · kind (fact \| inference) · status (verified \| unverified \| contradicted) · source_locator · source_class (primary \| secondary \| tertiary) · retrieved_at · quote (500 chars max; required when `verified`) · applicability · counterevidence (array of claim ids)

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

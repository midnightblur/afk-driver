# Subtask contract (`plan/NNNN-{slug}.md`)

`/afk-toolkit:execute` parses these section headings exactly. Keep them verbatim.

```
## Goal
<one paragraph: what this subtask delivers>

## Complexity
<one token — the emitter's judgment of the thinking the slice demands, used by
orchestrators to size the executing agent (model/effort). This enum's one home
is this file; a skill that routes on it points here.
  mechanical — regen / sweep / rename / config / doc churn; no design judgment;
               verification is deterministic
  standard   — a typical implementation slice (the default; also what a parser
               assumes when the section is absent in an older plan)
  complex    — multi-seam integration, concurrency/transaction semantics,
               tricky domain logic, or high blast radius>
mechanical | standard | complex

## Review
<optional — omit to take the plan-level default (PLAN.md header `Review policy:`).
Either or both lines; policy semantics, deferrable-concern names, and resolution
order: skills/afk/review/SKILL.md "Gate policy">
policy: lean | full — overrides the plan default for this slice alone
opt-in: <concern>, … — lean-deferred concerns to run at this slice's gate anyway

## Design refs
<cited>
- SDD: SDD.md#<anchor> — <one phrase on what it binds>
- ADR: adr/design/NNNN-*.md — <one phrase>
<uncited>
(none — sliced from the PRD without an SDD, per human approval)

## Scope
- <glob 1>
- <glob 2>

## Seams
<cited — the SDD §9b external seams this subtask touches; mark each implement|use>
- implement: <SDD §9b row "boundary"> — this subtask owns the seam's code + seam-test
- use: <SDD §9b row "boundary"> — this subtask calls across it; relies on its contract
<uncited or no seam>
(none — no SDD seam register)

## Acceptance
<cited — every bullet ends with a citation tag: (PRD §X.Y) / (SDD §N) /
(SDD §N row "...") / (SDD §9b row "...") / (ADR-NNNN).
The criterion text itself must be a self-contained pass/fail statement a reader
understands WITHOUT opening the cited doc — the tag is provenance, never the
content. "Honours SDD §4" alone is invalid.>
- [ ] <criterion> (PRD §X.Y)
- [ ] Implements the public interface in SDD §8 row "<module>" unmodified (SDD §8)
- [ ] Conforms to ADR-<NNNN> — no silent pattern substitution (ADR-NNNN)
- [ ] Every artifact in ## Produces compiles + matches its declared signature (SDD §8)
- [ ] <iff this subtask implements a §9b seam> Seam-test asserts on <framework>'s
      real output (serialized result / generated schema / surfaced error), not our
      intermediate objects (SDD §9b row "<boundary>")
<uncited — bullets reference PRD prose, no tags>
- [ ] <criterion referencing User Story N>

## Produces
<cited — one bullet per consumer-visible artifact this subtask creates>
- <file-path>#<grep-anchor> — <one-line contract>
<iff the seam was materialized at slicing time (stub + contract test already on
the branch), the bullet ends with the marker — the anchor then resolves at HEAD
and the contract is compiler-checked, not just grep-checked>
- <file-path>#<grep-anchor> — <one-line contract> [materialized]
<uncited — omit this block>

## Consumes
<cited AND Blocked by non-empty — one bullet per upstream artifact read;
a line citing a materialized Produces bullet carries the same trailing marker>
- <PRODUCER-ID> <file-path>#<grep-anchor> — <what we expect>
- <PRODUCER-ID> <file-path>#<grep-anchor> — <what we expect> [materialized]
<otherwise — omit this block>

## Verification
<tiered — one row per tier this subtask needs; static is always present.
The implementor (/afk-toolkit:execute) must turn EVERY listed tier green.
api / e2e rows must drive the same interaction shape the real client uses —
server-provided data round-trips verbatim; an input massaged solely to dodge a
server rejection is forbidden (an unexpected failure on a faithful interaction
is a candidate defect, not an input-shaping cue).>
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `<compile/lint/type cmd>` + grep the ## Produces anchors | code builds; declared symbols present |
| unit | `<unit test cmd, e.g. mvn -pl {module} test -Dtest=FooTest>` | unit behavior |
| integration | `<cmd>` | cross-module wiring / persistence / framework pickup |
| api | `<cmd, e.g. node --test verification/api/foo.test.mjs>` | endpoint contract direct over REST (no UI) — incl. below-the-UI authz |
| e2e/browser | `<the `e2e/browser` tier command from verification.tiers>` | user-visible flow end-to-end |

## Context excerpts
<verbatim quotes from the PRD/SDD/ADRs this slice's implementor needs —
selected at slicing time, when the emitter has the full sources open. Quotes
only, never paraphrase; each block carries its citation tag. Include: the
Acceptance bullets' source passages, the §8 interface rows this slice
implements, the §9b seam rows it touches, binding ADR decision lines. The
implementor works from these and opens the full parent doc only when a
question the excerpts don't settle arises. Both modes; omit a source that
doesn't exist.>
> (PRD §X.Y) <quoted passage>
> (SDD §8 row "<module>") <quoted signature/contract>
> (ADR-NNNN) <quoted decision>

## Parent PRD
<prd_path>

## Parent SDD
<sdd_path or "(none — uncited mode)">

## Blocked by
<subtask ids (NNNN-slug) or "(none)">

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk-toolkit:grill-solution` for a
superseding ADR.
(omit this block in uncited mode)
```

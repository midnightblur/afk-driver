## Goal
Create the plugin-owned pure domain package for glossary identities, definitions, routes, fingerprints, findings, gate specifications, and append-only record replay.

## Complexity
complex

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — pure values and functions own parsing, projection, specifications, and replay
- ADR: adr/design/0001-split-definition-and-publication-ledgers.md — definitions and publication records remain separate authorities
- ADR: adr/design/0002-stable-markdown-identity-and-adoption.md — terms use stable identity metadata
- ADR: adr/design/0007-ordered-selection-with-bounded-semantic-strategy.md — deterministic selection owns merge and limits

## Scope
- scripts/glossary_lifecycle/domain.py
- scripts/glossary_lifecycle/markdown.py
- scripts/glossary_lifecycle/tests/test_domain.py
- scripts/glossary_lifecycle/tests/test_markdown.py

## Seams
- implement: SDD §14 row "Append-only reconstruction" — codec and reducer detect edits, gaps, and unresolved findings (INV-012)
- implement: SDD §14 row "Glossary Markdown" — one grammar preserves ID, canonical term, aliases, and replacement links (INV-012)
- implement: SDD §14 row "Routing" — manifest routes and ownership resolve deterministically (INV-012)

## Acceptance
- [ ] Stable values represent RE-01 through RE-08 without provider or filesystem types leaking into the domain package. (SDD §6)
- [ ] Fingerprints are deterministic and change only for the inputs named by RE-03 and RE-04. (PRD §Records and evidence)
- [ ] Replay derives all open confirmed findings and never lets a later passing record hide one. (PRD §Acceptance Criteria)
- [ ] The Markdown grammar rejects duplicate IDs, unresolved replacement links, and alias collisions. (SDD §9b row "Glossary Markdown parser")
- [ ] Implements the public interface in SDD §8 row "Pure domain rules" unmodified. (SDD §8)
- [ ] Seam tests assert parsed records, stable reducer output, and surfaced typed errors rather than helper state. (SDD §14 row "Append-only reconstruction")

## Produces
- scripts/glossary_lifecycle/domain.py#class GlossaryDomainRules — stable public entry point for domain operations
- scripts/glossary_lifecycle/markdown.py#class GlossaryMarkdownCodec — canonical definition parser and serializer

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/domain.py scripts/glossary_lifecycle/markdown.py` plus grep the Produces anchors | modules compile and contracts exist |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_domain.py scripts/glossary_lifecycle/tests/test_markdown.py` including the cross-parser golden corpus | canonical bytes agree across every glossary parser; identity, fingerprint, routing, gate, and replay rules hold |

## Context excerpts
> (PRD §Acceptance Criteria) "Validation derives open findings from all RE-08 records; every confirmed RE-05 blocks its applicable gate, and a later passing record cannot hide it."
>
> (SDD §8 row "Pure domain rules") "Parse definitions, project fingerprints, evaluate specifications, replay state | Pure values and functions | None | All four"
>
> (ADR-0002) "Adopt explicit stable identity metadata in Markdown and require prerequisite migration before the lifecycle can govern an existing glossary."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

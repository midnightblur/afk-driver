## Goal
Implement pinned Git/configuration reads, tracked-text discovery, glossary definition writes, and the bounded semantic-candidate adapter behind the repository port.

## Complexity
complex

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — repository access reads pinned controls and definitions and writes definitions
- ADR: adr/design/0003-separate-ownership-and-delivery-routing.md — routing and ownership use separate authorities
- ADR: adr/design/0007-ordered-selection-with-bounded-semantic-strategy.md — semantic discovery is the only variable selection stage
- ADR: adr/design/0008-pinned-repository-and-atomic-local-evidence.md — target controls come from a refreshed pinned snapshot

## Scope
- scripts/glossary_lifecycle/repository.py
- scripts/glossary_lifecycle/tests/test_repository.py
- CONFIG.md
- scripts/afk-config.py
- scripts/tests/test_afk_config.py

## Seams
- implement: SDD §14 row "AFK configuration" — add the optional manifest pointer and committed-at-ref view (INV-012)
- use: SDD §14 row "Git and local evidence" — provide NUL-safe Git inputs to the combined linked-worktree/evidence seam test (INV-012)
- implement: SDD §14 row "Semantic provider" — search only tracked text and enforce candidate and evidence limits (INV-012)
- use: SDD §14 row "Glossary Markdown" — read and write definitions through the canonical codec (INV-012)
- use: SDD §14 row "Routing" — resolve manifests through domain rules (INV-012)

## Acceptance
- [ ] Every command refreshes and records the target reference before it reads controls from the merge base. (PRD §Acceptance Criteria)
- [ ] Exact term and route matches are deterministic and never truncated. (PRD §Acceptance Criteria)
- [ ] Semantic fallback reads only tracked text in configured roots and returns at most 20 candidates with 3 snippets each. (PRD §Acceptance Criteria)
- [ ] Provider failure and unverifiable target state return typed errors instead of empty success. (SDD §9b row "Git tracked-file and ref commands")
- [ ] Implements the public interface in SDD §8 row "Repository access" unmodified. (SDD §8)
- [ ] Seam tests assert real Git output in linked worktrees and real ranked provider output. (SDD §14 row "Git and local evidence")

## Produces
- scripts/glossary_lifecycle/repository.py#class PinnedRepositoryAdapter — repository port implementation for pinned controls and tracked sources
- scripts/afk-config.py#glossary-manifest — configuration key exposed by the single strict reader

## Consumes
- 0001-pure-domain-rules scripts/glossary_lifecycle/domain.py#class GlossaryDomainRules — route, fingerprint, and selection rules
- 0001-pure-domain-rules scripts/glossary_lifecycle/markdown.py#class GlossaryMarkdownCodec — canonical definition bytes

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/repository.py scripts/afk-config.py` plus grep the Produces anchors | modules compile and contracts exist |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_repository.py scripts/tests/test_afk_config.py` | configuration, normalization, limits, and failure rules |
| integration | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_repository.py -k "linked_worktree or tracked_text_ranking_bounds"` | pinned-ref and NUL-safe Git behavior plus real tracked-text ranking, 20-candidate/3-snippet bounds, truncation, and provider-error output |

## Context excerpts
> (PRD §Acceptance Criteria) "Semantic fallback returns at most 20 ranked candidates per declared domain area and 3 evidence snippets per candidate; truncation is recorded."
>
> (SDD §8 row "Repository access") "Read pinned controls and definitions; write definitions | Repository port | Git implementation | Repository glossary"
>
> (ADR-0008) "Read repository policy and glossary state from a refreshed, pinned target snapshot."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0001-pure-domain-rules

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

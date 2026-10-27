# P2P-2067 — AFK glossary lifecycle

## Problem Statement

Teams define domain language, but the delivery flow does not consistently use or recheck it.

- Requirements can introduce terms without routing them to an owner.
- Agents can receive too many definitions or miss the relevant definitions.
- Reviews can detect wording drift without a consistent finding and closure contract.
- Implementation can change meaning after the requirements discussion.
- Repository receipts create maintenance work without improving definition history.

## Solution

AFK adds a repository-independent glossary lifecycle. It selects relevant definitions before work, audits changed vocabulary, and reconciles definitions after implementation. Git records definition history. Merge request comments record audit and reconciliation outcomes.

Repository configuration stays with the owning team. For core-services, it lives under `tools/payable`. The mechanism does not change CI.

## Catalog

### Lifecycle contracts

| ID | Contract | Required result | Failure result |
|---|---|---|---|
| LC-01 | Glossary route | Every derived or declared domain area resolves to a glossary and human owner. | The current AFK phase cannot close. |
| LC-02 | Glossary consultation | AFK presents the selected definitions before the next phase starts. | The next phase cannot start. |
| LC-03 | Vocabulary audit | Every changed vocabulary surface is mapped, excluded with evidence, or covered by a resolved finding. | The applicable review gate fails. |
| LC-04 | Glossary reconciliation | Every affected definition receives a retain, revise, add, or reject outcome and owner state. | The merge request cannot become Ready or settle, as defined by AC-018 and AC-019. |

### Records and evidence

| ID | Record | Required content | Freshness rule |
|---|---|---|---|
| RE-01 | Feature vocabulary scope | Declared terms, inherited terms, routed glossaries, changed user interface text, contracts, events, configuration keys, domain-bearing persistence fields, identifiers, observable business behavior, and explicit exclusions. | Changes when an included surface or exclusion changes. |
| RE-02 | Surface inventory | Ordered path and surface-kind entries from changed-path routes and author declarations. | Changes when an inventoried surface changes. |
| RE-03 | Consultation fingerprint | Normalized RE-01, routed paths, selected term IDs, selected definitions, owners, routes, mappings, target merge-base glossary state, and semantic-search evidence naming roots, exclusions, method, model, and truncation. | Changes only for a semantic change to its inputs. |
| RE-04 | Audit fingerprint | RE-03 plus RE-02, changed vocabulary surfaces, the semantic-search evidence used by the audit, and the audited head SHA. | Changes when RE-03, an inventoried surface, its search evidence, or the head SHA changes. |
| RE-05 | Finding | Stable ID, class, evidence, affected term or surface, owner, closure test, status, and resolution ID when closed. | Remains open until a resolution names its ID. |
| RE-06 | Tool-failure override | Failed check, scope, reason, owner act, expiry gate, UTC expiry, and bound fingerprints. | Expires at the next vocabulary gate, fingerprint change, or timestamp. |
| RE-07 | Solo-owner attestation | Human prompt and answer, decision-maker, publisher, harness, session ID, UTC timestamp, term IDs, hashes, fingerprints, and head SHA. | Invalid when either fingerprint changes. |
| RE-08 | Merge request record | Append-only audit or reconciliation result with author, audited head SHA, glossary paths, selected terms, findings, resolutions, auditors, and outcome. | Edited records and detectable interior deletions or sequence gaps are invalid. Comment history cannot prove deletion of its complete newest suffix. |

## User Stories

1. As a feature owner, I want to define and route terms during requirements, so later work uses agreed language.
2. As an implementation agent, I want only the relevant definitions, so context stays focused without hiding applicable terms.
3. As an independent auditor, I want a bounded vocabulary scope and closure rules, so findings are reproducible and actionable.
4. As a glossary owner, I want to reconcile definitions after implementation, so the glossary reflects delivered behavior.
5. As a repository maintainer, I want a standard bootstrap path, so another repository can adopt the mechanism safely.

## Acceptance Criteria

- [ ] **AC-001:** LC-01 derives domain areas from changed-path routes and author declarations; an unresolved area blocks phase closure.
- [ ] **AC-002:** LC-02 selects relevant routed and declared terms; it does not load an entire glossary unless every term is selected.
- [ ] **AC-003:** LC-02 records RE-01 and RE-03 before design or execution starts; a missing record blocks the transition.
- [ ] **AC-004:** Exact term and route matches are deterministic and never truncated.
- [ ] **AC-005:** Semantic fallback returns at most 20 ranked candidates per declared domain area and 3 evidence snippets per candidate; truncation is recorded.
- [ ] **AC-006:** Semantic fallback reads only tracked text inside configured roots and RE-01; generated output, dependencies, logs, binaries, fixtures, seeds, and known data exports are excluded.
- [ ] **AC-007:** A semantic-search signal does not block until an independent auditor supplies every RE-05 field except resolution.
- [ ] **AC-008:** New requirement-stage definitions are written to the owning glossary on the feature branch and remain provisional until owner finalization.
- [ ] **AC-009:** Glossary definitions do not require volatile code references; RE-02 carries implementation locations instead.
- [ ] **AC-010:** A confirmed whitespace, markup, or typo-only edit does not change RE-03; an unconfirmed edit does.
- [ ] **AC-011:** A change to a selected definition, owner, route, mapping, merge-base glossary state, or RE-01 changes RE-03 and requires delta consultation.
- [ ] **AC-012:** A change to RE-02 or RE-03 changes RE-04 and requires another applicable audit.
- [ ] **AC-013:** A routine addition receives 1 independent audit; a meaning change or disputed term receives 2. An ambiguous classification defaults to meaning-changing and receives 2 audits.
- [ ] **AC-014:** An independent auditor did not author the affected definitions or contracts, remains read-only, and cannot approve its own resolution.
- [ ] **AC-015:** A non-author on the single-service owner chain finalizes its terms through a forge approval. For a cross-service term, every affected owner chain supplies a forge approval from at least 1 non-author; the product-domain owner resolves deadlock. An author-owner can finalize only through the single-service RE-07 exception in AC-017 and cannot count for a cross-service approval.
- [ ] **AC-016:** A temporary delegate is valid only when an owner record names the delegate, scope, reason, and expiry.
- [ ] **AC-017:** RE-07 is available only when a single-service owner chain resolves to exactly 1 human who authored the merge request and has no active delegate; cross-service terms cannot use it.
- [ ] **AC-018:** `/afk:preflight` requires LC-04 with valid RE-03 and RE-04, no blocking finding, and no active RE-06 before it makes a merge request Ready; definitions may still have provisional owner state.
- [ ] **AC-019:** `/afk:settle-change` refuses settlement until every affected definition has final owner state and the latest valid RE-08 matches RE-03 and RE-04.
- [ ] **AC-020:** Owner rejection returns the merge request to Draft and requires impact analysis plus another LC-04 before Ready.
- [ ] **AC-021:** RE-06 can permit intermediate work but cannot permit Ready or settlement.
- [ ] **AC-022:** Before a Draft merge request exists, consultation and audit records remain uncommitted run artifacts; the first RE-08 copies them and recomputes fingerprints.
- [ ] **AC-023:** Each audit or reconciliation run posts a new RE-08; no run edits a prior record.
- [ ] **AC-024:** Validation derives open findings from all RE-08 records; every confirmed RE-05 blocks its applicable gate, and a later passing record cannot hide it.
- [ ] **AC-025:** A repository without a glossary uses a separate prerequisite bootstrap merge request that creates routes, an owning glossary, and owner declarations.
- [ ] **AC-026:** Only LC-01 applies to the bootstrap merge request; the first feature requirements phase cannot close until bootstrap reaches the target branch.
- [ ] **AC-027:** The bootstrap requires a non-author maintainer approval or RE-07 when the author is the only maintainer.
- [ ] **AC-028:** An in-progress feature adopts the lifecycle at its next AFK phase and audits all still-reachable vocabulary without inventing earlier records.
- [ ] **AC-029:** Non-AFK work can run a manual LC-03 and LC-04 through AFK before settlement.
- [ ] **AC-030:** CI configuration remains unchanged; a human merge outside AFK can bypass these gates and is an accepted limitation.
- [ ] **AC-031:** Git stores glossary definition history; RE-08 stores audit history; no `.glossary-rebuild` or committed receipt archive is created.
- [ ] **AC-032:** Core-services stores team-owned glossary configuration under `tools/payable`; no mechanism state directory is added at repository root.
- [ ] **AC-033:** RE-07 uses an interactive human-only prompt that shows term IDs, term hashes, RE-03, RE-04, and head SHA and accepts only final or reject. Free text and agent-supplied answers are invalid; hands-off or driven work parks without timeout until the human answers.
- [ ] **AC-034:** A confirmed RE-05 closes only when its resolution ID records one of: a term or work change, an ownership or routing correction, or an evidence-backed false-positive dismissal that satisfies the finding's closure test.
- [ ] **AC-035:** Every gate loads owner chains, declarations, search configuration, source roots, routes, mappings, and glossary state from the target branch at the recorded merge base, after refreshing the target reference and recording its commit; feature-branch control changes cannot authorize that same feature.
- [ ] **AC-036:** A gate blocks when the target reference, merge base, or target-branch controls cannot be verified, unless a valid RE-06 permits intermediate work; an RE-06 never permits Ready or settlement.
- [ ] **AC-037:** When the forge cannot verify RE-08 edit metadata, validation requires a new owner-confirmed RE-08 that cites the unverifiable record and supersedes its outcome without editing it.
- [ ] **AC-038:** A legacy vocabulary gap enters the feature scope only when the feature adds, changes, removes, or semantically relies on its surface or mapping; other legacy gaps are recorded as nonblocking observations.
- [ ] **AC-039:** Validation detects edited RE-08 records and gaps or deletions inside the retained record sequence. Deletion of the complete newest record suffix is an accepted forge limitation because the remaining comments cannot prove that the suffix existed.

## Access & validation policy

| Capability / User Story | Permitted role(s) | Denied role(s) | Data scope | Key validation rules |
|---|---|---|---|---|
| Propose or revise a definition | Feature author; AFK agent | Read-only auditor | Repository sources in RE-01 | Proposal remains provisional. |
| Promote a signal to RE-05 | Independent auditor | Author of affected definition or contract | Evidence inside RE-01 | AC-007 and AC-014. |
| Finalize a single-service definition | Non-author glossary owner through forge approval; author-owner through RE-07 | Unowned developer; AFK agent; author-owner without RE-07 | Owning glossary | AC-015; RE-07 exception under AC-017. |
| Finalize a cross-service definition | At least 1 non-author approver from every affected glossary owner chain; product-domain owner on deadlock | Merge-request author; solo owner acting alone; AFK agent | Affected owning glossaries | AC-015 and AC-017. |
| Approve RE-06 | Glossary-owner chain | Feature agent; non-owner | Failed check and bound fingerprints | AC-021. |
| Bootstrap a repository | Non-author maintainer; sole maintainer through RE-07 | Non-maintainer; AFK agent | Bootstrap merge request | AC-025 through AC-027. |
| Settle a change | `/afk:settle-change` with final owner evidence | Merge-request author acting without owner evidence | Current merge request and target merge base | AC-019 and AC-024. |

## Implementation Decisions

| ID | Module | Responsibility | Test scope |
|---|---|---|---|
| MOD-01 | Glossary engine | Resolve routes, build RE-01 and RE-02, select terms, compute RE-03 and RE-04, classify findings, and evaluate freshness. | Deterministic unit and property tests. |
| MOD-02 | AFK workflow integration | Apply LC-01 through LC-04 during requirements, design, execution, review, preflight, and settlement. | Workflow contract tests across every transition and refusal. |
| MOD-03 | Forge record adapter | Publish and validate RE-06 through RE-08, owner acts, edited records, detectable interior deletions, and record sequences. | Provider-adapter contract tests with failure simulations. |
| MOD-04 | Repository bootstrap | Create and validate the first routes, glossary, owner declaration, and team configuration. | Complete fixture-repository lifecycle tests. |

- **DEC-01:** AFK-only enforcement keeps CI unchanged. See [ADR-0001](adr/requirements/0001-keep-ci-unchanged.md).
- **DEC-02:** Git stores definitions and merge request comments store audit records. See [ADR-0002](adr/requirements/0002-split-definition-and-audit-history.md).
- **DEC-03:** Repository adoption starts with a separate bootstrap merge request. See [ADR-0003](adr/requirements/0003-bootstrap-before-first-feature.md).
- **DEC-04:** Definitions may remain provisional at Ready but must be final before settlement. See [ADR-0004](adr/requirements/0004-finalize-before-settlement.md).
- **DEC-05:** A sole owner can use an explicit interactive attestation for a single-service term. See [ADR-0005](adr/requirements/0005-allow-solo-owner-attestation.md).
- **DEC-06:** Consultation loads relevant definitions instead of every glossary term. See [ADR-0006](adr/requirements/0006-consult-relevant-definitions.md).
- **DEC-07:** The plugin workflow glossary will own the 9 mechanism terms introduced by this feature.
- **DEC-08:** Candidate workflow staple: every feature defines terms during requirements, consults scoped terms, and reconciles them after implementation.

## Testing Decisions

- Test MOD-01 with stable fixtures for route precedence, normalized definitions, surface ordering, head-SHA traceability, fingerprint changes, and non-semantic edits.
- Test MOD-02 with contract fixtures for every lifecycle gate, stale record, owner rejection, temporary override, and in-progress adoption path.
- Test MOD-03 against provider stubs for authorship, approval, append-only records, edit metadata, deletion gaps, unavailable metadata, and attestation publication.
- Test MOD-04 with repositories that have complete configuration, partial configuration, no glossary, no `CODEOWNERS`, one maintainer, and multiple owners.
- Add one end-to-end fixture flow from first requirements through settlement. Include positive and negative outcomes for AC-001 through AC-039.
- Keep assertions on observable workflow results and record contracts. Do not assert prompt wording or internal orchestration order unless the wording is the contract.

## Out of Scope

- CI jobs, required pipeline checks, or forge rules that prevent a manual merge.
- Runtime customer or vendor data as semantic-search input.
- A committed rebuild directory, receipt store, or root mechanism-state directory.
- Rewriting unrelated legacy glossary gaps.
- Reusing the existing core-services draft tooling without redesign against this PRD.
- Updating current glossary content beyond terms affected by a feature.

## Further Notes

- Accepted risk: a human can merge without running AFK because CI stays unchanged.
- Accepted risk: the forge cannot prove that RE-07 came from the human. Integrity depends on the interactive harness and developer account.
- The workflow glossary does not yet contain the 9 mechanism terms in DEC-07. `/afk:glossary` must add them before implementation uses them as durable workflow language.
- No Payable staple matched this repository-independent plugin mechanism.

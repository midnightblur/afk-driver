## Goal
Make two provider-layer changes. Add to PROVIDERS.md the one equivalence rule sentence keyed on the tier row, so a single-model role on a failed provider continues on an equivalent model from another provider (change C12). Set each Codex agent stub's name field to the skill name, keeping the `afk-afk-*.toml` filenames, so a spawn of `afk-reader` resolves on Codex (change C18). The conformance proof row, the PROVIDERS.md rows and the changelog follow. The slice ends at the provider layer: the contact agent picks the substitute at run time in the team skill, and agent-start's AFK_PROVIDER route for a Codex pane agent is another subtask (plan D-20).

## Complexity
standard

## Design refs
- SDD: SDD.md#§8 L7 — Module Decomposition — row "Model equivalence": same tier row, another harness column
- SDD: SDD.md#§14 L9 — Implementation Seams & Change Impact — rows "`Model tiers` table in PROVIDERS.md" (change C12) and "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`" (change C18)
- SDD: SDD.md#§9b External Seams & Failure Affordance — row "Codex agent lookup"
- ADR: adr/design/0015-a-change-that-only-adds-keeps-the-contract.md — the tier-table change only adds, so the existing contract holds

## Scope
- PROVIDERS.md
- providers/codex/agents/*.toml
- providers/CONFORMANCE.md
- CHANGELOG.md

## Seams
- implement: §14 row "`Model tiers` table in PROVIDERS.md" — the one equivalence rule sentence, written as prose in the fallback paragraph at PROVIDERS.md:105 (INV-056)
- implement: §9b row "Codex agent lookup" via §14 row "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`" — each stub's name field becomes the skill name; filenames stay (INV-013)

## Acceptance
- [ ] Implements the public interface in SDD §8 row "Model equivalence" unmodified: the equivalent model is the same tier row in another harness column, found by a read of the tier map, with the tier map document as its one home (SDD §8 row "Model equivalence")
- [ ] PROVIDERS.md gains one equivalence rule sentence keyed on the tier row and ordered against the in-harness fallback; it goes in the one-line fallback paragraph at PROVIDERS.md:105, as prose outside the two tables check L parses (PROVIDERS.md:107-120), so no later line moves (SDD §14 row "`Model tiers` table in PROVIDERS.md")
- [ ] The sentence holds no column bar and does not open with a ## heading, so native check L reads the same tables and gives the same 0 problems as today; scripts/tests/test_model_tier_gate.py:58 and test_native_contract_events.py:57 stay green (SDD §14 row "`Model tiers` table in PROVIDERS.md")
- [ ] The sentence holds no INV-NNN and no model-name token, which the genericity gate refuses (hooks/lib/sensitive-patterns.tsv:8-9) (SDD §14 row "`Model tiers` table in PROVIDERS.md")
- [ ] The change only adds; an older reader keeps today's contract, and it rolls back by reverting the commit or installing the previous plugin version (SDD §14 row "`Model tiers` table in PROVIDERS.md")
- [ ] On a provider failure, a single-model role continues on an equivalent model from another provider, where the tier map supplies one; a debate role does not substitute, it waits (PRD AC-022)
- [ ] The rule adds no availability or quota check; a provider failure is detected when a call fails, never predicted (PRD AC-020)
- [ ] The equivalence rule does not continue a run in a reduced shape: beyond the provider's wait horizon the run parks with a dated report (PRD AC-023)
- [ ] The rule works whether team topology is on or off, so team topology and multi-model stay independently switchable (PRD AC-002)
- [ ] Each Codex agent stub's name field becomes the skill name, as in `afk-reader`; the filenames stay `afk-afk-*.toml` (SDD §14 row "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`")
- [ ] The conformance proof row in providers/CONFORMANCE.md, the PROVIDERS.md rows and the changelog follow the stub rename in the same change (SDD §14 row "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`")
- [ ] An installed stub keeps its old name until setup copies it again, and no gate reads the name field; rollback is reverting the commit or installing the previous plugin version, then running setup again (SDD §14 row "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`")
- [ ] Codex finds an agent by its file's name field, not its filename; after the rename a skill's spawn of `afk-reader` no longer fails as an unknown agent type, and a live spawn on Codex confirms it (SDD §9b row "Codex agent lookup")
- [ ] Conforms to ADR-0015 — a change that only adds keeps the existing contract, with its older-reader posture and rollback stated; no silent pattern substitution (ADR-0015)
- [ ] Every artifact in ## Produces exists with its declared contract (SDD §8 row "Model equivalence")

## Produces
- PROVIDERS.md#equivalent model from another provider — the C12 equivalence rule sentence
- providers/codex/agents/afk-afk-reader.toml#name = "afk-reader" — the C18 stub name field, the skill name

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `grep -n 'equivalent model from another provider' PROVIDERS.md`; `grep -n 'name = "afk-reader"' providers/codex/agents/afk-afk-reader.toml`; `grep -c '^name = "afk-afk-' providers/codex/agents/*.toml` prints 0 for each | Produces anchors present; every stub carries the skill name |
| unit | `python -m pytest scripts/tests/test_model_tier_gate.py scripts/tests/test_native_contract_events.py -q` | check L still parses the tier table with 0 problems; seam-test for the row "`Model tiers` table in PROVIDERS.md" |
| integration | Environment-gated on Codex CLI: a live Codex spawn of an AFK agent by its skill name, as in `afk-reader`, succeeds; recorded in the conformance proof row | the stub name field (S-127); seam-test for the row "Codex agent lookup" |

## Context excerpts
> (SDD §8 row "Model equivalence") | Model equivalence | Same tier row, another harness column (C12) | read of the tier map | tier map document | — |

> (SDD §14 row "`Model tiers` table in PROVIDERS.md", Existing contract) One home, parsed by native check L, which refuses an agent file or Codex stub whose model or effort differs from its tier's cell, and exits 2 on a difference (hooks/native-contract-gate.sh:218-266, :525-527); it reads the section to the next ## heading, a tier row is a 4-cell line with cells 2-4 backticked, an agent row a 2-cell line with a backticked first cell (:221, :227-233); it runs at Stop and pre-commit (stop-gates.sh:156; precommit-gates.sh:146-148); in-harness fallback at PROVIDERS.md:105, a second in-harness rule at :126, restated at CAPABILITIES.md:16; a cell holds an alias or an exact model id (PROVIDERS.md:107-122); every other reader is prose (DELEGATION.md:43-48; autopilot/SKILL.md:35; FRESHNESS.md:70; AGENTS.md:22) (INV-056)

> (SDD §14 row "`Model tiers` table in PROVIDERS.md", Planned change) C12: one equivalence rule sentence keyed on the tier row, ordered against the in-harness fallback, written as prose outside the two tables check L parses (PROVIDERS.md:107-120), in the one-line fallback paragraph at PROVIDERS.md:105, so no later line moves and no cite of PROVIDERS.md goes stale (inferred, INV-056); it holds no column bar and does not open with a ## heading (native-contract-gate.sh:221, :227-232)

> (SDD §14 row "`Model tiers` table in PROVIDERS.md", Impacted flows) Every single-model failover. Unchanged: check L and its result, since a prose sentence with no column bar gives the same 0 problems as today (probe in INV-056); scripts/behavior_registry.py:515-522, which reads only PROVIDERS.md's Construct mapping row; pinned by scripts/tests/test_model_tier_gate.py:58 and test_native_contract_events.py:57; the fallback lines and doc pointers are unguarded (INV-056)

> (SDD §14 row "`Model tiers` table in PROVIDERS.md", Conventions / landmines) Native check A excludes PROVIDERS.md (native-contract-gate.sh:88); a sentence in table shape fails check L, a 4-cell backticked line silently replaces a tier's cells, and a new ## heading between the two tables drops the agent table (INV-056). The genericity gate refuses an INV-NNN or a model-name token in the sentence (hooks/lib/sensitive-patterns.tsv:8-9). Compatibility: only adds (S-246). Rollback: revert the commit, or install the previous plugin version (S-246)

> (SDD §14 row "Codex agent stubs' name field, the type a `DELEGATION` spawn names as `afk-reader`") C18: each stub's name field becomes the skill name; filenames stay `afk-afk-*.toml`; the conformance proof row, PROVIDERS.md rows and the changelog follow (S-123, S-127) … An installed stub keeps its old name until setup copies it again; no gate reads the name field. Compatibility: each Codex agent file names its agent by the skill name (S-246). Rollback: revert the commit or install the previous plugin version, then run setup again so the old names come back (S-246)

> (SDD §9b row "Codex agent lookup") | Codex agent lookup | Codex CLI 0.157.0, observed once (trials T5, T6) | Finds an agent by its file's name field, not its filename; `afk-reader` is refused while the stub's name field reads `afk-afk-reader` (INV-013) | A skill's spawn of `afk-reader` fails as an unknown agent type | C18: set the name field; a live spawn on Codex confirms (S-127) |

> (PRD AC-002) **AC-002** Team topology and multi-model are independently switchable; all four combinations run.

> (PRD AC-020) **AC-020** No availability or quota check runs before or during a run. A provider failure is detected when a call fails, never predicted.

> (PRD AC-022) **AC-022** On a provider failure, a single-model role continues on an equivalent model from another provider, where the tier map supplies one. A debate role does not substitute; it waits.

> (PRD AC-023) **AC-023** Beyond the provider's wait horizon the run parks and writes a dated report naming the provider, the role and the time it parked. It does not continue in a reduced shape.

> (ADR-0015) A change takes extends when every existing caller keeps the contract it has today and the change only adds: a key, a row, a field, a line, a step or a count (S-199). Its §14 row states what an older reader and a session with no team see, and how the change rolls back: revert the commit or install the previous plugin version, after the first step S-246 names for a change that needs one (S-246). The 13 rows cite this record as extends (design ADR-0015). Three later rows cite it too: the row of audit round 14 and the rows for the SessionStart hook and the built-in pattern records (charter C3 and C6); all three are agent-decided. The agent decided this under the human's delegation of 2026-09-30 (`GRILL-LOG.md` row "Agent-decided, 2026-10-05", design-audit open points, L31).

## Parent PRD
docs/afk/agent-team-topology/PRD.md

## Parent SDD
docs/afk/agent-team-topology/SDD.md

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

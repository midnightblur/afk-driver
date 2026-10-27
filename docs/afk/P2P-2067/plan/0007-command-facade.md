## Goal
Create the versioned JSON command facade and connect the existing requirements, glossary, design, execution, review, preflight, and settlement skills to it without transferring commit, push, merge, or CI ownership.

## Complexity
complex

## Review
policy: full

## Design refs
- SDD: SDD.md#8-l7--module-decomposition — one facade builds a command-scoped object graph
- ADR: adr/design/0004-reconcile-before-proof.md — preflight and settlement consume fresh proof
- ADR: adr/design/0006-strict-solo-owner-decision-control.md — strict human choice is part of the bound evidence

## Scope
- scripts/glossary_lifecycle/cli.py
- scripts/glossary_lifecycle/tests/test_cli.py
- skills/afk/grill-requirements/**
- skills/utils/glossary/**
- skills/afk/to-prd/**
- skills/afk/execute/**
- skills/afk/preflight/**
- skills/utils/settle-change/**
- skills/afk/setup/**
- scripts/lavish/**
- scripts/tests/test_lavish_render.py
- CHANGELOG.md

## Seams
- implement: SDD §14 row "Requirements and glossary skills" — call the facade while callers retain commit ownership (INV-012)
- implement: SDD §14 row "Preflight" — reconcile before proof and gate immediately before Ready (INV-012)
- implement: SDD §14 row "Settlement" — gate the final pushed head and return rejected changes to Draft (INV-012)
- implement: SDD §14 row "Other glossary consumers" — route lifecycle reads through the facade and selected paths (INV-012)
- implement: SDD §14 row "RE-07 prompt" — accept exactly final or reject with no notes or fallback (INV-012)
- implement: SDD §14 row "Packaging" — add shared scripts and update existing skill prose without a new skill (INV-012)
- use: SDD §14 row "AFK configuration" — create adapters from the repository manifest pointer (INV-012)
- use: SDD §14 row "Forge registry" — select a provider-independent forge kind (INV-012)
- use: SDD §14 row "Return to Draft" — invoke the verified inverse state operation (INV-012)
- use: SDD §14 row "Bootstrap and adoption" — refuse normal work until the prerequisite reaches target (INV-012)

## Acceptance
- [ ] `execute(request) -> result` accepts and emits versioned JSON and constructs no global singleton. (SDD §8)
- [ ] Requirements define provisional terms, consultation precedes the next phase, and implementation triggers reconciliation. (PRD §User Stories)
- [ ] Preflight gates immediately before Ready; settlement gates the final pushed head and preserves review closure. (SDD §14 row "Preflight")
- [ ] Strict solo-owner prompting is human-present only, accepts exactly `final` or `reject`, and parks in driven or Markdown-only modes. (PRD §Acceptance Criteria)
- [ ] No CI configuration, merge behavior, or caller commit ownership changes. (ADR-0001)
- [ ] Implements the public interface in SDD §8 row "Command facade" unmodified. (SDD §8)
- [ ] Seam tests assert serialized facade results, rendered choice controls, and observable skill refusal/advance states. (SDD §14 row "RE-07 prompt")

## Produces
- scripts/glossary_lifecycle/cli.py#class GlossaryCommandFacade — versioned execute request/result composition root
- skills/afk/grill-requirements/SKILL.md#Glossary lifecycle gate — requirements-stage caller contract
- skills/afk/preflight/SKILL.md#Glossary reconciliation gate — Ready transition caller contract

## Consumes
- 0002-repository-access scripts/glossary_lifecycle/repository.py#class PinnedRepositoryAdapter — repository adapter factory input
- 0004-forge-anti-corruption-adapter scripts/glossary_lifecycle/forge.py#class GlossaryForgeAdapter — forge adapter factory input
- 0006-application-use-cases scripts/glossary_lifecycle/application.py#class GlossaryLifecycleApplication — lifecycle handlers

## Verification
| Tier | Check (command or method) | Proves |
|---|---|---|
| static | `afk-python -m py_compile scripts/glossary_lifecycle/cli.py` plus native-contract and Produces-anchor gates | facade and skill contracts are discoverable |
| unit | `afk-python -m pytest scripts/glossary_lifecycle/tests/test_cli.py scripts/tests/test_lavish_render.py` | JSON protocol, object graph, and strict choice |
| integration | workflow fixtures plus the Lavish strict-choice render and live-response test for `final`, `reject`, write-in, fallback, and driven modes | every caller advances or refuses at the required phase; only a bound human `final` or `reject` response is valid |

## Context excerpts
> (PRD §Solution) "AFK adds a repository-independent glossary lifecycle. It selects relevant definitions before work, audits changed vocabulary, and reconciles definitions after implementation."
>
> (SDD §8 row "Command facade") "Parse versioned request and serialize typed result | execute(request) -> result | Application use cases and adapter factory | None"
>
> (ADR-0006) "Use a strict human-present choice control for RE-07 with exactly `final` and `reject`."

## Parent PRD
../PRD.md

## Parent SDD
../SDD.md

## Blocked by
0002-repository-access, 0004-forge-anti-corruption-adapter, 0006-application-use-cases

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality during implementation, classify per the decision protocol (`DECISIONS.md`, workflow plugin root): a two-way-door correction is recorded in `plan/DECISIONS.md` and implemented; a one-way door or a tie exits `design_conflict` quoting the SDD section + the conflict. Never override off the record. Parked conflicts route back to `/afk:grill-solution` for a superseding ADR.

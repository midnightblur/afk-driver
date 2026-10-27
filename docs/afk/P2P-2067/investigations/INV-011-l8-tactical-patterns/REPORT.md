# INV-011 — L8 tactical patterns

Verdict: closed-with-frontier.

## Closed premises

- Selection has fixed precedence: routes and exact matches are deterministic and untruncated; semantic search is a bounded fallback (`PRD.md:53-59`, requirements ADR-0006).
- RE-03 and RE-04 use different canonical inputs and explicit semantic-change rules (`PRD.md:34-40,62-64`).
- The closest ledger uses pure canonicalization and digest functions, explicit transition tables, an ordered replay reducer, stable operation identifiers, and one injected adapter. It does not use polymorphic State objects or reflective discovery (`skills/afk/review/scripts/forge_ledger.py:55-83,172-308,505-552,691-787,829-893,1021-1105`).
- Existing strict schemas reject unknown keys before normalization. Existing registries are closed data maps with duplicate and shape checks (`scripts/lavish/schema.py:22-97,476-553`, `scripts/behavior_registry.py:102-160`).
- Shared commands use fixed command dispatch at one composition point. The closest command boundary distinguishes success, expected refusal, and invalid or unexpected failure, although its JSON envelopes are not fully consistent (`scripts/afk-config.py:1210-1338`, `skills/afk/review/scripts/forge_ledger.py:2391-2454`).
- Gate callers treat one ledger command as the rule owner instead of copying gate logic into skill prose (`skills/utils/settle-change/SKILL.md:34,98`).

## Counter-search

- Searched named patterns and structural forms: Strategy, Specification, Registry, Factory, Visitor, Builder, command maps, handler collections, transition tables, canonical projectors, and runtime discovery.
- No general pattern framework exists in the applicable plugin code. The reusable precedent is explicit tables, pure functions, static maps, stable values, and injected boundary adapters.
- B1-B5, B7-B8, and B12-B13 are closed. B6 and B9-B11 are not applicable.

## Frontier

- B14: the concrete semantic candidate implementation and live behavior of the two new forge verbs do not exist. Their Strategy and Adapter contracts can be fixed now, but implementation and bounded live tests must prove them before shipment.

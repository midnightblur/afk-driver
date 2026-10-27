midnightblur/afk-driver@a140274a785ff080d2ad24224766c532939ed687 · closed-with-frontier · boundaries 13/14 · unverified 1 (load-bearing 0) · ledger: docs/afk/P2P-2067/investigations/INV-013-current-plugin-ground/COVERAGE.json

## Answer

The plugin already has glossary format, discovery, and Lavish tooltip consumers. The new lifecycle must preserve these paths while it adds stable identity metadata, deterministic routing, and append-only record replay.

## Facts

- `scripts/lavish/inject.py:84-114` parses glossary metadata and currently removes only `Avoid`, `Code`, and `Related` fields.
- `scripts/lavish/inject.py:588-613` discovers service glossaries and publishes parsed terms to the Lavish tooltip dictionary.
- `scripts/tests/test_lavish_inject.py:105-118` pins the tooltip dictionary output.
- `skills/utils/glossary/GLOSSARY-FORMAT.md:34-35` defines the current metadata grammar.
- `skills/utils/glossary/GLOSSARY-FORMAT.md:61-73` defines current glossary placement and discovery.
- `skills/afk/grill-requirements/SKILL.md:16` consumes the glossary workflow during requirements work.

## Inferences

- Inference: stable `ID` and `Replaces` fields require coordinated parser, format, and tooltip changes because the current metadata filter does not know them.
- Inference: the new domain package can be added without replacing existing consumers in subtask 0001; later integration subtasks must migrate those consumers together.

## Unverified

- None inside the repository boundary.

## Frontier

- External repositories, deployment manifests, and live consumers remain outside this repository check.

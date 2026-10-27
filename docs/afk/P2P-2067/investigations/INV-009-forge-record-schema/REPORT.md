nakisainc/core/core-services@82c3db898ad82c86186989c1166547f05e060fb7 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-009-forge-record-schema/COVERAGE.json

## Answer
The forge change stores records as immutable HTML markers in comments and thread replies. Version 1 is the only accepted format.

The parser requires exact fields for each marker and record kind. It rejects unknown versions, kinds, fields, transitions, sequence gaps, and operation IDs. History objects also require an exact field set.

The only old-format adapter handles the legacy summary marker. No general record migration exists. Inference: a format change must keep the old parser. Readers must deploy before writers if different plugin versions can use one change.

Reconstruction reads every trusted, unedited marker. It groups records by key, validates the sequence, applies transitions, and derives current state from surviving records.

The ledger has no retention, pruning, compaction, or delete command. Forge comments remain for the change lifespan.

A missing middle record causes a sequence error. A missing newest record silently restores the prior state. A missing middle summary is not detected. A missing newest summary silently restores the prior round.

Nine focused compatibility and reconstruction tests passed.

## Sites
- `skills/afk/review/scripts/forge_ledger.py:184` — emits version 1 records.
- `skills/afk/review/scripts/forge_ledger.py:204` — parses marker versions and values.
- `skills/afk/review/scripts/forge_ledger.py:240` — enforces exact fields.
- `skills/afk/review/scripts/forge_ledger.py:268` — owns record-kind schemas.
- `skills/afk/review/scripts/forge_ledger.py:655` — owns the exact history schema.
- `skills/afk/review/scripts/forge_ledger.py:829` — reconstructs forge state.
- `skills/afk/review/scripts/forge_ledger.py:870` — validates record sequences and operation IDs.
- `skills/afk/review/scripts/forge_ledger.py:968` — folds summary history.
- `skills/afk/review/SETTLEMENT.md:145` — defines immutable summaries and legacy support.
- `FRESHNESS.md:52` — defines the same-commit compatibility set.
- `scripts/tests/test_forge_ledger.py:315` — tests malformed versions, sequences, IDs, and transitions.

## Unverified
- None.

## Frontier
- Live forge records and provider behavior were not queried.

nakisainc/core/core-services@ad1bb118e84c5158902a8100674e40829d8caca9 · closed-with-frontier · boundaries 13/14 · unverified 0 (load-bearing 0) · ledger: 11700-payable/specs/2026r2/P2P-2067/investigations/INV-006-forge-anchor-capability/COVERAGE.json

## Answer

No. Both adapters expose description reads and full-description writes, but neither exposes enough edit metadata for a safe glossary-record high-water anchor.

## Facts

- `change-fetch` writes the raw forge response to `mr.json`; GitHub explicitly requests `body`. (`adapters/forge/github/forge.sh:335`, `adapters/forge/gitlab/forge.sh:324`)
- The normalized change object omits `body` and `description`. (`ADAPTERS.md:68`, `adapters/forge/github/forge.sh:272`, `adapters/forge/gitlab/forge.sh:174`)
- `change-update-body` replaces the full description on both forges. (`adapters/forge/github/forge.sh:433`, `adapters/forge/gitlab/forge.sh:440`)
- The write answers contain no description revision, edit timestamp, or editor identity. (`adapters/forge/github/forge.sh:438`, `adapters/forge/gitlab/forge.sh:457`)
- Note-level `author` and `edited` fields apply to notes, not the change description. (`ADAPTERS.md:103`, `ADAPTERS.md:110`)
- The adapter test suite passed: `afk-python -m pytest scripts/tests/test_forge_adapters.py -q` returned 113 passed.

## Inferences

- Inference: a read-modify-write can overwrite an intervening human edit because the contract has no compare-and-set token.
- Inference: add a normalized description plus a description revision or equivalent conflict check before using it as the anchor.

## Sites

- `adapters/forge/github/forge.sh:330`
- `adapters/forge/github/forge.sh:431`
- `adapters/forge/gitlab/forge.sh:308`
- `adapters/forge/gitlab/forge.sh:428`
- `scripts/tests/test_forge_adapters.py:210`
- `skills/afk/execute/SKILL.md:63`
- `skills/afk/preflight/SKILL.md:179`

## Frontier

- B14: other repositories, deployment manifests, and live forge consumers were not crossed.

## Unverified

- None inside the pinned repository snapshot.

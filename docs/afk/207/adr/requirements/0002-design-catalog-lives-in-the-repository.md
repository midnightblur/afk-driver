# The design catalog lives in the repository

> Layer: Requirements
> Context ticket: 207

The design catalog is committed in the consuming repository, one per frontend, and neither skill sends anything to claude.ai/design. v1 kept the catalog in claude.ai/design. A catalog in the repository is versioned and works on Claude and Codex; afkv2 does not set up the claude.ai/design tools.

## Considered Options

- claude.ai/design only, as v1. Rejected by the developer in card i-ds-home, because afkv2 does not set up its tools.
- Both, kept in sync. Rejected by the developer in card i-ds-home, because the 2 records drift.
- An opt-in push from design-system to claude.ai/design. Rejected by the developer in card i-claude-design, to match the dropped share push (card i-share).

# ADR-0005 — Managed behavior uses user instruction sentinels

> Status: Accepted
> Date: 2026-09-28

## Context

Team behavior must reach both supported harnesses. The plugin cannot edit a
consuming repository's instruction files. No native pre-model transport has a
proven receipt across fresh, resumed, cleared, compacted, custom-agent, and
subagent sessions.

## Decision

`BEHAVIORS.md` is the registry and body source. Setup generates one managed
`afk:behaviors` block in each user instruction file. The block records the
registry revision and exact body hash. Setup substitutes the active plugin root
for `${AFK_PLUGIN_ROOT}`.

The block has 2 parts. The first applies in all repositories. The second tells
the model to apply its rows only when `.afk/config.yaml` exists. This repository
guard is model-evaluated. It is not a deterministic security boundary.

Setup reuses consent from any legacy H7, H8, or H10 block. A first install
without that proof requires consent. Teardown removes every managed block.

## Consequences

- Both harnesses receive one generated block from one registry.
- A SessionStart hook can detect drift from the revision and hash.
- Setup can migrate and remove blocks without changing repository files.
- Repository scope depends on model compliance until receipt probes prove a
  stronger native transport.
- The generated block for each harness is capped at 6,000 UTF-8 bytes,
  binding; the gate fails above the cap and never truncates. ~1,500 tokens is
  a rough estimate for this prose at that byte cap, never a guarantee — no
  tokenizer is named, so bytes are the only unit the gate can prove.

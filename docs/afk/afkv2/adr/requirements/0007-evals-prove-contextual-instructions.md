# Evals prove contextual instructions, not AFK skills

> Layer: Requirements
> Context ticket: GitHub #153

The eval harness proves that contextual instructions change agent behaviour: the core behaviors, and a repository's root and nested AGENTS.md files. Each case runs with and without the instruction, on Claude and on Codex. AFK's own skills get no evals for now. The harness belongs to the contextual-instruction writing capability, which runs in the sync-harness subtask, so both arrive in P1. Why: owner rulings S-6, E-1 and E-3 in GRILL-LOG.

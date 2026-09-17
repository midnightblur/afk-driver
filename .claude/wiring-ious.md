# Wiring IOUs

One line per artifact whose consumer does not exist yet, in the grammar
`hooks/wiring-gate.sh` parses. The gate closes a line when a referrer appears.

- [x] `docs/afk/agent-team-topology/research/PROBE-codex.ps1` -> anchor: contract "`docs/afk/agent-team-topology/research/BRIEF.md` Deliverables §1 `FACTS-codex.md` evidence column will cite `PROBE-codex.ps1` as the command behind each provider-probe fact"
- [x] `docs/afk/agent-team-topology/research/EVIDENCE-codex-providers.md` -> anchor: contract "`docs/afk/agent-team-topology/research/BRIEF.md` Deliverables §1 `FACTS-codex.md` evidence column will cite `EVIDENCE-codex-providers.md` for provider-availability facts"
- [x] `docs/afk/agent-team-topology/research/EVIDENCE-codex-flag-error.json` -> anchor: contract "`docs/afk/agent-team-topology/research/BRIEF.md` Deliverables §1 `FACTS-codex.md` evidence column will cite `EVIDENCE-codex-flag-error.json` for the Codex flag-error fact"
- [x] `docs/afk/agent-team-topology/research/EVIDENCE-codex-mcp.json` -> anchor: contract "`docs/afk/agent-team-topology/research/BRIEF.md` Deliverables §1 `FACTS-codex.md` evidence column will cite `EVIDENCE-codex-mcp.json` for the onedevtool MCP facts"
- [x] `docs/afk/agent-team-topology/research/RESPONSE-claude.md` -> anchor: contract "`docs/afk/agent-team-topology/research/CONVERGE.md` Step 2: `debater-astra` reads `RESPONSE-claude.md`, and Rules: `debater-fable` cites it in `VERDICT-claude.md`"
- [x] `docs/afk/agent-team-topology/research/RESPONSE-codex.md` -> anchor: contract "`docs/afk/agent-team-topology/research/CONVERGE.md` Step 2: `debater-fable` reads `RESPONSE-codex.md`, and Rules: `debater-astra` cites it in `VERDICT-codex.md`"
- [x] `docs/afk/agent-team-topology/research/VERDICT-claude.md` -> anchor: contract "`docs/afk/agent-team-topology/GRILL-LOG.md` Requirements grill Open row: the contact agent carries the DISAGREE-FINAL rows of `VERDICT-claude.md` into grill round 2 and cites the file there"
- [x] `docs/afk/agent-team-topology/research/VERDICT-codex.md` -> anchor: contract "`docs/afk/agent-team-topology/GRILL-LOG.md` Requirements grill Open row: the contact agent carries the DISAGREE-FINAL rows of `VERDICT-codex.md` into grill round 2 and cites the file there"
- [x] `skills/utils/investigate/scripts/merge_fragments.py` -> anchor: contract "`skills/utils/investigate/SKILL.md` step 5 will call `merge_fragments.py` to fold tracer fragments into the staging ledger by the rules in `skills/utils/investigate/LEDGER-FORMAT.md` § Merging, which step performs in prose today"
- [x] `docs/afk/agent-team-topology/research/PROPOSAL-claude.md` -> anchor: contract "`docs/afk/agent-team-topology/research/BRIEF.md` Deliverables §2: the contact agent (herdr pane `w5:p1`) reads `PROPOSAL-claude.md` in the cross-critique round against `PROPOSAL-codex.md`, then `/afk:grill-requirements` consumes the merged proposal"
- [x] `docs/afk/agent-team-topology/research/CRITIQUE-claude.md` -> anchor: contract "round-2 cross-critique: the contact agent (herdr pane `w5:p1`) reads `CRITIQUE-claude.md` with `CRITIQUE-codex.md` to settle the shared design before `/afk:grill-requirements`"

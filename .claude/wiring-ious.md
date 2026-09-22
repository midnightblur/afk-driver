# Wiring IOUs

One line per artifact whose consumer does not exist yet, in the grammar
`hooks/wiring-gate.sh` parses. The gate closes a line when a referrer appears.

- [x] `skills/utils/investigate/scripts/merge_fragments.py` -> anchor: contract "`skills/utils/investigate/SKILL.md` step 5 will call `merge_fragments.py` to fold tracer fragments into the staging ledger by the rules in `skills/utils/investigate/LEDGER-FORMAT.md` § Merging, which step performs in prose today"
- [x] `skills/afk/AGENTS.md` -> anchor: plan "core-services/docs/plans/2026-09-agents-md-standard.md" P5 "New row: JSON merge of `instructionFiles` into `~/.claude/settings.json`" — with the root `CLAUDE.md` bridge present, a Claude session loads this nested `AGENTS.md` only once `pluginConfigs."agents-md@builtin".options.instructionFiles = claude-md-and-agents-md` is set; P3 (`nested_steering` injector) covers the harness that loads nested files only at start — closed by setup row H11

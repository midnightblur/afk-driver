## Mission control, preflight, render points

`mission-control/` (read-only feature dashboard; extend a panel via `scripts/mc/panels/`, wired in `scripts/mission_control.py`) and `preflight/` (ship-gate ladder; extend by adding a step to its SKILL.md table, inside the shared fix-cap) are self-contained skill dirs — invocation in each one's own SKILL.md. Render points (human-present lavish-axi visualization woven into individual skill files) are governed entirely by `../../LAVISH.md` (pin, playbook map, fallback, forbid-list) — edit a skill's render point there, not here. Full design: `tools/payable/ai-agents/spec/mission-control/`.

## Bug pipeline

`bug/` is self-contained — extend a subcommand in its `SKILL.md` (frozen subcommand set lives there), add/rename a Catalog-A lifecycle state in its `LEDGER-FORMAT.md` (one home for both, keep in lockstep), extend a subagent contract in `FIXER-PROMPT.md`/`RETEST-PROMPT.md` rather than inline in `SKILL.md`. Full design: `tasks/afk-bug/` (PRD.md, SDD.md, ADRs).

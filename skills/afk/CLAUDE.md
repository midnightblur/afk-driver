## Mission control, preflight, render points

`mission-control/` (read-only feature dashboard; extend a panel via `scripts/mc/panels/`, wired in `scripts/mission_control.py`) and `preflight/` (ship-gate ladder; extend by adding a step to its SKILL.md table, inside the shared fix-cap) are self-contained skill dirs — invocation in each one's own SKILL.md. Render points (human-present lavish-axi visualization woven into individual skill files) are governed entirely by `../../LAVISH.md` (pin, playbook map, fallback, forbid-list) — edit a skill's render point there, not here. Full design: `tools/payable/ai-agents/spec/mission-control/`.

## Bug pipeline

`bug/` is self-contained — extend a subcommand in its `SKILL.md` (frozen subcommand set lives there), add/rename a Catalog-A lifecycle state in its `LEDGER-FORMAT.md` (one home for both, keep in lockstep), extend a subagent contract in `FIXER-PROMPT.md`/`RETEST-PROMPT.md` rather than inline in `SKILL.md`. Full design: `tasks/afk-bug/` (PRD.md, SDD.md, ADRs).

## Lesson ledger

`lessons/` is self-contained — the ledger grammar, class enum, status model, and escalation ladder live in `LEDGER-FORMAT.md` (one home); the capture protocol detection points follow lives in `CAPTURE.md`; the ledger's sole emitting/parsing sites are `../../hooks/lesson-append.sh` / `lesson-digest.sh` (lockstep with the grammar). Extend a class or status in `LEDGER-FORMAT.md` + both scripts in the same commit; extend the capture rule in `CAPTURE.md`, never inline in a detection point's SKILL.md.

## Understanding artifact

`understand/` is self-contained — the one-home format contract (Catalog-A section model, trivial-file + notable-deviation predicates, quiz/anti-slop self-eval, and the `afk-understanding` meta-header grammar the dashboard parses) lives in `UNDERSTANDING-FORMAT.md`, and the checked-in `shell-template.html` owns all offline chrome (tour, quiz engine, injection slots); extend a section shape or self-eval rule in the format contract, chrome in the template, never inline in `SKILL.md`. The mission-control Understanding panel (`mission-control/scripts/mc/panels/`) reads only that meta header, so a grammar change is a same-commit edit to the panel + its A-suite. Full design: `tasks/afk-understand/` (PRD.md, SDD.md, ADRs).

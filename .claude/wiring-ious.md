# Wiring IOUs

One line per artifact whose consumer does not exist yet, in the grammar
`hooks/wiring-gate.sh` parses. The gate closes a line when a referrer appears.

- [x] `skills/utils/investigate/scripts/merge_fragments.py` -> anchor: contract "`skills/utils/investigate/SKILL.md` step 5 will call `merge_fragments.py` to fold tracer fragments into the staging ledger by the rules in `skills/utils/investigate/LEDGER-FORMAT.md` § Merging, which step performs in prose today"
- [ ] `docs/afk/research-enhancement/plan/` -> anchor: contract "`/afk:autopilot` walks `plan/PLAN.md` and `/afk:execute` Step 1 parses each `plan/NNNN-slug.md` contract per `skills/afk/execute/SKILL.md`; execution is a later stage the orchestrator starts"

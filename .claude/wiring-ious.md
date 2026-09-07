# Wiring IOUs

An artifact whose consumer does not exist yet, anchored to the contract that
names it. One row per IOU; delete the row when the consumer lands.

| Artifact | Consumer owed | Anchor |
|---|---|---|
| `skills/utils/investigate/scripts/merge_fragments.py` | `/afk:investigate` step 5, which folds tracer fragments into the staging ledger by the merge keys in `skills/utils/investigate/LEDGER-FORMAT.md` § "Merging" | `skills/utils/investigate/SKILL.md` step 5 — the step performs the merge in prose today; the script replaces the prose, and the merge rules it implements are already fixed by LEDGER-FORMAT.md |

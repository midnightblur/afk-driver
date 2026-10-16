# In driven mode afk-lite does not stop after its design step

> Status: Decided by agent
> Audited: not yet
> Layer: Requirements
> Context ticket: agent-team-topology

In an interactive run afk-lite stops for the human after its design step (AC-037), as the human settled in the requirements grill (PT-Q3, round 13). In driven mode no human is present, so afk-lite classifies its design per the decision protocol (`DECISIONS.md`, plugin root) and does not stop. A two-way door is recorded in the decision ledger and the run continues. A one-way door or a DISAGREE-FINAL point ends `/afk:fix` with `needs_decision`, carrying the design; the caller passes it up unchanged, and `/afk:autopilot` parks the subtask. A stop after every design step would park every driven `/afk:fix` call. The agent took this call under the human's delegation of 2026-09-30 (grill log row "Agent-decided, 2026-10-05", Q34). This record narrows PT-Q3 to interactive runs.

## Considered Options

- Keep the stop in every run and route `blocked` to a park at all five call sites of `/afk:fix`. Rejected: every driven `/afk:fix` call reaches the stop, so every one would park.

## Consequences

- `/afk:fix` gains `needs_decision`, a status its set does not hold today. It returns that status only in driven mode.
- The `/afk:bug` fixer keeps its own stop in every run: blocked, notify, resume (solution grill S-164).
- This changes existing behaviour (human-locked aspect HL-6). The delegation of 2026-09-30 covers it until a human audits this record.

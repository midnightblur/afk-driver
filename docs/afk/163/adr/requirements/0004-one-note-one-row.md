# Each note is its own note and its own row, even when answers repeat

> Status: Decided by agent
> Audited: not yet
> Layer: Requirements
> Context ticket: #163

The ticket asked for one row per note or per group of equal notes. The owner's round 0 note overrides it: "each note should be on its own, and if the response is the same for them, so be it". Each note the human sends gets its own id and row, also when several sit on one element, and a shared answer repeats in each row. Today the engine joins every note on one element into one note per round, so this needs the new page format version.

## Considered Options

- One row per group of equal notes, as the ticket said. Rejected by the agent, with the owner's accept, in i-own-row, because the owner's round 0 note replaces it.
- One row per note with a "same as row N" pointer. Rejected by the agent, with the owner's accept, in i-own-row, because it hides the answer behind a jump.
- One note per element per round, as today. Rejected by the agent, with the owner's accept, in i-r7-note-rows, after the owner's round 6 steer: several notes shared one row.

# The latest instruction always wins

> Layer: Requirements
> Context ticket: 211

On receipt of a milestone note, the main agent follows the new text at once, also inside a skill run that has already started, and redoes the delta of work it did under the old text, with no question to the developer. It tells the developer what it redid. The developer: "then do the delta between old and new instructions (aka always do the latest instruction)".

## Considered Options

- Finish the current step on the old text and switch at the next step. Rejected by the developer in i-dv-step: "main agent should apply immediately when it receives the new instruction".
- Apply only to later work, and ask before any redo. Rejected by the developer in i-dv-done2.

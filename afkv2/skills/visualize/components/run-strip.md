# Simulated-run strip

## Holds

The steps of one run in time order: the run as it is today, the run as
proposed, or both. Type `run-strip`. Props: `current` and `proposed`, each a
list of steps; give at least one. A step has `label`, an optional `detail` and
an optional `tone` (`kept`, `removed`, `new` or `proposed`).

## Use it when

The point changes what happens during a run: a step added, removed or moved, a
gate in a new place. Show the current lane and the proposed lane together so the
human sees the difference.

## How it looks

One horizontal lane per list, steps left to right. A step with a tone has that
tone's look: removed steps struck through, new steps in a blue chip, proposed
steps dashed.

## Example

```json fragment=component
{
  "type": "run-strip",
  "id": "r-export-run",
  "props": {
    "current": [
      {"label": "read orders"},
      {"label": "write file"},
      {"label": "email file", "tone": "removed"}
    ],
    "proposed": [
      {"label": "read orders", "tone": "kept"},
      {"label": "write file", "tone": "kept"},
      {"label": "store file", "detail": "link valid 7 days", "tone": "new"}
    ]
  }
}
```

# Card

## Holds

One point the human reads or answers. A card is an item in `rounds[].items[]`:
`id`, `kind`, `node` (the map node it belongs to), `state`, `body` (one
component tree) and, once settled, `settled`. Kinds:

| Kind | The card | The human |
|------|----------|-----------|
| `decided` | states a call you took, with its evidence | accepts it or reopens it |
| `confirm` | states a reading you need confirmed | accepts it or corrects it |
| `debate` | shows a fork: the options side by side and your recommendation | picks an option or writes one in |
| `signoff` | states an aspect only a human may approve, with the exact wording | signs it or asks for changes |
| `info` | shows context; it asks nothing | may note it |

`state` is a point state: `open`, `blocked`, `needs_reading`,
`settled_by_mark`, `settled_by_note`. A new card is `open`. A card that waits on
another open point is `blocked`, and its body names the card it waits on.

## Use it when

One card per map node or per question. Set `node` when the card belongs to a
map node. A card stays in its round when the round settles.

When the human sends a round, the engine settles each point with one mark and
moves each point with a note to `needs_reading`. Go through that round's cards
before you mark the round `settled`:

- `needs_reading` with a clear note: set `state` to `settled_by_note` and write
  `settled`, for example `{"by": "note", "round": 2, "signal": "N-2-i-format", "reading": "Picks CSV."}`.
  The `signal` is the note id.
- `needs_reading` with an unclear note or signals in conflict: set `state` to `open`.
- `blocked` with the point it waits on now settled: set `state` to `open`.

Then mark the round `settled` and append the next round. Each point that is still
`open` or `blocked` gets a new card there, with a new id, and its body names the
old card id. The old card stays as it is.

## How it looks

A box in the cards section, below the maps, with the controls of its kind. A
round chip in the round colour marks every card that needs the human in that
round. A note-settled card shows "settled by note", which differs from "settled
by mark". For a `debate` card, put the options in a `table`, one column per
option, each option cell with the id `<item id>-opt-<letter>`.

## Example

```json fragment=item
{
  "id": "i-format",
  "kind": "debate",
  "node": "n-format",
  "state": "open",
  "body": {
    "type": "text",
    "props": {"text": "Which file format does the export write? Recommended: A."},
    "children": [
      {"type": "table", "id": "i-format-options", "props": {
        "columns": ["A — CSV", "B — JSON lines"],
        "rows": [[
          {"type": "text", "id": "i-format-opt-a", "props": {"text": "Opens in a spreadsheet; flat rows only."}},
          {"type": "text", "id": "i-format-opt-b", "props": {"text": "Keeps nested fields; needs a reader tool."}}
        ]]
      }}
    ]
  }
}
```

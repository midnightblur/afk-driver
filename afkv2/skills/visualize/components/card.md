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

When the human sends a round, the engine settles a point with one `accept`,
`sign` or option mark. It moves a point to `needs_reading` on `reopen`,
`changes`, a write-in, a note, a mark plus a note, or 2 marks. Before you mark
the round `settled`, go through the cards of the current round. Never change a
card in a settled round. A note whose `target` is a map node id is a steer: leave
it out when you read the signals, because it settles nothing.

- `needs_reading` with a clear note and no signal that disagrees with it: set
  `state` to `settled_by_note` and write `settled`, for example `{"by": "note", "round": 2, "signal": "N-2-i-format", "reading": "Picks CSV."}`.
  The `signal` is the note id. A note that leaves the answer open is not a clear
  note. A note that changes the wording of a `signoff` card is not a clear note: the
  new card asks the human to sign the new wording. A note on an `info` card is not a
  clear note: it answers nothing, so it gets a reply only. A `reopen` or `changes`
  mark always disagrees.
- `needs_reading` in any other case: set `state` to `open`. A write-in has no note
  id, so it cannot settle by note: the new card for that point is a `confirm` card
  that states the write-in as your reading.
- `blocked` with the point it waits on now settled: set `state` to `open`.

Then mark the round `settled` and append the next round. Make one new card for
each point that returns:

- a `decided`, `confirm`, `debate` or `signoff` card of the round you settled that
  is still `open` or `blocked`;
- a `decided`, `confirm`, `debate` or `signoff` card of an earlier round that the
  human noted or reopened in this send.

The new card has a new id. Its body names each old card id and shows the signals
that returned the point, for example both the mark and the note. A carried
`blocked` card names the current card id of the point it waits on. An `info` card
stays in its round. The old card stays as it is.

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

# Card

## Holds

One point the human reads or answers. A card is an item in `rounds[].items[]`:
`id`, `kind`, `title`, `node` (the map node it belongs to), `state`, `body` (one
component tree), `carries` (the ids of the earlier cards of the same point) and,
once settled, `settled`. `title` is optional, at most 90
characters: the point in plain words. Kinds:

| Kind | The card | The human |
|------|----------|-----------|
| `decided` | states a call you took, with its evidence | accepts it or reopens it |
| `confirm` | states a reading you need confirmed | accepts it or corrects it |
| `debate` | shows a fork: the options side by side and your recommendation | picks an option or writes one in |
| `signoff` | states an aspect only a human may approve, with the exact wording | signs it or asks for changes |
| `info` | shows context; it asks nothing | may annotate it |

`state` is a point state: `open`, `blocked`, `needs_reading`,
`settled_by_mark`, `settled_by_note`. A new card is `open`. A card that waits on
another open point is `blocked`, and its body names the card it waits on.

## Use it when

One card per map node or per question. Give every card a `title`. Set `node`
when the card belongs to a map node. A card stays in its round when the round settles.

When the human sends a round, the engine settles a point with one `accept`,
`sign` or option mark. It moves a point to `needs_reading` on `reopen`,
`changes`, a write-in, a note, a mark plus a note, or 2 marks. On a card that is
already settled, a signal that changes the answer sets `state` to `open` and
removes `settled`, and a note stays on that card, also in a settled round. Its
signal has `reopened: true`. Before you mark the round `settled`, go through the
cards of the current round. Never change a card in a settled round: only the
engine writes there. A note whose `target` is a map node id is a steer: leave it
out when you read the signals, because it settles nothing.

- `needs_reading` with a clear note and no signal that disagrees with it: set
  `state` to `settled_by_note` and write `settled`, for example `{"by": "note", "round": 2, "signal": "N-2-i-format", "reading": "Picks CSV."}`.
  The `signal` is the note id. A note that leaves the answer open is not a clear
  note. A `signoff` card settles only by a `sign` mark: a note on it is never a clear
  note, even when it keeps the wording, and `apply-readings` refuses that reading. The
  new card asks the human to sign. A note on an `info` card is not a
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

The new card has a new id. Its `carries` lists each old card id; each id must be
a card of an earlier round. Its body shows the signals that returned the point,
for example both the mark and the note. A carried
`blocked` card names the current card id of the point it waits on. An `info` card
stays in its round. The old card stays as it is.

## How it looks

A box with the mark radios of its kind. The page shows each point once, as its
newest card: the card that no later card carries. Under the heading come the
notes and replies of that card. At the end, a closed "History (R-1 i-x, …)"
holds the earlier cards of the point, newest first, each with its chip, state
and body. An annotation on an earlier card stays on that card.

The cards section, below the maps, holds the points of the current round in kind
order: `debate`, `confirm`, `decided`, `signoff`, `info`. An asking card of an
earlier round that is still open stays there too. Below it, "Settled by earlier
rounds" holds the other points, newest round first, each folded to its heading
and settled line until the human opens it.

A mark goes to the lavish queue at once. The human writes a note as a lavish
annotation on the card or on any part of it, and sends marks and notes with
lavish's Send to Agent. The heading shows the `title`, then the kind as a small
label, the state, and the card id small and muted at the end. With no `title`,
the heading is the kind and the id. Every card has the chip of its round. The chip is solid in the round colour
when the card needs the human now, and muted otherwise. An open `info` card
shows no state word. A note-settled card shows "settled by note", which differs from "settled
by mark". For a `debate` card, put the options in a `table`, one column per
option, each option cell with the id `<item id>-opt-<letter>`.

A `decided` card shows its fields as labelled blocks, one `text` with a `label`
each, in this order: "Decision" in bold, "Why this one", "Other options
considered (rejected)" as a list, "Evidence" with the grade as a badge, "To
undo", "Depends on". The label says that the other options are rejected, so they
never read as parts of the decision.

## Example

```json fragment=item
{
  "id": "i-format",
  "kind": "debate",
  "title": "The file format of the export",
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

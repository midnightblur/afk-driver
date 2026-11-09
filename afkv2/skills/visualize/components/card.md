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

## How it looks

A box with the mark radios of its kind. The page shows each point once, as its
newest card: the card that no later card carries. Under the heading come the
notes and replies of that card. At the end, a closed "History (R-1 i-x, …)"
holds the earlier cards of the point, newest first, each with its chip, state
and body. An annotation on an earlier card stays on that card.

A mark goes to the lavish queue at once. The human writes a note as a lavish
annotation on the card or on any part of it, and sends marks and notes with
lavish's Send to Agent. Until the send, lavish keeps the picked marks, the
queue and an annotation being typed on an element (not on selected text) in
its store for the browser tab: they
come back after a reload or a re-render, and after a restart of the lavish
host. A closed tab loses them. After the send, the host keeps the send on
disk, and the engine keeps it beside the document until ingest. The heading shows the `title`, then the kind as a small
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
never read as parts of the decision. The round input of a `decided` card holds these fields in its
`decided` object. The build refuses a `decided` card with no `decided` object
(`no-decided-fields`), and writes a card with a gap in its fields as `confirm`,
listed in `degraded` in its result.

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

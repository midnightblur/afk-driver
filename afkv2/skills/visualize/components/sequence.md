# Sequence diagram

## Holds

Actors and the messages between them, in order. Type `sequence`. Props:
`actors` (each with `id` and `label`) and `messages` (each with `from`, `to`
and `text`), in the order they happen. A message also takes `tone` (`removed`, `kept` or
`new`), to show what a change does to it, and `tip`, a text of 1 to 300 characters that shows when the human
hovers the message, and `you`, `true` when the message is an act of the human.

## Use it when

The point is about who talks to whom and in which order: a request through
services, a hand-off between people and systems, a retry or a time-out path.
Use `tone` when the point changes the sequence: `removed` for a message that goes
away, `new` for one that comes in, `kept` for one that stays.
Set `you` on each message that the human does, so the human sees their own
acts apart from what the system does. Give a message a `tip` to explain a term or
a name that the short label cannot hold.

## How it looks

One lifeline per actor across the top, one arrow per message, top to bottom in
time order. A message with a tone shows the tone's word after its text and the
tone's look: a removed message is struck through with a dashed red line, a new
one is blue. A message with `you` has a YOU badge at its top right and an edge in the YOU
colour, the same strong colour on the whole page. A message with a `tip` shows the
pointer for help and shows its text on hover.

## Example

```json fragment=component
{
  "type": "sequence",
  "id": "q-export",
  "props": {
    "actors": [
      {"id": "user", "label": "User"},
      {"id": "api", "label": "Export endpoint"},
      {"id": "store", "label": "Order store"}
    ],
    "messages": [
      {"from": "user", "to": "api", "text": "start export", "you": true, "tip": "The human presses Export"},
      {"from": "api", "to": "store", "text": "read orders", "tone": "kept"},
      {"from": "store", "to": "api", "text": "orders", "tone": "kept"},
      {"from": "api", "to": "user", "text": "file by email", "tone": "removed"},
      {"from": "api", "to": "user", "text": "file link", "tone": "new"}
    ]
  }
}
```

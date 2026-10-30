# Sequence diagram

## Holds

Actors and the messages between them, in order. Type `sequence`. Props:
`actors` (each with `id` and `label`) and `messages` (each with `from`, `to`
and `text`), in the order they happen.

## Use it when

The point is about who talks to whom and in which order: a request through
services, a hand-off between people and systems, a retry or a time-out path.

## How it looks

One lifeline per actor across the top, one arrow per message, top to bottom in
time order.

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
      {"from": "user", "to": "api", "text": "start export"},
      {"from": "api", "to": "store", "text": "read orders"},
      {"from": "store", "to": "api", "text": "orders"},
      {"from": "api", "to": "user", "text": "file link"}
    ]
  }
}
```

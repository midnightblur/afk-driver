# Map

## Holds

A diagram that keeps the high-level view of the session's topic: a scope tree,
a module structure, a simulated run. A map is a component of type `map` in the
document's `maps` list. Props: `title`, `nodes` and optional `edges`. Each node
has `id`, `label`, `state` (`open`, `settled` or `focus`) and `round`, the round
in which its state last changed. Each edge has `from`, `to` and an optional
`label`.

## Use it when

The topic has parts the human must keep in view while answering one card. Use
as many maps as the topic needs, one per view. Link each card to its node with
the item's `node` field. Update a node in place when its point changes state,
and set its `round` to the current round.

## How it looks

Boxes and arrows in the maps section, below notes and replies. Settled, open and
current-focus nodes have different colours. The human can note a node; the
engine records that note as a steer for the node.

## Example

```json fragment=map
{
  "type": "map",
  "id": "m-scope",
  "props": {
    "title": "Scope",
    "nodes": [
      {"id": "n-export", "label": "Export", "state": "settled", "round": 1},
      {"id": "n-format", "label": "File format", "state": "focus", "round": 2},
      {"id": "n-access", "label": "Who may export", "state": "open", "round": 1}
    ],
    "edges": [
      {"from": "n-export", "to": "n-format"},
      {"from": "n-export", "to": "n-access"}
    ]
  }
}
```

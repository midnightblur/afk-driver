# Map

## Holds

A diagram that keeps the high-level view of the session's topic: a scope tree,
a module structure, a simulated run. A map is a component of type `map` in the
document's `maps` list. Props: `title`, `nodes`, optional `edges` and optional
`groups`. Each node
has `id`, `label`, `state` (`open`, `settled` or `focus`) and `round`, the round
in which its state last changed. A node also takes `tip`, a text of 1 to 300 characters that shows when the human
hovers the node, `you`, `true` when the node is an act of the human, and `group`, the id of its group. Each edge has
`from`, `to` and an optional `label`. Each group has `id` and `label`; the engine refuses a node whose `group` names no
group of the map.

## Use it when

The topic has parts the human must keep in view while answering one card. Use
as many maps as the topic needs, one per view. Link each card to its node with
the item's `node` field. Update a node in place when its point changes state,
and set its `round` to the current round. Set `you` on each node that the human does, so the human sees their own
acts apart from what the system does. Give a node a `tip` to explain a term or
a name that the short label cannot hold. For a scope map, give each module or
area a group, and put each node in its group.

## How it looks

Boxes and arrows. Settled, open and
current-focus nodes have different colours. The human can note a node; that
note is a steer for the node (`notes-and-replies.md`). A node with `you` has a YOU badge at its top right and an edge in the YOU
colour, the same strong colour on the whole page. A node with a `tip` shows the
pointer for help and shows its text on hover. A map with groups draws each group
as its own labelled box, side by side, and stacks them on a narrow window; the
nodes in no group come last. An arrow inside a group is drawn. An arrow between
2 groups is a line under the groups: "<from> settles before <to>".
Each group canvas starts its boxes at the top, so boxes in 2 groups do not line up. When arrows join
boxes of different groups, put a `graph` with groups in the map's `children`: SKILL.md, "Arrows between groups".

## Example

```json fragment=map
{
  "type": "map",
  "id": "m-scope",
  "props": {
    "title": "Scope",
    "nodes": [
      {"id": "n-export", "label": "Export", "state": "settled", "round": 1},
      {"id": "n-format", "label": "File format", "state": "focus", "round": 1, "tip": "The file type the export writes"},
      {"id": "n-access", "label": "Who may export", "state": "open", "round": 1, "you": true}
    ],
    "edges": [
      {"from": "n-export", "to": "n-format"},
      {"from": "n-export", "to": "n-access"}
    ]
  }
}
```

A scope map with groups:

```json fragment=map
{
  "type": "map",
  "id": "m-areas",
  "props": {
    "title": "Scope by area",
    "groups": [{"id": "g-ui", "label": "Screens"}, {"id": "g-data", "label": "Data"}],
    "nodes": [
      {"id": "n-list", "label": "Order list", "state": "open", "round": 1, "group": "g-ui"},
      {"id": "n-file", "label": "Export file", "state": "focus", "round": 1, "group": "g-data"},
      {"id": "n-store", "label": "Order store", "state": "settled", "round": 1, "group": "g-data"}
    ],
    "edges": [{"from": "n-store", "to": "n-list"}]
  }
}
```

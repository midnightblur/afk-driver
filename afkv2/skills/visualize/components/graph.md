# Graph

## Holds

Nodes and arrows: a flow chart, a dependency graph, a module structure with
grouped boxes. Type `graph`. Props: `nodes` (each with `id`, `label` and an
optional `group`), optional `edges` (each with `from`, `to` and an optional
`label`), optional `groups` (each with `id` and `label`) and optional
`direction` (`right` or `down`). A node also takes `tip`, a text of 1 to 300 characters that shows when the human
hovers the node, and `you`, `true` when the node is an act of the human.

## Use it when

The point is about how things connect: which module calls which, which step
leads to which, what depends on what. Use groups for the boxes around modules,
services or layers. For the high-level view of the whole topic, use a map.
Set `you` on each node that the human does, so the human sees their own
acts apart from what the system does. Give a node a `tip` to explain a term or
a name that the short label cannot hold.

## How it looks

Boxes joined by arrows, drawn left to right or top down. A group draws as a
labelled frame around its nodes. A graph fits inside a card and inside a table
cell. A node with `you` has a YOU badge at its top right and an edge in the YOU
colour, the same strong colour on the whole page. A node with a `tip` shows the
pointer for help and shows its text on hover.

## Example

```json fragment=component
{
  "type": "graph",
  "id": "g-modules",
  "props": {
    "direction": "right",
    "groups": [{"id": "web", "label": "web module"}, {"id": "core", "label": "core module"}],
    "nodes": [
      {"id": "g-user", "label": "press Export", "you": true, "tip": "The button on the orders page"},
      {"id": "g-controller", "label": "export endpoint", "group": "web"},
      {"id": "g-service", "label": "export service", "group": "core"},
      {"id": "g-store", "label": "order store", "group": "core"}
    ],
    "edges": [
      {"from": "g-user", "to": "g-controller"},
      {"from": "g-controller", "to": "g-service", "label": "start export"},
      {"from": "g-service", "to": "g-store", "label": "read orders"}
    ]
  }
}
```

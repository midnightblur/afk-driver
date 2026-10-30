---
name: visualize
description: Authoring guide for page documents (schema afkv2.page/0) — the components, when to use each, how each looks, and example fragments. Use before you write or change a page document.
---

# visualize — write a page document

You write the page document, a JSON file. The page engine turns it into the page
the human reads and answers. You never write page HTML: HTML goes only into the
`html` field of a freestyle component.

## The document

Save the document in the feature spec folder as `pages/<skill>-<session id>.json`.
Field constraints: the engine's schema file `engine/schema/page-v0.schema.json`
(plugin root). The shape:

```json fragment=document
{
  "schema": "afkv2.page/0",
  "session": {"id": "s-01", "skill": "grill", "feature": "example-feature",
              "ticket": "PROJ-123", "started": "2026-01-05T09:00:00Z"},
  "maps": [],
  "rounds": [
    {"n": 1, "state": "current",
     "banner": {"settled": [], "unlocks": ["the scope map"], "parked": []},
     "items": [
       {"id": "i-goal", "kind": "confirm",
        "body": {"type": "text", "props": {"text": "The goal is one export file per order."}}}
     ]}
  ]
}
```

- `session.skill` is `grill`, `propose-solution` or `propose-verification`; `started` is ISO-8601 UTC.
- `maps` holds the session's maps; you update their nodes in place.
- `rounds`: exactly one round is `current`. A new round appends with the next `n`. A `settled` round is never rewritten.
- An item is one card. Its `body` is one component; every component can hold more components in `children`.
- Ids: every item id and component id is unique in the document and never reused. Give an id to every element the human may want to note.
- `responses`, `notes` and the mark settles are written by the engine. You write `replies`, and for a point the human settled by a note, its `settled` reading (`card` page).

## Components

Load the page of each component you use.

| Component | Where it goes | Page |
|-----------|---------------|------|
| round banner | `rounds[].banner` | `components/round-banner.md` |
| notes and replies | `rounds[].replies`; notes come from the engine | `components/notes-and-replies.md` |
| map | `maps[]`, type `map` | `components/map.md` |
| card | `rounds[].items[]` | `components/card.md` |
| graph | any body, type `graph` | `components/graph.md` |
| table | any body, type `table` | `components/table.md` |
| sequence diagram | any body, type `sequence` | `components/sequence.md` |
| simulated-run strip | any body, type `run-strip` | `components/run-strip.md` |
| chip and styled text | any body, types `chip` and `text` | `components/chip-and-text.md` |
| freestyle | any body, type `freestyle` | `components/freestyle.md` |

Every component takes an open `style` field (any CSS) and nests inside any other.
One document that uses every component: `examples/all-components.json`.

## Picture before a critical-aspect question

Before a card that asks a critical-aspect question, show the current state as a
picture, in that card's body above the question:

- a code area: a `graph` with grouped boxes (modules, files, the calls between them);
- data: a `table` of the current entities, fields or sample rows;
- a flow: a `sequence` diagram or a `run-strip` of today's run.

Mark what the question would change with chips (`kept`, `removed`, `new`, `proposed`).

## Freestyle is the marked escape

Use a freestyle component only for what no other component holds. Every freestyle
use carries an `id` and a `props.reason` that names what it shows. The page marks
it as freestyle.

When the session ends, group the freestyle uses by `props.reason`. Report each
reason used two or more times in your final report as one line:
`candidate component: <reason> — <n> uses (<ids>)`.

## Done

Run the engine `check` verb on the document. It is done when `check` answers
`{"ok": true}`. A refusal names the item and the field: fix that field and run
`check` again.

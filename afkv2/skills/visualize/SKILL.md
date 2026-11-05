---
name: visualize
description: Authoring guide for page documents (schema afkv2.page/1) — the components, when to use each, how each looks, and example fragments. Use before you write or change a page document.
---

# visualize — write a page document

You write the page document, a JSON file. The page engine turns it into the page
the human reads and answers. You never write page HTML: HTML goes only into the
`html` field of a freestyle component.

## The document

Save the document in the feature spec folder as `pages/<skill>-<session id>.json`.
Field constraints: the engine's schema file `engine/schema/page-v1.schema.json`
(plugin root). The shape:

```json fragment=document
{
  "schema": "afkv2.page/1",
  "session": {"id": "s-01", "skill": "grill", "feature": "example-feature",
              "ticket": "PROJ-123", "started": "2026-01-05T09:00:00Z",
              "short_title": "Order export", "step": "Requirements grill"},
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
- `session.step` and `session.short_title` come from the round input's `step` and `short_title`; the build writes the short title in round 1 only.
- `session.links` (optional) holds the URL templates that link references in the page text: `issue`, `change`, `commit`, `ticket`, each with `{id}` for the reference, and `projects`, the Jira project keys that `ticket` links. The skill's build writes it; the forms: `components/chip-and-text.md`.
- `maps` holds the session's maps; you update their nodes in place.
- `rounds`: exactly one round is `current`. A new round appends with the next `n`. A `settled` round is never rewritten.
- An item is one card. Its `body` is one component; every component can hold more components in `children`.
- Ids: every item id and component id is unique in the document and never reused. Give an id to every element the human may want to note. An id is also the HTML id of its element, so it never starts with `afkv2-` or `lavish-`.
- `responses`, the document's `notes` list and the mark settles are written by the engine. You write `replies`, and for a point the human settled by a note, its `settled` reading.

## Page-owned tips

Put optional `tips` at the document root. Its entries supply local
explanations for terms and identifier titles:

| Field | Entry |
|-------|-------|
| `tips.terms` | `term`, `definition` |
| `tips.ids` | `id`, `title` |

The field contract and limits live in `engine/schema/page-v1.schema.json`, under
`$defs.tips`. Use plain text for definitions and titles. Example:
`examples/page-owned-tips.json`.

The shared round writer accepts `tips` in its round input and writes it at the
document root. Supplying `tips` replaces the dictionary; omit it to keep existing
entries. Supply `{}` to clear them.

A format 0 file opens and renders as it is, with its legacy feature tips file.
Its next round writes format 1; from then on the page reads only its own `tips`.

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
| key-number tile | any body, type `tile` | `components/tile.md` |
| bar chart | any body, type `bars` | `components/bars.md` |
| line chart | any body, type `line` | `components/line.md` |
| bullet graph | any body, type `bullet` | `components/bullet.md` |
| range bars | any body, type `range` | `components/range.md` |
| signed bars | any body, type `signed-bars` | `components/signed-bars.md` |
| box plot | any body, type `box-plot` | `components/box-plot.md` |
| flame graph | any body, type `flame` | `components/flame.md` |
| sparklines | any body, type `sparkline` | `components/sparkline.md` |
| span waterfall | any body, type `waterfall` | `components/waterfall.md` |
| diagram text | any body, type `diagram` | `components/diagram.md` |
| code block | any body, type `code` | `components/code.md` |
| diff | any body, type `diff` | `components/diff.md` |
| freestyle | any body, type `freestyle` | `components/freestyle.md` |

Every component takes an open `style` field (any CSS) and nests inside any other.
Every component also takes `tip` (format 1), a hover text of 1 to 300 characters: `components/chip-and-text.md`.
Every component also takes `fold`, a label: the page shows the component closed
under that label, and the human opens it.
Give a folded component an `id`: only then does an open fold stay open through a reload.
Give each item a `title` (at most 90 characters): the card heading shows it.
One document that uses every component: `examples/all-components.json`.

## Page layout

The engine lays out the page in this order:

1. the title and the banner of the current round;
2. "Notes on the whole session": every note of the session, card notes included, with its answer, in one fold per round;
3. the maps;
4. the points of the current round, one card per point, then the copy bar;
5. "Settled by earlier rounds": the other points, each folded to its heading and settled line;
6. "Earlier banners", closed.

A point is the newest card and the cards it `carries` (`components/card.md`).

The browser tab title and the page heading are `<ticket> · <short title> · <step>`.
They hold no round number, so they stay the same every round. A page with no
`short_title` (an upgraded format 0 page) shows its feature. A part drops out when
it is empty or repeats an earlier part. A later round shows in the tab that the
first show opened: `present` answers `tab: reused`. Give the human the `url` in
one line then, so a closed tab costs nothing.

## Controls the engine adds

You do not write these; the engine puts them on every page.

- Copy bar, below the current round: copies the marks when the page has no lavish session.
- btw? button, bottom left: a one-line side question and one Ask button. Ask posts only the
  question to the side-question listener of the wait; the marks and notes the human queued stay
  queued for Send. The wait asks it in the agent's terminal pane (`/btw` on Claude, `/side` on
  Codex, through herdr), and the panel shows the answer; the round stays open. With no wait
  running, the panel says so. Engine modules: `engine/btw_listener.py` and
  `engine/side_question.py` (plugin root).

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

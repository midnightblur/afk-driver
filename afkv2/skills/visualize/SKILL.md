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
- `session.links` (optional) holds the URL templates that link references in the page text: `issue`, `change`, `commit`, `ticket`, each with `{id}` for the reference, and `projects`, the Jira project keys that `ticket` links. The skill's build writes it: `projects` holds the projects of the session ticket and its links, the config's `tracker.project` and `tracker.projects`, and the round input's `ticket_projects`, a list such as `["ABC"]` for the other projects the page names. `titles` maps a reference as the text writes it (`ABC-123`, `#123`, `!123`) to its title, which the link shows on hover; the build writes it from the round input's `ticket_titles` over the earlier rounds' titles. The forms: `components/chip-and-text.md`.
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
The card body starts with that heading, so do not repeat the title as the first text of the body.
One document that uses every component: `examples/all-components.json`.

## Arrows between groups

When arrows join boxes of different groups, draw all the boxes on one canvas, so that related boxes line up:

- Use a `graph` with `groups`. It puts each group in a lane and each dependency step in a column (`direction: right`) or a row (`direction: down`). A box sits 1 step after the box it waits for, in every group.
- Do not use a `map` with `groups` for this. A map draws each group on its own canvas, with its boxes from the top. Its arrows between groups become text lines under the groups.
- Pick `direction: right` when 1 step holds many boxes of 1 group. With `down`, those boxes stand side by side, and the canvas grows wide.
- Show a box of another group that blocks this group inside this group, as its own box, once per group that it blocks. Mark it with a word and a symbol, and with `you` when the human pushes it.
- A map keeps its place on top: give it the summary nodes, and put the graph in its `children`.

## Pictures

Show information as pictures wherever a picture helps the human understand or
decide: a flow, how a bug happens, now against proposed, options side by side.
You pick the form and the count. A forms table of a page skill holds
suggestions. A skill can set a floor of its own, such as 1 picture per design
section.

## Pictures in an artifact

When you write an artifact from a page (PRD, SDD, ADR, `VERIFICATION.md`), carry
each page picture that helps its reader. A picture to carry is a diagram text:
the engine draws it as the same picture in the artifact. For each one, write its
Mermaid text to a scratch file and run, from the repository root (`<python>`: the
Python in the setup install record):

```
<python> "<this skill's folder>/../../engine/engine.py" export "<text file>" --dest "<spec folder>/pictures/<diagram id>.svg" --artifact "<artifact>"
```

Paste the `markdown` of the answer into the artifact where the picture goes: the
picture, with its Mermaid source in a fold below it. `no-picture` names why the
picture failed: fix the text, or have the setup skill install a missing renderer.

## Picture before a critical-aspect question

Before a card that asks a critical-aspect question, show the current state as a
picture, in that card's body above the question:

- a code area: a `graph` with grouped boxes (modules, files, the calls between them);
- data: a `table` of the current entities, fields or sample rows;
- a flow: a `sequence` diagram or a `run-strip` of today's run.

Mark what the question would change with chips (`kept`, `removed`, `new`, `proposed`).

## Captions

The caption rule and the picture types: `../propose-solution/DRAFT.md`,
section "Sections". A caption child looks like this:
`{"type": "text", "props": {"label": "What to see", "text": "One export request, from the button to the file link."}}`.

## Design sections

A design page shows the design in sections. The section ids, their order and
the shape of each kind: `../propose-solution/DRAFT.md`, section "Sections". The
body of a section is 1 component. These 2 kinds open with a picture.

### A level section

Shape: the level-section bullet of `../propose-solution/DRAFT.md` "Sections".

```json fragment=component
{
  "type": "sequence",
  "id": "sec-l2-request",
  "props": {
    "actors": [
      {"id": "l2-user", "label": "User"},
      {"id": "l2-api", "label": "Export endpoint"},
      {"id": "l2-store", "label": "Order store"}
    ],
    "messages": [
      {"from": "l2-user", "to": "l2-api", "text": "start export"},
      {"from": "l2-api", "to": "l2-store", "text": "read orders", "tone": "kept"},
      {"from": "l2-api", "to": "l2-user", "text": "file link", "tone": "new"}
    ]
  },
  "children": [
    {"type": "text", "id": "sec-l2-see", "props": {"label": "What to see", "text": "One export request, from the button to the file link."}},
    {"type": "text", "id": "sec-l2-summary", "props": {"label": "Summary", "text": "The endpoint reads the orders and stores the file.\nThe user gets a link in place of an email."}},
    {"type": "table", "id": "sec-l2-surfaces", "fold": "Each callable surface", "props": {
      "columns": ["Surface", "Answer"],
      "rows": [["POST /exports", "the export id"], ["GET /exports/{id}", "the file link"]]},
     "children": [{"type": "text", "id": "sec-l2-surfaces-see", "props": {"label": "What to see", "text": "The 2 surfaces this level adds."}}]}
  ]
}
```

### A critical section

Shape: the critical-section bullet of `../propose-solution/DRAFT.md` "Sections".

```json fragment=component
{
  "type": "run-strip",
  "id": "sec-crit-cancel-run",
  "props": {
    "current": [
      {"label": "mark cancelled"},
      {"label": "refund"}
    ],
    "proposed": [
      {"label": "ask for a reason", "tone": "new"},
      {"label": "mark cancelled", "tone": "kept"},
      {"label": "refund", "tone": "kept"}
    ]
  },
  "children": [
    {"type": "text", "id": "sec-crit-cancel-see", "props": {"label": "What to see", "text": "A cancel asks for a reason before it marks the order."}},
    {"type": "chip", "id": "sec-crit-cancel-chip", "props": {"text": "critical", "tone": "proposed"}}
  ]
}
```

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

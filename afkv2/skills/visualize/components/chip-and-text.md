# Chip and styled text

## Holds

A short label (type `chip`) or a run of text (type `text`), with a semantic
tone. Props: `text` and `tone`. A chip needs a tone or a set (below); for text the tone is
optional. A chip also takes a tone of state or certainty (second table). A `text` takes `markdown: true` to render a safe subset: blank-line
paragraphs, `**bold**`, `` `code` ``, `- ` lists, `#` headings as bold lines and
http(s) links. The engine escapes all HTML first. A `text` also takes `label`
(at most 60 characters), a small line above its words that names what the words
are, and `badge` (at most 30 characters), a neutral chip on that line. Tones:

| Tone | Means | Looks |
|------|-------|-------|
| `removed` | goes away | strike-through, red |
| `kept` | stays as it is | grey chip; on a chip, = |
| `new` | new or changed | blue chip; on a chip, + |
| `proposed` | suggested, not yet agreed | dashed outline |

State and certainty tones, for a chip only:

| Tone | Means | Looks |
|------|-------|-------|
| `open` | not decided yet | amber, ○ |
| `blocked` | waits on something else | red, ✕ |
| `settled` | decided | green, ✓ |
| `measured` | a fact from a run, a count or a file | blue, ● |
| `inferred` | read from other facts, not checked | dashed blue outline, ◐ |
| `estimated` | a guess of a size or a time | dotted grey outline, ≈ |
| `unverified` | a claim no one checked | dashed amber outline, ? |
| `you` | the human does it | the YOU colour, bold, ★ |

A value chip takes `set` instead of a tone: `set` names a value set of the
document, and `text` is one value of that set. A chip takes a tone or a set, never
both. The document names its sets in `value_sets` (format 1, `afkv2.page/1`):
`{name: {values, ordered}}`, with `values` the list of values in order and
`ordered` true when the values run from strong to weak, such as a risk level. The
engine refuses a chip whose set is no set of the document, or whose text is no
value of its set. The round input of the skill's build takes `value_sets` in the
same form: each sent set is added by name, a set of the same name is replaced, and
the other sets stay.

Any component, a chip or a text too, takes `tip` (format 1), a text of 1 to 300
characters that shows when the human points at the component.

A `text` component is also the plain container of a body: its `children` follow
its text.

References link by themselves, in every text of the page, not only in a `text`:
`#123` (an issue), `!123` and `PR #123` (a change), `ABC-123` (a ticket of a
project in `session.links.projects`) and a commit sha after "commit" or "sha".
Each opens in a new tab. A kind links only when `session.links` has its template;
otherwise it stays text. Write the reference in that form, for example `#159`,
not `issue 159`, and a ticket with its project key, `ABC-123`, not `123`. A hover
tip holds no link: write a reference the human must open in a label or a text.
A reference inside a URL stays text. Plain text, a table cell among it, renders no
Markdown: write the bare key `ABC-123`, not `[ABC-123](https://...)`, which shows
its brackets and its URL. A reference in `session.links.titles` shows its title
on hover.

## Use it when

A value, step or element must show whether it stays, goes, is new or is only
proposed. Use `markdown: true` for text that comes as Markdown, such as a
ticket description. Use `label` when a card holds several fields, so each block
says what it is. Use a state chip for the state of a point or a part, and a
certainty chip for how sure a value is: `measured`, `inferred`, `estimated` or
`unverified`. Write the meaning in the chip's text too, for example "blocked: waits
on the format". Use the tone for that meaning only; for any other look, use `style`.

Use a value chip for a column or field whose values come from one fixed list, such
as a risk level or an owner: put a chip with that `set` in each cell of the
column. Use a set, not a colour per chip: the engine picks the colours, so the same
value looks the same on the whole page. Give a component a `tip` to explain a term
or a value where it shows.

## How it looks

A chip is a small rounded label inline with the text around it; it fits inside
a table cell. Styled text keeps the text flow and takes the tone's look. A chip of
a state or certainty tone shows its tone's symbol before its text and its tone's
colour, in the light and dark themes. No tone shows its meaning by colour alone.

A value chip shows its value as its word, on a tint of the value's colour. The
colour comes from the value's position in its set, so the same value has the same
colour on the whole page. A set that is not ordered takes up to 8 different
colours, then starts again. An ordered set runs from a strong colour to a faint one
in one hue. The value YOU, in any case, always has the same strong colour. A
component with a `tip` shows the help cursor, and the tip shows on hover.

## Example

```json fragment=component
{
  "type": "text",
  "props": {"text": "The export changes three things:"},
  "children": [
    {"type": "chip", "props": {"text": "per-order file", "tone": "kept"}},
    {"type": "chip", "props": {"text": "email delivery", "tone": "removed"}},
    {"type": "chip", "props": {"text": "download link", "tone": "new"}},
    {"type": "chip", "props": {"text": "size: 2 MB measured", "tone": "measured"}},
    {"type": "chip", "props": {"text": "blocked: waits on the format", "tone": "blocked"}},
    {"type": "text", "props": {"text": "Archive after 7 days", "tone": "proposed"}}
  ]
}
```

A format 1 document with a value set, a column of value chips and a tip:

```json fragment=document
{
  "schema": "afkv2.page/1",
  "session": {"id": "s-values", "skill": "grill", "feature": "order-export", "ticket": "PROJ-123",
              "started": "2026-01-05T09:00:00Z", "step": "Requirements grill"},
  "maps": [],
  "notes": [],
  "value_sets": {
    "risk": {"values": ["high", "medium", "low"], "ordered": true},
    "owner": {"values": ["agent", "reviewer", "YOU"], "ordered": false}
  },
  "rounds": [{
    "n": 1, "state": "current",
    "banner": {"settled": [], "unlocks": [], "parked": []},
    "items": [{
      "id": "i-risks", "kind": "info", "title": "Risks of the export",
      "body": {
        "type": "table", "id": "t-risks",
        "tip": "Each risk, how bad it is and who acts on it",
        "props": {
          "columns": ["Risk", "Level", "Owner"],
          "rows": [
            ["The file is too large to mail", {"type": "chip", "props": {"text": "high", "set": "risk"}},
             {"type": "chip", "props": {"text": "YOU", "set": "owner"}}],
            ["An order changes during the export", {"type": "chip", "props": {"text": "medium", "set": "risk"}},
             {"type": "chip", "props": {"text": "agent", "set": "owner"}}],
            ["The link opens after 7 days", {"type": "chip", "props": {"text": "low", "set": "risk"}},
             {"type": "chip", "props": {"text": "reviewer", "set": "owner"}}]
          ]
        }
      }
    }]
  }]
}
```

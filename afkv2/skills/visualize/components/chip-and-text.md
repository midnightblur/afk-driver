# Chip and styled text

## Holds

A short label (type `chip`) or a run of text (type `text`), with a semantic
tone. Props: `text` and `tone`. A chip needs a tone; for text the tone is
optional. A chip also takes a tone of state or certainty (second table). A `text` takes `markdown: true` to render a safe subset: blank-line
paragraphs, `**bold**`, `` `code` ``, `- ` lists, `#` headings as bold lines and
http(s) links. The engine escapes all HTML first. A `text` also takes `label`
(at most 60 characters), a small line above its words that names what the words
are, and `badge` (at most 30 characters), a neutral chip on that line. Tones:

| Tone | Means | Looks |
|------|-------|-------|
| `removed` | goes away | strike-through, red |
| `kept` | stays as it is | grey chip |
| `new` | new or changed | blue chip |
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

A `text` component is also the plain container of a body: its `children` follow
its text.

References link by themselves, in every text of the page, not only in a `text`:
`#123` (an issue), `!123` and `PR #123` (a change), `ABC-123` (a ticket of a
project in `session.links.projects`) and a commit sha after "commit" or "sha".
Each opens in a new tab. A kind links only when `session.links` has its template;
otherwise it stays text. Write the reference in that form, for example `#159`,
not `issue 159`.

## Use it when

A value, step or element must show whether it stays, goes, is new or is only
proposed. Use `markdown: true` for text that comes as Markdown, such as a
ticket description. Use `label` when a card holds several fields, so each block
says what it is. Use a state chip for the state of a point or a part, and a
certainty chip for how sure a value is: `measured`, `inferred`, `estimated` or
`unverified`. Write the meaning in the chip's text too, for example "blocked: waits
on the format". Use the tone for that meaning only; for any other look, use `style`.

## How it looks

A chip is a small rounded label inline with the text around it; it fits inside
a table cell. Styled text keeps the text flow and takes the tone's look. A chip of
a state or certainty tone shows its tone's symbol before its text and its tone's
colour, in the light and dark themes. No tone shows its meaning by colour alone.

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

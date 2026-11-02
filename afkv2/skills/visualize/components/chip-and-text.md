# Chip and styled text

## Holds

A short label (type `chip`) or a run of text (type `text`), with a semantic
tone. Props: `text` and `tone`. A chip needs a tone; for text the tone is
optional. Tones:

| Tone | Means | Looks |
|------|-------|-------|
| `removed` | goes away | strike-through, red |
| `kept` | stays as it is | grey chip |
| `new` | new or changed | blue chip |
| `proposed` | suggested, not yet agreed | dashed outline |

A `text` component is also the plain container of a body: its `children` follow
its text.

## Use it when

A value, step or element must show whether it stays, goes, is new or is only
proposed. Use the tone for that meaning only; for any other look, use `style`.

## How it looks

A chip is a small rounded label inline with the text around it; it fits inside
a table cell. Styled text keeps the text flow and takes the tone's look.

## Example

```json fragment=component
{
  "type": "text",
  "props": {"text": "The export changes three things:"},
  "children": [
    {"type": "chip", "props": {"text": "per-order file", "tone": "kept"}},
    {"type": "chip", "props": {"text": "email delivery", "tone": "removed"}},
    {"type": "chip", "props": {"text": "download link", "tone": "new"}},
    {"type": "text", "props": {"text": "Archive after 7 days", "tone": "proposed"}}
  ]
}
```

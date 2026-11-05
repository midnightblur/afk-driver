# Freestyle

## Holds

Any HTML or SVG fragment. Type `freestyle`. Fields: `id`, `html` (the
fragment) and `props.reason` (what the fragment shows that no other component
holds). Only a freestyle component has an `html` field.

## Use it when

No other component holds what the point needs: a chart that no chart component
draws, an annotated screenshot layout, a drawing. Give the same `props.reason` to every use for the
same purpose, so the uses group in the end-of-session count (`SKILL.md`,
"Freestyle is the marked escape").

## How it looks

The fragment as written, in a frame the page marks as freestyle. The human can
note it like any other element.

## Example

```json fragment=component
{
  "type": "freestyle",
  "id": "f-score-radar",
  "props": {"reason": "radar chart of 5 scores"},
  "html": "<svg viewBox=\"0 0 40 40\" role=\"img\" aria-label=\"5 quality scores\"><polygon points=\"20,4 36,16 30,36 10,36 4,16\" fill=\"none\" stroke=\"currentColor\"/></svg>"
}
```

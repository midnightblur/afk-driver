# Freestyle

## Holds

Any HTML or SVG fragment. Type `freestyle`. Fields: `id`, `html` (the
fragment) and `props.reason` (what the fragment shows that no other component
holds). Only a freestyle component has an `html` field.

## Use it when

No other component holds what the point needs: a custom chart, an annotated
screenshot layout, a drawing. Give the same `props.reason` to every use for the
same purpose, so the uses group in the end-of-session count (`SKILL.md`,
"Freestyle is the marked escape").

## How it looks

The fragment as written, in a frame the page marks as freestyle. The human can
note it like any other element.

## Example

```json fragment=component
{
  "type": "freestyle",
  "id": "f-load-curve",
  "props": {"reason": "line chart of a measured value over time"},
  "html": "<svg viewBox=\"0 0 120 40\" role=\"img\" aria-label=\"export time per day\"><polyline points=\"0,35 30,30 60,18 90,12 120,5\" fill=\"none\" stroke=\"currentColor\"/></svg>"
}
```

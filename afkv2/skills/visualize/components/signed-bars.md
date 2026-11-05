# Signed bars

## Holds

Differences above and below zero. Type `signed-bars`. Props: `caption` (1 to
160 characters, what to see), `items` (1 to 40, each with `label`, at most 60
characters, and `value`, a number that may be negative), optional `unit` (at
most 12 characters), and optional `below` and `above`, the words for the 2
sides (at most 30 characters each, such as "faster" and "slower").

## Use it when

The direction is the message: faster or slower than before, over or under
budget, more or fewer findings. Sizes that are never negative: bars
(`components/bars.md`).

## How it looks

Bars grow left and right of a zero line, in the order given. Each label writes
its sign: "+130 ms", "−420 ms". `below` and `above` sit over the zero line with
an arrow to their side. The sign and the words carry the meaning, never colour
alone.

## Example

```json fragment=component
{
  "type": "signed-bars",
  "id": "k-time-change",
  "props": {"caption": "Export got faster; import got a little slower", "unit": "ms",
            "below": "faster", "above": "slower",
            "items": [{"label": "export", "value": -420}, {"label": "import", "value": 130},
                      {"label": "search", "value": 0}]}
}
```

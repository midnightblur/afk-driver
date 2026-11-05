# Range bars

## Holds

Estimates of time, cost or size. Type `range`. Props: `caption` (1 to 160
characters, what to see), `items` (1 to 40, each with `label`, at most 60
characters, `low`, `likely` and `high`, with `low` ≤ `likely` ≤ `high`), `means`
(1 line on what the range means, at most 160 characters) and optional `unit` (at
most 12 characters).

## Use it when

The point gives an estimate. A single number reads as more exact than it is:
show the range. One estimate alone fits a tile with `low` and `high`
(`components/tile.md`).

## How it looks

One bar per item on one shared scale, from low to high, with a dot at the likely
value and the numbers at the end: "3 to 9 days, likely 5". The `means` line sits
under the bars. The numbers carry the meaning, never colour alone.

## Example

```json fragment=component
{
  "type": "range",
  "id": "k-estimates",
  "props": {"caption": "The rework carries most of the doubt", "unit": "days",
            "means": "9 in 10 such tasks end between low and high",
            "items": [{"label": "export rework", "low": 3, "likely": 5, "high": 9},
                      {"label": "cache", "low": 1, "likely": 2, "high": 3}]}
}
```

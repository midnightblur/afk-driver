# Line chart

## Holds

A number over days, runs or versions. Type `line`. Props: `caption` (1 to 160
characters, what to see), `points` (2 to 400, each with `at`, the date, run or
version as text of at most 30 characters, and `value`, a number), optional
`unit` (at most 12 characters) and optional `target` (a number).

## Use it when

The point is a trend: export time per release, failures per week. With 2 or 3
points, show the change itself as signed bars (`components/signed-bars.md`).
Many measures side by side: sparklines (`components/sparkline.md`).

## How it looks

The points joined by one line, evenly spaced from the first `at` to the last.
The latest value is labelled at the end of the line. The lowest and the highest
value sit on the left axis. A `target` draws as a dashed line with the words
"target" and its value: the dash and the words carry it, never colour alone.

## Example

```json fragment=component
{
  "type": "line",
  "id": "k-export-trend",
  "props": {"caption": "Export time fell by half in 3 weeks", "unit": "ms", "target": 1000,
            "points": [{"at": "2026-10-01", "value": 2400}, {"at": "2026-10-08", "value": 2100},
                       {"at": "2026-10-15", "value": 1300}, {"at": "2026-10-22", "value": 1240}]}
}
```

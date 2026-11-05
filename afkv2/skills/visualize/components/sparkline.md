# Sparklines

## Holds

Several measures over time, side by side. Type `sparkline`. Props: `caption` (1
to 160 characters, what to see) and `rows` (1 to 40, each with `label`, at most
60 characters, `values`, 2 to 400 numbers oldest first, and an optional `unit`
of at most 12 characters).

## Use it when

The point shows many trends in little space: the health measures of a service,
the timings of several steps across releases. One measure with its dates and a
target: a line chart (`components/line.md`).

## How it looks

One row per measure: its label, a tiny line on the row's own scale, and the
latest value beside it in bold. Rows do not share a scale, so compare shapes,
not heights. The written value carries the number, never colour alone.

## Example

```json fragment=component
{
  "type": "sparkline",
  "id": "k-service-health",
  "props": {"caption": "Both measures improved in the last release",
            "rows": [{"label": "export time", "values": [2400, 2100, 1300, 1240], "unit": "ms"},
                     {"label": "error rate", "values": [2, 3, 1, 0.5], "unit": "%"}]}
}
```

# Bullet graph

## Holds

One measure with a goal and named bands. Type `bullet`. Props: `caption` (1 to
160 characters, what to see), `label` (the measure, at most 60 characters),
`value`, `target`, `bands` (1 to 5, each with `upto`, the number the band ends
at, and `label`, its name of at most 30 characters, in rising order), optional
`unit` (at most 12 characters) and optional `start` (where the first band
starts, 0 by default). `value` and `target` lie from `start` to the last band's
`upto`.

## Use it when

The point is how far one number is from its goal: coverage against the target,
a response time against its limit. One number with no goal: a tile
(`components/tile.md`).

## How it looks

The bands behind, each one strength of one hue with its name written on it; a
dark bar for the value; a thick tick for the target. The line under the drawing
writes the value, the target and the band the value falls in, so no meaning
rests on colour alone.

## Example

```json fragment=component
{
  "type": "bullet",
  "id": "k-coverage",
  "props": {"caption": "Coverage is 8 points short of its target", "label": "test coverage",
            "value": 72, "target": 80, "unit": "%",
            "bands": [{"upto": 50, "label": "poor"}, {"upto": 75, "label": "fair"},
                      {"upto": 100, "label": "good"}]}
}
```

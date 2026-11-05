# Tile

## Holds

One key number. Type `tile`. Props: `caption` (1 to 160 characters, what to
see), `value` (a number), `label` (the short name of the number, at most 60
characters), `grade` (how the number is known: `measured`, `inferred`,
`estimated` or `unverified`), `source` (where the number comes from, at most
160 characters), optional `unit` (at most 12 characters), and optional `low`
and `high` for an estimate with a range: both or neither, with `low` ≤ `value`
≤ `high`.

## Use it when

The point turns on one number: a count, a size, a duration, a cost, an
estimate. Against a target, use a bullet graph (`components/bullet.md`).

## How it looks

The number large, the label under it, then the range line when the number has
one. Under the drawing: the grade as a certainty chip with its symbol, then the
source. The caption sits under the tile. The grade carries a symbol and a word,
never colour alone.

## Example

```json fragment=component
{
  "type": "tile",
  "id": "k-export-time",
  "props": {"caption": "One export takes about 1.2 seconds today", "value": 1240, "unit": "ms",
            "low": 900, "high": 1500, "label": "export time", "grade": "estimated",
            "source": "3 runs on the staging host"}
}
```

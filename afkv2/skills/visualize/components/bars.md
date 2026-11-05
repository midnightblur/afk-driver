# Bars

## Holds

Sizes or counts compared across items. Type `bars`. Props: `caption` (1 to
160 characters, what to see), `items` (1 to 40, each with `label`, at most 60
characters, and `value`, a number of 0 or more), optional `unit` (at most 12
characters) and optional `split` (`true` when the items are the shares of one
whole).

## Use it when

The point compares how big things are: rows per table, calls per service,
findings per kind. A share of a whole is `split`, never a pie. Under 20 items
whose exact values matter: a table. Differences that can be negative: signed
bars (`components/signed-bars.md`).

## How it looks

Horizontal bars, sorted largest first by the engine, each with its label on the
left and its value at the end. With `split`: one bar cut into segments, largest
first, each segment numbered, and a key under it that writes each number, label,
value and share. The number and the key carry the meaning, never colour alone.

## Example

```json fragment=component
{
  "type": "bars",
  "id": "k-rows-per-table",
  "props": {"caption": "Returns hold most of the rows", "unit": "rows",
            "items": [{"label": "orders", "value": 120}, {"label": "returns", "value": 340},
                      {"label": "refunds", "value": 15}]}
}
```

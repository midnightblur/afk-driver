# Table

## Holds

Rows and cells. Type `table`. Props: `columns` (a list of headings) and `rows`
(a list of rows, each a list with one cell per column). A cell is plain text or
any component: a chip, a graph, another table.

## Use it when

The point compares things across the same attributes: entities and their
fields, options side by side, sample data a feature makes, before and after
values. Put a chip in a cell to mark a value as kept, removed, new or proposed.

## How it looks

A grid with a heading row. Wide tables scroll inside their card; no cell text
is cut off.

## Example

```json fragment=component
{
  "type": "table",
  "id": "t-order-fields",
  "props": {
    "columns": ["Field", "Today", "After the change"],
    "rows": [
      ["order id", "text", {"type": "chip", "props": {"text": "kept", "tone": "kept"}}],
      ["export path", "—", {"type": "chip", "props": {"text": "new field", "tone": "new"}}],
      ["fax number", "text", {"type": "chip", "props": {"text": "removed", "tone": "removed"}}]
    ]
  }
}
```

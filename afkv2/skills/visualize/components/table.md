# Table

## Holds

Rows and cells. Type `table`. Props: `columns` (a list of headings) and `rows`
(a list of rows, each a list with one cell per column). A cell is plain text or
any component: a chip, a graph, another table. Plain text renders no Markdown: a
ticket key links by itself (`chip-and-text.md`); for a Markdown link, put a `text`
with `markdown: true` in the cell.

## Use it when

The point compares things across the same attributes: entities and their
fields, options side by side, sample data a feature makes, before and after
values. Put a chip in a cell to mark a value as kept, removed, new or proposed.

## How it looks

A grid with a heading row. Wide tables scroll inside their card; no cell text
is cut off. Give the table an `id`: then a note on any cell lands on the table,
and so on its card, and keeps its row as its noted text: `row 3 (<words>)`, the
words of the first cell that holds a letter. Put the words that name a row first. Without an id, a note on a cell
lands on no element.

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

# Diagram text

## Holds

A diagram that the engine draws as a picture from Mermaid text. Type `diagram`.
Props: `caption` (1 to 160 characters, what to see) and `text` (the Mermaid
text, 1 to 20,000 characters).

## Use it when

The form is one that no box diagram draws:

| The point shows | Mermaid text starts with |
|-----------------|--------------------------|
| an item that moves through states | `stateDiagram-v2` |
| entities, keys and relations | `erDiagram` |
| an interface and its implementations | `classDiagram` |
| a rule or run that takes different paths | `flowchart` with diamonds |
| hosts, machines and containers inside each other | `flowchart` with `subgraph` |
| steps that wait for one another | `gantt` |
| options placed by 2 measures | `quadrantChart` |
| one spread of times or sizes, as a histogram | `xychart-beta` with `bar` |
| how a quantity splits and flows | `sankey-beta` |
| causes grouped by area around a problem | `mindmap` |
| sizes of nested parts | `treemap-beta` |
| how branches split and merged | `gitGraph` |

A note on a box diagram stands on one box: `graph`, `map`, `sequence` and
`run-strip`. A note on a diagram text stands on the whole picture. When the
human must note one part, use a box diagram.

## How it looks

The picture in the page's theme, with the caption below it. The engine draws
each text once per theme and keeps the picture, so an unchanged text costs no
time at the next round. On a machine with no renderer, or when the text does not
parse, the diagram shows as text in a code block with one line that says why;
the page still shows. Read that line: a parse error is yours to fix. A missing
renderer is set up by the setup skill. The picture carries words, never colour
alone.

## Example

```json fragment=component
{
  "type": "diagram",
  "id": "d-order-states",
  "props": {"caption": "An order is exported only from the paid state",
            "text": "stateDiagram-v2\n  [*] --> open\n  open --> paid: pay\n  paid --> exported: export\n  open --> cancelled: cancel"}
}
```

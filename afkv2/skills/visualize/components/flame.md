# Flame graph

## Holds

Where a slow run spends its time. Type `flame`. Props: `caption` (1 to 160
characters, what to see), `root` (one frame) and optional `unit` (at most 12
characters). A frame has `name` (at most 80 characters), `value` (its time,
above 0) and optional `children` (the frames it calls). The children of a frame
take no more time than the frame. At most 500 frames and 16 levels.

## Use it when

The point is which function a slow run spends its time in: a profile of one
request, one job or one test run.

## How it looks

Each frame is a box; its width is its share of the time of the root. Callers
sit below their callees, the root at the bottom. A box writes its name when it
fits; on hover it shows its name, time and share of the total. The width carries
the meaning, never colour alone: the 2 strengths of one hue only part the levels.

## Example

```json fragment=component
{
  "type": "flame",
  "id": "k-export-profile",
  "props": {"caption": "Most of the export time is the order query", "unit": "ms",
            "root": {"name": "export job", "value": 1000, "children": [
              {"name": "read orders", "value": 600, "children": [{"name": "sql query", "value": 550}]},
              {"name": "write file", "value": 300}]}}
}
```

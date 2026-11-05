# Span waterfall

## Holds

One request that crosses several steps or services. Type `waterfall`. Props:
`caption` (1 to 160 characters, what to see), `spans` (1 to 200, each with `id`,
`label`, at most 60 characters, `start` and `duration`, numbers of 0 or more,
and an optional `parent`, the `id` of an earlier span) and optional `unit` (at
most 12 characters). Each `id` is unique in the waterfall; it is no element id.

## Use it when

The point is where the time of one slow request goes and what runs in parallel:
a trace across services, the steps of one job.

## How it looks

One bar per span on one shared time axis, in the order given, each label
indented under its parent, the duration at the end. The slowest path is strong:
from the root that ends last, each time the child that ends last. A strong span
has a full bar, a bold label and the ◆ mark; the key "◆ the slowest path" sits
on top, so the path never rests on colour alone.

## Example

```json fragment=component
{
  "type": "waterfall",
  "id": "k-export-trace",
  "props": {"caption": "The order read holds the request up", "unit": "ms",
            "spans": [{"id": "s-api", "label": "export endpoint", "start": 0, "duration": 900},
                      {"id": "s-auth", "label": "check access", "start": 10, "duration": 60, "parent": "s-api"},
                      {"id": "s-read", "label": "read orders", "start": 80, "duration": 700, "parent": "s-api"},
                      {"id": "s-sql", "label": "sql query", "start": 90, "duration": 650, "parent": "s-read"},
                      {"id": "s-mail", "label": "send mail", "start": 100, "duration": 200, "parent": "s-api"}]}
}
```

# Box plot

## Holds

Several spreads on one scale. Type `box-plot`. Props: `caption` (1 to 160
characters, what to see), `items` (1 to 20, each with `label`, at most 60
characters, `min`, `q1`, `median`, `q3` and `max`, each at most the next) and
optional `unit` (at most 12 characters).

## Use it when

The point is about request times, sizes or durations where an average hides the
tail: before and after a change, one spread per service. One spread alone reads
better as a histogram.

## How it looks

One row per item on one shared scale: a whisker from min to max, a box from the
first to the third quartile, a line at the median, and the words "median 120 ms
(20 to 900)" at the end. The scale ends sit under the rows. The words carry the
numbers, never colour alone.

## Example

```json fragment=component
{
  "type": "box-plot",
  "id": "k-request-times",
  "props": {"caption": "The cache cut the tail, not only the median", "unit": "ms",
            "items": [{"label": "before", "min": 20, "q1": 80, "median": 120, "q3": 300, "max": 900},
                      {"label": "after", "min": 15, "q1": 40, "median": 60, "q3": 110, "max": 400}]}
}
```

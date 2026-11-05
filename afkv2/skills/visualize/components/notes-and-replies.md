# Notes and replies

## Holds

The human's notes and your replies, per round. The human writes a note as a
lavish annotation. Each annotation is one note. The poll gives it the element id
that the annotation names. A note on no element becomes a steer on the first
map, or on the round banner when the page has no map. A note on a card lives on
its item: `items[].notes[]` with `id`, `round`, `target`, `text`, `deleted`, and
the engine mints its id as `N-<round>-<item>-<k>`. A steer, a note on a map, a
map node, a round banner or another element that no card holds, lives on its
round: `rounds[].notes[]`, id `N-<round>-<target>-<k>`. `k` counts 1, 2, 3 per
card or target in the round, in annotation order. The banner of round n has the
element id `R-<n>`. A steer names no card. An older document keeps its ids
`N-<round>-<item>` and `N-<round>-<target>`: one note per card or target per
round. An older document can keep a steer on a card; it is still a steer. On a
format 1 page, every note lives in the one session list `notes[]`, with `item`,
the card that holds it (none for a steer), and `quote`, the text the human
selected. A reply lives on the round: `rounds[].replies[]` with `text`, `notes`
and `changed`. `notes` lists the 1 or more note ids it answers; `changed` lists
each element id it changed. The engine gives each reply its id `A-<round>-<k>`.
`about` is read on format 0 pages only: the element ids and note ids a reply
answers.

## Use it when

Every round that follows input from the human: write `replies`, the answers to
the notes. The engine writes `notes`.

## How it looks

One row per note, with the human's words quoted: `# | Where you wrote it | Noted
text | Your note | My answer / what changed`. Noted text holds the text the human
selected, when the note is on a selection; Your note holds only the human's
words. A deleted note has no row.

A note on a card, or on a part of a card, is a row under the heading of that
card, newest round first. A history card shows its own rows.

"Notes on the whole session", below the round banner, holds every note and every
answer of the session, card notes included, newest round first. It adds an
`Open` column, a link to the card, map or round the row is on. A group row with
the round colour and a count line opens each round. The current round and the
round before stay open; each older round is its own closed group, and its count
line opens it with one click.

An answer stands in the row of each note it names: the note ids in its `notes`.
One answer that names 2 notes stands in both rows. Under the answer, "Changed:"
links each element in its `changed`. An answer that names no note gets its own
row, "From me", on the first card, card element or note that it names, else in
the session table. On a page from format 0, an answer pairs by its `about`.

An annotation on a row stands for the card of that row, or for the node of a
steer. An annotation on any other row is a steer.

## Example

```json fragment=answer
{
  "text": "Read as: the export stays per order. The format question moves to this round.",
  "notes": ["N-1-i-export-1"],
  "changed": ["i-export"]
}
```

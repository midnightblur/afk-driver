# Notes and replies

## Holds

The human's notes and your replies, per round. The human writes a note as a
lavish annotation. The poll gives it the element id that the annotation names;
a note on no element becomes a steer on the first map. A note on a card lives on
its item: `items[].notes[]` with `id`, `round`, `target`, `text`, `deleted`, and
the engine mints its id as `N-<round>-<item>`. A steer, a note on a map, a map
node or another element that no card holds, lives on its round:
`rounds[].notes[]`, id `N-<round>-<target>`. A steer names no card. An older
document can keep a steer on a card; it is still a steer. A reply
lives on the round: `rounds[].replies[]` with `text` and `about`, the list of
the element ids it answers.

## Use it when

Every round that follows input from the human: the notes of the last round, or
the human's input in Round 0. Treat Round 0 input as unverified. Read every note,
then write one reply per note or per group of notes on the same point. State your
reading in the reply for every point a note settled. Leave `notes` to the engine:
every note in the document comes from the human. A note with `deleted` set is not
input.

A steer is a note on the round, or a note whose `target` is a map or a map node.
It is a steer for that element. Repeat it word for word in your reply and hold
to it for that element until the session ends. When
2 steers on one node conflict, do not choose: state the conflict in your reply
and ask the human.

## How it looks

One row per note, with the human's words quoted: `# | Where you wrote it | Your
note | My answer / what changed`. A deleted note has no row.

A note on a card, or on a part of a card, is a row under the heading of that
card, newest round first. A history card shows its own rows.

"Notes on the whole session", below the round banner, holds the other rows: the
steers, and the replies that name no card. It adds an `Open` column. A group row
with the round colour opens each round, newest round first. The current round
and the round before stay open; older rounds fold into "Earlier rounds".

A reply answers a note when its `about` holds the note's `target`, its item id
or its note id. The engine looks in the round of the reply first, then in the
round before. A reply that answers no note gets its own row, "From me", on the
first card, card element or note that its `about` names, else in the session
table. So name the noted element in `about`.

An annotation on a row stands for the card of that row, or for the node of a
steer. An annotation on any other row is a steer.

## Example

```json fragment=reply
{
  "text": "Read as: the export stays per order. The format question moves to this round.",
  "about": ["i-export"]
}
```

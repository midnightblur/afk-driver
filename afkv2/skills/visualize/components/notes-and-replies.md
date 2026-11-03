# Notes and replies

## Holds

The human's notes and your replies, per round. The human writes a note as a
lavish annotation. The poll gives it the element id that the annotation names;
a note on no element becomes a steer on the first map. A note lives on its item:
`items[].notes[]` with `id`, `round`, `target`, `text`, `deleted`. The engine
mints each note id as `N-<round>-<item>` from the human's response. A reply
lives on the round: `rounds[].replies[]` with `text` and `about`, the list of
the element ids it answers.

## Use it when

Every round that follows input from the human: the notes of the last round, or
the human's input in Round 0. Treat Round 0 input as unverified. Read every note,
then write one reply per note or per group of notes on the same point. State your
reading in the reply for every point a note settled. Leave `notes` to the engine:
every note in the document comes from the human. A note with `deleted` set is not
input.

A note whose `target` is a map node id is a steer for that node. Repeat it word
for word in your reply and hold to it for that node until the session ends. When
2 steers on one node conflict, do not choose: state the conflict in your reply
and ask the human.

## How it looks

One table below the round banner: `# | Where you wrote it | Your note | My answer
/ what changed | Card`. One row per note, with the human's words quoted. A group
row with the round colour opens each round, newest round first. The current
round and the round before stay open; older rounds fold into "Earlier rounds".
A deleted note has no row.

A reply answers a note when its `about` holds the note's `target`, its item id
or its note id. The engine looks in the round of the reply first, then in the
round before. A reply that answers no note gets its own row, "From me". So name
the noted element in `about`.

An annotation on a note row is a note on the card of that note, or a steer on
the node of a steer note. An annotation on any other row is a steer.

## Example

```json fragment=reply
{
  "text": "Read as: the export stays per order. The format question moves to this round.",
  "about": ["i-export"]
}
```

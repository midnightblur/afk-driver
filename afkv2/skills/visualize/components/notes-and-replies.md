# Notes and replies

## Holds

The human's notes and your replies, per round. A note lives on its item:
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

A block below the round banner, newest round first, one collapsible section per
round. Each note shows its target; each reply shows the elements it is about.

## Example

```json fragment=reply
{
  "text": "Read as: the export stays per order. The format question moves to this round.",
  "about": ["i-export"]
}
```

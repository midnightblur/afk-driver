# Notes and replies

## Holds

The human's notes and your replies, per round. A note lives on its item:
`items[].notes[]` with `id`, `round`, `target`, `text`, `deleted`. The engine
mints each note id as `N-<round>-<item>` from the human's response. A reply
lives on the round: `rounds[].replies[]` with `text` and `about`, the list of
the element ids it answers.

## Use it when

Every round after one with notes. Read every note of the last round, then write
one reply per note or per group of notes on the same point. State your reading
in the reply for every point a note settled. Leave `notes` to the engine: every
note in the document comes from the human.

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

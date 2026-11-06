# The round pass

How to read a round answer after `ingest`, card by card and note by note. Write the result as readings and apply them with `apply-readings`.

## Read the cards

When the human sends a round, the engine settles a point with one `accept`,
`sign` or option mark. It moves a point to `needs_reading` on `reopen`,
`changes`, a write-in, a note, a mark plus a note, or 2 marks. On a card that is
already settled, a signal that changes the answer sets `state` to `open` and
removes `settled`, and a note stays on that card, also in a settled round. Its
signal has `reopened: true`. Before you mark the round `settled`, go through the
cards of the current round. Never change a card in a settled round: only the
engine writes there. A steer lives on the round, and its signal has `steer: true`
and no `item`: leave it out when you read the signals, because it settles nothing.

- `needs_reading` with a clear note and no signal that disagrees with it: set
  `state` to `settled_by_note` and write `settled`, for example `{"by": "note", "round": 2, "signal": "N-2-i-format", "reading": "Picks CSV."}`.
  The `signal` is the note id. A note that leaves the answer open is not a clear
  note. A `signoff` card settles only by a `sign` mark: a note on it is never a clear
  note, even when it keeps the wording, and `apply-readings` refuses that reading. The
  new card asks the human to sign. A note on an `info` card is not a
  clear note: it answers nothing, so it gets a reply only. A `reopen` or `changes`
  mark always disagrees.
- `needs_reading` in any other case: set `state` to `open`. A write-in has no note
  id, so it cannot settle by note: the new card for that point is a `confirm` card
  that states the write-in as your reading.
- `blocked` with the point it waits on now settled: set `state` to `open`.

Then mark the round `settled` and append the next round. Make one new card for
each point that returns:

- a `decided`, `confirm`, `debate` or `signoff` card of the round you settled that
  is still `open` or `blocked`;
- a `decided`, `confirm`, `debate` or `signoff` card of an earlier round that the
  human noted or reopened in this send.

The new card has a new id. Its `carries` lists each old card id; each id must be
a card of an earlier round. Its body shows the signals that returned the point,
for example both the mark and the note. A carried
`blocked` card names the current card id of the point it waits on. An `info` card
stays in its round. The old card stays as it is.

## Read the notes

Every round that follows input from the human: the notes of the last round, or
the human's input in Round 0. Treat Round 0 input as unverified. Read every note,
then answer each note by the answer rules ([SKILL.md](SKILL.md) "Answer rules"):
each note gets its own reply, and a reply on a version 2 page names exactly 1 note
in `notes`. A note with several meanings gets 1 reply that states each reading.
State your reading in the reply for every point a note settled. Leave `notes` of the document to the
engine: every note in the document comes from the human. A note with `deleted`
set is not input.

A steer is a note on the round, or a note whose `target` is a map or a map node.
It is a steer for that element. Hold to it for that element until the session
ends. When 2 steers on one node conflict, do not choose: state the conflict in
your answer and ask the human.

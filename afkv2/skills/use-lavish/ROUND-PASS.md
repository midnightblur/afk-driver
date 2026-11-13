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
- `needs_reading` in any other case: set `state` to `open`. A write-in never
  settles by note: its words arrive as the signal's `text` and as the first note of
  its card, and the new card for that point is a `confirm` card that states the
  write-in as your reading. A write-in with no `text` came from an older page: take
  its words from the other notes on its card, or ask again.
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
then reply to each note by the answer rules ([SKILL.md](SKILL.md) "Answer rules").
Each note gets its own reply. A reply names the id of its note in `notes`. On a
version 2 page, a reply that names 2 or more notes is refused. A note with
several meanings gets 1 reply that states each reading. State your reading in the
reply for every point a note settled. Leave `notes` of the document to the
engine: every note in the document comes from the human. A note with `deleted`
set is not input.

A steer is a note on the round, or a note whose `target` is a map or a map node.
It is a steer for that element. Hold to it for that element until the session
ends. When 2 steers on one node conflict, do not choose: state the conflict in
your reply and ask the human.

## Read the questions and the settled notes

On a version 2 page, the result of `ingest` adds 2 lists. `questions_to_read`
holds each signal on a question for others: a tick, a note, an edit or a
delete. `settled_notes_to_read` holds the id of each note on a settled card. A
tick or a note changes no state: write a reading for each entry. `apply-readings`
takes 4 readings on a version 2 page only:

- `keep` {`note`, `reply`, `changed`}: the note on a settled card agrees, fixes a
  typo or is about another part, so the point stays settled. `reply` is the reply
  to the note. A thought about another part goes into that part in the next round, with
  a change line. A note that changes, doubts or adds to the point gets no `keep`:
  the point returns as a new card in the next round, and the note gets its reply
  in `replies`.
- `answer` {`question`, `text`, `choices`, `role`, `date`, `signal`}: the
  developer relays an answer.
  - `signal` is `tick` for the developer's tick on the question. Else it is the
    id of a live note of this round (`answer-no-signal`).
  - `choices` holds the ticked option ids.
  - `role` is the role the note names, else the question's only role. It is
    never `everyone` (`everyone-answered`).
  - A note names no role, and the question is for everyone or for several
    roles: ask the developer, and write no answer yet.
  - `date` is the day the note names, else the day the note was sent.
  - An answer settles no card. Each point it touches returns as a card for the
    developer to confirm. Each section it changes gets a change line with cause
    `answer_from`.
  - A partial answer is no `answer`. The question stays open, and the next
    round adds what is known to its context.
  - A follow-up is a new question with `after`.
- `drop` {`question`, `reason`, `note`}: the question is no longer needed.
  `reason` says why (`drop-no-reason`); `note` is the note that dropped it.
- `assume` {`question`, `text`, `card`}: the developer accepted an assumed answer.
  `card` is the card that proposed it, settled by the developer's `accept` mark
  (`assume-no-card`). A later `answer` replaces the assumption and keeps it on
  record.

A reading that names no question for others of the page is refused
(`not-a-question`). A refused batch writes nothing.

# Grill log format — `GRILL-LOG.md`

On-disk checkpoint of a grill's settled state, written in the ticket's spec folder (sibling to where the PRD lands). Grills settle decisions in conversation, and conversation is ephemeral: a compaction, crash, or multi-day pause loses the ledger, and "a lost ledger means re-verifying". The grill log is the insurance: update it **as decisions lock**, not at the end, so a resumed session (or a synthesis skill whose context lost the conversation) picks up from disk.

A checkpoint, not a document: terse rows, no prose, superseded rows overwritten in place. Synthesis skills own the real artifacts — the log never substitutes for a PRD/SDD/verification plan, and is deletable once the ticket ships.

## Ownership

One `##` section per grill skill; each grill writes **only its own section** and creates the file (title line + its section) if missing.

## Template

```
# Grill log — {TICKET-ID}

Checkpoint of interactive grill sessions. Working state, updated as decisions lock;
superseded when the synthesized artifacts (PRD / SDD / VERIFICATION-PLAN) land.

## Requirements grill

- Ledger: {claim} → pending (INV-NNN) | verified (INV-NNN) | refuted (INV-NNN) | unverified-external (user acknowledged)
- Staples: {staple} → in|out — {one-clause why}
- Settled: {decision, one line each, as they lock}{agent tail — grammar below}
- Spinoffs: {spinoff row — grammar below}
- Open: {what's still unsettled — the resume point}{steer and escape lines — grammar below}

### Settled row — the agent tail

A decision the agent took itself and the human accepted in a round carries the
provenance the round holds (`ROUND.md`):

```
- Settled: {decision} · decided-by agent R-{n} · accepted {YYYY-MM-DD} · {grade}: {evidence, one sentence} · reverse: {one clause}
```

The tail is absent on a decision the human made — the plain row above is that
case. A tail without `accepted {date}` does not exist: an unaccepted decision
is not settled, so the row is not written until the mark arrives. `{grade}` is
one of the evidence grades in `ROUND.md`. Synthesis reads the row as any other
settled decision and carries the provenance into the record it mints.

### Open row — steers and the escape

```
- Open: {the live question}
  steer: {the human's words, verbatim}
  escape: taken R-{n}
```

A `steer:` line is a standing constraint a resumed session honours and cites as
`spec`-grade evidence; an `escape:` line says the human took the session back,
so a resumed session keeps asking one question at a time. Both stay until the
grill ends. The merged round response is appended here verbatim until the round
is applied, so a crash between poll and apply loses no human words.

## Solution grill

- Locked: L{n} {one-line decision} (INV-NNN, …) | inherited (INV-NNN | gap acknowledged: {what the human accepted unproven})
- … one row per layer as it locks (L1–L9)
- Seams (L9): one locked-seam row per seam, in the six-column grammar `skills/afk/grill-solution/L9-SEAM-GRILL.md` states
- Signoff: {signoff row — grammar below}
- Spinoffs: {spinoff row — grammar below}
- Open: {the layer under discussion + the live question}

## Verification grill

- Aspect: {aspect} → triggered ({proving scenario ids}) | N/A ({reason}) | env-limited
- Journeys settled: {ids/names, one line}
- API scenarios: designed | deferred (pre-SDD)
- Spinoffs: {spinoff row — grammar below}
- Open: {what's still unsettled}
```

Sections appear as their grill first runs; an absent section means that grill hasn't run. Rows are overwritten as state changes — the log holds current state, not history (the conversation and synthesized artifacts hold the history).

## Signoff row

The register of human-locked design aspects (set, contract grades, and
protocol: `skills/afk/grill-solution/HUMAN-SIGNOFF.md`). One row per aspect,
under the solution grill's section, written the moment its outcome lands:

```
{HL-id} {aspect} → signed {YYYY-MM-DD} "{human's approving words, verbatim}" — covers {scope, one clause}
{HL-id} {aspect} → changes-requested — {what they asked for}
{HL-id} {aspect} → pending
{HL-id} {aspect} → n/a — {reason the trigger didn't fire}
```

Only a human's own words fill the quote; an agent never writes a `signed` row
for a signature it did not receive. A signed row is void the moment the aspect's
design changes — set it back to `pending` and re-sign rather than leaving a row
describing a design that moved.

## Spinoff row

Deferred/adjacent work a grill spins off into its own ticket (protocol +
field meanings: `SPINOFF-TICKET.md`, plugin root). One row per spinoff, under
the recording grill's own section:

```
{kind} · {summary} → {status} — pain: {one sentence} · why-out: {one clause} — links: {rel} {target}, …
```

`kind` = deferred | adjacent · `status` = candidate | filed {KEY} |
filed {KEY} · link-debt · `links` = each `{blocked-by|relates} {KEY}` the stub
needs. A `filed {KEY}` row is the dedup guard on resume — never mint a second
for the same spinoff.

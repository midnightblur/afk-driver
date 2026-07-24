# SPINOFF-TICKET.md — deferred work becomes a tracked spinoff

The one home for the spinoff protocol: how a grill captures work that
surfaces mid-interview but belongs to a **different** ticket, so the
conversation never swallows it. Skills weaving this carry a pointer here
("spinoff per SPINOFF-TICKET.md") — they never restate the below. This file
names no caller.

## What a spinoff is

Work a grill settles as **real** but **out of the current ticket's scope** —
it can't ride this PRD, and losing it to the conversation is the failure a
spinoff prevents. Two kinds this protocol mints, each fixing the link
relation the stub later needs:

- **deferred** — blocked on another ticket's delivery → `blocked-by`
- **adjacent** — a neighbouring pain this feature exposes but won't fix → `relates`

A **defect** discovered while grilling is not a spinoff — it routes to
`/afk:bug` (the sanctioned Bug writer, with reproduction-bundle discipline),
not here.

Not every tangent spins off. Only work the user confirms is worth tracking —
a spinoff the user won't own is a conversation note, not a ticket.

## The candidate row (a grill's only spinoff write)

A grill records a spinoff as a **candidate row** in its own `GRILL-LOG.md`
section (grammar: `skills/afk/grill-requirements/GRILL-LOG-FORMAT.md`) — a
disk write, never a tracker write, so a grill's local-only nature holds. It
carries: **kind** (deferred | adjacent), **summary** (the stub's title),
**pain** (one sentence — what goes wrong without it), **why-out** (the blocker
or the scope line that keeps it off this ticket), **links** (each intended
relation + target key), and **status** (`candidate` → `filed {KEY}` →
`filed {KEY} · link-debt`).

## Minting the stub

Creating the ticket is a tracker write, so it goes through the sanctioned
tracker-writer — `/afk:to-ticket` spinoff mode — never the grill itself. The
grill hands it a candidate row; the mode owns the create mechanism and the
link handling.

- **Human-present + user-directed only.** Minting is outward-facing: a
  hands-off (driven) run never mints — it leaves the candidate row for the
  human. A grill under a no-tracker rule likewise writes only the candidate
  and never invokes the mint.
- **A stub, not a PRD.** Summary, the pain, why-deferred / what-unblocks,
  parent epic, fix version, issue type — requirements-level, no
  repo-artifact references (ticket readers have no repo access). A later grill
  expands it when its own turn comes.

## Link-debt

The stub's `blocked-by` / `relates` links are set by whatever path the mint
uses — and when that path **cannot** set them (Jira's field-update API refuses
`issuelinks`), the intended relation is recorded as **link-debt** on the
candidate row (`status: filed {KEY} · link-debt`) and surfaced to the human to
set by hand. Link-debt is never silent: an unlinked spinoff that reads as
linked is the failure the ledger row exists to prevent.

## Dedup on resume

Before minting, scan the section's spinoff rows — a matching `filed {KEY}` row
means the stub already exists; never mint a second. Record the returned key on
the candidate row the instant the create succeeds, so a compaction or resume
landing between create and record can't double-file.

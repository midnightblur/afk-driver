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

- Ledger: {claim} → verified ({where}) | refuted ({where}) | unverified-external (user acknowledged)
- Staples: {staple} → in|out — {one-clause why}
- Settled: {decision, one line each, as they lock}
- Open: {what's still unsettled — the resume point}

## Solution grill

- Locked: L1 {one-line decision} | inherited
- … one row per layer as it locks (L1–L9)
- Seams (L9): {seam} → {verdict: fits | extends (ADR-candidate) | reworked}
- Open: {the layer under discussion + the live question}

## Verification grill

- Aspect: {aspect} → triggered ({proving scenario ids}) | N/A ({reason}) | env-limited
- Journeys settled: {ids/names, one line}
- API scenarios: designed | deferred (pre-SDD)
- Open: {what's still unsettled}
```

Sections appear as their grill first runs; an absent section means that grill hasn't run. Rows are overwritten as state changes — the log holds current state, not history (the conversation and synthesized artifacts hold the history).

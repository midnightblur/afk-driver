# SETTLEMENT.md — the review gate's settle loop

> **Language:** read `LANGUAGE.md` (plugin root) first — it binds every word this file produces.

One home for the caller-side review protocol. The change request is the review record. `plan/review/` remains run telemetry. No gate decision reads that telemetry.

The review pass stays read-only and single-shot. The caller owns the loop, remediation, disputes, and termination.

## Roles

- **Implementor** — fixes or disputes findings.
- **Reviewer side** — fresh reviewers for each pass and a fresh adjudicator for each dispute.
- **Referee** — runs the loop and writes the change record.

## Referee tool

Run `${AFK_PLUGIN_ROOT}/skills/afk/review/scripts/forge_ledger.py` from the consuming repository. It owns marker emission, parsing, trust checks, transitions, anchoring, and gate checks. Run `reconstruct` before every stateful command.

Pass the authenticated forge user with `--trust`. On a cross-identity resume, add each accepted earlier writer with another `--trust`. Classify every other marker author with `--reject`. An unclassified author or an edited marker causes exit 2 before any write or resolution.

### Commands

Run each form through the referee tool above. B1–B5 and B7 accept repeated `--trust USER` and `--reject USER` options. Commands emit one JSON object. Exit 0 means success, exit 2 means a ledger, gate, or forge failure, and exit 3 means invalid use.

- **B1 post:** `post --change REF --unit U --findings F.json --diff D --head SHA [--hints H.json] [--map M.json] [--state S.json] [--trust USER]... [--reject USER]...`. It returns post, anchor, reuse, and stale-locator counts plus the key map. Invalid findings, maps, trust, markers, or forge writes fail before the next phase. A location outside the diff becomes unanchored.
- **B2 reply:** `reply --change REF --key K --kind KIND --text TEXT [--sha SHA] [--path PATH] [--line N] [--side SIDE] [--result RESULT] [--reason REASON] [--gate GATE] [--home PATH] [--to URL] [--head SHA] [--data DATA] [--mapped VALUE] [--attr NAME VALUE]... [--state S.json] [--trust USER]... [--reject USER]...`. It returns the key, kind, and operation id. Invalid attributes, transitions, locators, trust, markers, or forge writes fail before publication.
- **B3 resolve:** `resolve --change REF --key K [--reopen] [--state S.json] [--trust USER]... [--reject USER]...`. It returns `resolved`, `resolvable`, and the key. Invalid trust or markers fail before resolution. An unanchored key returns `resolvable:false`; unsupported forge resolution returns `resolved:false`.
- **B4 summary:** `summary --change REF --unit U --round N --head SHA --clean true|false --ledger-only true|false --text-file F --history-file H.json [--state S.json] [--trust USER]... [--reject USER]...`. It returns the note, unit, and round. Invalid history, a duplicate round, a false ledger-only claim, trust, markers, or a forge write fails before publication.
- **B5 reconstruct:** `reconstruct --change REF [--unit U] [--trust USER]... [--reject USER]...`. It returns the current change head and reconstructed units. Invalid trust, edited markers, malformed records, or conflicting records fail closed.
- **B6 trailers:** `trailers --keys K1,K2`. It returns one `Settles: <key>` trailer per ordered, unique key. A malformed or empty key list is invalid use.
- **B7 gate:** `gate --change REF --unit U --phase progress|closure --head SHA [--expected F.json] [--round N] [--state S.json] [--trust USER]... [--reject USER]...`. Progress returns whether the pass is clean after it proves every expected finding is durable. Closure returns `settled:true` after every closure condition passes. A missing required phase input or failed condition exits 2.

## The round

1. **Reconstruct.** Run `reconstruct --change {ref} --unit {unit}`. Build every later-round input only from its result.
2. **Review and publish.** Run the review pass. Pass its findings, the current diff, and the current head to `post`. The command publishes every returned finding or writes a durable `seen` record for a reused key.
3. **Filter.** Record every non-actionable finding on its key. Use `disposition result=pattern-debt` for pattern debt. Use `deferred gate={name}` only when the caller declares a later gate. Product debt requires a dispute, a `verdict result=stands`, and the referee's later disposition. A `reused_closed` result needs no new disposition.
4. **Prove publication.** Run `gate --phase progress --expected {findings-file} --head {head}` before any fixer starts. Stop on failure.
5. **Fix or dispute every actionable finding.** Brief a fixer with the key and active location. A dispute must cite evidence. Write `dispute` before adjudication.
6. **Adjudicate.** Give a fresh adjudicator the finding, rationale, diff path, contract paths, and `AGENTS.md` chain. Write `verdict result=withdrawn|stands reason=...`. Resolve every withdrawn key.
7. **Close the round.** Commit fixes with the `Settles: {key}` trailers returned by `trailers`. Push. Write `fixed` records for settle-mode fixes and `verified` records for review-only triage. Both carry the full head SHA and exact locator. Resolve their threads. Write `carried` for an open key. Land a product-debt home through `/afk:agents-md`, then write its disposition and resolve it. Run cheap verification. Write a new summary note with `clean=false` and the validated history entry.
8. **Repeat.** A review with no actionable finding writes a new summary with `clean=true`. A valid final ledger-only round writes `ledger_only=true`. Run `gate --phase closure` before any settled verdict.

Every round can also write `plan/review/*.outcomes.json` as telemetry. Retro and mission-control can read it. The settle gate cannot.

## Later-round input

Build these inputs only from `reconstruct`:

- **Delta roster** — earlier critical and high owners from `history[].observed`; new `AGENTS.md` chain paths from `agents_md_chain_new`.
- **Scope escalation** — two consecutive history entries with matching `scope_shape_keys`.
- **Consistency sweep** — every fixed key's verbatim finding data and fix locator.
- **Cap report** — blocking findings from the last two `observed` lists and the last round where `code_changed=true`.

`blocks_ship` means severity `critical` or `high`. Reconstruction derives it. Records never store it.

## Deferral rule

A caller can route a finding class to a named later gate. Write `deferred gate={name}` on the original key. The later gate reconstructs the change. It selects slice keys whose `ever_deferred_to` contains its name. It works and closes those keys at their existing locations.

## Ledger-only rounds

The script reads `review.ledger-only-paths` from the effective repository configuration. The default permits only `plan/review/**` and `plan/JOURNAL.md`.

A final round is ledger-only only when every observed key and every changed path from `start_head` through `head` matches the configured paths. Every key must also have a terminal outcome. The script derives `start_head` and `observed`. The history input cannot omit or change them.

## Scope escalation

Two consecutive rounds with the same fix-one-copy-leave-another shape trigger escalation. Pass `--scope-escalated`. Review the full touched surface. Add `consistency-sweep` with the reconstructed fixed-key input.

## Termination

- **Settled** — closure gate succeeds for the current forge head.
- **Open** — review-only work remains. Run progress and summary only.
- **Stalemate** — 10 rounds finish with open findings. Run progress and summary only. Report the open keys, blocking findings from the last two rounds, and when code last changed.

### Closure gate

Closure requires all these conditions:

- The supplied head equals the forge's current `head_sha`.
- The unit's latest summary names that head and round. It is clean or carries a validated ledger-only claim.
- Every unit key is terminal. A feature unit also includes every slice key deferred to `feature`.
- Every active locator is current and inline. Unanchored keys block closure for every outcome.
- Every inline thread ever used by each key is resolved. A deferred slice thread stays open until the later gate closes it.
- Every `fixed` SHA is an ancestor of the supplied head. Its commit message carries `Settles: <key>`. A `verified` record is exempt from the trailer.
- Every product-debt disposition names an existing home whose `## Known debt` entry carries `ledger: <key>`.

An unsupported resolve fails closure.

## Information diet

Reviewer, fixer, and adjudicator prompts omit the round number, cap, summary, reconstruct output, and termination rules. A fixer receives only its key and active location plus normal code and contract context.

## Record grammar

This section owns the forge record grammar. Marker values use percent encoding. Paths use `/`, are relative to the repository root, and omit `./`. Hash inputs use canonical JSON: UTF-8, Unicode Normalization Form C, sorted keys, and no whitespace.

### Finding

Append this marker to a thread root or plain note:

`<!-- afk:finding v1 key=<K> seq=1 rfp=<h> sfp=<h> file=<enc> old_path=<enc> new_path=<enc> line=<n> old_line=<n|-> side=<new|old|context> data=<base64url-json> [moved_from=<op>] -->`

The key is `<unit>/f<NNN>`. Allocate the next number from the maximum valid marker for that unit. `data` is the verbatim reviewer finding. Its optional `side` field uses `new`, `old`, or `context`.

`rfp` hashes `unit`, `reviewed_head`, `concern`, `criterion`, `severity`, `class`, `file`, `old_path`, `new_path`, `line`, `old_line`, `side`, `finding`, `why`, `fix`, and `evidence`. It identifies a retry. `sfp` hashes `criterion`, `file`, `finding`, `why`, and `evidence`. It matches across review passes.

### Records

Every record is a new thread reply or plain note:

`<!-- afk:record v1 key=<K> seq=<n> kind=<kind> op=<id> [attrs] -->`

Sequence numbers increase per key. The operation id hashes the key, kind, attributes, and prior sequence.

Outcome kinds are `dispute`; `verdict result=withdrawn|stands reason=<enc>`; `fixed sha= path= line= side=`; `verified sha= path= line= side=`; `carried`; `deferred gate=<enc>`; and `disposition result=pattern-debt|product-debt [home=<enc>]`.

Outcome-neutral kinds are `seen head= data= file= old_path= new_path= line= old_line= side= [mapped=1]`; `reclassified data=`; `move-intent to=`; `moved to=`; and `move-failed note= move_op=`.

Valid outcome transitions:

- none or `carried` → `dispute`, `fixed`, `verified`, `carried`, `deferred`, or pattern-debt disposition.
- `dispute` → `verdict`.
- `verdict stands` → `fixed`, `verified`, `carried`, a new evidence-based `dispute`, or product-debt disposition.
- `deferred` → `fixed`, `verified`, `dispute`, pattern-debt disposition, or `carried`.
- `verdict withdrawn`, `fixed`, `verified`, and either disposition are terminal.

`reclassified` is valid only in a non-terminal state. Location records are outcome-neutral. A fixed or verified recurrence gets a new key. A withdrawn or disposition recurrence reuses its key when routing changes. Its `seen` record carries the current routing. It does not write `reclassified`.

### Move transaction

Write `move-intent to=<base64url-locator>` on the active location. Its record `op` is the move id. Post the inline copy with `require_inline=true` and `moved_from=<move-id>`. Then write `moved to=<url>` on the old location. A failed cleanup writes `move-failed note=<id> move_op=<move-id>`; reconstruction ignores that orphan origin. Two origins are valid only when they form this transaction. All other duplicate origins are corruption.

### Summary

Write a new plain note per closed round. Its first line is:

`<!-- afk:settle:summary v1 unit=<U> round=<n> reviewed_head=<sha> clean=<true|false> ledger_only=<true|false> -->`

Include `<!-- afk:settle:trust v1 trusted=<enc-list> rejected=<enc-list> -->`.

Include one history entry. Its fields are `round`, `start_head`, `reviewed_head`, `code_changed`, `keys_new`, `keys_remediated`, `scope_shape_keys`, `agents_md_chain_new`, `scope_escalated`, `ledger_only`, and `observed`. Each observed item carries `key`, `concern`, `severity`, and `class`. The script derives `start_head`, `code_changed`, `keys_new`, `keys_remediated`, and `observed`.

Summary notes are immutable. The latest round is current. The ordered notes form history. A legacy `<!-- afk:settle-mr:summary -->` reads as unit `change`, unknown round and head, `clean=false`, and empty history.

### Trust and immutability

Accept markers only from trusted authors. Ignore rejected authors and count them. Fail before any state change when a marker author is unclassified.

The `afk:settle:trust` marker records the declared author lists for audit only. Reconstruction uses the command's `--trust` and `--reject` options, not this marker.

Ignore a marker-bearing note or comment when `updated_at` is later than `created_at`. Count it as `edited_markers`. Any positive count fails every reconstructing command before any state change.

### Reconstruction

GitLab note duplicates use the newest `updated_at`. Equal timestamps with different bodies are corruption. Unknown versions, kinds, transitions, or conflicting sequence records are corruption.

Records have contiguous sequence numbers. Each operation id must match its record and prior sequence. Every history entry must match the complete Summary schema. Its keys must belong to the unit, including deferred slice keys at the feature gate.

For each key, reconstruction returns the latest outcome, routing, active location, canonical finding, every inline thread, `locator_current`, and every deferred gate. The latest `seen` or origin supplies the current locator. Closure requires every historical inline thread resolved.

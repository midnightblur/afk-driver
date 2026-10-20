## Goal
Deliver the diagnosis record's three lockstep parts: the diagnosis format file (fields, one writer per part, the required-parts table, the evidence marker grammar), the diagnosis check script (accepts or refuses a `DIAGNOSIS.md`, names the missing parts, derives the state), and the one outside-writes helper (the only code that appends to Outside writes; reads back before each retry).

## Complexity
complex

## Review
opt-in: design-quality, resilience

## Design refs
- SDD: SDD.md#§4 L3 — Data Architecture — entity design of `DIAGNOSIS.md`, field by field
- SDD: SDD.md#§6 L5 — Domain Model — invariants, derived state and its "Read from" table
- SDD: SDD.md#§5 L4 — Cross-Cutting & Quality Attributes — retry + timeout, idempotency keys
- SDD: SDD.md#§8 L7 — Module Decomposition — rows "diagnosis format file", "diagnosis check script", "outside-writes helper"
- ADR: adr/design/0002-diagnosis-file-is-the-hand-off-and-the-state.md — state derived from fields, table-driven check
- ADR: adr/design/0003-outside-writes-run-as-named-steps-with-read-back.md — append-only list, read-back before retry

## Scope
- skills/utils/diagnose/DIAGNOSIS-FORMAT.md
- skills/utils/diagnose/scripts/*.py
- scripts/tests/test_check_diagnosis.py
- scripts/tests/test_outside_writes.py

## Seams
- implement: outside-writes helper over `tracker_api` — appends each write after it succeeds and reads back before a retry; this subtask owns the helper and its tests (INV-025)

## Acceptance
- [ ] The format file defines every `DIAGNOSIS.md` field — work id, ticket key, verdict (V-1..V-5), base, diagnosis branch, symptom, spec comparison, reproduction, attempts, root cause, fix proposal, approval, outside writes — with its nullability and its one writer (SDD §4)
- [ ] The format file holds the required-parts-per-verdict table, and the check script reads that table from the file rather than a copy of it (SDD §8)
- [ ] The check script refuses a diagnosis missing a part its verdict needs and prints each missing part: reproduction unless cannot reproduce; attempts for cannot reproduce; root cause for V-1, V-2, V-3; fix proposal for V-1, V-2 (SDD §4)
- [ ] The check script refuses a verdict with neither a reproduction nor a recorded attempt (PRD AC-007)
- [ ] The check script refuses a fact that carries no certainty mark (PRD AC-004)
- [ ] The check script derives the state from the file per the §6 "Read from" table and nothing stores it (design ADR-0002)
- [ ] The helper is the only code that appends to Outside writes; it appends straight after a write succeeds and never rewrites an earlier entry (SDD §4)
- [ ] The helper retries a failed write at most twice, after 5 s and then 20 s, and only after a read-back shows the write did not take effect; a write with no read-back is not retried (SDD §5)
- [ ] An adapter answer of `error` or `unavailable` with exit 0, and a create that returns an empty key, count as failed writes (SDD §14 row "outside-writes helper over `tracker_api`")
- [ ] The format file, the helper and the check script land in one commit (SDD §8)
- [ ] Implements the public interfaces of SDD §8 rows "diagnosis format file", "diagnosis check script" and "outside-writes helper" unmodified (SDD §8)
- [ ] Every new test passes on Windows and on WSL (SDD §10)

## Produces
- skills/utils/diagnose/DIAGNOSIS-FORMAT.md#Required parts per verdict — the table the check script reads, one row per verdict
- skills/utils/diagnose/DIAGNOSIS-FORMAT.md#Evidence marker grammar — the visible marker each evidence comment carries
- skills/utils/diagnose/scripts/check_diagnosis.py#def check_diagnosis( — path in → accept, or refuse with the missing parts; the derived state
- skills/utils/diagnose/scripts/outside_writes.py#def append_outside_write( — append(entry) to Outside writes
- skills/utils/diagnose/scripts/outside_writes.py#def retry_with_read_back( — retry(write, read-back), at most 2 retries

## Verification
| Tier | Check (command or method) | Proves |
|------|---------------------------|--------|
| static | `bash hooks/plugin-source-gates.sh --staged`; grep each ## Produces anchor | gates pass; declared symbols present |
| unit | `afk-python -m pytest scripts/tests/test_check_diagnosis.py scripts/tests/test_outside_writes.py -q` | accept/refuse per verdict; certainty marks; derived state; retry count, backoff, read-back; `unavailable` and empty key count as failed |
| integration | `afk-python -m pytest scripts/tests -q` and `bash hooks/tests/hook-smoke.sh`, on Windows and WSL | nothing else broke |

## Context excerpts
> (SDD §4) | Verdict | enum: obvious fix, several fixes, spec gap, works as specified, cannot reproduce (V-1..V-5) | no | none | — | set by diagnose; a re-run replaces it; needs a Reproduction or Attempts | — | — |
> (SDD §4) | Reproduction | test path, command, failing output; light diagnosis: the reused check or finding | yes only for cannot reproduce | none | — | the test fails on the Base commit | — | — |
> (SDD §4) | Attempts | list of attempt + result | yes unless cannot reproduce | none | — | required for cannot reproduce | — | — |
> (SDD §4) | Root cause | text with file and line | yes unless obvious fix, several fixes or spec gap | none | — | — | — | — |
> (SDD §4) | Fix proposal | one option or labelled options | yes unless obvious fix or several fixes | none | — | an approval covers it as it stood when approved | — | — |
> (SDD §4) | Approval | who; their words or the prior approval; what it covers (code, ticket writes, change); date | yes | empty | date: ISO 8601 | written by `/afk:fix` only; emptied by every diagnose rewrite; nothing checks it (ADR-0008) | — | — |
> (SDD §4) | Outside writes | list: ticket key, change link, each evidence comment marker, feature-branch push, in-review move | yes | empty | — | append-only; appended straight after each write succeeds, only through the outside-writes helper | — | a re-run skips listed writes and reads back the rest before retrying (ADR-0003) |
> (SDD §4) Every fact carries a certainty mark (evidence-bundle grades, AC-004).
> (SDD §6) Writers per part: diagnose — work id through fix proposal; `/afk:fix` — approval; bug mode — ticket key while empty; bug mode (ticket writes) and fix (change writes) — append to Outside writes.
> (SDD §6) | Diagnosed | a verdict is set | · | Sent to a grill | verdict several fixes or spec gap; back to Diagnosed when the grill's log carries a "still small" size-call row | · | Stopped | verdict works as specified or cannot reproduce | · | Approved | Approval filled | · | Landed | a feature-branch push in Outside writes | · | Shipped | a change link in Outside writes | · | In review | the in-review move in Outside writes |
> (SDD §5) | Any outside write with a read-back | 1 + at most 2 retries, each after a read-back shows no effect | 5, then 20 | adapter default |
> (SDD §5) | Any outside write without a read-back | 1, no retry | — | adapter default |
> (SDD §8) | diagnosis check script (beside diagnose) | required parts per verdict, evidence, certainty marks; derives state | path in → accept or refuse with the missing parts; state | format file | diagnosis |
> (SDD §8) | outside-writes helper (one) | only code that appends to Outside writes; read-back before retry | append(entry), retry(write, read-back) | format file | diagnosis |
> (SDD §8) Lockstep: format file ↔ helper ↔ check script move in one commit.
> (SDD §14 row "outside-writes helper over `tracker_api`") INV-025: adapter answers `error` and `unavailable` with exit 0 (`github-issues/api.py:95`, against `ADAPTERS.md:32`); create can return an empty key with no error (`:321-326`) | one helper appends and reads back before retry; an empty key or `unavailable` counts as a failed write

## Parent PRD
docs/afk/small-lane/PRD.md

## Parent SDD
docs/afk/small-lane/SDD.md

## Blocked by
(none)

## Conflict procedure
If a binding decision in SDD/ADR is wrong / infeasible / contradicts reality
during implementation, classify per the decision protocol (`DECISIONS.md`,
workflow plugin root): a two-way-door correction is recorded in
`plan/DECISIONS.md` and implemented; a one-way door or a tie exits
`design_conflict` quoting the SDD section + the conflict. Never override off
the record. Parked conflicts route back to `/afk:grill-solution` for a
superseding ADR.
